from persistence_memory import FeedbackEvent, InMemoryStore, MemoryController, MemoryItem, TaskContext
from persistence_memory.models import MemoryState


def test_controller_allows_validated_and_quarantines_harmful():
    good = MemoryItem(
        id="good",
        text="Validated useful project memory.",
        context_scope="project",
        relevance=0.95,
        confidence=0.9,
        importance=0.8,
        burden=0.05,
        risk=0.05,
        usefulness_score=0.7,
        harm_score=0.0,
    )
    bad = MemoryItem(
        id="bad",
        text="Relevant but harmful stale memory.",
        context_scope="project",
        relevance=0.95,
        confidence=0.4,
        importance=0.8,
        burden=0.4,
        risk=0.8,
        usefulness_score=-0.4,
        harm_score=0.8,
    )

    controller = MemoryController(InMemoryStore([good, bad]))
    task = TaskContext(query="project", context_scope="project", need=0.8, risk_tolerance=0.5)
    scored = controller.retrieve_and_gate(task, top_k=3)

    ids = [item.memory.id for item in scored]
    assert "good" in ids
    assert "bad" not in ids
    assert controller.store.get("bad").state == MemoryState.QUARANTINED


def test_feedback_validates_helpful_memory():
    item = MemoryItem(id="m", text="useful", relevance=0.9, usefulness_score=0.5)
    controller = MemoryController(InMemoryStore([item]))

    for _ in range(3):
        controller.apply_feedback(FeedbackEvent(memory_id="m", outcome="helped", helped=True))

    assert controller.store.get("m").state == MemoryState.VALIDATED
    assert controller.store.get("m").help_count == 3


def test_feedback_quarantines_harmful_memory():
    item = MemoryItem(id="m", text="harmful", relevance=0.9, usefulness_score=0.1)
    controller = MemoryController(InMemoryStore([item]))

    controller.apply_feedback(FeedbackEvent(memory_id="m", outcome="bad", harmed=True))
    controller.apply_feedback(FeedbackEvent(memory_id="m", outcome="bad_again", harmed=True))

    assert controller.store.get("m").state == MemoryState.QUARANTINED
    assert controller.store.get("m").harm_count == 2
