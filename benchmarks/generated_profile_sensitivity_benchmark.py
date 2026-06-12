from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.comparative_benchmark import load_cases, run_case, summarize_results, write_csv
from benchmarks.generate_synthetic_comparative_cases import generate_cases, write_jsonl


@dataclass(frozen=True)
class ProfileSummary:
    profile: str
    method: str
    cases: int
    false_allows: int
    false_blocks: int
    flagged_answers: int
    safe_answers: int
    clean_cases: int
    false_allow_rate: float
    false_block_rate: float
    flagged_answer_rate: float
    clean_rate: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generated comparative benchmark across gate profiles.")
    parser.add_argument("--count", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--profiles", default="permissive,balance d,conservative".replace(" ", ""))
    parser.add_argument("--case-out", type=Path, default=Path("benchmark_data/generated_profile_sensitivity_cases.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("benchmark_results/generated_profile_sensitivity"))
    args = parser.parse_args()

    cases = generate_cases(args.count, args.seed)
    write_jsonl(args.case_out, cases)
    loaded_cases = load_cases(args.case_out)
    profiles = [profile.strip() for profile in args.profiles.split(",") if profile.strip()]

    rows: list[ProfileSummary] = []
    all_case_rows = []
    for profile in profiles:
        case_rows = [run_case(case, method="persistence_gate", top_k=args.top_k, profile=profile) for case in loaded_cases]
        all_case_rows.extend(case_rows)
        summary = summarize_results(case_rows)[0]
        rows.append(
            ProfileSummary(
                profile=profile,
                method=summary.method,
                cases=summary.cases,
                false_allows=summary.false_allows,
                false_blocks=summary.false_blocks,
                flagged_answers=summary.unsafe_answers,
                safe_answers=summary.safe_answers,
                clean_cases=summary.clean_cases,
                false_allow_rate=summary.false_allows / summary.cases if summary.cases else 0.0,
                false_block_rate=summary.false_blocks / summary.cases if summary.cases else 0.0,
                flagged_answer_rate=summary.unsafe_answers / summary.cases if summary.cases else 0.0,
                clean_rate=summary.clean_cases / summary.cases if summary.cases else 0.0,
            )
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "profile_sensitivity_case_results.csv", all_case_rows)
    with (args.out_dir / "profile_sensitivity_summary.csv").open("w", encoding="utf-8") as handle:
        if rows:
            header = list(asdict(rows[0]).keys())
            handle.write(",".join(header) + "\n")
            for row in rows:
                data = asdict(row)
                handle.write(",".join(str(data[key]) for key in header) + "\n")

    print("Generated Profile Sensitivity Benchmark")
    print("======================================")
    print(f"Cases: {len(loaded_cases)}")
    print(f"Seed: {args.seed}")
    print(f"Profiles: {', '.join(profiles)}")
    print(f"Top-k: {args.top_k}")
    print("\nSummary:")
    for row in rows:
        print(
            f"{row.profile}: "
            f"false_allows={row.false_allows} ({row.false_allow_rate:.1%}), "
            f"false_blocks={row.false_blocks} ({row.false_block_rate:.1%}), "
            f"flagged_answers={row.flagged_answers} ({row.flagged_answer_rate:.1%}), "
            f"safe_answers={row.safe_answers}, "
            f"clean_cases={row.clean_cases}/{row.cases} ({row.clean_rate:.1%})"
        )
    print(f"\nSaved cases: {args.case_out}")
    print(f"Saved: {args.out_dir / 'profile_sensitivity_case_results.csv'}")
    print(f"Saved: {args.out_dir / 'profile_sensitivity_summary.csv'}")


if __name__ == "__main__":
    main()
