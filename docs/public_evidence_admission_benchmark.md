# Public Evidence Admission Benchmark

This benchmark is designed to be the simple side-by-side test for Persistence Gate.

It uses public documentation pages where legacy or removed guidance remains highly related to a current query. The goal is to test whether a normal relevance-only retrieval pipeline sends related-but-excluded sources into context, and whether Persistence Gate keeps the required current source while blocking the excluded source.

## What it tests

For each case, the benchmark defines:

- a user query,
- one or more required current source documents,
- one or more excluded legacy/removed source documents,
- public URLs used as the document library.

It compares:

- `ordinary_top_k`,
- `metadata_status_filter`,
- `recency_filter`,
- `persistence_gate:<profile>`.

## Metrics

The benchmark writes these metrics to `summary.csv`:

- `excluded_info_exposure_rate`: how often excluded-but-related sources entered context.
- `required_info_retention_rate`: how often required current sources stayed in context.
- `clean_context_rate`: how often context retained required sources while exposing no excluded sources.
- `total_context_tokens`: approximate context-token count.

The strongest result is high retention, low exposure, and high clean-context rate.

## Run

```bash
python benchmarks/public_evidence_admission_benchmark.py \
  --profile conservative \
  --top-k 4 \
  --candidate-pool 12 \
  --refresh \
  --out-dir benchmark_results/public_evidence_admission
```

The benchmark fetches public pages and caches their visible text in `benchmark_data/public_web_cache`.

Use `--refresh` to re-fetch. Omit `--refresh` to reuse cached pages.

## Outputs

```text
benchmark_results/public_evidence_admission/source_manifest.csv
benchmark_results/public_evidence_admission/case_details.csv
benchmark_results/public_evidence_admission/gate_audit_log.csv
benchmark_results/public_evidence_admission/summary.csv
benchmark_results/public_evidence_admission/examples.md
```

## Interpretation

This is not meant to prove every production use case. It is meant to show the core mechanism on public data:

> Relevant does not mean allowed to influence.

A source can be highly related to a query and still be the wrong source to send into the model context for current guidance.
