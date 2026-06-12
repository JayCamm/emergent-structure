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
class PublicDoc:
    id: str
    url: str
    title: str
    status: str
    family: str
    role: str
    year: int
    risk: float
    usefulness: float
    notes: str


@dataclass(frozen=True)
class PublicCase:
    id: str
    query: str
    required_docs: tuple[str, ...]
    excluded_docs: tuple[str, ...]
    notes: str


PUBLIC_DOCS = (
    PublicDoc(
        id="k8s_pod_security_policy_removed",
        url="https://kubernetes.io/docs/concepts/security/pod-security-policy/",
        title="Kubernetes PodSecurityPolicy removed feature",
        status="removed",
        family="kubernetes",
        role="exclude",
        year=2022,
        risk=0.72,
        usefulness=0.10,
        notes="Official Kubernetes page for a removed feature.",
    ),
    PublicDoc(
        id="k8s_pod_security_admission_current",
        url="https://kubernetes.io/docs/concepts/security/pod-security-admission/",
        title="Kubernetes Pod Security Admission current feature",
        status="current",
        family="kubernetes",
        role="require",
        year=2026,
        risk=0.04,
        usefulness=0.92,
        notes="Official Kubernetes page for current Pod Security Admission guidance.",
    ),
    PublicDoc(
        id="python2_urllib2_legacy",
        url="https://docs.python.org/2.7/library/urllib2.html",
        title="Python 2.7 urllib2 legacy documentation",
        status="legacy",
        family="python",
        role="exclude",
        year=2020,
        risk=0.58,
        usefulness=0.12,
        notes="Legacy Python 2 documentation that is related to URL opening but not current Python 3 guidance.",
    ),
    PublicDoc(
        id="python3_urllib_request_current",
        url="https://docs.python.org/3/library/urllib.request.html",
        title="Python 3 urllib.request current documentation",
        status="current",
        family="python",
        role="require",
        year=2026,
        risk=0.04,
        usefulness=0.90,
        notes="Current Python 3 documentation for urllib.request.",
    ),
    PublicDoc(
        id="react_legacy_lifecycle",
        url="https://legacy.reactjs.org/docs/react-component.html",
        title="Legacy React component lifecycle documentation",
        status="legacy",
        family="react",
        role="exclude",
        year=2020,
        risk=0.42,
        usefulness=0.20,
        notes="Legacy React lifecycle page, useful as history but not ideal as current guidance.",
    ),
    PublicDoc(
        id="react_current_component_guidance",
        url="https://react.dev/reference/react/Component",
        title="Current React Component reference",
        status="current",
        family="react",
        role="require",
        year=2026,
        risk=0.06,
        usefulness=0.88,
        notes="Current React component reference.",
    ),
)

PUBLIC_CASES = (
    PublicCase(
        id="kubernetes_current_pod_security",
        query="How should I enforce pod security restrictions on a current Kubernetes cluster?",
        required_docs=("k8s_pod_security_admission_current",),
        excluded_docs=("k8s_pod_security_policy_removed",),
        notes="Removed Kubernetes feature remains highly related to the modern query.",
    ),
    PublicCase(
        id="python_current_urlopen",
        query="In current Python 3 code, how should I open a URL and read data?",
        required_docs=("python3_urllib_request_current",),
        excluded_docs=("python2_urllib2_legacy",),
        notes="Legacy Python 2 docs are related but should not guide Python 3 instructions.",
    ),
    PublicCase(
        id="react_modern_side_effects",
        query="Where should side effects or subscriptions go in a modern React component?",
        required_docs=("react_current_component_guidance",),
        excluded_docs=("react_legacy_lifecycle",),
        notes="Legacy React lifecycle docs are related but should not dominate modern guidance.",
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
    req = Request(url, headers={"User-Agent": "PersistenceGateBenchmark/0.1"})
    with urlopen(req, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="ignore")
    parser = VisibleTextExtractor()
    parser.feed(html)
    return parser.text()


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", text.lower())
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "which", "should",
        "how", "what", "where", "when", "why", "current", "modern", "code", "using",
        "use", "uses", "used", "can", "will", "are", "you", "your", "their", "there",
        "documentation", "docs", "page", "reference",
    }
    return [t for t in tokens if t not in stop]


def chunk_text(text: str, chunk_chars: int = 1400, overlap_chars: int = 250) -> list[str]:
    text = normalize_ws(text)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


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


def build_chunks(cache_dir: Path, refresh: bool) -> tuple[list[dict], list[dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict] = []
    manifest: list[dict] = []

    for doc in PUBLIC_DOCS:
        cache_file = cache_dir / f"{doc.id}.txt"
        fetch_error = ""
        if refresh or not cache_file.exists():
            try:
                text = fetch_visible_text(doc.url)
                cache_file.write_text(text, encoding="utf-8")
            except Exception as exc:
                fetch_error = repr(exc)
                text = ""
        else:
            text = cache_file.read_text(encoding="utf-8", errors="ignore")

        if not text and cache_file.exists():
            text = cache_file.read_text(encoding="utf-8", errors="ignore")

        if not text:
            manifest.append({
                "doc_id": doc.id,
                "url": doc.url,
                "title": doc.title,
                "status": doc.status,
                "family": doc.family,
                "role": doc.role,
                "year": doc.year,
                "fetch_error": fetch_error or "empty_text",
                "chunk_count": 0,
            })
            continue

        doc_chunks = chunk_text(f"{doc.title}. {text}")
        for idx, chunk in enumerate(doc_chunks):
            chunks.append({
                "id": f"{doc.id}::chunk_{idx:03d}",
                "doc_id": doc.id,
                "text": chunk,
                "source": doc.url,
                "context_scope": "global",
                "risk": doc.risk,
                "harm_score": 0.65 if doc.role == "exclude" and doc.status in {"removed", "legacy"} else 0.0,
                "usefulness_score": doc.usefulness,
                "label_risky": doc.role == "exclude",
                "label_stale": doc.status in {"removed", "deprecated", "legacy"},
                "label_helpful": doc.role == "require",
                "metadata": {
                    "doc_id": doc.id,
                    "title": doc.title,
                    "status": doc.status,
                    "family": doc.family,
                    "role": doc.role,
                    "year": doc.year,
                    "notes": doc.notes,
                },
            })

        manifest.append({
            "doc_id": doc.id,
            "url": doc.url,
            "title": doc.title,
            "status": doc.status,
            "family": doc.family,
            "role": doc.role,
            "year": doc.year,
            "fetch_error": fetch_error,
            "chunk_count": len(doc_chunks),
        })

    return chunks, manifest


def retrieve_candidates(query: str, chunks: list[dict], candidate_pool: int) -> list[dict]:
    scored = []
    for chunk in chunks:
        relevance_raw = simple_relevance(query, chunk["text"])
        if relevance_raw <= 0:
            continue
        row = dict(chunk)
        row["relevance_raw"] = relevance_raw
        scored.append(row)
    scored.sort(key=lambda row: row["relevance_raw"], reverse=True)
    scored = scored[:candidate_pool]
    max_score = max((row["relevance_raw"] for row in scored), default=1.0)
    for row in scored:
        row["relevance"] = round(row["relevance_raw"] / max_score, 6) if max_score else 0.0
    return scored


def ordinary_top_k(candidates: list[dict], top_k: int) -> list[dict]:
    return sorted(candidates, key=lambda row: row["relevance"], reverse=True)[:top_k]


def metadata_status_filter(candidates: list[dict], top_k: int) -> list[dict]:
    blocked_status = {"removed", "deprecated", "legacy"}
    rows = [row for row in candidates if row["metadata"].get("status") not in blocked_status]
    return ordinary_top_k(rows, top_k)


def recency_filter(candidates: list[dict], top_k: int, min_year: int = 2024) -> list[dict]:
    rows = [row for row in candidates if int(row["metadata"].get("year", 0)) >= min_year]
    return ordinary_top_k(rows, top_k)


def selected_doc_ids(rows: list[dict]) -> set[str]:
    return {str(row.get("doc_id") or row.get("metadata", {}).get("doc_id") or row["id"].split("::")[0]) for row in rows}


def evaluate_selection(case: PublicCase, rows: list[dict]) -> dict:
    docs = selected_doc_ids(rows)
    required = set(case.required_docs)
    excluded = set(case.excluded_docs)
    exposed = docs & excluded
    retained = required <= docs
    clean = retained and not exposed
    return {
        "selected_doc_ids": ";".join(sorted(docs)),
        "excluded_doc_ids_exposed": ";".join(sorted(exposed)),
        "excluded_info_exposed": int(bool(exposed)),
        "required_info_retained": int(retained),
        "clean_context": int(clean),
        "context_tokens": sum(approx_tokens(row["text"]) for row in rows),
    }


def run_case(case: PublicCase, chunks: list[dict], profile: str, top_k: int, candidate_pool: int) -> tuple[list[dict], list[dict]]:
    candidates = retrieve_candidates(case.query, chunks, candidate_pool)
    details: list[dict] = []
    audit_rows: list[dict] = []

    selections = {
        "ordinary_top_k": ordinary_top_k(candidates, top_k),
        "metadata_status_filter": metadata_status_filter(candidates, top_k),
        "recency_filter": recency_filter(candidates, top_k),
    }

    gate = PersistenceGate(profile=profile, top_k=top_k, context_scope="global")
    result = gate.filter(query=case.query, retrieved_items=candidates, context_scope="global")
    selections[f"persistence_gate:{profile}"] = [
        {
            "id": item.id,
            "doc_id": item.metadata.get("doc_id", item.id.split("::")[0]),
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

    for row in result.audit_log:
        audit_rows.append({
            "case_id": case.id,
            "query": case.query,
            "profile": profile,
            **row,
            "doc_id": row["id"].split("::")[0],
        })

    for method, rows in selections.items():
        metrics = evaluate_selection(case, rows)
        details.append({
            "case_id": case.id,
            "query": case.query,
            "method": method,
            "required_doc_ids": ";".join(case.required_docs),
            "excluded_doc_ids": ";".join(case.excluded_docs),
            **metrics,
            "notes": case.notes,
        })
    return details, audit_rows


def summarize(details: list[dict]) -> list[dict]:
    methods = sorted({row["method"] for row in details})
    summary = []
    for method in methods:
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
        "# Public Evidence Admission Benchmark Examples",
        "",
        "This benchmark uses public documentation pages where legacy or removed guidance can remain highly related to a current query.",
        "The key question is whether a method sends excluded-but-related sources into context while keeping the required current source.",
        "",
    ]
    for case in PUBLIC_CASES:
        lines.extend([f"## {case.id}", "", f"Query: `{case.query}`", ""])
        for row in [r for r in details if r["case_id"] == case.id]:
            lines.append(
                f"- **{row['method']}**: exposed={row['excluded_info_exposed']}, "
                f"retained={row['required_info_retained']}, clean={row['clean_context']}, "
                f"selected={row['selected_doc_ids']}"
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
    parser = argparse.ArgumentParser(description="Run public-web evidence-admission benchmark for Persistence Gate.")
    parser.add_argument("--profile", default="conservative", choices=["permissive", "balanced", "conservative"])
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--candidate-pool", type=int, default=12)
    parser.add_argument("--out-dir", default="benchmark_results/public_evidence_admission")
    parser.add_argument("--cache-dir", default="benchmark_data/public_web_cache")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch public web pages instead of using cached text.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks, manifest = build_chunks(Path(args.cache_dir), refresh=args.refresh)
    if not chunks:
        raise SystemExit("No public documents could be fetched. Try again with network access.")

    details: list[dict] = []
    audit_rows: list[dict] = []
    for case in PUBLIC_CASES:
        case_details, case_audit = run_case(case, chunks, args.profile, args.top_k, args.candidate_pool)
        details.extend(case_details)
        audit_rows.extend(case_audit)

    summary = summarize(details)
    write_csv(out_dir / "source_manifest.csv", manifest)
    write_csv(out_dir / "case_details.csv", details)
    write_csv(out_dir / "gate_audit_log.csv", audit_rows)
    write_csv(out_dir / "summary.csv", summary)
    write_examples(out_dir / "examples.md", details, audit_rows)

    print("\nPublic Evidence Admission Benchmark")
    print(f"Profile: {args.profile} | top_k={args.top_k} | candidate_pool={args.candidate_pool}")
    print(f"Fetched chunks: {len(chunks)}")
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
