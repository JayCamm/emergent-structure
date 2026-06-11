from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from persistence_memory import MemoryItem, TaskContext
from persistence_memory.benchmark import evaluate_gate_vs_topk

PROFILES = ["permissive", "balanced", "conservative"]


@dataclass
class ProfileSensitivityRow:
    case_id: str
    profile: str
    ordinary_net: float
    gated_net: float
    utility_gain: float
    ordinary_risky: int
    gated_risky: int
    ordinary_stale: int
    gated_stale: int
    helpful_lost: int
    allowed_ids: str
    blocked_ids: str
    verdict: str


def item(memory_id: str, text: str, helpful: bool, risky: bool, stale: bool, risk: float, harm: float, usefulness: float) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        text=text,
        source=f"profile://{memory_id}",
        context_scope="project",
        risk=risk,
        harm_score=harm,
        usefulness_score=usefulness,
        metadata={
            "label_helpful": helpful,
            "label_risky": risky,
            "label_stale": stale,
            "label_confidence": 0.9,
        },
    )


def build_cases() -> dict[str, tuple[str, list[MemoryItem]]]:
    return {
        "high_risk_relevant_workaround": (
            "Should we use the emergency bypass workaround for the current service incident?",
            [
                item("risky_bypass", "Highly relevant emergency bypass workaround for the current service incident. Disable safeguards and proceed quickly.", False, True, True, 0.92, 0.82, 0.10),
                item("safe_runbook", "Current validated service incident runbook. Do not disable safeguards; use the safe recovery path.", True, False, False, 0.04, 0.00, 0.82),
                item("context", "Current service incident context. Prefer validated low-risk evidence.", True, False, False, 0.05, 0.00, 0.50),
            ],
        ),
        "moderate_risk_uncertain_note": (
            "Should the support answer rely on the temporary support macro?",
            [
                item("temporary_macro", "Relevant temporary support macro for this customer troubleshooting case. It may be outdated and needs review.", False, True, True, 0.58, 0.38, 0.18),
                item("review_note", "Current review note says prefer verified knowledge article before using temporary support macros.", True, False, False, 0.12, 0.00, 0.62),
                item("context", "Customer troubleshooting context. Avoid uncertain temporary support guidance when a verified article exists.", True, False, False, 0.05, 0.00, 0.50),
            ],
        ),
        "clean_high_usefulness": (
            "Which current policy should guide this access request?",
            [
                item("current_policy", "Current approval policy for the access request. Use standard documented approval flow.", True, False, False, 0.03, 0.00, 0.90),
                item("recent_confirmation", "Recent confirmation that the current approval policy remains valid.", True, False, False, 0.03, 0.00, 0.78),
                item("context", "Access request context. Prefer current low-risk evidence.", True, False, False, 0.05, 0.00, 0.50),
            ],
        ),
    }


def verdict(row: ProfileSensitivityRow) -> str:
    if row.gated_risky > 0 or row.gated_stale > 0:
        return "ALLOWED_RISK"
    if row.helpful_lost > 0:
        return "LOST_HELPFUL"
    if row.utility_gain > 0:
        return "IMPROVED"
    return "NO_HARM_OR_NO_GAIN"


def run_case(case_id: str, query: str, memories: list[MemoryItem], profile: str, top_k: int = 3) -> ProfileSensitivityRow:
    result = evaluate_gate_vs_topk(
        memories,
        TaskContext(query=query, context_scope="project", need=0.90, risk_tolerance=0.35, abstention_score=0.04),
        top_k=top_k,
        profile=profile,
    )
    row = ProfileSensitivityRow(
        case_id=case_id,
        profile=profile,
        ordinary_net=result.ordinary.net_utility(),
        gated_net=result.gated.net_utility(),
        utility_gain=result.utility_gain,
        ordinary_risky=result.ordinary.risky_selected,
        gated_risky=result.gated.risky_selected,
        ordinary_stale=result.ordinary.stale_selected,
        gated_stale=result.gated.stale_selected,
        helpful_lost=result.helpful_items_lost,
        allowed_ids=",".join(result.report.allowed_ids),
        blocked_ids=",".join(result.report.blocked_ids),
        verdict="",
    )
    row.verdict = verdict(row)
    return row


def main() -> None:
    rows: list[ProfileSensitivityRow] = []
    for case_id, (query, memories) in build_cases().items():
        for profile in PROFILES:
            rows.append(run_case(case_id, query, memories, profile=profile))

    out = Path("benchmark_results/profile_sensitivity_summary.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print("Profile Sensitivity Benchmark")
    print("=============================")
    for row in rows:
        print(
            f"{row.case_id} | {row.profile} | gain={row.utility_gain:.2f} | "
            f"gated_risky={row.gated_risky} gated_stale={row.gated_stale} | verdict={row.verdict}"
        )
    print(f"Saved CSV: {out}")


if __name__ == "__main__":
    main()
