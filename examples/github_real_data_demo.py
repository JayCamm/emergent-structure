from __future__ import annotations

import argparse
import json
from pathlib import Path

from persistence_memory import FeedbackEvent, InMemoryStore, MemoryController, MemoryItem, TaskContext


def load_jsonl(path: Path) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        items.append(MemoryItem(**raw))
    return items


def print_scored_section(title: str, scored_items) -> None:
    print(f"\n{title}:")
    if not scored_items:
        print("  None")
        return
    for item in scored_items:
        print(f"- {item.memory.id}: decision={item.decision.value}, score={item.score:.3f}, reasons={item.reasons}")
        print(f"  {item.memory.text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Run against bundled sample corpus")
    parser.add_argument("--corpus", type=Path, default=Path(__file__).with_name("sample_corpus.jsonl"))
    parser.add_argument("--query", default="Should we build persistence-aware memory software and what should influence the decision?")
    parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()

    items = load_jsonl(args.corpus)
    store = InMemoryStore(items)
    controller = MemoryController(store=store)

    task = TaskContext(
        query=args.query,
        context_scope="project",
        need=0.85,
        risk_tolerance=0.55,
        abstention_score=0.05,
    )

    report = controller.retrieve_report(task, top_k=args.top_k)

    print("\nOrdinary top-k baseline, relevance only:")
    for item in report.ordinary_top_k:
        print(f"- {item.id}: relevance={item.relevance:.3f}, risk={item.risk:.3f}, harm={item.harm_score:.3f}, usefulness={item.usefulness_score:.3f}")
        print(f"  {item.text}")

    print_scored_section("Allowed memory after persistence gate", report.allowed)
    print_scored_section("Blocked / gated-out memory", report.blocked)

    print("\nBlocked memories that ordinary top-k would have used:")
    blocked_from_topk = report.blocked_from_ordinary_top_k
    if blocked_from_topk:
        for memory_id in blocked_from_topk:
            print(f"- {memory_id}")
    else:
        print("  None")

    print("\nAllowed context:\n")
    print(controller.allowed_context(report.allowed))

    # Example feedback: mark allowed validated result as helpful.
    for item in report.allowed:
        if item.memory.id == "validated_v2_result":
            controller.apply_feedback(FeedbackEvent(memory_id=item.memory.id, outcome="used_in_answer", helped=True))

    print("\nUpdated memory states:")
    for item in store.all(include_deleted=True):
        print(
            f"- {item.id}: state={item.state.value}, help={item.help_count}, harm={item.harm_count}, "
            f"usefulness={item.usefulness_score:.2f}, harm_score={item.harm_score:.2f}, risk={item.risk:.2f}"
        )


if __name__ == "__main__":
    main()
