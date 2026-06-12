from __future__ import annotations

from dataclasses import dataclass, field

from .models import EvidenceRole, QueryIntent


@dataclass(frozen=True)
class RoleRule:
    evidence_role: EvidenceRole
    query_intent: QueryIntent
    role_match: float
    role_risk: float
    note: str = ""


@dataclass
class RolePolicy:
    """Configurable role/intent policy table for product integrations."""

    rules: dict[tuple[EvidenceRole, QueryIntent], RoleRule] = field(default_factory=dict)
    default_match: float = 0.50
    default_risk: float = 0.10

    def fit(self, evidence_role: EvidenceRole, query_intent: QueryIntent) -> tuple[float, float]:
        rule = self.rules.get((evidence_role, query_intent))
        if rule is None:
            return self.default_match, self.default_risk
        return rule.role_match, rule.role_risk

    def add_rule(
        self,
        evidence_role: EvidenceRole,
        query_intent: QueryIntent,
        role_match: float,
        role_risk: float,
        note: str = "",
    ) -> None:
        self.rules[(evidence_role, query_intent)] = RoleRule(
            evidence_role=evidence_role,
            query_intent=query_intent,
            role_match=role_match,
            role_risk=role_risk,
            note=note,
        )

    def to_rows(self) -> list[dict[str, str | float]]:
        return [
            {
                "evidence_role": rule.evidence_role.value,
                "query_intent": rule.query_intent.value,
                "role_match": rule.role_match,
                "role_risk": rule.role_risk,
                "note": rule.note,
            }
            for rule in self.rules.values()
        ]


def default_role_policy() -> RolePolicy:
    policy = RolePolicy()
    policy.add_rule(EvidenceRole.CURRENT_GUIDANCE, QueryIntent.CURRENT_ACTION, 1.00, 0.00, "current guidance for current action")
    policy.add_rule(EvidenceRole.WARNING_AGAINST_LEGACY, QueryIntent.CURRENT_ACTION, 0.92, 0.00, "warning evidence is useful for current action")
    policy.add_rule(EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.CURRENT_ACTION, 0.05, 1.00, "legacy instruction should not guide current action")
    policy.add_rule(EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.CURRENT_ACTION, 0.32, 0.38, "history is weak guidance for current action")
    policy.add_rule(EvidenceRole.HISTORICAL_CONTEXT, QueryIntent.HISTORY_COMPARISON, 1.00, 0.00, "history requested")
    policy.add_rule(EvidenceRole.CURRENT_GUIDANCE, QueryIntent.HISTORY_COMPARISON, 0.85, 0.00, "current guidance helps compare changes")
    policy.add_rule(EvidenceRole.LEGACY_INSTRUCTION, QueryIntent.HISTORY_COMPARISON, 0.45, 0.30, "legacy instruction may be historical but risky as guidance")
    policy.add_rule(EvidenceRole.AUDIT_BACKGROUND, QueryIntent.AUDIT_REVIEW, 1.00, 0.00, "audit evidence requested")
    return policy
