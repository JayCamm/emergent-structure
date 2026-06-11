from __future__ import annotations

import math
import re
from collections import Counter
from copy import deepcopy

from .models import MemoryItem

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]{1,}")


def tokenize(text: str) -> list[str]:
    """Simple dependency-free tokenizer for prototype retrieval."""
    return [token.lower() for token in TOKEN_RE.findall(text)]


def lexical_relevance(query: str, text: str) -> float:
    """Return a 0..1 relevance score using weighted token overlap.

    This is intentionally simple. The goal is not to replace embeddings; it gives
    the prototype a real retriever so we can compare relevance-only top-k against
    persistence-gated retrieval on arbitrary corpora.
    """
    query_tokens = tokenize(query)
    text_tokens = tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0

    query_counts = Counter(query_tokens)
    text_counts = Counter(text_tokens)

    overlap = 0.0
    for token, q_count in query_counts.items():
        if token in text_counts:
            # Log dampening prevents repeated words from dominating.
            overlap += min(q_count, text_counts[token]) * (1.0 + math.log1p(text_counts[token]))

    norm = math.sqrt(sum(v * v for v in query_counts.values())) * math.sqrt(sum(math.log1p(v) ** 2 for v in text_counts.values()))
    if norm <= 0:
        return 0.0
    return max(0.0, min(1.0, overlap / norm))


def rank_by_relevance(query: str, items: list[MemoryItem], top_k: int | None = None, copy_items: bool = True) -> list[MemoryItem]:
    """Score items by lexical relevance and return them sorted descending.

    By default this returns copies so callers can compare different retrieval
    strategies without mutating the original corpus.
    """
    scored_items = deepcopy(items) if copy_items else list(items)
    for item in scored_items:
        item.relevance = lexical_relevance(query, item.text)
    scored_items.sort(key=lambda item: item.relevance, reverse=True)
    if top_k is None:
        return scored_items
    return scored_items[:top_k]
