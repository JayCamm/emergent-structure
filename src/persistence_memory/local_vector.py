from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def bag_of_words_vector(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass(frozen=True)
class LocalVectorDocument:
    """LangChain-like document returned by LocalVectorRetriever."""

    page_content: str
    metadata: dict[str, Any]


class LocalVectorStore:
    """Small dependency-free vector-like store for local testing.

    This is intentionally simple and deterministic. It uses bag-of-words cosine
    similarity so Persistence Gate can be tested against a vector-store-shaped
    interface without external services, API keys, or heavyweight dependencies.
    """

    def __init__(self, documents: Iterable[LocalVectorDocument | dict[str, Any] | str] = ()) -> None:
        self._documents: list[LocalVectorDocument] = []
        self._vectors: list[Counter[str]] = []
        for document in documents:
            self.add(document)

    def add(self, document: LocalVectorDocument | dict[str, Any] | str) -> None:
        doc = self._coerce_document(document)
        self._documents.append(doc)
        self._vectors.append(bag_of_words_vector(doc.page_content))

    def as_retriever(self, top_k: int = 4) -> "LocalVectorRetriever":
        return LocalVectorRetriever(self, top_k=top_k)

    def search(self, query: str, top_k: int = 4) -> list[LocalVectorDocument]:
        query_vector = bag_of_words_vector(query)
        ranked = []
        for index, (document, vector) in enumerate(zip(self._documents, self._vectors)):
            score = cosine_similarity(query_vector, vector)
            ranked.append((score, index, document))
        ranked.sort(key=lambda row: (-row[0], row[1]))

        results: list[LocalVectorDocument] = []
        for score, _, document in ranked[:top_k]:
            metadata = dict(document.metadata)
            metadata["retrieval_score"] = score
            results.append(LocalVectorDocument(page_content=document.page_content, metadata=metadata))
        return results

    def _coerce_document(self, document: LocalVectorDocument | dict[str, Any] | str) -> LocalVectorDocument:
        if isinstance(document, LocalVectorDocument):
            return document
        if isinstance(document, str):
            return LocalVectorDocument(page_content=document, metadata={})
        if isinstance(document, dict):
            text = document.get("text") or document.get("page_content") or document.get("content")
            if text is None:
                raise ValueError("LocalVectorStore document dict must include text, page_content, or content")
            metadata = dict(document.get("metadata") or {})
            for key, value in document.items():
                if key not in {"text", "page_content", "content", "metadata"}:
                    metadata.setdefault(key, value)
            return LocalVectorDocument(page_content=str(text), metadata=metadata)
        raise TypeError(f"Unsupported local vector document type: {type(document)!r}")


class LocalVectorRetriever:
    """Retriever wrapper exposing common retriever methods."""

    def __init__(self, store: LocalVectorStore, top_k: int = 4) -> None:
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, **kwargs: Any) -> list[LocalVectorDocument]:
        top_k = int(kwargs.get("top_k", self.top_k))
        return self.store.search(query, top_k=top_k)

    def get_relevant_documents(self, query: str, **kwargs: Any) -> list[LocalVectorDocument]:
        return self.retrieve(query, **kwargs)

    def invoke(self, query: str, **kwargs: Any) -> list[LocalVectorDocument]:
        return self.retrieve(query, **kwargs)
