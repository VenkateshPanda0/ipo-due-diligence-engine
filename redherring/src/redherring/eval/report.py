"""Markdown rendering of an EvalReport."""

from __future__ import annotations

from redherring.eval.metrics import EvalReport


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def eval_markdown(r: EvalReport) -> str:
    lines = [
        f"Labelled fields: {r.n_labelled} ({r.n_present} present, {r.n_absent} absent)",
        "",
        f"- value accuracy: {r.correct}/{r.n_present} ({_pct(r.value_accuracy)})",
        f"- citation accuracy (of correct values): {r.citation_correct}/{r.correct} "
        f"({_pct(r.citation_accuracy)})",
        f"- abstention rate: {r.abstained}/{r.n_present} ({_pct(r.abstention_rate)})",
        f"- hallucination rate: {r.hallucinated}/{r.n_absent} ({_pct(r.hallucination_rate)})",
        "",
        "| field family | present | correct | wrong | abstained | absent | hallucinated "
        "| value accuracy | citation accuracy |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for f in r.families:
        lines.append(
            f"| {f.family} | {f.n_present} | {f.correct} | {f.wrong} | {f.abstained} "
            f"| {f.n_absent} | {f.hallucinated} | {_pct(f.value_accuracy)} "
            f"| {_pct(f.citation_accuracy)} |"
        )
    return "\n".join(lines)
