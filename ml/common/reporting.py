# Small shared helpers for KnightVision ML reports and artifacts

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def json_safe(value: Any) -> Any:
    """Convert common Python objects into JSON-serializable values."""

    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")

def metric_rows(metrics: dict[str, float | int]) -> list[str]:
    rows = []
    for name, value in metrics.items():
        if isinstance(value, float):
            rows.append(f"| {name} | {value:.4f} |")
        else:
            rows.append(f"| {name} | {value} |")
    return rows

def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]

def write_model_card(
    path: Path,
    *,
    title: str,
    summary: str,
    dataset: list[str],
    metrics: dict[str, float | int],
    artifacts: list[str],
    limitations: list[str],
    interpretation: list[str],
    extra_sections: dict[str, list[str]] | None = None,
) -> None:
    """Write a consistent human-readable model card."""

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Dataset",
        "",
        *[f"- {item}" for item in dataset],
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *metric_rows(metrics),
        "",
        "## Artifacts",
        "",
        *[f"- `{item}`" for item in artifacts],
    ]
    for heading, section_lines in (extra_sections or {}).items():
        lines.extend(["", f"## {heading}", "", *section_lines])
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in limitations],
            "",
            "## Recommended Interpretation",
            "",
            *[f"- {item}" for item in interpretation],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")