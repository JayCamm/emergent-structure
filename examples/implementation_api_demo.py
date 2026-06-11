from persistence_memory.api import PersistenceGate


def main() -> None:
    retrieved = [
        {
            "id": "old_workaround",
            "text": "Old temporary workaround: disable safeguards and use the emergency bypass.",
            "source": "demo://old-workaround",
            "risk": 0.88,
            "harm_score": 0.82,
            "usefulness_score": -0.25,
            "label_risky": True,
            "label_stale": True,
        },
        {
            "id": "current_runbook",
            "text": "Current runbook: do not disable safeguards. Use the validated low-risk recovery path.",
            "source": "demo://current-runbook",
            "risk": 0.04,
            "harm_score": 0.0,
            "usefulness_score": 0.90,
            "label_helpful": True,
        },
        {
            "id": "context",
            "text": "Current task context: prefer validated, current, low-risk evidence.",
            "source": "demo://context",
            "risk": 0.05,
            "usefulness_score": 0.55,
            "label_helpful": True,
        },
    ]

    gate = PersistenceGate(profile="balanced", top_k=3)
    result = gate.filter("Which runbook guidance should influence the current incident answer?", retrieved)

    print("Allowed IDs:", result.allowed_ids)
    print("Blocked IDs:", result.blocked_ids)
    print("Warnings:", result.warnings)
    print("\nAllowed context:\n")
    print(result.allowed_context)
    print("\nAudit log:")
    for row in result.audit_log:
        print(row)


if __name__ == "__main__":
    main()
