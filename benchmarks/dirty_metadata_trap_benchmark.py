from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from persistence_memory.api import PersistenceGate  # noqa: E402


@dataclass(frozen=True)
class SourcePair:
    family: str
    current_url: str
    legacy_url: str
    current_title: str
    legacy_title: str
    current_terms: tuple[str, ...]
    legacy_terms: tuple[str, ...]


@dataclass(frozen=True)
class CaseSpec:
    id: str
    family: str
    query: str
    required_docs: tuple[str, ...]
    excluded_docs: tuple[str, ...]
    notes: str


SOURCE_PAIRS = (
    SourcePair(
        family="kubernetes",
        current_url="https://kubernetes.io/docs/concepts/security/pod-security-admission/",
        legacy_url="https://kubernetes.io/docs/concepts/security/pod-security-policy/",
        current_title="Current Kubernetes Pod Security Admission guidance",
        legacy_title="Removed Kubernetes PodSecurityPolicy guidance",
        current_terms=("pod security admission", "enforce", "audit", "warn"),
        legacy_terms=("podsecuritypolicy", "deprecated", "removed"),
    ),
    SourcePair(
        family="python",
        current_url="https://docs.python.org/3/library/urllib.request.html",
        legacy_url="https://docs.python.org/2.7/library/urllib2.html",
        current_title="Current Python 3 urllib.request guidance",
        legacy_title="Legacy Python 2 urllib2 guidance",
        current_terms=("urllib.request", "urlopen", "python 3"),
        legacy_terms=("urllib2", "python 2", "legacy"),
    ),
    SourcePair(
        family="react",
        current_url="https://react.dev/reference/react/Component",
        legacy_url="https://legacy.reactjs.org/docs/react-component.html",
        current_title="Current React Component guidance",
        legacy_title="Legacy React lifecycle guidance",
        current_terms=("component", "react", "effects"),
        legacy_terms=("legacy", "unsafe", "componentwillmount"),
    ),
)

CASE_SPECS = (
    CaseSpec(
        id="kubernetes_current_action_dirty_metadata",
        family="kubernetes",
        query="What should guide current Kubernetes pod security enforcement?",
        required_docs=("kubernetes_current_authoritative", "kubernetes_current_warning"),
        excluded_docs=("kubernetes_legacy_mislabeled_current",),
        notes="Legacy content is mislabeled current, so metadata and recency filters should not be enough.",
    ),
    CaseSpec(
        id="kubernetes_history_required",
        family="kubernetes",
        query="What changed from the old Kubernetes pod security approach to the current approach?",
        required_docs=("kubernetes_historical_comparison", "kubernetes_current_authoritative"),
        excluded_docs=("kubernetes_legacy_mislabeled_current",),
        notes="A useful historical document is old by metadata, so simple recency/status filtering may falsely block it.",
    ),
    CaseSpec(
        id="python_current_action_dirty_metadata",
        family="python",
        query="What should guide current Python 3 URL opening code?",
        required_docs=("python_current_authoritative", "python_current_warning"),
        excluded_docs=("python_legacy_mislabeled_current",),
        notes="Python 2 guidance is mislabeled current while current warning text mentions legacy names.",
    ),
    CaseSpec(
        id="python_history_required",
        family="python",
        query="What changed from Python 2 URL opening guidance to current Python 3 guidance?",
        required_docs=("python_historical_comparison", "python_current_authoritative"),
        excluded_docs=("python_legacy_mislabeled_current",),
        notes="History is required for a comparison query, even though it is old.",
    ),
    CaseSpec(
        id="react_current_action_dirty_metadata",
        family="react",
        query="What should guide current React component side effect handling?",
        required_docs=("react_current_authoritative", "react_current_warning"),
        excluded_docs=("react_legacy_mislabeled_current",),
        notes="Legacy lifecycle material is mislabeled current; a warning memo should not be blocked just because it mentions old lifecycle names.",
    ),
    CaseSpec(
        id="react_history_required",
        family="react",
        query="What changed from older React lifecycle guidance to current React component guidance?",
        required_docs=("react_historical_comparison", "react_current_authoritative"),
        excluded_docs=("react_legacy_mislabeled_current",),
        notes="The old material is relevant as history, but not as current action guidance.",
    ),
)


class VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return normalize_ws(" ".join(self.parts))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_visible_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": "PersistenceGateDirtyMetadataBenchmark/0.1"})
    with urlopen(req, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="ignore")
    parser = VisibleTextExtractor()
    parser.feed(html)
    return parser.text()


def snippet_around_terms(text: str, terms: tuple[str, ...], max_chars: int = 1800) -> str:
    lower = text.lower()
    best = 0
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            best = max(0, idx - max_chars // 3)
            break
    return normalize_ws(text[best: best + max_chars])


def fallback_text(pair: SourcePair, kind: str) -> str:
    if kind == "current":
        return f"{pair.current_title}. Current guidance for {pair.family}. Use the current documented approach and avoid relying on legacy behavior."
    return f"{pair.legacy_title}. Legacy guidance for {pair.family}. This material is historically relevant but should not be treated as current action guidance."


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-\.]{2,}", text.lower())
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "which", "should",
        "how", "what", "where", "when", "why", "current", "modern", "code", "using",
        "use", "uses", "used", "can", "will", "are", "you", "your", "their", "there",
        "documentation", "docs", "page", "reference", "guidance", "approach",
    }
    return [token for token in tokens if token not in stop]


def simple_relevance(query: str, text: str) -> float:
    q_terms = tokenize(query)
    if not q_terms:
        return 0.0
    counts = Counter(tokenize(text))
    if not counts:
        return 0.0
    numerator = sum(counts[t] for t in q_terms)
    denom = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return numerator / denom


def approx_tokens(text: str) -> int:
    return max(1, round(len(text.split()) * 1.33))


def source_cache(pair: SourcePair, cache_dir: Path, refresh: bool) -> tuple[str, str, list[dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    texts = {}
    for key, url in {"current": pair.current_url, "legacy": pair.legacy_url}.items():
        cache_file = cache_dir / f"{pair.family}_{key}.txt"
        error = ""
        if refresh or not cache_file.exists():
            try:
                text = fetch_visible_text(url)
                cache_file.write_text(text, encoding="utf-8")
            except Exception as exc:
                error = repr(exc)
                text = ""
        else:
            text = cache_file.read_text(encoding="utf-8", errors="ignore")
        if not text and cache_file.exists():
            text = cache_file.read_text(encoding="utf-8", errors="ignore")
        if not text:
            text = fallback_text(pair, key)
        texts[key] = text
        manifest.append({
            "family": pair.family,
            "kind": key,
            "url": url,
            "fetch_error": error,
            "text_chars": len(text),
        })
    return texts["current"], texts["legacy"], manifest


def make_dirty_workspace(cache_dir: Path, refresh: bool) -> tuple[list[dict], list[dict]]:
    docs: list[dict] = []
    manifest: list[dict] = []
    for pair in SOURCE_PAIRS:
        current_text, legacy_text, source_manifest = source_cache(pair, cache_dir, refresh)
        manifest.extend(source_manifest)
        current_snippet = snippet_around_terms(current_text, pair.current_terms)
        legacy_snippet = snippet_around_terms(legacy_text, pair.legacy_terms)

        docs.append({
            "id": f"{pair.family}_current_authoritative",
            "doc_id": f"{pair.family}_current_authoritative",
            "source": pair.current_url,
            "text": f"CURRENT AUTHORITATIVE SOURCE. {pair.current_title}. {current_snippet}",
            "status": "current",
            "year": 2026,
            "family": pair.family,
            "role": "required",
            "risk": 0.04,
            "harm_score": 0.0,
            "usefulness_score": 0.92,
        })
        docs.append({
            "id": f"{pair.family}_legacy_mislabeled_current",
            "doc_id": f"{pair.family}_legacy_mislabeled_current",
            "source": pair.legacy_url,
            "text": f"CURRENT QUICK REFERENCE COPY. {pair.legacy_title}. This copied page is marked current in the workspace, but the body comes from legacy material. {legacy_snippet}",
            "status": "current",
            "year": 2026,
            "family": pair.family,
            "role": "excluded",
            "risk": 0.78,
            "harm_score": 0.72,
            "usefulness_score": 0.08,
        })
        docs.append({
            "id": f"{pair.family}_current_warning",
            "doc_id": f"{pair.family}_current_warning",
            "source": f"synthetic-warning-derived-from-{pair.current_url}",
            "text": f"CURRENT WARNING MEMO. For current {pair.family} work, do not treat the old legacy source as action guidance. It is okay to mention it only to explain what changed. Current guidance should come from: {current_snippet}. Legacy reference being warned about: {legacy_snippet[:700]}",
            "status": "current",
            "year": 2026,
            "family": pair.family,
            "role": "required",
            "risk": 0.05,
            "harm_score": 0.0,
            "usefulness_score": 0.86,
        })
        docs.append({
            "id": f"{pair.family}_historical_comparison",
            "doc_id": f"{pair.family}_historical_comparison",
            "source": f"historical-comparison-derived-from-{pair.legacy_url}",
            "text": f"HISTORICAL COMPARISON NOTE. This is old by metadata, but it is useful when the user asks what changed. Legacy source summary: {legacy_snippet}. Current source summary: {current_snippet}",
            "status": "legacy",
            "year": 2020,
            "family": pair.family,
            "role": "required_history",
            "risk": 0.06,
            "harm_score": 0.0,
            "usefulness_score": 0.84,
        })
    return docs, manifest


def retrieve_candidates(query: str, docs: list[dict], candidate_pool: int) -> list[dict]:
    rows = []
    for doc in docs:
        relevance_raw = simple_relevance(query, doc["text"])
        if relevance_raw <= 0:
            continue
        row = dict(doc)
        row["relevance_raw"] = relevance_raw
        rows.append(row)
    rows.sort(key=lambda row: row["relevance_raw"], reverse=True)
    rows = rows[:candidate_pool]
    max_score = max((row["relevance_raw"] for row in rows), default=1.0)
    for row in rows:
        row["relevance"] = round(row["relevance_raw"] / max_score, 6) if max_score else 0.0
        row["metadata"] = {
            "doc_id": row["doc_id"],
            "status": row["status"],
            "year": row["year"],
            "family": row["family"],
            "role": row["role"],
        }
    return rows


def top_k(rows: list[dict], k: int) -> list[dict]:
    return sorted(rows, key=lambda row: row["relevance"], reverse=True)[:k]


def metadata_status_filter(rows: list[dict], k: int) -> list[dict]:
    return top_k([row for row in rows if row["status"] == "current"], k)


def recency_filter(rows: list[dict], k: int, min_year: int = 2024) -> list[dict]:
    return top_k([row for row in rows if int(row["year"]) >= min_year], k)


def keyword_caution_filter(rows: list[dict], k: int) -> list[dict]:
    flagged = ("legacy", "removed", "deprecated", "unsafe", "old")
    kept = [row for row in rows if not any(word in row["text"].lower() for word in flagged)]
    return top_k(kept, k)


def selected_ids(rows: list[dict]) -> set[str]:
    return {row["doc_id"] for row in rows}


def evaluate_selection(case: CaseSpec, rows: list[dict]) -> dict:
    ids = selected_ids(rows)
    required = set(case.required_docs)
    excluded = set(case.excluded_docs)
    exposed = ids & excluded
    missing = required - ids
    retained = not missing
    clean = retained and not exposed
    return {
        "selected_doc_ids": ";".join(sorted(ids)),
        "excluded_doc_ids_exposed": ";".join(sorted(exposed)),
        "required_doc_ids_missing": ";".join(sorted(missing)),
        "excluded_info_exposed": int(bool(exposed)),
        "required_info_retained": int(retained),
        "clean_context": int(clean),
        "context_tokens": sum(approx_tokens(row["text"]) for row in rows),
    }


def run_case(case: CaseSpec, docs: list[dict], profile: str, top_k_n: int, candidate_pool: int) -> tuple[list[dict], list[dict]]:
    family_docs = [doc for doc in docs if doc["family"] == case.family]
    candidates = retrieve_candidates(case.query, family_docs, candidate_pool)
    selections = {
        "ordinary_top_k": top_k(candidates, top_k_n),
        "metadata_status_filter": metadata_status_filter(candidates, top_k_n),
        "recency_filter": recency_filter(candidates, top_k_n),
        "keyword_caution_filter": keyword_caution_filter(candidates, top_k_n),
    }

    gate = PersistenceGate(profile=profile, top_k=top_k_n, context_scope="global")
    result = gate.filter(query=case.query, retrieved_items=candidates, context_scope="global")
    selections[f"persistence_gate:{profile}"] = [
        {
            "id": item.id,
            "doc_id": item.metadata.get("doc_id", item.id),
            "text": item.text,
            "source": item.source,
            "metadata": item.metadata,
            "relevance": item.relevance,
            "risk": item.risk,
            "harm_score": item.harm_score,
            "usefulness_score": item.usefulness_score,
        }
        for item in result.allowed_items
    ]

    details = []
    for method, rows in selections.items():
        details.append({
            "case_id": case.id,
            "family": case.family,
            "query": case.query,
            "method": method,
            "required_doc_ids": ";".join(case.required_docs),
            "excluded_doc_ids": ";".join(case.excluded_docs),
            **evaluate_selection(case, rows),
            "notes": case.notes,
        })

    audit_rows = []
    for row in result.audit_log:
        audit_rows.append({
            "case_id": case.id,
            "family": case.family,
            "query": case.query,
            "profile": profile,
            **row,
            "doc_id": row["id"].split("::")[0],
        })
    return details, audit_rows


def summarize(details: list[dict]) -> list[dict]:
    summary = []
    for method in sorted({row["method"] for row in details}):
        rows = [row for row in details if row["method"] == method]
        n = len(rows)
        exposed = sum(int(row["excluded_info_exposed"]) for row in rows)
        retained = sum(int(row["required_info_retained"]) for row in rows)
        clean = sum(int(row["clean_context"]) for row in rows)
        tokens = sum(int(row["context_tokens"]) for row in rows)
        summary.append({
            "method": method,
            "cases": n,
            "excluded_info_exposed_cases": exposed,
            "excluded_info_exposure_rate": round(exposed / n, 4) if n else 0.0,
            "required_info_retained_cases": retained,
            "required_info_retention_rate": round(retained / n, 4) if n else 0.0,
            "clean_context_cases": clean,
            "clean_context_rate": round(clean / n, 4) if n else 0.0,
            "total_context_tokens": tokens,
        })
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_examples(path: Path, details: list[dict], audit_rows: list[dict]) -> None:
    lines = [
        "# Dirty Metadata Trap Benchmark Examples",
        "",
        "This benchmark mixes public-source snippets into dirty workspace documents.",
        "The key traps are mislabeled legacy content, useful historical notes, and current warning notes that mention legacy terms.",
        "",
    ]
    for case in CASE_SPECS:
        lines.extend([f"## {case.id}", "", f"Query: `{case.query}`", ""])
        for row in [r for r in details if r["case_id"] == case.id]:
            lines.append(
                f"- **{row['method']}**: exposed={row['excluded_info_exposed']}, "
                f"retained={row['required_info_retained']}, clean={row['clean_context']}, "
                f"missing={row['required_doc_ids_missing']}, selected={row['selected_doc_ids']}"
            )
        blocked = [r for r in audit_rows if r["case_id"] == case.id and r["bucket"] == "blocked"]
        if blocked:
            lines.append("")
            lines.append("Blocked by Persistence Gate:")
            for row in blocked[:8]:
                lines.append(f"- `{row['id']}` decision={row['decision']} reasons={row['reasons']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dirty metadata trap benchmark for Persistence Gate.")
    parser.add_argument("--profile", default="conservative", choices=["permissive", "balanced", "conservative"])
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-pool", type=int, default=8)
    parser.add_argument("--out-dir", default="benchmark_results/dirty_metadata_trap")
    parser.add_argument("--cache-dir", default="benchmark_data/dirty_metadata_public_cache")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs, source_manifest = make_dirty_workspace(Path(args.cache_dir), args.refresh)
    workspace_manifest = [
        {
            "doc_id": doc["doc_id"],
            "family": doc["family"],
            "status": doc["status"],
            "year": doc["year"],
            "role": doc["role"],
            "risk": doc["risk"],
            "harm_score": doc["harm_score"],
            "usefulness_score": doc["usefulness_score"],
            "source": doc["source"],
            "text_preview": doc["text"][:240],
        }
        for doc in docs
    ]

    details: list[dict] = []
    audit_rows: list[dict] = []
    for case in CASE_SPECS:
        case_details, case_audit = run_case(case, docs, args.profile, args.top_k, args.candidate_pool)
        details.extend(case_details)
        audit_rows.extend(case_audit)

    summary = summarize(details)
    write_csv(out_dir / "source_manifest.csv", source_manifest)
    write_csv(out_dir / "workspace_manifest.csv", workspace_manifest)
    write_csv(out_dir / "case_details.csv", details)
    write_csv(out_dir / "gate_audit_log.csv", audit_rows)
    write_csv(out_dir / "summary.csv", summary)
    write_examples(out_dir / "examples.md", details, audit_rows)

    print("\nDirty Metadata Trap Benchmark")
    print(f"Profile: {args.profile} | top_k={args.top_k} | candidate_pool={args.candidate_pool}")
    print(f"Workspace docs: {len(docs)}")
    print(f"Output: {out_dir}")
    print("\nmethod,exposure_rate,retention_rate,clean_context_rate,total_context_tokens")
    for row in summary:
        print(
            f"{row['method']},"
            f"{row['excluded_info_exposure_rate']},"
            f"{row['required_info_retention_rate']},"
            f"{row['clean_context_rate']},"
            f"{row['total_context_tokens']}"
        )


if __name__ == "__main__":
    main()
