# Role-Intent Gating

This refinement addresses the main weakness found in the dirty-metadata/bias-audit benchmarks: a simple usefulness-only filter can sometimes match Persistence Gate when all useful documents are good and all low-usefulness documents are bad.

The fix is to separate general usefulness from task-specific permission to influence.

## New concepts

### Query intent

What kind of question is being asked?

- `current_action`: user wants current operational guidance.
- `history_comparison`: user wants to know what changed or compare old and current guidance.
- `audit_review`: user wants audit/background evidence.
- `training_background`: user wants explanatory/training context.
- `general_lookup`: fallback intent.

### Evidence role

What role does a retrieved item play?

- `current_guidance`: current instruction or approved guidance.
- `legacy_instruction`: old instruction that should not guide current action.
- `warning_against_legacy`: current evidence warning users not to follow old guidance.
- `historical_context`: useful history/comparison evidence.
- `audit_background`: audit/background material.
- `uncertain`: fallback role.

## Why this matters

A document can be useful but still not allowed to influence a specific answer.

Example:

- A legacy instruction can be useful for history.
- The same legacy instruction can be dangerous for a current-action answer.
- A warning document can mention risky old terms but still be useful current evidence.

So the gate now asks:

> Is this evidence useful for this task, in this role, with acceptable risk?

## API usage

```python
from persistence_memory.api import PersistenceGate

gate = PersistenceGate(profile="conservative", top_k=3)
result = gate.filter(
    "What should guide the current process now?",
    retrieved_items=[
        {
            "id": "legacy_high_usefulness",
            "text": "Legacy instruction: use the old shortcut procedure.",
            "relevance": 1.0,
            "risk": 0.70,
            "harm_score": 0.45,
            "usefulness_score": 0.95,
            "evidence_role": "legacy_instruction",
        },
        {
            "id": "current_guidance",
            "text": "Current guidance: use the approved current process.",
            "relevance": 0.82,
            "risk": 0.03,
            "harm_score": 0.0,
            "usefulness_score": 0.85,
            "evidence_role": "current_guidance",
        },
    ],
    query_intent="current_action",
)
```

Expected behavior:

- `legacy_high_usefulness` is blocked even though it has high usefulness.
- `current_guidance` is allowed.

## Interpretation

This is not automatic perfect understanding. The role and intent values are governance signals that can come from metadata, rules, classifier output, human review, or future feedback learning.

The goal is to beat single-signal filters by combining:

- relevance,
- usefulness,
- risk,
- harm,
- validity,
- query intent,
- evidence role.
