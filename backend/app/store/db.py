"""Zapis przebiegu sprawdzeń i zdarzeń bezpieczeństwa (PostgreSQL + pgvector)."""

import json
from datetime import UTC, datetime

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.schemas import CheckResponse, CheckStatus
from app.store.models import Base, CheckRow, SecurityEventRow


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


class Store:
    def __init__(self, database_url: str):
        if not database_url.startswith("postgresql"):
            raise ValueError(
                "Prawdowid wymaga PostgreSQL z rozszerzeniem pgvector. "
                "Ustaw DATABASE_URL na postgresql+psycopg://..."
            )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._ensure_schema()

    @property
    def engine(self) -> Engine:
        return self._engine

    def _ensure_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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
