from decimal import Decimal
from pathlib import Path

import pytest

from redherring.eval.labels import Label, LabelFile, check_labels, load_labels
from redherring.eval.metrics import Prediction, family_of, score


def lab(key: str, status: str = "present", value: str | None = "100", pages: tuple[int, ...] = (5,),
        span: str | None = "row | 100", **kw: object) -> Label:  # fmt: skip
    return Label.model_validate(
        {"key": key, "status": status, "value_rupees": value if status == "present" else None,
         "pages": list(pages) if status == "present" else [],
         "span": span if status == "present" else None, **kw}
    )  # fmt: skip


def lfile(*labels: Label, doc_id: str = "d1") -> LabelFile:
    return LabelFile(
        doc_id=doc_id, doc_sha256="abc", labelled_by="tester", labelled_on="2026-10-24",
        method="read from the PDF text", fields=list(labels),
    )  # fmt: skip


def pred(key: str, value: str, page: int = 5) -> Prediction:
    return Prediction(key=key, value=Decimal(value), pdf_page=page, span="row")


# ---- label validation -------------------------------------------------------------------------


def test_present_label_needs_value_pages_and_span() -> None:
    with pytest.raises(ValueError):
        Label.model_validate({"key": "k", "status": "present"})
    with pytest.raises(ValueError):
        Label.model_validate({"key": "k", "status": "present", "value_rupees": "1", "pages": [1]})
    ok = lab("k")
    assert ok.status == "present"


def test_absent_label_must_not_carry_a_value() -> None:
    with pytest.raises(ValueError):
        Label.model_validate({"key": "k", "status": "absent", "value_rupees": "1"})
    assert lab("k", status="absent").value_rupees is None


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        lfile(lab("a"), lab("a"))


def test_check_labels_flags_unreviewed_and_unfound_values() -> None:
    f = lfile(
        lab("a", span="Total income | 1,013.25", value="101325000", raw="1,013.25"),
        lab("b", status="unreviewed", value=None),
        lab("c", span="x | 9.99", value="999", raw="9.99"),
    )  # fmt: skip
    problems = check_labels(f, lambda page: "Total income 1,013.25" if page == 5 else "")
    text = " ".join(problems)
    assert "b: still unreviewed" in text
    assert "c: raw value '9.99' not found on cited page 5" in text
    assert not any(p.startswith("a:") for p in problems)


def test_check_labels_requires_raw_text_for_present_labels() -> None:
    f = lfile(lab("a"))  # no `raw`: cannot be re-checked against the PDF
    assert any("a: present label needs `raw`" in p for p in check_labels(f, lambda p: ""))


def test_load_labels_reads_a_directory(tmp_path: Path) -> None:
    (tmp_path / "d1.json").write_text(lfile(lab("a")).model_dump_json())
    (tmp_path / "d2.draft.json").write_text(lfile(lab("a"), doc_id="d2").model_dump_json())
    loaded = load_labels(tmp_path)
    assert list(loaded) == ["d1"]  # drafts are not ground truth


# ---- scoring ------------------------------------------------------------------------------------


def test_family_strips_the_period_suffix() -> None:
    assert family_of("financials.total_income.FY2026") == "financials.total_income"
    assert family_of("issue.fresh_issue_amount") == "issue.fresh_issue_amount"
    assert family_of("financials.net_worth.AT-2026-06-30") == "financials.net_worth"


def test_correct_wrong_missing_and_hallucinated_values() -> None:
    labels = {
        "d1": lfile(
            lab("issue.fresh_issue_amount", value="7500000000"),
            lab("issue.ofs_amount", value="3416800000", pages=(12,)),
            lab("issue.total_issue_amount", value="10916800000"),
            lab("objects.gcp_amount", status="absent"),
            lab("objects.unidentified_acquisition_amount", status="absent"),
        )
    }
    preds = {
        "d1": [
            pred("issue.fresh_issue_amount", "7500000000", page=5),  # correct, right page
            pred("issue.ofs_amount", "3416800000", page=9),  # correct value, wrong page
            pred("issue.total_issue_amount", "9000000000"),  # wrong value
            pred("objects.gcp_amount", "1117150000"),  # hallucination: label says absent
        ]
    }
    r = score(labels, preds)
    assert (r.n_labelled, r.n_present, r.n_absent) == (5, 3, 2)
    assert r.correct == 2
    assert r.wrong == 1
    assert r.abstained == 0
    assert r.hallucinated == 1
    assert r.correct_abstentions == 1
    assert r.value_accuracy == pytest.approx(2 / 3)
    assert r.citation_accuracy == pytest.approx(1 / 2)  # of the two correct values, one page right
    assert r.hallucination_rate == pytest.approx(1 / 2)  # of the two absent labels
    assert r.abstention_rate == pytest.approx(0 / 3)


def test_missing_prediction_for_a_present_label_is_an_abstention() -> None:
    labels = {"d1": lfile(lab("issue.fresh_issue_amount", value="1000"))}
    r = score(labels, {"d1": []})
    assert (r.abstained, r.correct, r.wrong) == (1, 0, 0)
    assert r.abstention_rate == 1.0


def test_tolerance_accepts_rounding_but_not_real_differences() -> None:
    labels = {"d1": lfile(lab("financials.total_income.FY2026", value="18507930000"))}
    near = {"d1": [pred("financials.total_income.FY2026", "18508000000")]}  # 18,508 mn vs 18,507.93
    far = {"d1": [pred("financials.total_income.FY2026", "18900000000")]}
    assert score(labels, near).correct == 1
    assert score(labels, far).wrong == 1


def test_per_family_breakdown_and_unsure_labels_are_excluded() -> None:
    labels = {
        "d1": lfile(
            lab("financials.total_income.FY2026", value="100"),
            lab("financials.total_income.FY2025", value="90"),
            lab("financials.profit_after_tax.FY2026", value="5"),
            Label.model_validate({"key": "issue.ofs_amount", "status": "unsure"}),
        )
    }
    preds = {
        "d1": [
            pred("financials.total_income.FY2026", "100"),
            pred("financials.total_income.FY2025", "1"),
            pred("financials.profit_after_tax.FY2026", "5"),
        ]
    }
    r = score(labels, preds)
    assert r.n_labelled == 3  # the unsure label is not scored
    fam = {f.family: f for f in r.families}
    assert (fam["financials.total_income"].correct, fam["financials.total_income"].wrong) == (1, 1)
    assert fam["financials.profit_after_tax"].correct == 1


def test_documents_without_labels_are_not_scored() -> None:
    labels = {"d1": lfile(lab("issue.fresh_issue_amount", value="1"))}
    r = score(labels, {"d1": [pred("issue.fresh_issue_amount", "1")], "other": [pred("x", "5")]})
    assert r.n_labelled == 1
