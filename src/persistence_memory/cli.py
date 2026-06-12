from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .api import PersistenceGate
from .reports import write_audit_csv, write_html_report, write_markdown_report


def load_payload(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "query" not in data:
        raise ValueError("Input JSON must include a 'query' field")
    if "retrieved_items" not in data and "items" not in data:
        raise ValueError("Input JSON must include 'retrieved_items' or 'items'")
    return data


def run_filter(args: argparse.Namespace) -> int:
    payload = load_payload(args.input)
    items = payload.get("retrieved_items") or payload.get("items") or []
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gate = PersistenceGate(
        profile=args.profile or payload.get("profile", "balanced"),
        top_k=args.top_k or int(payload.get("top_k", 6)),
        context_scope=payload.get("context_scope", "project"),
    )
    result = gate.filter(
        query=payload["query"],
        retrieved_items=items,
        query_intent=args.query_intent or payload.get("query_intent"),
        metadata=payload.get("metadata") or {},
    )

    (out_dir / "result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    (out_dir / "allowed_context.txt").write_text(result.allowed_context, encoding="utf-8")
    write_audit_csv(result, out_dir / "audit.csv")
    write_markdown_report(result, out_dir / "report.md")
    write_html_report(result, out_dir / "report.html")

    print(f"allowed={len(result.allowed_ids)} blocked={len(result.blocked_ids)}")
    print(f"wrote {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistence-gate", description="Persistence Gate command line tool")
    sub = parser.add_subparsers(dest="command", required=True)

    filt = sub.add_parser("filter", help="Filter retrieved evidence from an input JSON file")
    filt.add_argument("input", help="Path to input JSON")
    filt.add_argument("--out-dir", default="persistence_gate_report", help="Output directory")
    filt.add_argument("--profile", default=None, help="Gate profile")
    filt.add_argument("--top-k", type=int, default=None, help="Maximum allowed items")
    filt.add_argument("--query-intent", default=None, help="Optional query intent override")
    filt.set_defaults(func=run_filter)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
