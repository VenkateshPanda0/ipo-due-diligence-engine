"""
Case workflow services: cases, data versions, field corrections and screening.

Case data is stored as immutable, numbered versions of a CompanyData-shaped JSON
payload. Every manual edit, extraction merge or review resolution creates a new
version; a screening report records the exact version it evaluated. Original
extracted values are never overwritten in place.
"""

from __future__ import annotations

import copy
import enum
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Database
from app.db.models import (
    AuditEventRow,
    CaseDataVersionRow,
    CaseRow,
    DocumentRow,
    ExtractionRunRow,
    ReportRow,
    ReviewItemEventRow,
    ReviewItemRow,
)
from app.db.repositories import SqlReportStorage, audit, latest_version, next_version_number
from app.engine.decision_engine import DecisionEngine
from app.models.company_data import CompanyData
from app.models.enums import ConfidenceLevel, ExtractionMethod, FieldStatus, ListingRoute
from app.models.exceptions import InvalidStateError, NotFoundError
from app.models.extracted_value import ExtractedValue
from app.models.field_paths import get_value, set_value, set_value_in_place, value_type
from app.models.ipo_report import IPOReport


class CaseStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing_documents"
    AWAITING_REVIEW = "awaiting_review"
    READY = "ready_for_screening"
    SCREENED = "screened"
    ARCHIVED = "archived"


class ReviewItemStatus(str, enum.Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    MORE_EVIDENCE_REQUESTED = "more_evidence_requested"
    SUPERSEDED = "superseded"  # replaced by a newer extraction run of the same document


_UNIT_FOR_TYPE = {"decimal": "INR_CRORE", "int": "COUNT", "bool": "BOOLEAN"}


def parse_field_value(path: str, raw: Any) -> Decimal | int | bool:
    """Coerce a user-supplied value to the field's type (strict)."""
    kind = value_type(path)
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.lower() in ("true", "false", "yes", "no"):
            return raw.lower() in ("true", "yes")
        raise ValueError(f"{path} expects a boolean")
    if kind == "int":
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, str))
            or not str(raw).strip().lstrip("-").isdigit()
        ):
            raise ValueError(f"{path} expects an integer")
        return int(raw)
    if isinstance(raw, bool):
        raise ValueError(f"{path} expects a number")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"{path} expects a number") from exc
    if not value.is_finite():
        raise ValueError(f"{path} expects a finite number")
    return value


def _manual_value(
    path: str,
    value: Decimal | int | bool,
    actor: str,
    note: str | None,
    method: ExtractionMethod = ExtractionMethod.MANUAL,
    original: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unit = (
        "PERCENT"
        if (
            "percentage" in path or path.endswith(("_pct", "holding", "allocation", "contribution"))
        )
        and value_type(path) == "decimal"
        else _UNIT_FOR_TYPE[value_type(path)]
    )
    if path.endswith("lock_in_months"):
        unit = "MONTHS"
    notes = [
        f"Entered by {actor}" if method == ExtractionMethod.MANUAL else f"Corrected by {actor}"
    ]
    if note:
        notes.append(note)
    ev = ExtractedValue[Any](
        value=value,
        source_document=(original or {}).get("source_document") or "manual entry",
        document_id=(original or {}).get("document_id"),
        page_number=(original or {}).get("page_number"),
        extraction_method=method,
        confidence=ConfidenceLevel.HIGH,
        confirmed_by_human=method == ExtractionMethod.HUMAN_CORRECTED,
        unit=unit,
        original_text=(original or {}).get("original_text"),
        original_unit=(original or {}).get("original_unit"),
        period_label=(original or {}).get("period_label"),
        raw_text=(original or {}).get("raw_text"),
        field_status=FieldStatus.HUMAN_CONFIRMED
        if method == ExtractionMethod.HUMAN_CORRECTED
        else FieldStatus.MANUAL_ENTRY,
        notes=notes,
    )
    return ev.model_dump(mode="json")


def is_human_value(v: dict[str, Any] | None) -> bool:
    if not v:
        return False
    return bool(v.get("confirmed_by_human")) or v.get("extraction_method") in (
        "manual",
        "human_corrected",
    )


class CaseService:
    """Create cases and manage their versioned data."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # -- cases --------------------------------------------------------------

    def create(
        self,
        *,
        company_name: str,
        listing_route: ListingRoute,
        actor: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        case_id = str(uuid4())
        # Store only what was provided: schema defaults are not facts.
        payload = CompanyData.model_validate(
            {
                "identification": {"company_name": company_name},
                "issue_details": {"listing_route": listing_route.value},
            }
        ).model_dump(mode="json", exclude_unset=True)
        with self._db.session() as s:
            s.add(
                CaseRow(
                    id=case_id,
                    company_name=company_name,
                    listing_route=listing_route.value,
                    status=CaseStatus.DRAFT.value,
                    current_version=1,
                    notes=notes,
                    created_by=actor,
                )
            )
            s.flush()
            s.add(
                CaseDataVersionRow(
                    case_id=case_id,
                    version=1,
                    payload=payload,
                    source="created",
                    created_by=actor,
                    reason="case created",
                )
            )
            audit(
                s,
                actor=actor,
                action="case.created",
                entity_type="case",
                entity_id=case_id,
                case_id=case_id,
                details={"listing_route": listing_route.value},
            )
        return self.get(case_id)

    def _row(self, s: Session, case_id: str) -> CaseRow:
        row = s.get(CaseRow, case_id)
        if row is None:
            raise NotFoundError("case", case_id)
        return row

    @staticmethod
    def _out(row: CaseRow, counts: dict[str, int] | None = None) -> dict[str, Any]:
        return {
            "id": row.id,
            "company_name": row.company_name,
            "listing_route": row.listing_route,
            "status": row.status,
            "current_version": row.current_version,
            "notes": row.notes,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            **(counts or {}),
        }

    def get(self, case_id: str) -> dict[str, Any]:
        with self._db.session() as s:
            row = self._row(s, case_id)
            return self._out(row, self._counts(s, case_id))

    @staticmethod
    def _counts(s: Any, case_id: str) -> dict[str, int]:
        docs = s.execute(
            select(func.count()).select_from(DocumentRow).where(DocumentRow.case_id == case_id)
        ).scalar_one()
        open_items = s.execute(
            select(func.count())
            .select_from(ReviewItemRow)
            .where(
                ReviewItemRow.case_id == case_id,
                ReviewItemRow.status == ReviewItemStatus.OPEN.value,
            )
        ).scalar_one()
        reports = s.execute(
            select(func.count()).select_from(ReportRow).where(ReportRow.case_id == case_id)
        ).scalar_one()
        return {
            "document_count": int(docs),
            "open_review_items": int(open_items),
            "report_count": int(reports),
        }

    @staticmethod
    def _counts_many(s: Any, case_ids: list[str]) -> dict[str, dict[str, int]]:
        """Document / open-item / report counts for many cases in three grouped queries."""
        out = {
            cid: {"document_count": 0, "open_review_items": 0, "report_count": 0}
            for cid in case_ids
        }
        if not case_ids:
            return out
        queries = (
            ("document_count", DocumentRow.case_id, select(DocumentRow.case_id, func.count())),
            (
                "open_review_items",
                ReviewItemRow.case_id,
                select(ReviewItemRow.case_id, func.count()).where(
                    ReviewItemRow.status == ReviewItemStatus.OPEN.value
                ),
            ),
            ("report_count", ReportRow.case_id, select(ReportRow.case_id, func.count())),
        )
        for key, column, stmt in queries:
            for cid, n in s.execute(stmt.where(column.in_(case_ids)).group_by(column)):
                out[cid][key] = int(n)
        return out

    def list_cases(
        self, *, status: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        with self._db.session() as s:
            stmt = select(CaseRow)
            if status:
                stmt = stmt.where(CaseRow.status == status)
            if q:
                escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(CaseRow.company_name.ilike(f"%{escaped}%", escape="\\"))
            total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            rows = (
                s.execute(stmt.order_by(CaseRow.updated_at.desc()).limit(limit).offset(offset))
                .scalars()
                .all()
            )
            counts = self._counts_many(s, [r.id for r in rows])
            return {
                "items": [self._out(r, counts[r.id]) for r in rows],
                "total": int(total),
                "limit": limit,
                "offset": offset,
            }

    def update(
        self,
        case_id: str,
        *,
        actor: str,
        company_name: str | None = None,
        listing_route: ListingRoute | None = None,
        notes: str | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        with self._db.session() as s:
            row = self._row(s, case_id)
            if company_name is not None and company_name != row.company_name:
                changes["company_name"] = company_name
            if listing_route is not None and listing_route.value != row.listing_route:
                changes["listing_route"] = listing_route.value
            if notes is not None:
                row.notes = notes
            if archived is not None:
                row.status = CaseStatus.ARCHIVED.value if archived else CaseStatus.DRAFT.value
                changes["archived"] = archived
            if "company_name" in changes or "listing_route" in changes:
                payload = latest_version(s, case_id).payload  # type: ignore[union-attr]
                if "company_name" in changes:
                    payload = {
                        **payload,
                        "identification": {
                            **payload.get("identification", {}),
                            "company_name": company_name,
                        },
                    }
                    row.company_name = company_name  # type: ignore[assignment]
                if "listing_route" in changes:
                    payload = {
                        **payload,
                        "issue_details": {
                            **payload.get("issue_details", {}),
                            "listing_route": changes["listing_route"],
                        },
                    }
                    row.listing_route = changes["listing_route"]
                self._new_version(
                    s, row, payload, source="metadata", actor=actor, reason="case metadata updated"
                )
            if archived is False:
                s.flush()
                self._refresh_status(s, row)  # restore the status the case's state implies
            row.updated_at = datetime.now(tz=UTC)
            audit(
                s,
                actor=actor,
                action="case.updated",
                entity_type="case",
                entity_id=case_id,
                case_id=case_id,
                details={k: str(v) for k, v in changes.items()},
            )
        return self.get(case_id)

    # -- data versions ------------------------------------------------------------

    @staticmethod
    def _new_version(
        s: Any,
        row: CaseRow,
        payload: dict[str, Any],
        *,
        source: str,
        actor: str,
        reason: str | None = None,
        document_id: str | None = None,
        run_id: str | None = None,
    ) -> int:
        CompanyData.model_validate(payload)  # never persist an invalid snapshot
        version = next_version_number(s, row.id)
        s.add(
            CaseDataVersionRow(
                case_id=row.id,
                version=version,
                payload=payload,
                source=source,
                created_by=actor,
                reason=reason,
                document_id=document_id,
                extraction_run_id=run_id,
            )
        )
        row.current_version = version
        row.updated_at = datetime.now(tz=UTC)
        return version

    def data(self, case_id: str, version: int | None = None) -> dict[str, Any]:
        with self._db.session() as s:
            self._row(s, case_id)
            if version is None:
                v = latest_version(s, case_id)
            else:
                v = s.execute(
                    select(CaseDataVersionRow).where(
                        CaseDataVersionRow.case_id == case_id, CaseDataVersionRow.version == version
                    )
                ).scalar_one_or_none()
            if v is None:
                raise NotFoundError("case data version", f"{case_id}@{version}")
            return {
                "case_id": case_id,
                "version": v.version,
                "source": v.source,
                "reason": v.reason,
                "created_by": v.created_by,
                "created_at": v.created_at,
                "payload": v.payload,
            }

    def versions(self, case_id: str) -> list[dict[str, Any]]:
        with self._db.session() as s:
            self._row(s, case_id)
            rows = (
                s.execute(
                    select(CaseDataVersionRow)
                    .where(CaseDataVersionRow.case_id == case_id)
                    .order_by(CaseDataVersionRow.version.desc())
                )
                .scalars()
                .all()
            )
            return [
                {
                    "version": r.version,
                    "source": r.source,
                    "reason": r.reason,
                    "created_by": r.created_by,
                    "created_at": r.created_at,
                    "document_id": r.document_id,
                }
                for r in rows
            ]

    def replace_data(
        self, case_id: str, payload: dict[str, Any], *, actor: str, reason: str | None
    ) -> dict[str, Any]:
        """Replace the case data with a manually prepared CompanyData payload."""
        with self._db.session() as s:
            row = self._row(s, case_id)
            if row.status == CaseStatus.ARCHIVED.value:
                raise InvalidStateError("case", row.status, "Archived cases cannot be edited.")
            merged = dict(payload)
            merged["identification"] = {
                **payload.get("identification", {}),
                "company_name": row.company_name,
            }
            merged.setdefault("issue_details", {})
            merged["issue_details"] = {
                **merged["issue_details"],
                "listing_route": row.listing_route,
            }
            normalised = CompanyData.model_validate(merged).model_dump(
                mode="json", exclude_unset=True
            )
            version = self._new_version(
                s,
                row,
                normalised,
                source="manual",
                actor=actor,
                reason=reason or "manual data entry",
            )
            audit(
                s,
                actor=actor,
                action="case.data_replaced",
                entity_type="case",
                entity_id=case_id,
                case_id=case_id,
                details={"version": version},
            )
            self._refresh_status(s, row)
        return self.data(case_id)

    def set_fields(
        self, case_id: str, updates: list[dict[str, Any]], *, actor: str
    ) -> dict[str, Any]:
        """Set individual fields manually. Each update: {field_path, value|null, note}."""
        with self._db.session() as s:
            row = self._row(s, case_id)
            if row.status == CaseStatus.ARCHIVED.value:
                raise InvalidStateError("case", row.status, "Archived cases cannot be edited.")
            # One private copy of the stored (append-only) version, then in-place edits.
            payload = copy.deepcopy(latest_version(s, case_id).payload)  # type: ignore[union-attr]
            changed: list[str] = []
            for upd in updates:
                path = upd["field_path"]
                value_type(path)
                if upd.get("value") is None:
                    set_value_in_place(payload, path, None)
                else:
                    value = parse_field_value(path, upd["value"])
                    set_value_in_place(
                        payload,
                        path,
                        _manual_value(path, value, actor, upd.get("note")),
                        period_end=upd.get("period_end"),
                    )
                changed.append(path)
            version = self._new_version(
                s,
                row,
                payload,
                source="manual",
                actor=actor,
                reason=f"manual edit of {len(changed)} field(s)",
            )
            audit(
                s,
                actor=actor,
                action="case.fields_set",
                entity_type="case",
                entity_id=case_id,
                case_id=case_id,
                details={"version": version, "fields": changed},
            )
            self._refresh_status(s, row)
        return self.data(case_id)

    @staticmethod
    def _refresh_status(s: Any, row: CaseRow) -> None:
        if row.status == CaseStatus.ARCHIVED.value:
            return
        processing = s.execute(
            select(func.count())
            .select_from(DocumentRow)
            .where(
                DocumentRow.case_id == row.id, DocumentRow.status.in_(("uploaded", "extracting"))
            )
        ).scalar_one()
        open_items = s.execute(
            select(func.count())
            .select_from(ReviewItemRow)
            .where(
                ReviewItemRow.case_id == row.id, ReviewItemRow.status == ReviewItemStatus.OPEN.value
            )
        ).scalar_one()
        if processing:
            row.status = CaseStatus.PROCESSING.value
        elif open_items:
            row.status = CaseStatus.AWAITING_REVIEW.value
        else:
            # "Screened" only while a report exists for the current data version; once the
            # data changes the case needs screening again.
            screened = s.execute(
                select(ReportRow.report_id)
                .where(ReportRow.case_id == row.id, ReportRow.data_version == row.current_version)
                .limit(1)
            ).first()
            row.status = CaseStatus.SCREENED.value if screened else CaseStatus.READY.value

    def history(self, case_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._db.session() as s:
            self._row(s, case_id)
            rows = (
                s.execute(
                    select(AuditEventRow)
                    .where(AuditEventRow.case_id == case_id)
                    .order_by(AuditEventRow.id.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                {
                    "ts": r.ts,
                    "actor": r.actor,
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "details": r.details,
                }
                for r in rows
            ]

    # -- review workspace -----------------------------------------------------------

    def review_items(
        self,
        case_id: str | None = None,
        status: str | None = "open",
        *,
        item_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Review items with their event history and the case's current value.

        Events are fetched in one query and each case's latest payload is loaded once
        (not once per item).
        """
        with self._db.session() as s:
            stmt = select(ReviewItemRow)
            if item_id:
                stmt = stmt.where(ReviewItemRow.id == item_id)
            if case_id:
                stmt = stmt.where(ReviewItemRow.case_id == case_id)
            if status:
                stmt = stmt.where(ReviewItemRow.status == status)
            rows = s.execute(stmt.order_by(ReviewItemRow.created_at)).scalars().all()
            events_by_item: dict[str, list[ReviewItemEventRow]] = {}
            if rows:
                events = s.execute(
                    select(ReviewItemEventRow)
                    .where(ReviewItemEventRow.item_id.in_([r.id for r in rows]))
                    .order_by(ReviewItemEventRow.id)
                ).scalars()
                for e in events:
                    events_by_item.setdefault(e.item_id, []).append(e)
            payloads: dict[str, dict[str, Any]] = {}
            out = []
            for r in rows:
                if r.case_id not in payloads:
                    latest = latest_version(s, r.case_id)
                    payloads[r.case_id] = latest.payload if latest else {}
                current = get_value(payloads[r.case_id], r.field_path)
                out.append(
                    {
                        "id": r.id,
                        "case_id": r.case_id,
                        "document_id": r.document_id,
                        "run_id": r.run_id,
                        "field_path": r.field_path,
                        "reason": r.reason,
                        "field_status": r.field_status,
                        "status": r.status,
                        "proposed": r.proposed,
                        "current": current,
                        "candidates": r.candidates,
                        "created_at": r.created_at,
                        "resolved_at": r.resolved_at,
                        "history": [
                            {
                                "action": e.action,
                                "actor": e.actor,
                                "reason": e.reason,
                                "original_value": e.original_value,
                                "new_value": e.new_value,
                                "data_version": e.data_version,
                                "created_at": e.created_at,
                            }
                            for e in events_by_item.get(r.id, [])
                        ],
                    }
                )
            return out

    def resolve_item(
        self, item_id: str, *, action: str, actor: str, reason: str | None, value: Any = None
    ) -> dict[str, Any]:
        """Confirm, correct, reject or request more evidence for a review item."""
        if action not in ("confirm", "correct", "reject", "request_more_evidence"):
            raise ValueError("action must be confirm, correct, reject or request_more_evidence")
        if action in ("correct", "reject") and not (reason and reason.strip()):
            raise ValueError("A reason is required to correct or reject a value.")
        with self._db.session() as s:
            item = s.get(ReviewItemRow, item_id)
            if item is None:
                raise NotFoundError("review item", item_id)
            if item.status not in (
                ReviewItemStatus.OPEN.value,
                ReviewItemStatus.MORE_EVIDENCE_REQUESTED.value,
            ):
                raise InvalidStateError(
                    "review item", item.status, "This review item is already resolved."
                )
            case = self._row(s, item.case_id)
            payload = latest_version(s, item.case_id).payload  # type: ignore[union-attr]
            original = get_value(payload, item.field_path) or item.proposed
            new_value: dict[str, Any] | None = None
            version: int | None = None
            if action == "confirm":
                if (
                    not original
                    or original.get("value") is None
                    or "extraction_method" not in original
                ):
                    raise InvalidStateError(
                        "review item",
                        item.status,
                        "There is no normalised value to confirm (e.g. unknown unit); "
                        "use 'correct'.",
                    )
                confirmed = dict(original)
                confirmed.update(
                    {
                        "confirmed_by_human": True,
                        "field_status": FieldStatus.HUMAN_CONFIRMED.value,
                        "notes": [
                            *original.get("notes", []),
                            f"Confirmed by {actor}" + (f": {reason}" if reason else ""),
                        ],
                    }
                )
                new_value = ExtractedValue[Any].model_validate(confirmed).model_dump(mode="json")
                item.status = ReviewItemStatus.CONFIRMED.value
            elif action == "correct":
                parsed = parse_field_value(item.field_path, value)
                new_value = _manual_value(
                    item.field_path,
                    parsed,
                    actor,
                    reason,
                    ExtractionMethod.HUMAN_CORRECTED,
                    original,
                )
                item.status = ReviewItemStatus.CORRECTED.value
            elif action == "reject":
                new_value = None
                item.status = ReviewItemStatus.REJECTED.value
            else:
                item.status = ReviewItemStatus.MORE_EVIDENCE_REQUESTED.value
            if action != "request_more_evidence":
                payload = set_value(payload, item.field_path, new_value)
                version = self._new_version(
                    s,
                    case,
                    payload,
                    source="review",
                    actor=actor,
                    reason=f"{action} {item.field_path}",
                )
                item.resolved_at = datetime.now(tz=UTC)
            s.add(
                ReviewItemEventRow(
                    item_id=item.id,
                    action=action,
                    actor=actor,
                    reason=reason,
                    original_value=original,
                    new_value=new_value,
                    data_version=version,
                )
            )
            audit(
                s,
                actor=actor,
                action=f"review_item.{action}",
                entity_type="review_item",
                entity_id=item.id,
                case_id=item.case_id,
                details={"field_path": item.field_path, "data_version": version},
            )
            s.flush()
            self._refresh_status(s, case)
        return self.review_items(status=None, item_id=item_id)[0]


class CaseScreeningService:
    """Screen the current version of a case and persist an immutable report."""

    def __init__(self, db: Database, engine: DecisionEngine, reports: SqlReportStorage) -> None:
        self._db = db
        self._engine = engine
        self._reports = reports

    def screen(self, case_id: str, *, actor: str) -> IPOReport:
        with self._db.session() as s:
            case = s.get(CaseRow, case_id)
            if case is None:
                raise NotFoundError("case", case_id)
            if case.status == CaseStatus.ARCHIVED.value:
                raise InvalidStateError("case", case.status, "Archived cases cannot be screened.")
            busy = s.execute(
                select(func.count())
                .select_from(DocumentRow)
                .where(
                    DocumentRow.case_id == case_id,
                    DocumentRow.status.in_(("uploaded", "extracting")),
                )
            ).scalar_one()
            if busy:
                raise InvalidStateError("case", case.status, "Documents are still being processed.")
            version = latest_version(s, case_id)
            assert version is not None
            docs = (
                s.execute(select(DocumentRow.sha256).where(DocumentRow.case_id == case_id))
                .scalars()
                .all()
            )
            runs = (
                s.execute(
                    select(ExtractionRunRow.id)
                    .join(DocumentRow, ExtractionRunRow.document_id == DocumentRow.id)
                    .where(DocumentRow.case_id == case_id)
                )
                .scalars()
                .all()
            )
            company = CompanyData.model_validate(version.payload)
            data_version = version.version
        report = self._engine.evaluate(
            company, case_id=UUID(case_id), document_ids=list(docs), extraction_run_ids=list(runs)
        )
        self._reports.save(
            report.report_id, report, case_id=case_id, data_version=data_version, created_by=actor
        )
        with self._db.session() as s:
            case = s.get(CaseRow, case_id)
            assert case is not None
            case.updated_at = datetime.now(tz=UTC)
            CaseService._refresh_status(s, case)  # screened, unless review items remain open
        return report

    def list_reports(self, case_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._db.session() as s:
            # Listing columns only: the report payload can be large and is not needed here.
            stmt = select(
                ReportRow.report_id,
                ReportRow.case_id,
                ReportRow.data_version,
                ReportRow.ruleset_version,
                ReportRow.outcome,
                ReportRow.legacy_status,
                ReportRow.company_name,
                ReportRow.created_by,
                ReportRow.created_at,
            )
            if case_id:
                stmt = stmt.where(ReportRow.case_id == case_id)
            rows = s.execute(stmt.order_by(ReportRow.created_at.desc()).limit(limit)).all()
            return [
                {
                    "report_id": r.report_id,
                    "case_id": r.case_id,
                    "data_version": r.data_version,
                    "ruleset_version": r.ruleset_version,
                    "outcome": r.outcome,
                    "legacy_status": r.legacy_status,
                    "company_name": r.company_name,
                    "created_by": r.created_by,
                    "created_at": r.created_at,
                }
                for r in rows
            ]


def dashboard(db: Database) -> dict[str, Any]:
    """Aggregate counts for the dashboard (all computed from stored data)."""
    with db.session() as s:

        def count(stmt: Any) -> int:
            return int(s.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())

        status_rows = s.execute(select(CaseRow.status, func.count()).group_by(CaseRow.status)).all()
        outcome_rows = s.execute(
            select(ReportRow.outcome, func.count()).group_by(ReportRow.outcome)
        ).all()
        by_status: dict[str, int] = {str(k): int(v) for k, v in status_rows}
        latest_outcomes: dict[str, int] = {str(k): int(v) for k, v in outcome_rows}
        recent = (
            s.execute(select(AuditEventRow).order_by(AuditEventRow.id.desc()).limit(15))
            .scalars()
            .all()
        )
        return {
            "cases_total": count(select(CaseRow)),
            "cases_by_status": {k: int(v) for k, v in by_status.items()},
            "cases_awaiting_review": int(by_status.get(CaseStatus.AWAITING_REVIEW.value, 0)),
            "open_review_items": count(
                select(ReviewItemRow).where(ReviewItemRow.status == ReviewItemStatus.OPEN.value)
            ),
            "reports_total": count(select(ReportRow)),
            "reports_by_outcome": {str(k): int(v) for k, v in latest_outcomes.items()},
            "documents_failed": count(select(DocumentRow).where(DocumentRow.status == "failed")),
            "documents_processing": count(
                select(DocumentRow).where(DocumentRow.status.in_(("uploaded", "extracting")))
            ),
            "recent_activity": [
                {
                    "ts": r.ts,
                    "actor": r.actor,
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "case_id": r.case_id,
                }
                for r in recent
            ],
        }
