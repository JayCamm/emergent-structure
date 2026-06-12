# Installable Usage Guide

Persistence Gate can now be installed as a local Python package and used as a command-line evidence filter.

## Install from source

```bash
git clone https://github.com/JayCamm/persistence-gate.git
cd persistence-gate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q tests/test_role_intent_gating.py tests/test_product_mvp_wrappers.py tests/test_cli.py
```

## CLI usage

```bash
persistence-gate filter examples/cli_input_example.json --out-dir report
```

The command writes:

```text
report/result.json
report/allowed_context.txt
report/audit.csv
report/report.md
report/report.html
```

## Input JSON format

```json
{
  "query": "What should guide the current process now?",
  "profile": "conservative",
  "top_k": 3,
  "query_intent": "current_action",
  "retrieved_items": [
    {
      "id": "current_guidance",
      "text": "Current guidance: use the approved process.",
      "relevance": 0.9,
      "risk": 0.03,
      "harm_score": 0.0,
      "usefulness_score": 0.85,
      "evidence_role": "current_guidance"
    }
  ]
}
```

## Python middleware usage

```python
from persistence_memory.api import PersistenceGate
from persistence_memory.middleware import EvidenceAdmissionMiddleware


def retriever(query):
    return [
        {
            "id": "current",
            "text": "Current guidance: use the approved process.",
            "relevance": 0.9,
            "risk": 0.03,
            "usefulness_score": 0.9,
            "evidence_role": "current_guidance",
        }
    ]


def responder(query, allowed_context, gate_result):
    return f"Answer using:\n{allowed_context}"

middleware = EvidenceAdmissionMiddleware(
    retriever=retriever,
    responder=responder,
    gate=PersistenceGate(profile="conservative", top_k=3),
)

result = middleware.run("What should guide the current process now?", query_intent="current_action")
print(result.answer)
print(result.gate_result.audit_log)
```

## Product benchmark suite

```bash
python benchmarks/run_product_benchmarks.py --profile conservative --refresh
```

This runs the dirty metadata trap and bias audit benchmarks and writes outputs under `benchmark_results/product_suite`.
