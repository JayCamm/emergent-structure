from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from time import time

from persistence_memory import InMemoryStore, MemoryController, MemoryItem, TaskContext

DEFAULT_REPOS = [
    "JayCamm/persistence-gate",
    "JayCamm/emergent-structure",
    "JayCamm/error-catastrophe-sim",
    "JayCamm/pattern-sweep",
    "JayCamm/universe-simulator",
]

PROJECT_KEYWORDS = {
    "persistence",
    "memory",
    "gate",
    "retrieval",
    "influence",
    "governance",
    "software",
    "architecture",
    "emergent",
    "structure",
    "simulation",
}

RISK_KEYWORDS = {
    "deprecated",
    "obsolete",
    "old",
    "legacy",
    "stale",
    "broken",
    "experimental",
    "prototype",
    "draft",
    "todo",
    "fixme",
    "not production",
    "failed",
}

HELPFUL_KEYWORDS = {
    "validated",
    "test",
    "tests",
    "passed",
    "confirmed",
    "current",
    "readme",
    "architecture",
    "usage",
    "install",
}


def github_request(path: str) -> dict | list | None:
    url = f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "persistence-gate-demo"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"Warning: GitHub API returned {exc.code} for {path}", file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"Warning: could not reach GitHub for {path}: {exc}", file=sys.stderr)
    return None


def decode_content(payload: dict | None) -> str:
    if not payload or "content" not in payload:
        return ""
    encoded = payload.get("content", "")
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def keyword_score(text: str, keywords: set[str]) -> float:
    lowered = text.lower()
    hits = sum(1 for word in keywords if word in lowered)
    return clamp(hits / max(4, len(keywords) * 0.35))


def age_risk(pushed_at: str | None) -> float:
    pushed = parse_datetime(pushed_at)
    if pushed is None:
        return 0.25
    age_days = (datetime.now(timezone.utc) - pushed).days
    if age_days < 30:
        return 0.02
    if age_days < 180:
        return 0.10
    if age_days < 730:
        return 0.25
    return 0.45


def fetch_readme(repo_full_name: str, repo: dict) -> str:
    payload = github_request(f"/repos/{repo_full_name}/readme")
    readme = decode_content(payload if isinstance(payload, dict) else None)
    if readme:
        return readme

    # Some repos in early experiments were renamed or copied. Avoid accidentally
    # reusing the previous repo's README by trying only explicit candidate paths.
    branch = repo.get("default_branch") or "main"
    for filename in ["README.md", "readme.md", "README.txt"]:
        payload = github_request(f"/repos/{repo_full_name}/contents/{filename}?ref={branch}")
        readme = decode_content(payload if isinstance(payload, dict) else None)
        if readme:
            return readme
    return ""


def repo_to_memory(repo_full_name: str, query: str) -> MemoryItem | None:
    repo = github_request(f"/repos/{repo_full_name}")
    if not isinstance(repo, dict) or "full_name" not in repo:
        return None

    readme = fetch_readme(repo_full_name, repo)
    readme_head = re.sub(r"\s+", " ", readme).strip()[:1600]

    text = (
        f"Repository {repo.get('full_name')}. "
        f"Description: {repo.get('description') or 'No description provided.'}. "
        f"Language: {repo.get('language') or 'unknown'}. "
        f"Updated/pushed at: {repo.get('pushed_at')}. "
        f"README excerpt: {readme_head or 'No README text available.'}"
    )

    relevance = 0.25 + 0.55 * keyword_score(text + " " + query, PROJECT_KEYWORDS)
    if "persistence-gate" in repo_full_name.lower():
        relevance += 0.20

    risk = age_risk(repo.get("pushed_at")) + 0.35 * keyword_score(text, RISK_KEYWORDS)
    helpfulness = 0.10 + 0.55 * keyword_score(text, HELPFUL_KEYWORDS)
    confidence = 0.45 + (0.25 if readme else 0.0) + (0.15 if repo.get("description") else 0.0)
    burden = clamp(len(text) / 6000)

    return MemoryItem(
        id=repo_full_name.replace("/", "__"),
        text=text,
        source="github_api",
        context_scope="project" if "persistence" in text.lower() or "memory" in text.lower() else "research_history",
        created_at=time(),
        relevance=clamp(relevance),
        confidence=clamp(confidence),
        importance=clamp(0.35 + relevance * 0.5),
        burden=burden,
        risk=clamp(risk),
        usefulness_score=clamp(helpfulness),
        harm_score=clamp(max(0.0, risk - 0.20)),
        metadata={
            "repo": repo_full_name,
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "pushed_at": repo.get("pushed_at"),
            "url": repo.get("html_url"),
        },
    )


def print_section(title: str) -> None:
    print("\n" + title)
    print("=" * len(title))


def print_memory_item(prefix: str, item: MemoryItem) -> None:
    print(
        f"{prefix} {item.id}: relevance={item.relevance:.3f}, risk={item.risk:.3f}, "
        f"harm={item.harm_score:.3f}, usefulness={item.usefulness_score:.3f}, burden={item.burden:.3f}"
    )
    print(f"  {item.text[:260]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a real GitHub corpus and compare ordinary top-k with Persistence Gate.")
    parser.add_argument("--repos", nargs="*", default=DEFAULT_REPOS, help="Repos in owner/name form")
    parser.add_argument("--query", default="What should influence the next step for persistence-aware memory software?")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--save-corpus", type=Path, default=None, help="Optional path to save generated JSONL corpus")
    args = parser.parse_args()

    print_section("Building corpus from real GitHub repository data")
    items: list[MemoryItem] = []
    for repo_name in args.repos:
        print(f"Fetching {repo_name}...")
        item = repo_to_memory(repo_name, args.query)
        if item is not None:
            items.append(item)

    if not items:
        raise SystemExit("No GitHub repository data could be loaded.")

    if args.save_corpus:
        with args.save_corpus.open("w", encoding="utf-8") as handle:
            for item in items:
                row = item.__dict__.copy()
                row["state"] = item.state.value
                handle.write(json.dumps(row, default=str) + "\n")
        print(f"Saved corpus to {args.save_corpus}")

    controller = MemoryController(InMemoryStore(items))
    task = TaskContext(
        query=args.query,
        context_scope="project",
        need=0.85,
        risk_tolerance=0.55,
        abstention_score=0.05,
    )
    report = controller.retrieve_report(task, top_k=args.top_k)

    print_section("Ordinary top-k baseline, relevance only")
    for item in report.ordinary_top_k:
        print_memory_item("-", item)

    print_section("Allowed memory after Persistence Gate")
    for scored in report.allowed:
        print(
            f"- {scored.memory.id}: decision={scored.decision.value}, score={scored.score:.3f}, reasons={scored.reasons}"
        )
        print(f"  {scored.memory.text[:260]}...")

    print_section("Blocked / gated-out memory")
    if not report.blocked:
        print("None")
    for scored in report.blocked:
        print(
            f"- {scored.memory.id}: decision={scored.decision.value}, score={scored.score:.3f}, reasons={scored.reasons}"
        )
        print(f"  {scored.memory.text[:260]}...")

    print_section("Allowed but not selected because of top-k limit")
    if not report.not_selected:
        print("None")
    for scored in report.not_selected or []:
        print(
            f"- {scored.memory.id}: decision={scored.decision.value}, score={scored.score:.3f}, reasons={scored.reasons}"
        )
        print(f"  {scored.memory.text[:260]}...")

    print_section("Blocked memories that ordinary top-k would have used")
    if report.blocked_from_ordinary_top_k:
        for memory_id in report.blocked_from_ordinary_top_k:
            print(f"- {memory_id}")
    else:
        print("None in this run")

    print_section("Quick interpretation")
    if report.blocked_from_ordinary_top_k:
        print("Persistence Gate prevented at least one relevance-only top-k item from influencing the result.")
    elif report.not_selected:
        print("Persistence Gate changed the top-k context budget, but did not hard-block an ordinary top-k item in this corpus.")
    else:
        print("Persistence Gate did not block any ordinary top-k items in this corpus. That can be good if the corpus is clean, or a sign we need a messier test set.")


if __name__ == "__main__":
    main()
