from examples.rag_adapter_demo import deterministic_answer, fake_retriever
from persistence_memory.api import PersistenceGate


def test_rag_demo_blocks_old_workaround_and_changes_context():
    query = "How should we handle the current payment service failure?"
    retrieved = fake_retriever(query)
    assert retrieved[0]["id"] == "old_workaround"

    ordinary_context = "\n\n".join(item["text"] for item in retrieved)
    assert "disable safeguards" in ordinary_context

    gate = PersistenceGate(profile="balanced", top_k=4)
    result = gate.filter(query, retrieved)

    assert "old_workaround" in result.blocked_ids
    assert "current_runbook" in result.allowed_ids
    assert "postmortem_update" in result.allowed_ids
    assert "disable safeguards and use the emergency bypass" not in result.allowed_context
    assert "do not disable safeguards" in result.allowed_context


def test_deterministic_answer_prefers_gated_safe_context():
    query = "How should we handle the current payment service failure?"
    retrieved = fake_retriever(query)
    gate = PersistenceGate(profile="balanced", top_k=4)
    result = gate.filter(query, retrieved)

    answer = deterministic_answer(result.allowed_context)
    assert "Do not disable safeguards" in answer
