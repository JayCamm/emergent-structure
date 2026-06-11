from __future__ import annotations

from persistence_memory import MemoryItem, TaskContext
from persistence_memory.benchmark import evaluate_gate_vs_topk


def build_cases() -> list[MemoryItem]:
    """A controlled benchmark with relevant-but-wrong memory.

    This is the smoking-gun style test: ordinary retrieval should be tempted by
    highly relevant stale claims, while Persistence Gate should prefer current,
    validated evidence.
    """
    return [
        MemoryItem(
            id="old_topk_rule",
            text="Old claim: Always retrieve the top-k most similar memories and use them immediately for the answer.",
            context_scope="project",
            risk=0.88,
            harm_score=0.82,
            usefulness_score=-0.55,
            burden=0.12,
            metadata={"kind": "sample", "label_risky": True, "label_stale": True},
        ),
        MemoryItem(
            id="current_gate_rule",
            text="Current supported rule: retrieve candidates, then allow influence only after checking usefulness, risk, burden, validity, and context fit.",
            context_scope="project",
            risk=0.04,
            harm_score=0.0,
            usefulness_score=0.82,
            burden=0.14,
            metadata={"kind": "document", "label_helpful": True},
        ),
        MemoryItem(
            id="old_compression_claim",
            text="Previous conclusion: compression reliably improved Persistence Gate and should be treated as a supported mechanism.",
            context_scope="project",
            risk=0.76,
            harm_score=0.65,
            usefulness_score=-0.25,
            burden=0.10,
            metadata={"kind": "sample", "label_risky": True, "label_stale": True},
        ),
        MemoryItem(
            id="current_compression_warning",
            text="Current result: compression did not activate reliably, so compression should not be claimed as a supported mechanism yet.",
            context_scope="project",
            risk=0.05,
            harm_score=0.0,
            usefulness_score=0.78,
            burden=0.10,
            metadata={"kind": "document", "label_helpful": True},
        ),
        MemoryItem(
            id="ordinary_accuracy_claim",
            text="Outdated claim: ordinary top-k retrieval is enough because relevant information is always safe to use.",
            context_scope="project",
            risk=0.90,
            harm_score=0.80,
            usefulness_score=-0.40,
            burden=0.10,
            metadata={"kind": "sample", "label_risky": True, "label_stale": True},
        ),
        MemoryItem(
            id="validated_matched_result",
            text="Validated matched result: Persistence Gate beat ordinary retrieval on net utility in messy memory tests by reducing risky and stale influence.",
            context_scope="project",
            risk=0.06,
            harm_score=0.0,
            usefulness_score=0.86,
            burden=0.12,
            metadata={"kind": "document", "label_helpful": True},
        ),
        MemoryItem(
            id="irrelevant_universe_note",
            text="A universe simulator repository explored unrelated pattern dynamics and is not direct evidence for Persistence Gate software behavior.",
            context_scope="research_history",
            risk=0.10,
            harm_score=0.0,
            usefulness_score=0.05,
            burden=0.10,
            metadata={"kind": "document"},
        ),
    ]


def main() -> None:
    query = "What current rule should influence Persistence Gate decisions, and should ordinary top-k be trusted?"
    task = TaskContext(query=query, context_scope="project", need=0.95, risk_tolerance=0.35, abstention_score=0.05)
    result = evaluate_gate_vs_topk(build_cases(), task=task, top_k=5)

    print("Stale-Contradiction Benchmark")
    print("=============================")
    print(f"Ordinary top-k: helpful={result.ordinary.helpful_selected}, risky={result.ordinary.risky_selected}, stale={result.ordinary.stale_selected}, uncertain={result.ordinary.uncertain_selected}, net={result.ordinary.net_utility():.2f}")
    print(f"Persistence Gate: helpful={result.gated.helpful_selected}, risky={result.gated.risky_selected}, stale={result.gated.stale_selected}, uncertain={result.gated.uncertain_selected}, net={result.gated.net_utility():.2f}")
    print(f"Utility gain: {result.utility_gain:.2f}")
    print(f"Risky items prevented: {result.risky_items_prevented}")
    print(f"Stale items prevented: {result.stale_items_prevented}")
    print(f"Helpful items lost: {result.helpful_items_lost}")

    print("\nOrdinary selected:")
    for item in result.report.ordinary_top_k:
        print(f"- {item.id}: relevance={item.relevance:.3f}, risk={item.risk:.2f}, usefulness={item.usefulness_score:.2f}")

    print("\nGate allowed:")
    for scored in result.report.allowed:
        print(f"- {scored.memory.id}: score={scored.score:.3f}, decision={scored.decision.value}, reasons={scored.reasons}")

    print("\nGate blocked:")
    for scored in result.report.blocked:
        print(f"- {scored.memory.id}: score={scored.score:.3f}, decision={scored.decision.value}, reasons={scored.reasons}")

    if result.utility_gain > 0 and result.risky_items_prevented > 0 and result.stale_items_prevented > 0:
        print("\nResult: PASS — Persistence Gate prevented relevant-but-wrong memory from influencing the answer.")
    else:
        print("\nResult: FAIL/WEAK — Persistence Gate did not clearly outperform ordinary top-k on contradiction control.")


if __name__ == "__main__":
    main()
