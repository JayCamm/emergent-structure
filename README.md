# Persistence-Aware Memory

A prototype memory-control layer that sits between retrieval and downstream decision-making.

It does not replace search, embeddings, databases, or LLMs. It controls which retrieved information is allowed to influence a decision.

Core loop:

```text
retrieve -> score -> gate -> use -> feedback -> update
```

This repository starts as a small Python package plus evaluation harness for testing persistence-aware retrieval against ordinary retrieval on real or semi-real corpora.

## Current status

Research prototype. Not production software yet.

Supported claim so far: matched synthetic simulations show persistence-aware v2 beats ordinary retrieval on net utility by reducing harmful retrievals and burden while maintaining useful retrieval. The remaining design problem is abstention-aware retrieval: deciding when memory should not be used at all.

## Package layout

```text
src/persistence_memory/
  models.py        # data models and states
  scorer.py        # persistence scoring
  controller.py    # retrieve-score-gate-feedback loop
  store.py         # in-memory store
  evaluation.py    # metrics
examples/
  github_real_data_demo.py
  sample_corpus.jsonl
tests/
  test_controller.py
```

## Install

```bash
pip install -e .
pytest
```

## Quick demo

```bash
python examples/github_real_data_demo.py --sample
```

## Design principle

Data should not merely be retrieved because it is relevant. It should be allowed to influence the system only when its expected current value exceeds its risk, burden, and abstention baseline.
