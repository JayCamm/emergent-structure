from __future__ import annotations

from persistence_memory import MemoryItem, TaskContext
from persistence_memory.benchmark import evaluate_gate_vs_topk


def build_clean_cases() -> list[MemoryItem]:
    return [
        MemoryItem(
            id=f"clean_{idx}",
            text=f"Current useful documentation and passing test evidence for Persistence Gate module {idx}. This information is safe and relevant.",
            context_scope="project",
            risk=0.02,
            harm_score=0.0,
            usefulness_score=0.65,
            burden=0.10,
            metadata={"kind": "document", "label_helpful": True},
        )
        for idx in range(12)
    ]


def main() -> None:
    query = "What safe current information should influence Persistence Gate development?"
    task = TaskContext(query=query, context_scope="project", need=0.9, risk_tolerance=0.6, abstention_score=0.02)
    result = evaluate_gate_vs_topk(build_clean_cases(), task=task, top_k=8)

    print("Clean Negative-Control Benchmark")
    print("================================")
    print(f"Ordinary top-k: helpful={result.ordinary.helpful_selected}, risky={result.ordinary.risky_selected}, stale={result.ordinary.stale_selected}, uncertain={result.ordinary.uncertain_selected}, net={result.ordinary.net_utility():.2f}")
    print(f"Persistence Gate: helpful={result.gated.helpful_selected}, risky={result.gated.risky_selected}, stale={result.gated.stale_selected}, uncertain={result.gated.uncertain_selected}, net={result.gated.net_utility():.2f}")
    print(f"Utility gain: {result.utility_gain:.2f}")
    print(f"Helpful items lost: {result.helpful_items_lost}")

    if result.gated.helpful_selected >= result.ordinary.helpful_selected - 1 and result.gated.risky_selected == 0:
        print("Result: PASS — Persistence Gate does not overblock a clean corpus.")
    else:
        print("Result: FAIL/WEAK — Persistence Gate may be overblocking useful clean information.")


if __name__ == "__main__":
    main()
