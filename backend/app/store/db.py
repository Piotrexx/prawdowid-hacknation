"""Zapis przebiegu sprawdzeń, spraw moderatora i zdarzeń bezpieczeństwa (SQLite; URL wymienny na Postgres)."""

import json
import statistics
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.schemas import (
    CaseOut,
    CheckListItem,
    CheckResponse,
    CheckStatus,
    MetricsResponse,
    SecurityEventOut,
    Verdict,
)


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CheckRow(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    cache_key: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class CaseRow(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    risk: Mapped[str] = mapped_column(String(16), default="standard")
    occurrences: Mapped[int] = mapped_column(default=1)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[list["CaseLinkRow"]] = relationship(cascade="all, delete-orphan")


class CaseLinkRow(Base):
    __tablename__ = "case_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    check_id: Mapped[str] = mapped_column(String(32), index=True)


class SecurityEventRow(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    origin: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(Text)
    check_id: Mapped[str | None] = mapped_column(String(32))


def _aware(value: datetime | None) -> datetime | None:
    # SQLite gubi strefę czasową; wszystkie znaczniki zapisujemy w UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _case_out(row: CaseRow) -> CaseOut:
    return CaseOut(
        id=row.id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        claim_text=row.claim_text,
        status=row.status,
        risk=row.risk,
        occurrences=row.occurrences,
        channels=row.channels,
        notified_at=_aware(row.notified_at),
        note=row.note,
        check_ids=[link.check_id for link in row.links],
    )


class Store:
    def __init__(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)

    def _session(self) -> Session:
        return Session(self._engine, expire_on_commit=False)

    # --- sprawdzenia ---

    def save_check(self, response: CheckResponse, session_id: str | None, cache_key: str | None) -> None:
        with self._session() as db:
            db.merge(
                CheckRow(
                    id=response.id,
                    created_at=response.created_at,
                    channel=response.channel,
                    session_id=session_id,
                    cache_key=cache_key,
                    status=response.status.value,
                    error_code=response.error_code,
                    result=json.loads(response.model_dump_json()),
                )
            )
            db.commit()

    def get_check(self, check_id: str) -> CheckResponse | None:
        with self._session() as db:
            row = db.get(CheckRow, check_id)
            return CheckResponse.model_validate(row.result) if row else None

    def find_cached(self, cache_key: str, since: datetime) -> CheckResponse | None:
        with self._session() as db:
            row = db.scalars(
                select(CheckRow)
                .where(CheckRow.cache_key == cache_key, CheckRow.status == CheckStatus.COMPLETED.value)
                .where(CheckRow.created_at >= since)
                .order_by(CheckRow.created_at.desc())
                .limit(1)
            ).first()
            return CheckResponse.model_validate(row.result) if row else None

    def _forget_checks(self, db: Session, condition) -> int:
        ids = list(db.scalars(select(CheckRow.id).where(condition)))
        if ids:
            db.execute(delete(CaseLinkRow).where(CaseLinkRow.check_id.in_(ids)))
            db.execute(delete(SecurityEventRow).where(SecurityEventRow.check_id.in_(ids)))
            db.execute(delete(CheckRow).where(CheckRow.id.in_(ids)))
        return len(ids)

    def delete_session(self, session_id: str) -> int:
        with self._session() as db:
            deleted = self._forget_checks(db, CheckRow.session_id == session_id)
            db.commit()
            return deleted

    def purge_older_than(self, cutoff: datetime) -> int:
        with self._session() as db:
            deleted = self._forget_checks(db, CheckRow.created_at < cutoff)
            db.execute(delete(SecurityEventRow).where(SecurityEventRow.created_at < cutoff))
            db.commit()
            return deleted

    def list_checks(self, limit: int) -> list[CheckListItem]:
        return [self._list_item(r) for r in self._recent_rows(limit)]

    def all_results(self) -> list[CheckResponse]:
        return [CheckResponse.model_validate(r.result) for r in self._recent_rows(None)]

    def _recent_rows(self, limit: int | None) -> list[CheckRow]:
        with self._session() as db:
            query = select(CheckRow).order_by(CheckRow.created_at.desc())
            return list(db.scalars(query.limit(limit) if limit else query))

    @staticmethod
    def _list_item(row: CheckRow) -> CheckListItem:
        result = row.result
        return CheckListItem(
            id=row.id,
            created_at=_aware(row.created_at),
            channel=row.channel,
            status=row.status,
            input_kind=result["input"]["kind"],
            input_preview=result["input"]["text"][:140],
            verdicts=[c["verdict"] for c in result["claims"]],
            duration_ms=result["meta"]["duration_ms"],
            cost_usd=result["meta"]["cost_usd"],
        )

    # --- zdarzenia bezpieczeństwa ---

    def add_event(self, kind: str, origin: str, detail: str, check_id: str | None = None) -> None:
        with self._session() as db:
            db.add(SecurityEventRow(created_at=_now(), kind=kind, origin=origin, detail=detail[:500], check_id=check_id))
            db.commit()

    def list_events(self, limit: int) -> list[SecurityEventOut]:
        with self._session() as db:
            rows = db.scalars(select(SecurityEventRow).order_by(SecurityEventRow.created_at.desc()).limit(limit))
            return [
                SecurityEventOut(
                    id=r.id, created_at=_aware(r.created_at), kind=r.kind, origin=r.origin, detail=r.detail, check_id=r.check_id
                )
                for r in rows
            ]

    # --- sprawy moderatora ---

    def open_cases(self) -> list[CaseOut]:
        return self.list_cases(exclude_status="resolved")

    def list_cases(self, status: str | None = None, exclude_status: str | None = None) -> list[CaseOut]:
        with self._session() as db:
            query = select(CaseRow).order_by(CaseRow.updated_at.desc())
            if status:
                query = query.where(CaseRow.status == status)
            if exclude_status:
                query = query.where(CaseRow.status != exclude_status)
            return [_case_out(r) for r in db.scalars(query)]

    def create_case(self, claim_text: str, risk: str, channel: str, check_id: str) -> CaseOut:
        with self._session() as db:
            row = CaseRow(
                created_at=_now(), updated_at=_now(), claim_text=claim_text, risk=risk, channels=[channel],
                links=[CaseLinkRow(check_id=check_id)],
            )
            db.add(row)
            db.commit()
            return _case_out(row)

    def bump_case(self, case_id: int, risk: str, channel: str, check_id: str) -> CaseOut:
        with self._session() as db:
            row = db.get(CaseRow, case_id)
            row.occurrences += 1
            row.updated_at = _now()
            row.channels = sorted({*row.channels, channel})
            if risk == "high":
                row.risk = "high"
            row.links.append(CaseLinkRow(check_id=check_id))
            db.commit()
            return _case_out(row)

    def update_case(self, case_id: int, status: str | None = None, note: str | None = None, notified: bool = False) -> CaseOut | None:
        with self._session() as db:
            row = db.get(CaseRow, case_id)
            if row is None:
                return None
            if status:
                row.status = status
            if note is not None:
                row.note = note
            if notified:
                row.notified_at = _now()
            row.updated_at = _now()
            db.commit()
            return _case_out(row)

    # --- obserwowalność ---

    def metrics(self) -> MetricsResponse:
        results = self.all_results()
        completed = [r for r in results if r.status == CheckStatus.COMPLETED]
        verdicts = Counter(c.verdict.value for r in completed for c in r.claims)
        # Wstrzymanie się liczymy na poziomie twierdzeń podlegających weryfikacji.
        decidable = sum(n for v, n in verdicts.items() if v != Verdict.NOT_VERIFIABLE.value)
        durations = sorted(r.meta.duration_ms for r in results if not r.meta.cached)
        costs = [r.meta.cost_usd for r in results if r.meta.cost_usd is not None]
        with self._session() as db:
            events = dict(db.execute(select(SecurityEventRow.kind, func.count()).group_by(SecurityEventRow.kind)).all())
            open_cases = db.scalar(select(func.count()).select_from(CaseRow).where(CaseRow.status != "resolved"))
        return MetricsResponse(
            checks_total=len(results),
            by_status=dict(Counter(r.status.value for r in results)),
            by_channel=dict(Counter(r.channel for r in results)),
            by_verdict=dict(verdicts),
            abstention_rate=round(verdicts[Verdict.INSUFFICIENT.value] / decidable, 3) if decidable else None,
            median_duration_ms=int(statistics.median(durations)) if durations else None,
            p95_duration_ms=durations[min(len(durations) - 1, int(len(durations) * 0.95))] if durations else None,
            tokens_in=sum(r.meta.tokens_in for r in results),
            tokens_out=sum(r.meta.tokens_out for r in results),
            cost_usd_total=round(sum(costs), 4) if costs else None,
            cost_usd_per_1000=round(sum(costs) / len(costs) * 1000, 2) if costs else None,
            errors=dict(Counter(r.error_code for r in results if r.error_code)),
            security_events=events,
            open_cases=open_cases or 0,
        )
