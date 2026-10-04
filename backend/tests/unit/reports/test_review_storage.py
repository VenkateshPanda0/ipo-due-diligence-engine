"""Human review storage: append-only events, immutable decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.base import Database
from app.db.repositories import SqlReportStorage, SqlReviewStorage
from app.engine.decision_engine import DecisionEngine
from app.models.enums import IPOStatus
from app.models.human_review import HumanFinalDecision, HumanReviewRecord, HumanReviewStatus
from app.reports.review_storage import InMemoryReviewStorage
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def _db(tmp_path) -> Database:  # type: ignore[no-untyped-def]
    db = Database(f"sqlite:///{tmp_path / 'r.db'}")
    db.migrate()
    return db


def _completed(review: HumanReviewRecord) -> HumanReviewRecord:
    return review.model_copy(
        update={
            "status": HumanReviewStatus.COMPLETED,
            "reviewer_name": "R",
            "final_decision": HumanFinalDecision.PROCEED,
            "rationale": "ok",
            "completed_at": datetime.now(tz=UTC),
        }
    )


def test_sql_review_persists_and_derives_completion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = _db(tmp_path)
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    SqlReportStorage(db).save(report.report_id, report)
    store = SqlReviewStorage(db)
    review = HumanReviewRecord(report_id=report.report_id, machine_status=IPOStatus.ELIGIBLE)
    store.save(review, actor="alice")
    assert store.get(review.review_id).status == HumanReviewStatus.PENDING  # type: ignore[union-attr]
    store.save(_completed(review), actor="bob")
    got = SqlReviewStorage(db).get_by_report_id(report.report_id)
    assert (
        got is not None and got.status == HumanReviewStatus.COMPLETED and got.reviewer_name == "R"
    )
    events = store.history(review.review_id)
    assert [e["event_type"] for e in events] == ["opened", "decision"]
    assert events[1]["actor"] == "bob"


def test_sql_review_decision_is_immutable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = _db(tmp_path)
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    SqlReportStorage(db).save(report.report_id, report)
    store = SqlReviewStorage(db)
    review = HumanReviewRecord(report_id=report.report_id, machine_status=IPOStatus.ELIGIBLE)
    store.save(_completed(review))
    with pytest.raises(ValueError, match="immutable"):
        store.save(_completed(review))


def test_review_events_cannot_be_deleted_at_db_level(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = _db(tmp_path)
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    SqlReportStorage(db).save(report.report_id, report)
    SqlReviewStorage(db).save(
        HumanReviewRecord(report_id=report.report_id, machine_status=IPOStatus.ELIGIBLE)
    )
    with pytest.raises(Exception, match="append-only"), db.engine.begin() as conn:
        conn.execute(text("DELETE FROM human_review_events"))
    with pytest.raises(Exception, match="append-only"), db.engine.begin() as conn:
        conn.execute(text("UPDATE audit_events SET actor='x'"))


def test_in_memory_review_storage_refuses_recompletion() -> None:
    store = InMemoryReviewStorage()
    review = HumanReviewRecord(report_id=uuid4(), machine_status=IPOStatus.ELIGIBLE)
    store.save(_completed(review))
    with pytest.raises(ValueError):
        store.save(_completed(review))
