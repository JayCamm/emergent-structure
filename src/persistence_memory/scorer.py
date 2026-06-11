from __future__ import annotations

from math import exp
from time import time

from .models import GateDecision, MemoryItem, MemoryState, ScoredMemory, TaskContext


class PersistenceScorer:
    """Scores whether a memory should influence a current task.

    This is intentionally transparent and adjustable. It is not a learned model yet.
    """

    def __init__(
        self,
        allow_threshold: float = 0.28,
        warning_threshold: float = 0.15,
        quarantine_threshold: float = -0.10,
        harm_weight: float = 0.55,
        burden_weight: float = 0.35,
        staleness_weight: float = 0.35,
    ) -> None:
        self.allow_threshold = allow_threshold
        self.warning_threshold = warning_threshold
        self.quarantine_threshold = quarantine_threshold
        self.harm_weight = harm_weight
        self.burden_weight = burden_weight
        self.staleness_weight = staleness_weight

    def score(self, memory: MemoryItem, task: TaskContext, now: float | None = None) -> ScoredMemory:
        now = now or time()
        reasons: list[str] = []

        relevance = memory.relevance
        context_fit = 1.0 if memory.context_scope in {"global", task.context_scope} else 0.25
        validity = self._validity(memory, now)
        usefulness = memory.usefulness_score + 0.12 * memory.help_count
        harm = memory.harm_score + 0.16 * memory.harm_count
        burden = memory.burden
        risk = memory.risk
        validated_bonus = 0.15 if memory.state == MemoryState.VALIDATED else 0.0
        need = task.need

        raw_score = (
            0.34 * relevance
            + 0.20 * context_fit
            + 0.18 * validity
            + 0.22 * usefulness
            + 0.12 * need
            + validated_bonus
            - self.harm_weight * harm
            - self.burden_weight * burden
            - 0.28 * risk
        )

        # Abstention-aware adjustment. If task risk tolerance is low, memory must earn more influence.
        score = raw_score - (1.0 - task.risk_tolerance) * 0.12 - task.abstention_score

        if validity < 0.35:
            reasons.append("stale_or_expired")
        if context_fit < 0.5:
            reasons.append("context_mismatch")
        if harm > 0.5:
            reasons.append("high_harm_history")
        if burden > 0.5:
            reasons.append("high_burden")
        if memory.state == MemoryState.VALIDATED:
            reasons.append("validated")

        decision = self._decision(score, memory, reasons)
        return ScoredMemory(memory=memory, score=score, decision=decision, reasons=reasons)

    def _validity(self, memory: MemoryItem, now: float) -> float:
        if memory.valid_until is None:
            return 0.75
        remaining = memory.valid_until - now
        if remaining >= 0:
            return 1.0 / (1.0 + exp(-remaining / 86_400.0))
        return exp(remaining / 86_400.0)

    def _decision(self, score: float, memory: MemoryItem, reasons: list[str]) -> GateDecision:
        if memory.state in {MemoryState.DELETED, MemoryState.ARCHIVED}:
            return GateDecision.IGNORE
        if memory.state == MemoryState.QUARANTINED:
            return GateDecision.QUARANTINE
        if score >= self.allow_threshold:
            return GateDecision.ALLOW
        if score >= self.warning_threshold:
            return GateDecision.ALLOW_WITH_WARNING
        if score <= self.quarantine_threshold or "high_harm_history" in reasons:
            return GateDecision.QUARANTINE
        if "stale_or_expired" in reasons:
            return GateDecision.REFRESH_REQUIRED
        return GateDecision.IGNORE
