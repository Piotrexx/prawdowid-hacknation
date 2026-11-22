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
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, delete, func, or_, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.schemas import (
    ArchiveOut,
    CaseOut,
    CheckListItem,
    CheckResponse,
    CheckStatus,
    ConsentResponse,
    EventAnchor,
    EventDetailOut,
    EventGraphResponse,
    EventLinkOut,
    EventMemberOut,
    EventOut,
    GraphEdge,
    GraphNode,
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
    EventLinkRow,
    EventMemberRow,
    EventRow,
    SecurityEventRow,
)
from app.textutil import truncate

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


def _merge_anchors(current: list, incoming: list) -> list:
    """Scala kotwice po identyfikatorze incydentu, zachowując kolejność i limit."""
    merged: dict[str, dict] = {}
    for raw in [*(current or []), *(incoming or [])]:
        if not isinstance(raw, dict):
            continue
        incident_id = str(raw.get("incident_id") or "")
        if not incident_id:
            continue
        merged.setdefault(incident_id, raw)
    return list(merged.values())[:20]


def _anchor_date(raw: object) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _event_anchor(raw: dict) -> EventAnchor:
    return EventAnchor(
        incident_id=str(raw.get("incident_id") or ""),
        title=str(raw.get("title") or ""),
        publisher=str(raw.get("publisher") or ""),
        url=str(raw.get("url") or ""),
        date=_anchor_date(raw.get("date")),
        note=str(raw.get("note") or ""),
    )


def _event_out(row: EventRow) -> EventOut:
    return EventOut(
        id=row.id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        title=row.title,
        topic=row.topic or "",
        public_label=row.public_label or "",
        summary=row.summary or "",
        status=row.status,
        merged_into=row.merged_into,
        risk=row.risk,
        member_count=row.member_count or 0,
        proposed_count=row.proposed_count or 0,
        keywords=row.keywords or [],
        verdicts=row.verdicts or {},
        anchors=[_event_anchor(item) for item in (row.anchors or []) if isinstance(item, dict)],
        first_seen=_aware(row.first_seen),
        last_seen=_aware(row.last_seen),
    )


def _event_member_out(row: EventMemberRow) -> EventMemberOut:
    return EventMemberOut(
        id=row.id,
        event_id=row.event_id,
        check_id=row.check_id,
        claim_id=row.claim_id,
        claim_text=row.claim_text,
        verdict=Verdict(row.verdict) if row.verdict in {v.value for v in Verdict} else None,
        risk=row.risk,
        score=row.score or 0.0,
        reason=row.reason or "",
        status=row.status,
        source=row.source,
        created_at=_aware(row.created_at),
        reviewed_by=row.reviewed_by,
        reviewed_at=_aware(row.reviewed_at),
    )


def _event_link_out(row: EventLinkRow) -> EventLinkOut:
    return EventLinkOut(
        id=row.id,
        src_event_id=row.src_event_id,
        dst_event_id=row.dst_event_id,
        relation=row.relation,
        score=row.score or 0.0,
        reason=row.reason or "",
        evidence=row.evidence or {},
        model=row.model,
        status=row.status,
        created_at=_aware(row.created_at),
        reviewed_by=row.reviewed_by,
        reviewed_at=_aware(row.reviewed_at),
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
        self._migrate_event_graph()

    def _migrate_event_graph(self) -> None:
        """Kolumny dodane po pierwszej wersji mapy wydarzeń."""
        statements = [
            "ALTER TABLE event_members ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE event_members ADD COLUMN IF NOT EXISTS anchors JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE event_members ADD COLUMN IF NOT EXISTS topic TEXT DEFAULT ''",
            "ALTER TABLE event_links ADD COLUMN IF NOT EXISTS origin_check_id VARCHAR(32)",
            "CREATE INDEX IF NOT EXISTS event_links_origin_check_idx ON event_links(origin_check_id)",
            "CREATE INDEX IF NOT EXISTS events_embedding_hnsw ON events USING hnsw (embedding vector_cosine_ops)",
        ]
        with self._engine.begin() as conn:
            for statement in statements:
                try:
                    conn.execute(text(statement))
                except Exception:
                    log.warning("migracja mapy wydarzeń: nie udało się wykonać %s", statement, exc_info=True)

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

    def find_by_cache_key(self, cache_key: str) -> CheckResponse | None:
        """Permanentna deduplikacja — szuka bez limitu czasowego."""
        with self._session() as db:
            row = db.scalars(
                select(CheckRow)
                .where(CheckRow.cache_key == cache_key, CheckRow.status == CheckStatus.COMPLETED.value)
                .order_by(CheckRow.created_at.desc())
                .limit(1)
            ).first()
            if row is None:
                return None
            try:
                return CheckResponse.model_validate(row.result)
            except Exception:
                return None

    def increment_check_count(self, check_id: str) -> CheckResponse | None:
        """Zwiększa licznik zapytań i zapisuje zaktualizowany wynik w bazie."""
        with self._session() as db:
            row = db.get(CheckRow, check_id)
            if row is None:
                return None
            result = dict(row.result)
            result["request_count"] = result.get("request_count", 1) + 1
            row.result = result
            db.commit()
            try:
                return CheckResponse.model_validate(result)
            except Exception:
                return None

    def _forget_checks(self, db: Session, condition) -> int:
        ids = list(db.scalars(select(CheckRow.id).where(condition)))
        if ids:
            affected_events = set(
                db.scalars(
                    select(EventMemberRow.event_id).where(EventMemberRow.check_id.in_(ids))
                )
            )
            db.execute(delete(CaseLinkRow).where(CaseLinkRow.check_id.in_(ids)))
            db.execute(delete(SecurityEventRow).where(SecurityEventRow.check_id.in_(ids)))
            db.execute(delete(ArchivedMaterialRow).where(ArchivedMaterialRow.check_id.in_(ids)))
            db.execute(delete(EventLinkRow).where(EventLinkRow.origin_check_id.in_(ids)))
            db.execute(delete(EventMemberRow).where(EventMemberRow.check_id.in_(ids)))
            # Wydarzenie bez żadnego członka nie ma już treści użytkownika.
            empty: list[str] = []
            for event_id in affected_events:
                event = db.get(EventRow, event_id)
                if event is None:
                    continue
                self._refresh_event(db, event)
                if (event.member_count or 0) == 0 and (event.proposed_count or 0) == 0:
                    empty.append(event.id)
            if empty:
                db.execute(
                    delete(EventLinkRow).where(
                        or_(
                            EventLinkRow.src_event_id.in_(empty),
                            EventLinkRow.dst_event_id.in_(empty),
                        )
                    )
                )
                db.execute(delete(EventRow).where(EventRow.id.in_(empty)))
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

    # --- mapa wydarzeń ---

    def candidate_events(
        self, embedding: list[float] | None, since: datetime, limit: int
    ) -> list[tuple[EventRow, float]]:
        """Najbliższe wydarzenia w oknie czasowym (pgvector) albo ostatnie (fallback)."""
        with self._session() as db:
            base = select(EventRow).where(
                EventRow.status == "active",
                EventRow.member_count > 0,
                EventRow.last_seen >= since,
            )
            if embedding:
                distance = EventRow.embedding.cosine_distance(embedding)
                rows = db.execute(
                    select(EventRow, distance)
                    .where(
                        EventRow.status == "active",
                        EventRow.member_count > 0,
                        EventRow.last_seen >= since,
                        EventRow.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(limit)
                ).all()
                return [
                    (row, max(0.0, min(1.0, 1.0 - float(distance_value))))
                    for row, distance_value in rows
                ]
            rows = db.scalars(base.order_by(EventRow.last_seen.desc()).limit(limit))
            return [(row, 0.0) for row in rows]

    def create_event_with_member(
        self,
        *,
        title: str,
        topic: str,
        summary: str,
        keywords: list[str],
        risk: str,
        check_id: str,
        claim_id: str,
        claim_text: str,
        verdict: str | None,
        score: float,
        reason: str,
        status: str,
        source: str,
        embedding: list[float] | None,
        embedding_model: str | None,
        anchors: list[dict],
    ) -> EventOut:
        now = _now()
        with self._session() as db:
            row = EventRow(
                id=uuid.uuid4().hex,
                created_at=now,
                updated_at=now,
                title=truncate(title or claim_text, 240),
                topic=topic[:500],
                public_label="",
                summary=summary[:2000],
                status="active",
                risk=risk,
                member_count=0,
                proposed_count=0,
                keywords=[],
                verdicts={},
                anchors=[],
                first_seen=now,
                last_seen=now,
                embedding=None,
                embedding_model=embedding_model,
            )
            db.add(row)
            db.flush()
            db.add(
                EventMemberRow(
                    event_id=row.id,
                    check_id=check_id,
                    claim_id=claim_id,
                    claim_text=claim_text,
                    verdict=verdict,
                    risk=risk,
                    score=score,
                    reason=reason[:1000],
                    status=status,
                    source=source,
                    keywords=list(dict.fromkeys(keywords))[:12],
                    anchors=_merge_anchors([], anchors),
                    topic=topic[:500],
                    embedding=embedding,
                    created_at=now,
                )
            )
            db.flush()
            self._refresh_event(db, row)
            db.commit()
            return _event_out(row)

    def attach_event_member(
        self,
        event_id: str,
        *,
        check_id: str,
        claim_id: str,
        claim_text: str,
        verdict: str | None,
        risk: str,
        score: float,
        reason: str,
        status: str,
        source: str,
        embedding: list[float] | None,
        keywords: list[str],
        topic: str,
        anchors: list[dict],
    ) -> EventOut | None:
        now = _now()
        with self._session() as db:
            event = db.get(EventRow, event_id)
            if event is None or event.status != "active":
                return None
            existing = db.scalars(
                select(EventMemberRow).where(
                    EventMemberRow.event_id == event_id,
                    EventMemberRow.check_id == check_id,
                    EventMemberRow.claim_id == claim_id,
                )
            ).first()
            if existing is None:
                db.add(
                    EventMemberRow(
                        event_id=event_id,
                        check_id=check_id,
                        claim_id=claim_id,
                        claim_text=claim_text,
                        verdict=verdict,
                        risk=risk,
                        score=score,
                        reason=reason[:1000],
                        status=status,
                        source=source,
                        keywords=list(dict.fromkeys(keywords))[:12],
                        anchors=_merge_anchors([], anchors),
                        topic=topic[:500],
                        embedding=embedding,
                        created_at=now,
                    )
                )
            else:
                # Decyzja człowieka jest nadrzędna wobec automatycznej propozycji.
                if existing.status != "rejected":
                    existing.status = status
                    existing.source = source
                existing.score = max(existing.score or 0.0, score)
                existing.reason = reason[:1000] or existing.reason
                existing.keywords = list(dict.fromkeys(keywords))[:12]
                existing.anchors = _merge_anchors([], anchors)
                existing.topic = topic[:500]
                if embedding and existing.embedding is None:
                    existing.embedding = embedding
                existing.reviewed_at = None
                existing.reviewed_by = None
            db.flush()
            self._refresh_event(db, event)
            db.commit()
            return _event_out(event)

    def add_event_link(
        self,
        *,
        src_event_id: str,
        dst_event_id: str,
        relation: str,
        score: float,
        reason: str,
        evidence: dict[str, str] | None = None,
        model: str | None = None,
        status: str = "proposed",
        origin_check_id: str | None = None,
    ) -> EventLinkOut | None:
        if src_event_id == dst_event_id:
            return None
        with self._session() as db:
            src = db.get(EventRow, src_event_id)
            dst = db.get(EventRow, dst_event_id)
            if (
                src is None
                or dst is None
                or src.status != "active"
                or dst.status != "active"
            ):
                return None
            row = db.scalars(
                select(EventLinkRow).where(
                    EventLinkRow.src_event_id == src_event_id,
                    EventLinkRow.dst_event_id == dst_event_id,
                    EventLinkRow.relation == relation,
                )
            ).first()
            if row is None:
                row = EventLinkRow(
                    src_event_id=src_event_id,
                    dst_event_id=dst_event_id,
                    origin_check_id=origin_check_id,
                    relation=relation,
                    score=score,
                    reason=reason[:1000],
                    evidence=evidence or {},
                    model=model,
                    status=status,
                    created_at=_now(),
                )
                db.add(row)
            else:
                row.score = max(row.score or 0.0, score)
                row.reason = reason[:1000] or row.reason
                row.evidence = evidence or row.evidence or {}
                row.model = model or row.model
                if status == "accepted" and row.status != "accepted":
                    row.status = "accepted"
            db.commit()
            return _event_link_out(row)

    def _refresh_event(self, db: Session, event: EventRow) -> None:
        """Przelicza statystyki wydarzenia wyłącznie z zaakceptowanych członków."""
        db.flush()
        db.expire(event, ["members"])
        members = list(event.members)
        accepted = [m for m in members if m.status == "accepted"]
        proposed = [m for m in members if m.status == "proposed"]
        event.member_count = len(accepted)
        event.proposed_count = len(proposed)
        event.updated_at = _now()
        if accepted:
            event.risk = "high" if any(m.risk == "high" for m in accepted) else "standard"
            event.verdicts = dict(Counter(m.verdict for m in accepted if m.verdict))
            vectors = [m.embedding for m in accepted if m.embedding]
            if vectors:
                event.embedding = [
                    sum(values) / len(values)
                    for values in zip(*vectors, strict=False)
                ]
            event.first_seen = min(m.created_at for m in accepted)
            event.last_seen = max(m.created_at for m in accepted)
            event.summary = " • ".join(truncate(m.claim_text, 240) for m in accepted[:3])
            event.title = truncate(accepted[0].claim_text, 240)
            event.topic = next((m.topic for m in accepted if m.topic), "")
            # Agregaty liczymy z członków, nie doklejamy ich na stałe. Dzięki temu
            # usunięcie zgłoszenia usuwa też jego słowa kluczowe i kotwice.
            event.keywords = list(
                dict.fromkeys(
                    keyword for member in accepted for keyword in (member.keywords or [])
                )
            )[:12]
            event.anchors = _merge_anchors(
                [], [anchor for member in accepted for anchor in (member.anchors or [])]
            )
        else:
            event.verdicts = {}
            event.embedding = None
            event.risk = "standard"
            event.member_count = 0
            event.keywords = []
            event.anchors = []
            if proposed:
                event.topic = next((m.topic for m in proposed if m.topic), "")
                event.title = truncate(proposed[0].claim_text, 240)
            else:
                event.topic = ""
        # Publiczna etykieta nigdy nie spada do pełnej treści zgłoszenia.
        label = (event.topic or "").strip() or ", ".join((event.keywords or [])[:3])
        event.public_label = truncate(label, 120)

    def get_event(self, event_id: str) -> EventOut | None:
        with self._session() as db:
            row = db.get(EventRow, event_id)
            return _event_out(row) if row else None

    def get_event_detail(self, event_id: str) -> EventDetailOut | None:
        with self._session() as db:
            row = db.get(EventRow, event_id)
            if row is None:
                return None
            links = list(
                db.scalars(
                    select(EventLinkRow)
                    .where(
                        or_(
                            EventLinkRow.src_event_id == event_id,
                            EventLinkRow.dst_event_id == event_id,
                        )
                    )
                    .order_by(EventLinkRow.created_at.desc())
                )
            )
            return EventDetailOut(
                event=_event_out(row),
                members=[_event_member_out(m) for m in row.members],
                links=[_event_link_out(link) for link in links],
            )

    def event_graph(
        self,
        *,
        window_days: int,
        limit: int,
        include_proposed: bool = True,
    ) -> EventGraphResponse:
        now = _now()
        since = now - timedelta(days=window_days)
        with self._session() as db:
            query = select(EventRow).where(
                EventRow.status == "active",
                EventRow.last_seen >= since,
            )
            if include_proposed:
                query = query.where(
                    or_(EventRow.member_count > 0, EventRow.proposed_count > 0)
                )
            else:
                query = query.where(EventRow.member_count > 0)
            events = list(db.scalars(query.order_by(EventRow.last_seen.desc()).limit(limit)))
            return self._graph_response(
                db,
                events,
                window_days=window_days,
                public=False,
                include_proposed=include_proposed,
            )

    def public_event_graph(
        self, *, min_members: int, window_days: int, limit: int
    ) -> EventGraphResponse:
        now = _now()
        since = now - timedelta(days=window_days)
        with self._session() as db:
            events = list(
                db.scalars(
                    select(EventRow)
                    .where(
                        EventRow.status == "active",
                        EventRow.member_count >= max(1, min_members),
                        EventRow.last_seen >= since,
                    )
                    .order_by(EventRow.last_seen.desc())
                    .limit(limit)
                )
            )
            return self._graph_response(
                db,
                events,
                window_days=window_days,
                public=True,
                min_members=min_members,
                include_proposed=False,
            )

    def _graph_response(
        self,
        db: Session,
        events: list[EventRow],
        *,
        window_days: int,
        public: bool,
        min_members: int = 0,
        include_proposed: bool = True,
    ) -> EventGraphResponse:
        ids = {event.id for event in events}
        links: list[EventLinkRow] = []
        if ids:
            links = list(
                db.scalars(
                    select(EventLinkRow)
                    .where(
                        EventLinkRow.src_event_id.in_(ids),
                        EventLinkRow.dst_event_id.in_(ids),
                        EventLinkRow.status == "accepted"
                        if (public or not include_proposed)
                        else EventLinkRow.status.in_(("accepted", "proposed")),
                    )
                    .order_by(EventLinkRow.created_at.desc())
                )
            )
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        anchors: dict[str, GraphNode] = {}
        for event in events:
            if public:
                # Publicznie pokazujemy tylko słowa kluczowe wspólne dla co najmniej
                # dwóch zgłoszeń. Pojedyncze, unikalne sformułowania zostają w panelu.
                counts = Counter(
                    keyword
                    for member in event.members
                    if member.status == "accepted"
                    for keyword in (member.keywords or [])
                )
                keywords = [
                    keyword for keyword, count in counts.most_common() if count >= 2
                ][:6]
                label = event.topic or ", ".join(keywords[:3])
            else:
                keywords = (event.keywords or [])[:6]
                label = event.title
            nodes.append(
                GraphNode(
                    id=event.id,
                    kind="event",
                    label=label or "Wydarzenie bez etykiety",
                    subtitle=None if public else (event.topic or event.summary[:160] or None),
                    event_id=event.id,
                    risk=event.risk,
                    member_count=event.member_count or 0,
                    proposed_count=0 if public else (event.proposed_count or 0),
                    keywords=keywords,
                    verdicts=event.verdicts or {},
                    first_seen=_aware(event.first_seen),
                    last_seen=_aware(event.last_seen),
                )
            )
            for raw in event.anchors or []:
                if not isinstance(raw, dict):
                    continue
                incident_id = str(raw.get("incident_id") or "")
                if not incident_id:
                    continue
                anchor_id = f"anchor:{incident_id}"
                if anchor_id not in anchors:
                    anchors[anchor_id] = GraphNode(
                        id=anchor_id,
                        kind="anchor",
                        label=str(raw.get("title") or "Znany incydent"),
                        subtitle=str(raw.get("publisher") or "") or None,
                        url=str(raw.get("url") or "") or None,
                        event_id=event.id,
                    )
                edges.append(
                    GraphEdge(
                        id=f"anchor:{event.id}:{incident_id}",
                        source=event.id,
                        target=anchor_id,
                        relation="anchor",
                        status="accepted",
                    )
                )
        for link in links:
            edges.append(
                GraphEdge(
                    id=f"link:{link.id}",
                    source=link.src_event_id,
                    target=link.dst_event_id,
                    relation=link.relation,
                    score=link.score,
                    status="accepted" if link.status == "accepted" else "proposed",
                    reason=link.reason or "",
                    model=link.model,
                )
            )
        nodes.extend(anchors.values())
        return EventGraphResponse(
            generated_at=_now(),
            window_days=window_days,
            public=public,
            min_members=min_members,
            nodes=nodes,
            edges=edges,
        )

    def review_event_member(
        self,
        event_id: str,
        member_id: int,
        *,
        status: str,
        reviewer: str,
        note: str | None = None,
    ) -> tuple[bool, str | None]:
        """Akceptuje kandydata albo odłącza go do osobnego wydarzenia.

        Odrzucenie nie usuwa obserwacji: trafia do własnego wydarzenia, żeby nie
        zniknęła z mapy tylko dlatego, że automatyczna propozycja była błędna.
        """
        now = _now()
        new_event_id: str | None = None
        with self._session() as db:
            event = db.get(EventRow, event_id)
            member = db.get(EventMemberRow, member_id)
            if event is None or member is None or member.event_id != event_id:
                return False, None
            member.reviewed_by = reviewer
            member.reviewed_at = now
            member.source = "review"
            if status == "accepted":
                member.status = "accepted"
                if note:
                    member.reason = note[:1000]
                self._refresh_event(db, event)
            else:
                new_event = EventRow(
                    id=uuid.uuid4().hex,
                    created_at=now,
                    updated_at=now,
                    title=truncate(member.claim_text, 240),
                    topic=event.topic or "",
                    public_label="",
                    summary=member.claim_text[:2000],
                    status="active",
                    risk=member.risk or "standard",
                    member_count=0,
                    proposed_count=0,
                    keywords=list((event.keywords or [])[:6]),
                    verdicts={},
                    anchors=list((event.anchors or [])[:6]),
                    first_seen=member.created_at,
                    last_seen=member.created_at,
                    embedding=None,
                    embedding_model=event.embedding_model,
                )
                db.add(new_event)
                db.flush()
                member.event_id = new_event.id
                member.status = "accepted"
                if note:
                    member.reason = note[:1000]
                db.flush()
                self._refresh_event(db, new_event)
                self._refresh_event(db, event)
                new_event_id = new_event.id
                if (event.member_count or 0) == 0 and (event.proposed_count or 0) == 0:
                    db.delete(event)
            db.commit()
        return True, new_event_id

    def review_event_link(
        self,
        link_id: int,
        *,
        status: str,
        reviewer: str,
        relation: str | None = None,
        note: str | None = None,
    ) -> EventLinkOut | None:
        with self._session() as db:
            row = db.get(EventLinkRow, link_id)
            if row is None:
                return None
            row.status = status
            row.reviewed_by = reviewer
            row.reviewed_at = _now()
            if relation:
                row.relation = relation
            if note:
                row.reason = note[:1000]
            db.commit()
            return _event_link_out(row)

    def merge_events(self, source_event_id: str, target_event_id: str, reviewer: str) -> bool:
        if source_event_id == target_event_id:
            return False
        with self._session() as db:
            source = db.get(EventRow, source_event_id)
            target = db.get(EventRow, target_event_id)
            if (
                source is None
                or target is None
                or source.status != "active"
                or target.status != "active"
            ):
                return False
            existing = {(m.check_id, m.claim_id) for m in target.members}
            for member in list(source.members):
                key = (member.check_id, member.claim_id)
                if key in existing:
                    db.delete(member)
                    continue
                member.event_id = target.id
                existing.add(key)
            db.flush()
            db.expire(target, ["members"])
            self._refresh_event(db, target)
            source.status = "merged"
            source.merged_into = target.id
            source.member_count = 0
            source.proposed_count = 0
            source.updated_at = _now()
            db.execute(
                delete(EventLinkRow).where(
                    or_(
                        EventLinkRow.src_event_id == source.id,
                        EventLinkRow.dst_event_id == source.id,
                    )
                )
            )
            db.commit()
            return True

    def split_event_member(
        self, event_id: str, member_id: int, reviewer: str
    ) -> str | None:
        now = _now()
        with self._session() as db:
            event = db.get(EventRow, event_id)
            member = db.get(EventMemberRow, member_id)
            if event is None or member is None or member.event_id != event_id:
                return None
            new_event = EventRow(
                id=uuid.uuid4().hex,
                created_at=now,
                updated_at=now,
                title=truncate(member.claim_text, 240),
                topic=event.topic or "",
                public_label="",
                summary=member.claim_text[:2000],
                status="active",
                risk=member.risk or "standard",
                member_count=0,
                proposed_count=0,
                keywords=list((event.keywords or [])[:6]),
                verdicts={},
                anchors=list((event.anchors or [])[:6]),
                first_seen=member.created_at,
                last_seen=member.created_at,
                embedding=None,
                embedding_model=event.embedding_model,
            )
            db.add(new_event)
            db.flush()
            member.event_id = new_event.id
            member.status = "accepted"
            member.source = "review"
            member.reviewed_by = reviewer
            member.reviewed_at = now
            db.flush()
            self._refresh_event(db, new_event)
            self._refresh_event(db, event)
            if (event.member_count or 0) == 0 and (event.proposed_count or 0) == 0:
                db.delete(event)
            db.commit()
            return new_event.id

    def clear_event_graph(self) -> None:
        with self._session() as db:
            db.execute(delete(EventLinkRow))
            db.execute(delete(EventMemberRow))
            db.execute(delete(EventRow))
            db.commit()

    def event_count(self) -> int:
        with self._session() as db:
            return int(db.scalar(select(func.count()).select_from(EventRow)) or 0)

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
