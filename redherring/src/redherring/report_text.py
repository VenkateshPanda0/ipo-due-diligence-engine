"""Plain-text (markdown) rendering of analysis summaries."""

from __future__ import annotations

from redherring.analyze import Summary


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def summary_markdown(rows: list[Summary]) -> str:
    head = (
        "| doc | values | citation-verified | footing passed | multi-source groups "
        "| unanimous | no period | no unit |"
    )
    lines = [head, "|" + "---|" * 8]
    for r in rows:
        lines.append(
            f"| {r.doc_id} | {r.values_total} | {_pct(r.values_verified, r.values_total)} "
            f"| {_pct(r.footing_passed, r.footing_checked)} | {r.consensus_multi_source} "
            f"| {_pct(r.consensus_unanimous_multi, r.consensus_multi_source)} "
            f"| {r.values_without_period} | {r.values_without_unit} |"
        )
    return "\n".join(lines)
