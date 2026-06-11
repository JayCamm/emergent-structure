from persistence_memory import MemoryItem, TaskContext, evaluate_gate_vs_topk, lexical_relevance, rank_by_relevance


def test_lexical_relevance_ranks_matching_item_first():
    items = [
        MemoryItem(id="a", text="banana unrelated note"),
        MemoryItem(id="b", text="persistence memory gate controller"),
    ]
    ranked = rank_by_relevance("memory controller", items)
    assert ranked[0].id == "b"
    assert lexical_relevance("memory controller", ranked[0].text) > 0


def test_benchmark_gate_prevents_risky_relevant_item():
    good = MemoryItem(
        id="good",
        text="current persistence gate controller tests passed",
        context_scope="project",
        risk=0.02,
        harm_score=0.0,
        usefulness_score=0.8,
        burden=0.1,
        metadata={"label_helpful": True},
    )
    bad = MemoryItem(
        id="bad",
        text="old persistence gate controller deprecated failed approach",
        context_scope="project",
        risk=0.9,
        harm_score=0.8,
        usefulness_score=-0.5,
        burden=0.1,
        metadata={"label_risky": True, "label_stale": True},
    )
    result = evaluate_gate_vs_topk(
        [good, bad],
        TaskContext(query="persistence gate controller", context_scope="project", need=0.9, risk_tolerance=0.4),
        top_k=2,
    )
    assert "bad" in result.report.ordinary_top_k_ids
    assert "bad" not in result.report.allowed_ids
    assert result.risky_items_prevented >= 1
