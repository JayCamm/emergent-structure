from pathlib import Path

from benchmarks.comparative_benchmark import load_cases, run_case, summarize_results
from benchmarks.generate_synthetic_comparative_cases import generate_cases, write_jsonl


def test_comparative_benchmark_loads_snapshot_cases():
    cases = load_cases(Path("benchmark_data/snapshot_cases.jsonl"))
    assert len(cases) >= 5
    assert all("documents" in case for case in cases)


def test_persistence_gate_has_no_false_allows_on_snapshot_cases():
    cases = load_cases(Path("benchmark_data/snapshot_cases.jsonl"))
    rows = [run_case(case, method="persistence_gate", top_k=4, profile="balanced") for case in cases]
    assert sum(row.false_allows for row in rows) == 0
    assert sum(row.false_blocks for row in rows) == 0


def test_ordinary_top_k_allows_some_known_blocked_evidence():
    cases = load_cases(Path("benchmark_data/snapshot_cases.jsonl"))
    rows = [run_case(case, method="ordinary_top_k", top_k=4, profile="balanced") for case in cases]
    assert sum(row.false_allows for row in rows) >= 1


def test_summary_groups_methods():
    cases = load_cases(Path("benchmark_data/snapshot_cases.jsonl"))[:1]
    rows = [
        run_case(cases[0], method="ordinary_top_k", top_k=4, profile="balanced"),
        run_case(cases[0], method="persistence_gate", top_k=4, profile="balanced"),
    ]
    summaries = summarize_results(rows)
    assert {summary.method for summary in summaries} == {"ordinary_top_k", "persistence_gate"}


def test_comprehensive_cases_load_and_cover_many_domains():
    cases = load_cases(Path("benchmark_data/comprehensive_comparative_cases.jsonl"))
    assert len(cases) >= 20
    assert len({case["domain"] for case in cases}) >= 8


def test_comprehensive_benchmark_exposes_baseline_tradeoffs():
    cases = load_cases(Path("benchmark_data/comprehensive_comparative_cases.jsonl"))
    ordinary_rows = [run_case(case, method="ordinary_top_k", top_k=3, profile="balanced") for case in cases]
    recency_rows = [run_case(case, method="recency_filter", top_k=3, profile="balanced") for case in cases]
    metadata_rows = [run_case(case, method="metadata_filter", top_k=3, profile="balanced") for case in cases]
    gate_rows = [run_case(case, method="persistence_gate", top_k=3, profile="balanced") for case in cases]

    assert sum(row.false_allows for row in ordinary_rows) >= 10
    assert sum(row.false_blocks for row in recency_rows) >= 5
    assert sum(row.false_allows for row in metadata_rows) >= 10
    assert sum(row.false_allows for row in gate_rows) == 0
    assert sum(row.false_blocks for row in gate_rows) == 0


def test_synthetic_generator_is_deterministic_and_varied(tmp_path):
    cases_a = generate_cases(count=30, seed=123)
    cases_b = generate_cases(count=30, seed=123)
    assert cases_a == cases_b
    assert len({case["domain"] for case in cases_a}) >= 4
    assert len({case["variant"] for case in cases_a}) >= 4

    path = tmp_path / "generated_cases.jsonl"
    write_jsonl(path, cases_a)
    loaded = load_cases(path)
    assert loaded == cases_a


def test_generated_benchmark_exposes_baseline_tradeoffs():
    cases = generate_cases(count=80, seed=456)
    ordinary_rows = [run_case(case, method="ordinary_top_k", top_k=3, profile="balanced") for case in cases]
    recency_rows = [run_case(case, method="recency_filter", top_k=3, profile="balanced") for case in cases]
    metadata_rows = [run_case(case, method="metadata_filter", top_k=3, profile="balanced") for case in cases]
    gate_rows = [run_case(case, method="persistence_gate", top_k=3, profile="balanced") for case in cases]

    assert sum(row.false_allows for row in ordinary_rows) >= 60
    assert sum(row.false_blocks for row in recency_rows) >= 15
    assert sum(row.false_allows for row in metadata_rows) >= 60
    assert sum(row.false_allows for row in gate_rows) == 0
    assert sum(row.false_blocks for row in gate_rows) == 0
