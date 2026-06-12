from __future__ import annotations

from math import exp
from time import time

from .models import EvidenceRole, GateDecision, MemoryItem, MemoryState, QueryIntent, ScoredMemory, TaskContext
from .profiles import GateProfile, get_profile


class PersistenceScorer:
    """Scores whether a memory should influence a current task.

    This is intentionally transparent and adjustable. It is not a learned model yet.
    """

    def __init__(
        self,
        allow_threshold: float | None = None,
        warning_threshold: float | None = None,
        quarantine_threshold: float | None = None,
        harm_weight: float | None = None,
        burden_weight: float | None = None,
        staleness_weight: float | None = None,
        risk_weight: float | None = None,
        profile: str | GateProfile = "balanced",
    ) -> None:
        self.profile = get_profile(profile)
        self.allow_threshold = self.profile.allow_threshold if allow_threshold is None else allow_threshold
        self.warning_threshold = self.profile.warning_threshold if warning_threshold is None else warning_threshold
        self.quarantine_threshold = self.profile.quarantine_threshold if quarantine_threshold is None else quarantine_threshold
        self.harm_weight = self.profile.harm_weight if harm_weight is None else harm_weight
        self.burden_weight = self.profile.burden_weight if burden_weight is None else burden_weight
        self.staleness_weight = self.profile.staleness_weight if staleness_weight is None else staleness_weight
        self.risk_weight = self.profile.risk_weight if risk_weight is None else risk_weight

    def score(self, memory: MemoryItem, task: TaskContext, now: float | None = None) -> ScoredMemory:
        now = now or time()
        reasons: list[str] = []

        query_intent = self._infer_query_intent(task)
        evidence_role = self._infer_evidence_role(memory)
        role_match, role_risk = self._role_task_fit(evidence_role=evidence_role, query_intent=query_intent)

        relevance = memory.relevance
        context_fit = 1.0 if memory.context_scope in {"global", task.context_scope} else 0.25
        validity = self._validity(memory, now)
        usefulness = memory.usefulness_score + 0.12 * memory.help_count
        harm = memory.harm_score + 0.16 * memory.harm_count
        burden = memory.burden
        risk = memory.risk
        validated_bonus = 0.15 if memory.state == MemoryState.VALIDATED else 0.0
        need = task.need

        effective_risk = risk
        if evidence_role == EvidenceRole.WARNING_AGAINST_LEGACY and harm <= 0.15:
            # Warning evidence often mentions risky/legacy terms; do not treat that as
            # the same thing as recommending the legacy instruction.
            effective_risk *= 0.55

        raw_score = (
            0.30 * relevance
            + 0.18 * context_fit
            + 0.15 * validity
            + 0.20 * usefulness
            + 0.14 * role_match
            + 0.10 * need
            + validated_bonus
            - self.harm_weight * harm
            - self.burden_weight * burden
            - self.risk_weight * effective_risk
            - 0.32 * role_risk
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
        if evidence_role != EvidenceRole.UNCERTAIN:
            reasons.append(f"evidence_role:{evidence_role.value}")
        if query_intent != QueryIntent.GENERAL_LOOKUP:
            reasons.append(f"query_intent:{query_intent.value}")
        if role_match >= 0.85:
            reasons.append("role_matches_task")
        if role_risk >= 0.50:
            reasons.append("role_task_mismatch")
        if evidence_role == EvidenceRole.WARNING_AGAINST_LEGACY and harm <= 0.15:
            reasons.append("warning_against_legacy_not_instruction")
        if evidence_role == EvidenceRole.HISTORICAL_CONTEXT and query_intent == QueryIntent.HISTORY_COMPARISON:
            reasons.append("history_requested")
        if evidence_role == EvidenceRole.LEGACY_INSTRUCTION and query_intent == QueryIntent.CURRENT_ACTION:
            reasons.append("legacy_instruction_for_current_action")
        if self.profile.high_risk_block_threshold is not None and effective_risk >= self.profile.high_risk_block_threshold:
            reasons.append("profile_high_risk_block")
        if self.profile.high_harm_block_threshold is not None and harm >= self.profile.high_harm_block_threshold:
            reasons.append("profile_high_harm_block")
        if self._is_profile_gray_zone_block(harm=harm, risk=effective_risk, usefulness=usefulness):
            reasons.append("profile_gray_zone_block")
        if memory.state == MemoryState.VALIDATED:
            reasons.append("validated")

        decision = self._decision(score, memory, reasons)
        return ScoredMemory(memory=memory, score=score, decision=decision, reasons=reasons)

    def _infer_query_intent(self, task: TaskContext) -> QueryIntent:
        if task.query_intent != QueryIntent.GENERAL_LOOKUP:
            return task.query_intent
        metadata_intent = task.metadata.get("query_intent") or task.metadata.get("intent")
        if metadata_intent:
            return self._coerce_query_intent(str(metadata_intent))
        q = task.query.lower()
        history_terms = ("what changed", "changed from", "history", "historical", "older", "old ", "legacy", "migration", "compare", "comparison")
        audit_terms = ("audit", "review", "why did", "trace", "evidence trail")
        current_terms = ("current", "should", "now", "today", "guide", "enforce", "process", "procedure", "how do i", "how should")
        if any(term in q for term in history_terms):
            return QueryIntent.HISTORY_COMPARISON
        if any(term in q for term in audit_terms):
            return QueryIntent.AUDIT_REVIEW
        if any(term in q for term in current_terms):
            return QueryIntent.CURRENT_ACTION
        return QueryIntent.GENERAL_LOOKUP

    def _infer_evidence_role(self, memory: MemoryItem) -> EvidenceRole:
        if memory.evidence_role != EvidenceRole.UNCERTAIN:
            return memory.evidence_role
        metadata_role = memory.metadata.get("evidence_role") or memory.metadata.get("influence_role")
        if metadata_role:
            return self._coerce_evidence_role(str(metadata_role))
        text = memory.text.lower()
        if "current warning" in text or "do not treat" in text or "do not use" in text or "warning against" in text:
            return EvidenceRole.WARNING_AGAINST_LEGACY
        if "historical comparison" in text or "what changed" in text or "history" in text:
            return EvidenceRole.HISTORICAL_CONTEXT
        if "legacy instruction" in text or "legacy guidance" in text or "removed" in text or "deprecated" in text:
            return EvidenceRole.LEGACY_INSTRUCTION
        if "current authoritative" in text or "current guidance" in text or "validated" in text:
            return EvidenceRole.CURRENT_GUIDANCE
        return EvidenceRole.UNCERTAIN

    def _role_task_fit(self, evidence_role: EvidenceRole, query_intent: QueryIntent) -> tuple[float, float]:
        if evidence_role == EvidenceRole.UNCERTAIN or query_intent == QueryIntent.GENERAL_LOOKUP:
            return 0.50, 0.10

        table: dict[tuple[EvidenceRole, QueryIntent], tuple[float, float]] = {
            (EvidenceRole.CURRENT_GUIDANCE, QueryIntent.CURRENT_ACTION): (1.00, 0.00),
            (EvidenceRole.CURRENT_GUIDANCE, QueryIntent.HISTORY_COMPARISON): (0.85, 0.00),
            (EvidenceRole.CURRENT_GUIDANCE, QueryIntent.AUDIT_REVIEW): (0.70, 0.05),
            (EvidenceRole.CURRENT_GUIDANCE, QueryIntent.TRAINING_BACKGROUND): (0.80, 0.00),
            (EvidenceRole.WARNING_AGAINST_LEGACY, QueryIntent.CURRENT_ACTION): (0.92, 0.00),
            (EvidenceRole.WARNING_AGAINST_LEGACY, QueryIntent.HISTORY_COMPARISON): (0.82, 0.00),
            (EvidenceRole.WARNING_AGAINST_LEGACY, QueryIntent.AUDIT_REVIEW): (0.72, 0.05),
            (EvidenceRole.WARNING_AGAINST_LEGACY, QueryIntent.TRAINING_BACKGROUND): (0.75, 0.02),
            (EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.CURRENT_ACTION): (0.32, 0.38),
            (EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.HISTORY_COMPARISON): (1.00, 0.00),
            (EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.AUDIT_REVIEW): (0.90, 0.00),
            (EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.TRAINING_BACKGROUND): (0.82, 0.00),
            (EvidenceRole.AUDIT_BACKGROUND, QueryIntent.CURRENT_ACTION): (0.30, 0.28),
            (EvidenceRole.AUDIT_BACKGROUND, QueryIntent.HISTORY_COMPARISON): (0.78, 0.03),
            (EvidenceRole.AUDIT_BACKGROUND, QueryIntent.AUDIT_REVIEW): (1.00, 0.00),
            (EvidenceRole.AUDIT_BACKGROUND, QueryIntent.TRAINING_BACKGROUND): (0.70, 0.02),
            (EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.CURRENT_ACTION): (0.05, 1.00),
            (EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.HISTORY_COMPARISON): (0.45, 0.30),
            (EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.AUDIT_REVIEW): (0.55, 0.20),
            (EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.TRAINING_BACKGROUND): (0.35, 0.35),
        }
        return table.get((evidence_role, query_intent), (0.50, 0.10))

    def _coerce_query_intent(self, value: str) -> QueryIntent:
        try:
            return QueryIntent(value)
        except ValueError:
            return QueryIntent.GENERAL_LOOKUP

    def _coerce_evidence_role(self, value: str) -> EvidenceRole:
        try:
            return EvidenceRole(value)
        except ValueError:
            return EvidenceRole.UNCERTAIN

    def _is_profile_gray_zone_block(self, harm: float, risk: float, usefulness: float) -> bool:
        if (
            self.profile.gray_zone_harm_threshold is None
            or self.profile.gray_zone_risk_threshold is None
            or self.profile.gray_zone_usefulness_ceiling is None
        ):
            return False
        return (
            harm >= self.profile.gray_zone_harm_threshold
            and risk >= self.profile.gray_zone_risk_threshold
            and usefulness <= self.profile.gray_zone_usefulness_ceiling
        )

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
        if (
            "profile_high_risk_block" in reasons
            or "profile_high_harm_block" in reasons
            or "high_harm_history" in reasons
            or "profile_gray_zone_block" in reasons
            or "legacy_instruction_for_current_action" in reasons
        ):
            return GateDecision.QUARANTINE
        if score >= self.allow_threshold:
            return GateDecision.ALLOW
        if score >= self.warning_threshold:
            return GateDecision.ALLOW_WITH_WARNING
        if score <= self.quarantine_threshold:
            return GateDecision.QUARANTINE
        if "stale_or_expired" in reasons:
            return GateDecision.REFRESH_REQUIRED
        return GateDecision.IGNORE
