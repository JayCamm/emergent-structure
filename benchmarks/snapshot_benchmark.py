from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from persistence_memory.api import PersistenceGate


@dataclass
class SnapshotCaseResult:
    case_id: str
    domain: str
    profile: str
    expected_allowed: str
    actual_allowed: str
    expected_blocked: str
    actual_blocked: str
    false_allows: int
    false_blocks: int
    blocked_from_ordinary_top_k: int
    passed: bool


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_case(case: dict[str, Any], profile: str, top_k: int) -> SnapshotCaseResult:
    gate = PersistenceGate(profile=profile, top_k=top_k)
    result = gate.filter(case["query"], case["documents"])

    expected_allowed = {doc["id"] for doc in case["documents"] if doc.get("should_allow") is True}
    expected_blocked = {doc["id"] for doc in case["documents"] if doc.get("should_allow") is False}
    actual_allowed = set(result.allowed_ids)
    actual_blocked = set(result.blocked_ids)

    false_allows = len(actual_allowed & expected_blocked)
    false_blocks = len(actual_blocked & expected_allowed)
    passed = false_allows == 0 and false_blocks == 0

    return SnapshotCaseResult(
        case_id=case["case_id"],
        domain=case.get("domain", "unknown"),
        profile=profile,
        expected_allowed=",".join(sorted(expected_allowed)),
        actual_allowed=",".join(sorted(actual_allowed)),
        expected_blocked=",".join(sorted(expected_blocked)),
        actual_blocked=",".join(sorted(actual_blocked)),
        false_allows=false_allows,
        false_blocks=false_blocks,
        blocked_from_ordinary_top_k=len(result.report.blocked_from_ordinary_top_k),
        passed=passed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repeatable snapshot benchmark cases for Persistence Gate.")
    parser.add_argument("--cases", type=Path, default=Path("benchmark_data/snapshot_cases.jsonl"))
    parser.add_argument("--profile", choices=["permissive", "balanced", "conservative"], default="balanced")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("benchmark_results/snapshot_benchmark_summary.csv"))
    args = parser.parse_args()

    cases = load_cases(args.cases)
    rows = [run_case(case, args.profile, args.top_k) for case in cases]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    passed = sum(1 for row in rows if row.passed)
    false_allows = sum(row.false_allows for row in rows)
    false_blocks = sum(row.false_blocks for row in rows)
    blocked_from_topk = sum(row.blocked_from_ordinary_top_k for row in rows)

    print("Snapshot Benchmark")
    print("==================")
    print(f"Cases: {len(rows)}")
    print(f"Profile: {args.profile}")
    print(f"Passed: {passed}/{len(rows)}")
    print(f"False allows: {false_allows}")
    print(f"False blocks: {false_blocks}")
    print(f"Blocked from ordinary top-k: {blocked_from_topk}")
    print(f"Saved CSV: {args.out}")

    if passed != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
