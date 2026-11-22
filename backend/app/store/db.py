"""Zapis przebiegu sprawdzeń, spraw moderatora, zgód, archiwum i zdarzeń.

Wymagany jest PostgreSQL z rozszerzeniem pgvector – to jedyne źródło prawdy dla
przebiegu sprawdzeń i korpusu. Warstwa ORM jest cienka: tabele opisują tylko to,
co usługa musi pamiętać.
"""

import json
import logging
import statistics
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.schemas import (
    ArchiveOut,
    CaseOut,
    CheckListItem,
    CheckResponse,
    CheckStatus,
    ConsentResponse,
    MetricsResponse,
    SecurityEventOut,
    Verdict,
)
from app.store.models import (
    ArchivedMaterialRow,
    Base,
    CaseLinkRow,
    CaseRow,
    CheckRow,
    ConsentRow,
    SecurityEventRow,
)

log = logging.getLogger("store")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
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
        channels=row.channels or [],
        notified_at=_aware(row.notified_at),
        note=row.note,
        check_ids=[link.check_id for link in row.links],
        comments_count=len(row.comments or []),
    )


def _archive_out(row: ArchivedMaterialRow) -> ArchiveOut:
    return ArchiveOut(
        id=row.id,
        check_id=row.check_id,
        created_at=_aware(row.created_at),
        retention_until=_aware(row.retention_until),
        url=row.url,
        title=row.title,
        excerpt=row.excerpt,
        content_hash=row.content_hash,
        legal_basis=row.legal_basis,
    )


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
        self._migrate_articles()

    def _migrate_articles(self) -> None:
        """Lekka migracja bazy z wcześniejszej wersji (bez Alembica)."""
        statements = [
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS external_id VARCHAR(160)",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS text TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_type VARCHAR(24) DEFAULT 'official'",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS tier INTEGER DEFAULT 1",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS license TEXT DEFAULT ''",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS storage VARCHAR(16) DEFAULT 'excerpt'",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS claim_reviewed TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS rating VARCHAR(160)",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS appearance_urls JSONB DEFAULT '[]'::jsonb",
            "UPDATE articles SET external_id = source_key || ':' || left(md5(url), 12) WHERE external_id IS NULL",
            "ALTER TABLE articles ALTER COLUMN external_id SET NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS articles_external_id_key ON articles(external_id)",
            "ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_url_key",
            "DROP INDEX IF EXISTS articles_url_key",
        ]
        with self._engine.begin() as conn:
            for statement in statements:
                try:
                    conn.execute(text(statement))
                except Exception:
                    log.warning("migracja schematu: nie udało się wykonać %s", statement, exc_info=True)

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
            if row is None:
                return None
            try:
                return CheckResponse.model_validate(row.result)
            except Exception:
                log.warning("pominięto sprawdzenie %s zapisane w nieaktualnym schemacie", check_id)
                return None

    def get_check_session(self, check_id: str) -> str | None:
        with self._session() as db:
            row = db.get(CheckRow, check_id)
            return row.session_id if row else None

    def find_cached(self, cache_key: str, since: datetime) -> CheckResponse | None:
        with self._session() as db:
            row = db.scalars(
                select(CheckRow)
                .where(CheckRow.cache_key == cache_key, CheckRow.status == CheckStatus.COMPLETED.value)
                .where(CheckRow.created_at >= since)
                .order_by(CheckRow.created_at.desc())
                .limit(1)
            ).first()
            if row is None:
                return None
            try:
                return CheckResponse.model_validate(row.result)
            except Exception:
                return None

    def _forget_checks(self, db: Session, condition) -> int:
        ids = list(db.scalars(select(CheckRow.id).where(condition)))
        if ids:
            db.execute(delete(CaseLinkRow).where(CaseLinkRow.check_id.in_(ids)))
            db.execute(delete(SecurityEventRow).where(SecurityEventRow.check_id.in_(ids)))
            db.execute(delete(ArchivedMaterialRow).where(ArchivedMaterialRow.check_id.in_(ids)))
            db.execute(delete(CheckRow).where(CheckRow.id.in_(ids)))
        return len(ids)

    def delete_session(self, session_id: str) -> int:
        with self._session() as db:
            deleted = self._forget_checks(db, CheckRow.session_id == session_id)
            db.execute(delete(ConsentRow).where(ConsentRow.session_id == session_id))
            db.execute(delete(ArchivedMaterialRow).where(ArchivedMaterialRow.session_id == session_id))
            # Sprawa bez żadnego powiązanego zgłoszenia nie ma już treści użytkownika.
            db.execute(delete(CaseRow).where(~CaseRow.links.any()))
            db.commit()
            return deleted

    def purge_older_than(self, cutoff: datetime) -> int:
        with self._session() as db:
            deleted = self._forget_checks(db, CheckRow.created_at < cutoff)
            db.execute(delete(SecurityEventRow).where(SecurityEventRow.created_at < cutoff))
            db.execute(delete(ArchivedMaterialRow).where(ArchivedMaterialRow.retention_until < _now()))
            db.execute(delete(CaseRow).where(~CaseRow.links.any()))
            db.commit()
            return deleted

    def list_checks(self, limit: int) -> list[CheckListItem]:
        return [self._list_item(r) for r in self._recent_rows(limit)]

    def all_results(self) -> list[CheckResponse]:
        results = []
        for row in self._recent_rows(None):
            try:
                results.append(CheckResponse.model_validate(row.result))
            except Exception:
                log.warning("pominięto sprawdzenie %s zapisane w nieaktualnym schemacie", row.id)
        return results

    def _recent_rows(self, limit: int | None) -> list[CheckRow]:
        with self._session() as db:
            query = select(CheckRow).order_by(CheckRow.created_at.desc())
            return list(db.scalars(query.limit(limit) if limit else query))

    @staticmethod
    def _list_item(row: CheckRow) -> CheckListItem:
        result = row.result or {}
        input_info = result.get("input") or {}
        meta = result.get("meta") or {}
        claims = result.get("claims") or []
        return CheckListItem(
            id=row.id,
            created_at=_aware(row.created_at),
            channel=row.channel,
            status=row.status,
            input_kind=input_info.get("kind", "text"),
            input_preview=(input_info.get("text") or "")[:140],
            verdicts=[c.get("verdict") for c in claims if c.get("verdict")],
            duration_ms=int(meta.get("duration_ms") or 0),
            cost_usd=meta.get("cost_usd"),
            keywords=result.get("keywords") or [],
            factcheck_count=len(result.get("fact_check_results") or []),
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

    # --- zgody na politykę prywatności ---

    def record_consent(self, session_id: str, policy_version: str, accepted: bool) -> ConsentResponse:
        now = _now()
        with self._session() as db:
            db.merge(
                ConsentRow(
                    session_id=session_id, policy_version=policy_version, accepted=accepted, recorded_at=now
                )
            )
            db.commit()
        return ConsentResponse(
            session_id=session_id, policy_version=policy_version, accepted=accepted, recorded_at=now
        )

    def get_consent(self, session_id: str, policy_version: str) -> ConsentResponse | None:
        with self._session() as db:
            row = db.get(ConsentRow, (session_id, policy_version))
            if row is None:
                return None
            return ConsentResponse(
                session_id=row.session_id,
                policy_version=row.policy_version,
                accepted=row.accepted,
                recorded_at=_aware(row.recorded_at),
            )

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
            row.channels = sorted({*(row.channels or []), channel})
            if risk == "high":
                row.risk = "high"
            # Nie dodawaj duplikatów – po deduplikacji cache_key ten sam check_id może trafić tu dwa razy.
            existing_ids = {link.check_id for link in row.links}
            if check_id not in existing_ids:
                row.links.append(CaseLinkRow(check_id=check_id))
            db.commit()
            return _case_out(row)

    def update_case(
        self,
        case_id: int,
        status: str | None = None,
        note: str | None = None,
        notified: bool = False,
        claim_text: str | None = None,
        risk: str | None = None,
    ) -> CaseOut | None:
        with self._session() as db:
            row = db.get(CaseRow, case_id)
            if row is None:
                return None
            if status:
                row.status = status
            if note is not None:
                row.note = note
            if claim_text is not None:
                row.claim_text = claim_text.strip()
            if risk is not None:
                row.risk = risk
            if notified:
                row.notified_at = _now()
            row.updated_at = _now()
            db.commit()
            return _case_out(row)

    def get_case(self, case_id: int) -> CaseOut | None:
        with self._session() as db:
            row = db.get(CaseRow, case_id)
            return _case_out(row) if row else None

    # --- kontrolowana archiwizacja ---

    def create_archive(
        self,
        *,
        check_id: str,
        session_id: str | None,
        url: str | None,
        title: str | None,
        excerpt: str,
        content_hash: str,
        legal_basis: str,
        retention_days: int,
    ) -> ArchiveOut:
        now = _now()
        row = ArchivedMaterialRow(
            id=uuid.uuid4().hex,
            check_id=check_id,
            session_id=session_id,
            url=url,
            title=title,
            excerpt=excerpt,
            content_hash=content_hash,
            legal_basis=legal_basis,
            created_at=now,
            retention_until=now + timedelta(days=retention_days),
        )
        with self._session() as db:
            db.add(row)
            db.commit()
        self.add_event("archive_created", f"check:{check_id}", "zapisano kontrolowaną kopię materiału", check_id)
        return _archive_out(row)

    def get_archive(self, archive_id: str) -> ArchiveOut | None:
        with self._session() as db:
            row = db.get(ArchivedMaterialRow, archive_id)
            return _archive_out(row) if row else None

    def list_archives(self, limit: int = 100) -> list[ArchiveOut]:
        with self._session() as db:
            rows = db.scalars(
                select(ArchivedMaterialRow).order_by(ArchivedMaterialRow.created_at.desc()).limit(limit)
            )
            return [_archive_out(row) for row in rows]

    def delete_archive(self, archive_id: str) -> bool:
        with self._session() as db:
            row = db.get(ArchivedMaterialRow, archive_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
        self.add_event("archive_deleted", f"archive:{archive_id}", "usunięto materiał archiwalny")
        return True

    # --- obserwowalność ---

    def get_setting(self, key: str) -> dict | None:
        """Ustawienie zapisane w panelu; brak wpisu = wartość z `.env`."""
        from app.store.models import AppSettingRow

        with self._session() as db:
            row = db.get(AppSettingRow, key)
            return dict(row.value or {}) if row else None

    def set_setting(self, key: str, value: dict, updated_by: str | None) -> None:
        from app.store.models import AppSettingRow

        with self._session() as db:
            row = db.get(AppSettingRow, key)
            if row is None:
                db.add(
                    AppSettingRow(key=key, value=value, updated_at=_now(), updated_by=updated_by)
                )
            else:
                row.value = value
                row.updated_at = _now()
                row.updated_by = updated_by
            db.commit()

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
            consents = db.scalar(select(func.count()).select_from(ConsentRow).where(ConsentRow.accepted.is_(True)))
        factchecks = [len(r.fact_check_results) for r in completed]
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
            avg_factchecks=round(sum(factchecks) / len(factchecks), 2) if factchecks else 0.0,
            consents=consents or 0,
        )
