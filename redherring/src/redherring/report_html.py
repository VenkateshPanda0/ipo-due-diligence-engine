"""One self-contained HTML page per filing: what was found, what was flagged, what could not be
checked, every figure linked to its page in the source PDF.

Everything that came out of the document (row text, labels) is untrusted and is escaped; the page
has no script, no external resource and works offline.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from html import escape

from redherring.analyze import AnalysisReport, FactRecord
from redherring.flags.engine import Flag, RuleAudit
from redherring.ingest.manifest import ManifestEntry

DISCLAIMER = (
    "Not investment advice. Automated analysis of public disclosures; verify against the source "
    "document."
)
CRORE = Decimal(10_000_000)

_FY = re.compile(r"^FY(\d{4})$")
_ROWS = (
    ("revenue_from_operations", "Revenue from operations"),
    ("total_income", "Total income"),
    ("profit_before_tax", "Profit before tax"),
    ("tax_expense", "Tax expense"),
    ("profit_after_tax", "Profit after tax"),
    ("total_assets", "Total assets"),
    ("cash_from_operations", "Cash from operations"),
)
_ISSUE_ROWS = (
    ("issue.fresh_issue_amount", "Fresh issue"),
    ("issue.ofs_amount", "Offer for sale"),
    ("issue.total_issue_amount", "Total issue"),
    ("objects.gcp_amount", "General corporate purposes"),
    ("objects.unidentified_acquisition_amount", "Unidentified acquisitions"),
)
_STATUS_TEXT = {
    "flagged": "flagged",
    "clear": "checked, nothing found",
    "missing_inputs": "could not be checked: figures not extracted",
    "not_in_force": "not in force on the filing date",
    "other_platform": "applies to the other platform",
    "not_applicable": "not applied to this kind of business",
}


_SET_ASIDE = ("other_platform", "not_in_force")


def indian(x: Decimal, places: int = 2) -> str:
    """12345678.5 -> '1,23,45,678.50' (lakh/crore grouping), negatives in minus form."""
    q = x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    whole, _, frac = f"{abs(q):f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    body = ",".join([*groups, tail]) if groups else tail
    return f"{sign}{body}.{frac}" if places else f"{sign}{body}"


def _crore(rupees: Decimal) -> str:
    return indian(rupees / CRORE)


def _page_link(url: str, page: int) -> str:
    return f"{escape(url, quote=True)}#page={page}"


def _cite(url: str, page: int, hidden: frozenset[int] = frozenset()) -> str:
    mark = (
        ' <span title="this page has text a reader cannot see" class=warn>⚠</span>'
        if page in hidden
        else ""
    )
    return f'<a href="{_page_link(url, page)}">p.{page}</a>{mark}'


def _flag_html(f: Flag, url: str, hidden: frozenset[int]) -> str:
    cites = "".join(
        f"<li>{_cite(url, c.pdf_page, hidden)} <code>{escape(c.span)}</code></li>"
        for c in f.citations
    )
    srcs = "".join(
        f"<li>{escape(s.ref)}{', ' + escape(s.clause) if s.clause else ''}"
        f" (checked {s.checked_on.isoformat()})</li>"
        for s in f.sources
    )
    kind = "heuristic: threshold chosen by this project" if f.heuristic else "regulatory threshold"
    return (
        f'<article class="flag sev-{escape(f.severity)}">'
        f"<h3>{escape(f.rule_name)} <span class=badge>{escape(f.severity)}</span></h3>"
        f"<p>{escape(f.explanation)}</p><p class=kind>{kind}</p>"
        f"<details open><summary>Evidence</summary><ul>{cites}</ul></details>"
        f"<details><summary>Basis</summary><ul>{srcs}</ul></details></article>"
    )


def _audit_row(a: RuleAudit) -> str:
    why = _STATUS_TEXT.get(a.status, a.status)
    extra = ""
    if a.status == "missing_inputs" and a.missing:
        extra = " (" + ", ".join(escape(m) for m in a.missing) + ")"
    elif a.detail:
        extra = " (" + escape(a.detail) + ")"
    return f"<tr><td><code>{escape(a.rule_id)}</code></td><td>{escape(why)}{extra}</td></tr>"


def _fy_table(facts: dict[str, FactRecord], url: str, hidden: frozenset[int]) -> str:
    years = sorted(
        {m.group(1) for k in facts if (m := _FY.match(k.rsplit(".", 1)[-1]))}, reverse=True
    )[:5]
    if not years:
        return "<p>No annual figures could be extracted with enough confidence.</p>"
    head = "".join(f"<th>FY{y}</th>" for y in years)
    rows: list[str] = []
    for concept, title in _ROWS:
        cells = []
        for y in years:
            f = facts.get(f"financials.{concept}.FY{y}")
            cells.append(
                f"<td class=num>{_crore(f.value)} <small>{_cite(url, f.pdf_page, hidden)}</small></td>"
                if f
                else "<td class=num>–</td>"
            )
        if any("–</td>" not in c for c in cells):
            rows.append(f"<tr><th>{escape(title)}</th>{''.join(cells)}</tr>")
    return (
        "<p class=note>₹ crore (1 crore = 10 million). A dash means the figure was not found or "
        "the sources disagreed.</p>"
        f"<table><thead><tr><th></th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _issue_table(report: AnalysisReport, url: str, hidden: frozenset[int]) -> str:
    by_key = {f.key.value: f for f in report.issue_facts if f.verified}
    rows = []
    for key, title in _ISSUE_ROWS:
        f = by_key.get(key)
        if f:
            rows.append(
                f"<tr><th>{title}</th><td class=num>{_crore(f.value)} "
                f"<small>{_cite(url, f.pdf_page, hidden)}</small></td></tr>"
            )
    ma = by_key.get("objects.monitoring_agency_appointed")
    if ma:
        word = "appointed" if ma.value == 1 else "stated as not appointed or not required"
        rows.append(
            f"<tr><th>Monitoring agency</th><td>{word} <small>{_cite(url, ma.pdf_page, hidden)}</small>"
            "</td></tr>"
        )
    if not rows:
        return "<p>No issue size or objects figures are stated in a form that could be read.</p>"
    return (
        "<p class=note>₹ crore. Placeholders such as [●] (common in draft documents) are "
        "not read as figures.</p>"
        f"<table><tbody>{''.join(rows)}</tbody></table>"
    )


def _withheld(report: AnalysisReport) -> list[str]:
    kept = {f.key for f in report.facts}
    out = []
    for c in report.consensus:
        key = f"financials.{c.concept.value}.{c.period_key}"
        if _FY.match(c.period_key) and key not in kept:
            readings = [c.chosen_raw, *c.alternatives_raw]
            shown = ", ".join(escape(a) for a in readings[:5])
            more = f" and {len(readings) - 5} more" if len(readings) > 5 else ""
            out.append(
                f"<li>{escape(c.concept.value.replace('_', ' '))} {escape(c.period_key)}: "
                f"{len(readings)} different readings, e.g. {shown}{more}</li>"
            )
    return out


def report_html(report: AnalysisReport, entry: ManifestEntry) -> str:
    s = report.summary
    facts = {f.key: f for f in report.facts}
    url = entry.url
    hidden = frozenset(report.pages_with_hidden_text)
    flags = "".join(_flag_html(f, url, hidden) for f in report.flags)
    if not flags:
        flags = (
            f"<p>No flags raised. That is <strong>not</strong> a clean bill of health: "
            f"{s.rules_decisive} of {s.rules_applicable} applicable rules could be evaluated; the "
            "others lacked figures the extractor could read with confidence (see below).</p>"
        )
    live = [a for a in report.rule_audit if a.status not in _SET_ASIDE]
    aside = [a for a in report.rule_audit if a.status in _SET_ASIDE]
    audit = "".join(_audit_row(a) for a in live)
    audit_aside = (
        f"<details><summary>{len(aside)} rules set aside (other platform or not in force on the "
        f"filing date)</summary><table><tbody>{''.join(_audit_row(a) for a in aside)}</tbody>"
        "</table></details>"
        if aside
        else ""
    )
    withheld = _withheld(report)
    sectors = ", ".join(escape(x.sector.replace("_", " ")) for x in report.sectors)
    date_text = entry.filing_date.isoformat() if entry.filing_date else "not recorded"
    hidden_html = (
        "<div class=banner><strong>Text a reader cannot see.</strong> The text layer of page"
        f"{'s' if len(hidden) > 1 else ''} {', '.join(str(n) for n in sorted(hidden)[:12])}"
        f"{' and others' if len(hidden) > 12 else ''} contains characters that are not visible when "
        "the page is read (white text on nothing, or text too small to read). Figures cited from "
        "those pages are marked ⚠; check them against the rendered page."
        + (
            " Kept out of the red-flag rules for that reason: "
            + ", ".join(escape(k) for k in report.facts_held_back_hidden_text)
            + "."
            if report.facts_held_back_hidden_text
            else ""
        )
        + "</div>"
        if hidden
        else ""
    )
    withheld_html = (
        "<h2>Figures withheld because the document's tables disagree</h2><ul>"
        + "".join(withheld)
        + "</ul>"
        if withheld
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(entry.issuer)}: offer document review</title>
<style>
:root{{--bg:#fff;--fg:#1c1c1e;--mute:#5b5b66;--line:#d9d9e0;--card:#f6f6f9;--hi:#b3261e;--med:#a15c00;--lo:#3b6b2f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16161a;--fg:#ececf1;--mute:#a0a0ad;--line:#33333c;--card:#1f1f25;--hi:#ff8a80;--med:#ffb74d;--lo:#9ccc65}}}}
body{{margin:0 auto;max-width:56rem;padding:1rem 16px 3rem;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}}
h1{{font-size:1.5rem;margin:.2rem 0}} h2{{font-size:1.15rem;margin:2rem 0 .5rem;border-bottom:1px solid var(--line)}}
.meta,.note,.kind,small{{color:var(--mute)}} .banner{{background:var(--card);border-left:4px solid var(--med);padding:.6rem .9rem;margin:1rem 0}}
table{{border-collapse:collapse;width:100%;font-size:.95rem}} th,td{{padding:.3rem .5rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
td.num{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}} thead th{{color:var(--mute);font-weight:600}}
.flag{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:.4rem .9rem;margin:.8rem 0}}
.flag h3{{font-size:1rem;margin:.4rem 0}} .badge{{font-size:.75rem;border:1px solid currentColor;border-radius:4px;padding:0 .3rem;margin-left:.4rem}}
.warn{{color:var(--hi)}} .sev-high .badge{{color:var(--hi)}} .sev-medium .badge{{color:var(--med)}} .sev-low .badge,.sev-info .badge{{color:var(--lo)}}
code{{font-size:.85rem;word-break:break-word}} .table-wrap{{overflow-x:auto}}
</style></head><body>
<h1>{escape(entry.issuer)}</h1>
<p class=meta>{escape(entry.doc_type.value)} · {escape(entry.platform.value if entry.platform else "platform not recorded")} · filing date {date_text}<br>
Source: <a href="{escape(entry.url, quote=True)}">{escape(entry.url)}</a><br>
SHA-256 <code>{escape(entry.sha256)}</code></p>
<div class=banner><strong>{escape(DISCLAIMER)}</strong></div>
{hidden_html}
<h2>Flags</h2>
{flags}
<h2>Issue and objects</h2>
<div class=table-wrap>{_issue_table(report, url, hidden)}</div>
<h2>Annual figures</h2>
<div class=table-wrap>{_fy_table(facts, url, hidden)}</div>
<h2>What could and could not be checked</h2>
<div class=table-wrap><table><tbody>{audit}</tbody></table></div>
{audit_aside}
{withheld_html}
<h2>How far to trust the extraction</h2>
<ul>
<li>{s.values_verified} of {s.values_total} extracted numbers were found again in the PDF's own text layer on the cited page.</li>
<li>Accounting identities held in {s.footing_passed} of {s.footing_checked} table-year checks.</li>
<li>Of {s.consensus_multi_source} figures printed in more than one table, {s.consensus_unanimous_multi} agree exactly.</li>
{f"<li>Business type detected from the text: {sectors}.</li>" if sectors else ""}
</ul>
<p class=note>Generated from public filings by RedHerring. Every figure links to its page in the source PDF. {escape(DISCLAIMER)}</p>
</body></html>
"""
