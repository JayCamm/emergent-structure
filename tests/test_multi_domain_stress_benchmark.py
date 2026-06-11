from benchmarks.multi_domain_stress_benchmark import build_case, run_stress_case, summarize_group
import random


def test_stress_case_builder_returns_memories():
    rng = random.Random(1)
    name, query, memories = build_case(1, "software_policy", "stale_contradiction", rng)
    assert "software_policy" in name
    assert "current answer" in query
    assert len(memories) >= 5
    assert any(memory.metadata.get("label_stale") for memory in memories)
    assert all("label_confidence" in memory.metadata for memory in memories)


def test_stress_case_can_run():
    rng = random.Random(1)
    name, query, memories = build_case(1, "enterprise_policy", "risky_workaround", rng)
    summary = run_stress_case(name, query, memories, top_k=4)
    assert summary.case_id == name
    assert summary.utility_gain is not None
    assert summary.evidence_confidence_mean > 0.5
    assert summary.pass_fail in {"PASS", "WEAK"}


def test_group_summary_reports_nonpositive_gain():
    rng = random.Random(1)
    rows = []
    for scenario in ["clean_control", "stale_contradiction", "risky_workaround", "ambiguous_mixed"]:
        name, query, memories = build_case(1, "support_knowledge", scenario, rng)
        rows.append(run_stress_case(name, query, memories, top_k=4))
    summary = summarize_group("domain:support_knowledge", rows)
    assert summary.cases == 4
    assert 0 <= summary.pass_rate <= 1
    assert summary.mean_confidence > 0.5
