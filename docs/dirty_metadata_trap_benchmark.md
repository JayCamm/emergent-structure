# Dirty Metadata Trap Benchmark

This is the second-stage smoking-gun benchmark.

The first public evidence-admission benchmark showed that ordinary relevance retrieval can expose related-but-excluded legacy information, but clean metadata and recency filters could also solve those examples.

This benchmark is designed to answer the harder objection:

> Could we solve this with metadata or recency filters?

## Core idea

The benchmark creates a dirty workspace from public-source snippets. It pulls current and legacy public documentation, then creates workspace documents that mimic real messy knowledge stores:

1. **Current authoritative document**
   - Current metadata.
   - Should be retained.

2. **Legacy content mislabeled as current**
   - Current metadata and current year.
   - Body text comes from legacy/removed documentation.
   - Should be excluded.
   - Metadata and recency filters should struggle.

3. **Current warning memo**
   - Current metadata.
   - Mentions legacy terms because it warns users not to treat old guidance as current action guidance.
   - Should be retained.
   - Naive keyword caution filters may falsely block it.

4. **Historical comparison note**
   - Old metadata.
   - Useful when the query asks what changed.
   - Should be retained for history/comparison tasks.
   - Metadata and recency filters may falsely block it.

## Public source families

The current benchmark uses public documentation from:

- Kubernetes: current Pod Security Admission vs removed PodSecurityPolicy.
- Python: current Python 3 `urllib.request` vs legacy Python 2 `urllib2`.
- React: current React Component reference vs legacy React lifecycle documentation.

## Methods compared

- `ordinary_top_k`
- `metadata_status_filter`
- `recency_filter`
- `keyword_caution_filter`
- `persistence_gate:<profile>`

## Metrics

- `excluded_info_exposure_rate`: how often excluded-but-related sources entered context.
- `required_info_retention_rate`: how often required sources were retained.
- `clean_context_rate`: how often required sources were retained while excluded sources were not exposed.
- `total_context_tokens`: approximate context-token count.

## Run

```bash
python benchmarks/dirty_metadata_trap_benchmark.py \
  --profile conservative \
  --top-k 3 \
  --candidate-pool 8 \
  --refresh \
  --out-dir benchmark_results/dirty_metadata_trap
```

## Outputs

```text
benchmark_results/dirty_metadata_trap/source_manifest.csv
benchmark_results/dirty_metadata_trap/workspace_manifest.csv
benchmark_results/dirty_metadata_trap/case_details.csv
benchmark_results/dirty_metadata_trap/gate_audit_log.csv
benchmark_results/dirty_metadata_trap/summary.csv
benchmark_results/dirty_metadata_trap/examples.md
```

## Interpretation

The desired smoking-gun pattern is:

```text
ordinary_top_k: exposes excluded info
metadata_status_filter: exposes mislabeled excluded info or misses useful old history
recency_filter: exposes mislabeled excluded info or misses useful old history
keyword_caution_filter: may avoid some excluded info but falsely blocks warning/history docs
Persistence Gate: low exposure, high required retention, high clean-context rate
```

The benchmark is still controlled. It is not a production proof. Its purpose is to show why relevance, recency, metadata, and keyword filters are not enough when the library is dirty.
