"""Zapis przebiegu sprawdzeń i zdarzeń bezpieczeństwa (SQLite; URL wymienny na Postgres)."""

import json
import statistics
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.schemas import CheckResponse, CheckStatus


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


class SecurityEventRow(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    origin: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(String(500))
    check_id: Mapped[str | None] = mapped_column(String(32))


def _aware(value: datetime | None) -> datetime | None:
    # SQLite gubi strefę czasową; wszystkie znaczniki zapisujemy w UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


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

    # --- zdarzenia bezpieczeństwa ---

    def add_event(self, kind: str, origin: str, detail: str, check_id: str | None = None) -> None:
        with self._session() as db:
            db.add(SecurityEventRow(created_at=_now(), kind=kind, origin=origin, detail=detail[:500], check_id=check_id))
            db.commit()