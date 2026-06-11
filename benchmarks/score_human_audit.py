from __future__ import annotations

import argparse
import csv
from pathlib import Path


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score completed human audit labels against heuristic labels.")
    parser.add_argument("audit_csv", type=Path, help="Completed audit CSV with human_label_* columns filled in.")
    args = parser.parse_args()

    with args.audit_csv.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    labeled = [row for row in rows if any(row.get(col, "").strip() for col in ["human_label_helpful", "human_label_risky", "human_label_stale", "human_label_irrelevant"])]
    if not labeled:
        raise SystemExit("No human labels found. Fill in human_label_* columns first.")

    def agreement(col: str, heuristic_col: str) -> tuple[int, int]:
        total = 0
        matches = 0
        for row in labeled:
            human_value = row.get(col, "").strip()
            if not human_value:
                continue
            total += 1
            if truthy(human_value) == truthy(row.get(heuristic_col, "")):
                matches += 1
        return matches, total

    helpful_matches, helpful_total = agreement("human_label_helpful", "heuristic_helpful")
    risky_matches, risky_total = agreement("human_label_risky", "heuristic_risky")
    stale_matches, stale_total = agreement("human_label_stale", "heuristic_stale")

    print("Human Audit Score")
    print("=================")
    print(f"Rows with at least one human label: {len(labeled)} / {len(rows)}")
    for name, matches, total in [
        ("helpful", helpful_matches, helpful_total),
        ("risky", risky_matches, risky_total),
        ("stale", stale_matches, stale_total),
    ]:
        rate = matches / total if total else 0.0
        print(f"{name}: agreement={matches}/{total} ({rate:.1%})")

    print("\nInterpretation:")
    print("High agreement supports the benchmark labels. Low agreement means the heuristic benchmark is biased or too noisy and should not be used as proof yet.")


if __name__ == "__main__":
    main()
