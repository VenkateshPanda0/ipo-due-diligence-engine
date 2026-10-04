"""
SQL repositories.

The rules engine never imports this module. Services use repositories inside a
single ``Database.session()`` transaction per operation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Database
from app.db.models import (
    AuditEventRow,
    CaseDataVersionRow,
    HumanReviewEventRow,
    HumanReviewRow,
    ReportRow,
)
from app.models.enums import IPOStatus
from app.models.human_review import HumanFinalDecision, HumanReviewRecord, HumanReviewStatus
from app.models.ipo_report import IPOReport


def audit(
    session: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    case_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an audit event (no document contents or financial values)."""
    session.add(
        AuditEventRow(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            case_id=case_id,
            details=details or {},
        )
    )


def latest_version(session: Session, case_id: str) -> CaseDataVersionRow | None:
    return session.execute(
        select(CaseDataVersionRow)
        .where(CaseDataVersionRow.case_id == case_id)
        .order_by(CaseDataVersionRow.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def next_version_number(session: Session, case_id: str) -> int:
    current = session.execute(
        select(func.max(CaseDataVersionRow.version)).where(CaseDataVersionRow.case_id == case_id)
    ).scalar_one()
    return int(current or 0) + 1


def _report_exists(session: Session, report_id: UUID) -> bool:
    """Primary-key probe that does not load the (large) report payload."""
    found = session.execute(
        select(ReportRow.report_id).where(ReportRow.report_id == str(report_id))
    ).first()
    return found is not None


class SqlReportStorage:
    """ReportStorage implementation backed by the ``reports`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(
        self,
        report_id: UUID,
        report: IPOReport,
        *,
        case_id: str | None = None,
        data_version: int | None = None,
        created_by: str = "system",
    ) -> None:
        with self._db.session() as s:
            if _report_exists(s, report_id):
                raise ValueError("Reports are immutable; report_id already exists.")
            s.add(
                ReportRow(
                    report_id=str(report_id),
                    case_id=case_id,
                    data_version=data_version,
                    ruleset_version=report.ruleset_version.version,
                    outcome=report.outcome.value if report.outcome else None,
                    legacy_status=report.status.value,
                    input_sha256=report.input_sha256,
                    company_name=report.company_name,
                    payload=report.model_dump_json(),
                    created_by=created_by,
                )
            )
            audit(
                s,
                actor=created_by,
                action="report.created",
                entity_type="report",
                entity_id=str(report_id),
                case_id=case_id,
                details={
                    "ruleset": report.ruleset_version.version,
                    "outcome": report.outcome.value if report.outcome else None,
                },
            )

    def get(self, report_id: UUID) -> IPOReport | None:
        with self._db.session() as s:
            row = s.get(ReportRow, str(report_id))
            return IPOReport.model_validate_json(row.payload) if row else None

    def exists(self, report_id: UUID) -> bool:
        with self._db.session() as s:
            return _report_exists(s, report_id)


class SqlReviewStorage:
    """Human sign-off storage. Decisions are append-only events; the record is derived."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _record(row: HumanReviewRow, events: list[HumanReviewEventRow]) -> HumanReviewRecord:
        decision = next((e for e in events if e.event_type == "decision"), None)
        if decision is None:
            return HumanReviewRecord(
                review_id=UUID(row.review_id),
                report_id=UUID(row.report_id),
                machine_status=IPOStatus(row.machine_status),
                created_at=row.created_at,
            )
        return HumanReviewRecord(
            review_id=UUID(row.review_id),
            report_id=UUID(row.report_id),
            machine_status=IPOStatus(row.machine_status),
            status=HumanReviewStatus.COMPLETED,
            reviewer_name=decision.reviewer_name,
            final_decision=HumanFinalDecision(decision.decision),
            rationale=decision.rationale,
            conditions=list(decision.conditions),
            created_at=row.created_at,
            completed_at=decision.created_at,
        )

    def _events(self, s: Session, review_id: str) -> list[HumanReviewEventRow]:
        return list(
            s.execute(
                select(HumanReviewEventRow)
                .where(HumanReviewEventRow.review_id == review_id)
                .order_by(HumanReviewEventRow.id)
            ).scalars()
        )

    def save(self, review: HumanReviewRecord, actor: str = "system") -> None:
        """Persist a new review (pending) or append a completion event."""
        with self._db.session() as s:
            row = s.get(HumanReviewRow, str(review.review_id))
            if row is None:
                s.add(
                    HumanReviewRow(
                        review_id=str(review.review_id),
                        report_id=str(review.report_id),
                        machine_status=review.machine_status.value,
                        created_at=review.created_at,
                    )
                )
                s.flush()
                s.add(
                    HumanReviewEventRow(
                        review_id=str(review.review_id), event_type="opened", actor=actor
                    )
                )
            if review.status == HumanReviewStatus.COMPLETED:
                if any(e.event_type == "decision" for e in self._events(s, str(review.review_id))):
                    raise ValueError("Review already completed; decisions are immutable.")
                assert review.final_decision is not None
                s.add(
                    HumanReviewEventRow(
                        review_id=str(review.review_id),
                        event_type="decision",
                        actor=actor,
                        reviewer_name=review.reviewer_name,
                        decision=review.final_decision.value,
                        rationale=review.rationale,
                        conditions=list(review.conditions),
                        created_at=review.completed_at or datetime.now(tz=UTC),
                    )
                )
                audit(
                    s,
                    actor=actor,
                    action="human_review.decision",
                    entity_type="human_review",
                    entity_id=str(review.review_id),
                    details={"decision": review.final_decision.value},
                )

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        with self._db.session() as s:
            row = s.get(HumanReviewRow, str(review_id))
            return self._record(row, self._events(s, row.review_id)) if row else None

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        with self._db.session() as s:
            row = s.execute(
                select(HumanReviewRow).where(HumanReviewRow.report_id == str(report_id))
            ).scalar_one_or_none()
            return self._record(row, self._events(s, row.review_id)) if row else None

    def history(self, review_id: UUID) -> list[dict[str, Any]]:
        with self._db.session() as s:
            return [
                {
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "reviewer_name": e.reviewer_name,
                    "decision": e.decision,
                    "rationale": e.rationale,
                    "conditions": e.conditions,
                    "created_at": e.created_at,
                }
                for e in self._events(s, str(review_id))
            ]
