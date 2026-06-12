# Persistence Gate Product Roadmap

Persistence Gate is an evidence-admission layer for AI systems. It sits between retrieval and generation, then decides which retrieved evidence may influence the answer.

## MVP components

1. API wrapper
   - Input: query plus retrieved items.
   - Output: allowed context, blocked items, warnings, and audit log.

2. RAG middleware
   - Wrap a retriever and optional generator.
   - Flow: query -> retriever -> gate -> allowed context -> generator.

3. Evidence roles
   - current_guidance
   - legacy_instruction
   - warning_against_legacy
   - historical_context
   - audit_background
   - uncertain

4. Query intent
   - current_action
   - history_comparison
   - audit_review
   - training_background
   - general_lookup

5. Audit logs
   - Show score, decision, role, risk, usefulness, and reasons.

6. Report export
   - CSV for analysis.
   - Markdown for review.
   - HTML for presentation.

7. Benchmark runner
   - Run dirty metadata tests.
   - Run bias audit tests.
   - Save summary files.

## Pilot metrics

- Bad information exposure rate
- Required information retention rate
- Clean context rate
- Context size

## MVP success criteria

- Works with plain Python dictionaries.
- Requires no external service to run locally.
- Creates a clear audit trail.
- Can wrap any retriever that returns text candidates.
- Can export a readable review report.
