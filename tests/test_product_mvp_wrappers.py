from pathlib import Path

from persistence_memory.api import PersistenceGate
from persistence_memory.middleware import EvidenceAdmissionMiddleware
from persistence_memory.reports import markdown_report, write_audit_csv, write_html_report, write_markdown_report


def test_middleware_filters_context_before_responder():
    def retriever(query):
        return [
            {
                "id": "legacy",
                "text": "Legacy instruction: use the old shortcut.",
                "relevance": 1.0,
                "risk": 0.7,
                "harm_score": 0.45,
                "usefulness_score": 0.95,
                "evidence_role": "legacy_instruction",
            },
            {
                "id": "current",
                "text": "Current guidance: use the approved path.",
                "relevance": 0.9,
                "risk": 0.03,
                "harm_score": 0.0,
                "usefulness_score": 0.9,
                "evidence_role": "current_guidance",
            },
        ]

    def responder(query, allowed_context, gate_result):
        assert "old shortcut" not in allowed_context
        assert "approved path" in allowed_context
        return "Use the approved path."

    middleware = EvidenceAdmissionMiddleware(retriever=retriever, responder=responder, gate=PersistenceGate(profile="conservative", top_k=3))
    result = middleware.run("What should we do now?", query_intent="current_action")

    assert result.answer == "Use the approved path."
    assert result.gate_result.allowed_ids == ["current"]
    assert "legacy" in result.gate_result.blocked_ids


def test_report_exports(tmp_path: Path):
    gate = PersistenceGate(profile="conservative", top_k=2)
    result = gate.filter(
        "What should guide the current process now?",
        [
            {
                "id": "current",
                "text": "Current guidance: use the approved path.",
                "relevance": 1.0,
                "risk": 0.01,
                "usefulness_score": 0.9,
                "evidence_role": "current_guidance",
            }
        ],
        query_intent="current_action",
    )

    md = markdown_report(result)
    assert "Allowed items" in md
    csv_path = write_audit_csv(result, tmp_path / "audit.csv")
    md_path = write_markdown_report(result, tmp_path / "report.md")
    html_path = write_html_report(result, tmp_path / "report.html")
    assert csv_path.exists()
    assert md_path.exists()
    assert html_path.exists()
