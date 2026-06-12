from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .api import GateFilterResult, PersistenceGate
from .models import QueryIntent


@dataclass
class MiddlewareResult:
    query: str
    allowed_context: str
    answer: str | None
    gate_result: GateFilterResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "allowed_context": self.allowed_context,
            "gate": self.gate_result.to_dict(),
        }


class EvidenceAdmissionMiddleware:
    def __init__(self, retriever, responder=None, gate: PersistenceGate | None = None) -> None:
        self.retriever = retriever
        self.responder = responder
        self.gate = gate or PersistenceGate()

    def run(self, query: str, *, query_intent: str | QueryIntent | None = None, top_k: int | None = None, profile: str | None = None, metadata: dict[str, Any] | None = None) -> MiddlewareResult:
        candidates = list(self.retriever(query))
        gate_result = self.gate.filter(query=query, retrieved_items=candidates, query_intent=query_intent, top_k=top_k, profile=profile, metadata=metadata)
        allowed_context = gate_result.allowed_context
        answer = None
        if self.responder is not None:
            answer = self.responder(query, allowed_context, gate_result)
        return MiddlewareResult(query=query, allowed_context=allowed_context, answer=answer, gate_result=gate_result)


RAGMiddleware = EvidenceAdmissionMiddleware
