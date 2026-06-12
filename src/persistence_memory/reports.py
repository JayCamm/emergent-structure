from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .api import GateFilterResult


def audit_rows(result: GateFilterResult) -> list[dict[str, Any]]:
    return list(result.audit_log)


def write_audit_csv(result: GateFilterResult, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = audit_rows(result)
    if not rows:
        out.write_text("", encoding="utf-8")
        return out
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return out


def markdown_report(result: GateFilterResult, title: str = "Persistence Gate Report") -> str:
    lines = [
        f"# {title}",
        "",
        f"Query: `{result.query}`",
        f"Profile: `{result.profile}`",
        "",
        "## Summary",
        "",
        f"- Allowed items: {len(result.allowed_ids)}",
        f"- Blocked items: {len(result.blocked_ids)}",
        f"- Warnings: {len(result.warnings)}",
        "",
        "## Allowed IDs",
        "",
    ]
    lines.extend(f"- `{item}`" for item in result.allowed_ids)
    lines.extend(["", "## Blocked IDs", ""])
    lines.extend(f"- `{item}`" for item in result.blocked_ids)
    lines.extend(["", "## Audit Log", ""])
    for row in result.audit_log:
        reasons = ", ".join(row.get("reasons") or []) or "none"
        score = float(row.get("score", 0.0))
        lines.append(
            f"- `{row.get('id')}`: bucket={row.get('bucket')}, decision={row.get('decision')}, "
            f"score={score:.4f}, role={row.get('evidence_role', 'unknown')}, reasons={reasons}"
        )
    return "\n".join(lines) + "\n"


def write_markdown_report(result: GateFilterResult, path: str | Path, title: str = "Persistence Gate Report") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown_report(result, title=title), encoding="utf-8")
    return out


def html_report(result: GateFilterResult, title: str = "Persistence Gate Report") -> str:
    md = markdown_report(result, title=title)
    body = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "<!doctype html><html><body><pre>" + body + "</pre></body></html>"


def write_html_report(result: GateFilterResult, path: str | Path, title: str = "Persistence Gate Report") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_report(result, title=title), encoding="utf-8")
    return out
