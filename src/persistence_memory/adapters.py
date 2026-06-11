from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol

from .api import GateFilterResult, PersistenceGate
from .models import MemoryItem


class RetrieverProtocol(Protocol):
    """Minimal retriever protocol supported by PersistenceGateRetrieverAdapter."""

    def retrieve(self, query: str, **kwargs: Any) -> Iterable[Any]:
        ...


@dataclass
class AdapterResult:
    """Result from running a retriever through Persistence Gate."""

    query: str
    raw_items: list[Any]
    gated: GateFilterResult

    @property
    def allowed_context(self) -> str:
        return self.gated.allowed_context

    @property
    def allowed_ids(self) -> list[str]:
        return self.gated.allowed_ids

    @property
    def blocked_ids(self) -> list[str]:
        return self.gated.blocked_ids

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        return self.gated.audit_log


class PersistenceGateRetrieverAdapter:
    """Adapter that wraps an existing retriever and applies Persistence Gate.

    The wrapped retriever may be:
    - a callable: retriever(query, **kwargs) -> documents
    - an object with retrieve(query, **kwargs)
    - an object with get_relevant_documents(query, **kwargs)
    - an object with invoke(query, **kwargs)

    Documents may be dicts, MemoryItems, LangChain-like Document objects with
    page_content/metadata, or simple strings.
    """

    def __init__(
        self,
        retriever: Any,
        gate: PersistenceGate | None = None,
        *,
        profile: str = "balanced",
        top_k: int = 6,
        document_mapper: Callable[[Any], MemoryItem | dict[str, Any]] | None = None,
    ) -> None:
        self.retriever = retriever
        self.gate = gate or PersistenceGate(profile=profile, top_k=top_k)
        self.document_mapper = document_mapper

    def retrieve(self, query: str, **retriever_kwargs: Any) -> list[Any]:
        if callable(self.retriever):
            return list(self.retriever(query, **retriever_kwargs))
        if hasattr(self.retriever, "retrieve"):
            return list(self.retriever.retrieve(query, **retriever_kwargs))
        if hasattr(self.retriever, "get_relevant_documents"):
            return list(self.retriever.get_relevant_documents(query, **retriever_kwargs))
        if hasattr(self.retriever, "invoke"):
            result = self.retriever.invoke(query, **retriever_kwargs)
            return list(result if isinstance(result, list) else [result])
        raise TypeError("Retriever must be callable or expose retrieve/get_relevant_documents/invoke")

    def filter(self, query: str, **retriever_kwargs: Any) -> AdapterResult:
        raw_items = self.retrieve(query, **retriever_kwargs)
        mapped = [self._map_document(item) for item in raw_items]
        gated = self.gate.filter(query=query, retrieved_items=mapped)
        return AdapterResult(query=query, raw_items=raw_items, gated=gated)

    def allowed_context(self, query: str, **retriever_kwargs: Any) -> str:
        return self.filter(query, **retriever_kwargs).allowed_context

    def _map_document(self, document: Any) -> MemoryItem | dict[str, Any]:
        if self.document_mapper is not None:
            return self.document_mapper(document)
        return coerce_document(document)


def coerce_document(document: Any) -> MemoryItem | dict[str, Any]:
    """Coerce common retriever document shapes into Persistence Gate inputs."""
    if isinstance(document, MemoryItem):
        return document
    if isinstance(document, dict):
        if "text" in document:
            return document
        if "page_content" in document:
            data = dict(document)
            data["text"] = str(data.pop("page_content"))
            return data
        if "content" in document:
            data = dict(document)
            data["text"] = str(data.pop("content"))
            return data
    if isinstance(document, str):
        return {"text": document, "source": "string_document"}

    text = getattr(document, "page_content", None) or getattr(document, "text", None) or getattr(document, "content", None)
    if text is None:
        raise ValueError(f"Cannot coerce document of type {type(document)!r}; expected text/page_content/content")

    metadata = dict(getattr(document, "metadata", {}) or {})
    return {
        "id": str(metadata.get("id") or metadata.get("source") or abs(hash(str(text)))),
        "text": str(text),
        "source": str(metadata.get("source") or getattr(document, "source", "retrieved")),
        "metadata": metadata,
        "risk": float(metadata.get("risk", 0.05)),
        "harm_score": float(metadata.get("harm_score", metadata.get("harm", 0.0))),
        "usefulness_score": float(metadata.get("usefulness_score", metadata.get("usefulness", 0.5))),
        "burden": float(metadata.get("burden", 0.15)),
        "label_helpful": metadata.get("label_helpful", False),
        "label_risky": metadata.get("label_risky", False),
        "label_stale": metadata.get("label_stale", False),
    }
