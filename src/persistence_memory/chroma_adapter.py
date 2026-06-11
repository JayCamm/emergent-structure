from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .adapters import PersistenceGateRetrieverAdapter


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Deterministic dependency-free embedding for local Chroma demos/tests.

    This is intentionally simple. Production users should replace it with their
    normal embedding model while keeping the same Chroma retriever boundary.
    """
    vector = [0.0] * dimensions
    for token in _TOKEN_RE.findall(text.lower()):
        index = hash(token) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


@dataclass(frozen=True)
class ChromaDocument:
    page_content: str
    metadata: dict[str, Any]


class ChromaRetriever:
    """Small retriever wrapper for a Chroma collection.

    The collection must expose Chroma's query method. This class keeps the same
    retriever boundary as other adapters: retrieve/get_relevant_documents/invoke.
    """

    def __init__(self, collection: Any, top_k: int = 4, dimensions: int = 64) -> None:
        self.collection = collection
        self.top_k = top_k
        self.dimensions = dimensions

    def retrieve(self, query: str, **kwargs: Any) -> list[ChromaDocument]:
        top_k = int(kwargs.get("top_k", kwargs.get("k", self.top_k)))
        response = self.collection.query(
            query_embeddings=[hash_embedding(query, self.dimensions)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        results: list[ChromaDocument] = []
        for index, text in enumerate(documents):
            metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
            if index < len(distances):
                metadata["retrieval_distance"] = distances[index]
            results.append(ChromaDocument(page_content=str(text), metadata=metadata))
        return results

    def get_relevant_documents(self, query: str, **kwargs: Any) -> list[ChromaDocument]:
        return self.retrieve(query, **kwargs)

    def invoke(self, query: str, **kwargs: Any) -> list[ChromaDocument]:
        return self.retrieve(query, **kwargs)


def build_chroma_collection(
    documents: Iterable[dict[str, Any]],
    *,
    collection_name: str = "persistence_gate_demo",
    persist_directory: str | None = None,
    dimensions: int = 64,
) -> Any:
    """Build a Chroma collection from dictionaries without external embeddings.

    Requires installing the optional vector dependency:

        pip install -e ".[vector]"
    """
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - exercised when optional dep missing
        raise ImportError('Chroma support requires: pip install -e ".[vector]"') from exc

    if persist_directory:
        client = chromadb.PersistentClient(path=persist_directory)
    else:
        client = chromadb.Client()

    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(name=collection_name)
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []

    for index, document in enumerate(documents):
        text = str(document.get("text") or document.get("page_content") or document.get("content") or "")
        if not text:
            raise ValueError("Each Chroma document must include text, page_content, or content")
        doc_id = str(document.get("id") or f"doc_{index}")
        metadata = dict(document.get("metadata") or {})
        for key, value in document.items():
            if key not in {"text", "page_content", "content", "metadata"}:
                metadata[key] = value
        metadata.setdefault("id", doc_id)
        metadata.setdefault("source", str(document.get("source") or metadata.get("source") or "chroma"))

        ids.append(doc_id)
        texts.append(text)
        metadatas.append(metadata)
        embeddings.append(hash_embedding(text, dimensions))

    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    return collection


def build_chroma_gate_adapter(
    documents: Iterable[dict[str, Any]],
    *,
    profile: str = "balanced",
    top_k: int = 4,
    collection_name: str = "persistence_gate_demo",
    persist_directory: str | None = None,
    dimensions: int = 64,
) -> PersistenceGateRetrieverAdapter:
    collection = build_chroma_collection(
        documents,
        collection_name=collection_name,
        persist_directory=persist_directory,
        dimensions=dimensions,
    )
    retriever = ChromaRetriever(collection, top_k=top_k, dimensions=dimensions)
    return PersistenceGateRetrieverAdapter(retriever, profile=profile, top_k=top_k)
