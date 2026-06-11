from persistence_memory.api import PersistenceGate
from persistence_memory.models import MemoryItem


def test_filter_accepts_dict_items_and_blocks_risky_item():
    gate = PersistenceGate(profile="balanced", top_k=3)
    result = gate.filter(
        "Which current runbook should influence the answer?",
        [
            {
                "id": "risky_old",
                "text": "Old workaround: disable safeguards and use emergency bypass.",
                "risk": 0.9,
                "harm_score": 0.8,
                "usefulness_score": -0.2,
                "label_risky": True,
                "label_stale": True,
            },
            {
                "id": "safe_new",
                "text": "Current runbook: keep safeguards enabled and use validated recovery path.",
                "risk": 0.03,
                "usefulness_score": 0.9,
                "label_helpful": True,
            },
        ],
    )
    assert "safe_new" in result.allowed_ids
    assert "risky_old" in result.blocked_ids
    assert result.profile == "balanced"
    assert result.audit_log
    assert "safe_new" in result.allowed_context


def test_filter_accepts_memory_items():
    gate = PersistenceGate(profile="conservative", top_k=2)
    item = MemoryItem(
        id="clean",
        text="Current validated policy.",
        source="test",
        risk=0.01,
        usefulness_score=0.9,
        metadata={"label_helpful": True},
    )
    result = gate.filter("Which policy is current?", [item])
    assert result.allowed_ids == ["clean"]
    assert result.blocked_ids == []


def test_unknown_item_shape_raises():
    gate = PersistenceGate()
    try:
        gate.filter("test", [{"id": "missing_text"}])
    except ValueError as exc:
        assert "text" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
