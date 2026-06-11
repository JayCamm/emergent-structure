from persistence_memory import MemoryItem
from persistence_memory.audit import detect_circularity, shuffle_for_blind_review, stable_blind_id


def test_stable_blind_id_is_stable_and_hides_original_id():
    first = stable_blind_id("case", "memory_123")
    second = stable_blind_id("case", "memory_123")
    assert first == second
    assert "memory_123" not in first
    assert len(first) == 12


def test_detect_circularity_flags_self_reference():
    items = [MemoryItem(id="m", text="Persistence Gate benchmark summary risk_prevented", source="external_benchmark:sample")]
    warnings = detect_circularity(items)
    assert warnings
    assert {warning.warning_type for warning in warnings} >= {"system_self_reference", "benchmark_generated"}


def test_shuffle_for_blind_review_preserves_rows():
    rows = [{"id": str(idx)} for idx in range(5)]
    shuffled = shuffle_for_blind_review(rows, seed=1)
    assert sorted(row["id"] for row in shuffled) == ["0", "1", "2", "3", "4"]
