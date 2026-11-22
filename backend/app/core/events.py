"""Mapa wydarzeń: łączenie zgłoszeń w klastry i relacje między wydarzeniami.

Zasady:
  * kandydatów wyznacza tanie podobieństwo (pgvector + fallback leksykalny),
  * automatycznie akceptujemy tylko pary o wysokiej pewności,
  * szara strefa trafia do moderatora jako propozycja,
  * kwalifikator LLM jest opcjonalny i ocenia wyłącznie szarą strefę,
  * graf jest kontekstem analitycznym, nigdy dowodem w werdykcie.

Linkowanie nie może wydłużać odpowiedzi użytkownikowi, dlatego domyślnie działa
w tle (`event_graph_async`). Błąd mapy nigdy nie unieważnia sprawdzenia.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.core.prompts import EventRelationship, event_relation_prompts
from app.llm.base import LLMProvider
from app.retrieval.embeddings import Embedder
from app.schemas import CheckResponse, CheckStatus, EventOut, IncidentMatch
from app.store.db import Store
from app.store.models import EventRow
from app.textutil import jaccard, normalize_for_match, truncate

log = logging.getLogger("events")


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _anchor_from_incident(match: IncidentMatch) -> dict:
    return {
        "incident_id": match.incident_id,
        "title": match.title,
        "publisher": match.publisher,
        "url": match.url,
        "date": match.date.isoformat() if match.date else None,
        "note": match.note,
    }


class EventGraph:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        embedder: Embedder | None,
        provider_getter: Callable[[], LLMProvider | None] | None = None,
    ):
        self._settings = settings
        self._store = store
        self._embedder = embedder
        self._provider_getter = provider_getter or (lambda: None)
        # Online i ręczny rebuild nie mogą równocześnie tworzyć tych samych klastrów.
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    def set_provider_getter(self, getter: Callable[[], LLMProvider | None]) -> None:
        self._provider_getter = getter

    # --- wejście z pipeline'u ---

    def spawn(self, response: CheckResponse) -> None:
        """Uruchamia linkowanie w tle. Wynik nie blokuje odpowiedzi użytkownikowi."""
        if not self._settings.event_graph_enabled:
            return
        task = asyncio.create_task(self._safe_ingest(response))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Czeka na zadania w tle (używane w testach i przy zamykaniu usługi)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _safe_ingest(self, response: CheckResponse) -> None:
        try:
            await self.ingest_check(response)
        except Exception:
            log.exception("mapa wydarzeń: nie udało się połączyć zgłoszenia %s", response.id)

    async def ingest_check(self, response: CheckResponse) -> int:
        if not self._settings.event_graph_enabled:
            return 0
        if response.status != CheckStatus.COMPLETED or not response.claims:
            return 0

        topic = (response.main_topic or "").strip()
        keywords = [keyword for keyword in (response.keywords or []) if keyword.strip()]
        anchors = self._anchors(response)
        processed = 0
        async with self._lock:
            for claim in response.claims:
                text = (claim.text or "").strip()
                if not text:
                    continue
                await self._ingest_claim(
                    response=response,
                    claim=claim,
                    topic=topic,
                    keywords=keywords,
                    anchors=anchors,
                )
                processed += 1
        return processed

    def _anchors(self, response: CheckResponse) -> list[dict]:
        anchors = [_anchor_from_incident(match) for match in response.incident_matches]
        for result in response.fact_check_results[:5]:
            anchors.append(
                {
                    "incident_id": f"factcheck:{result.claim_review_url}",
                    "title": result.claim_review_title,
                    "publisher": result.publisher_name,
                    "url": result.claim_review_url,
                    "date": result.claim_date,
                    "note": f"Zewnętrzna ocena: {result.rating}",
                }
            )
        return anchors

    async def _ingest_claim(self, *, response: CheckResponse, claim, topic, keywords, anchors) -> None:
        text = claim.text.strip()
        embedding = await self._embed(text)
        since = datetime.now(UTC) - timedelta(days=self._settings.event_link_window_days)

        candidates = self._candidate_scores(text, embedding, since)
        best_event: EventRow | None = None
        best_score = 0.0
        for event, score in candidates:
            if score > best_score:
                best_event, best_score = event, score

        auto_threshold, review_threshold = self._thresholds(
            embedding, best_event
        )
        base = {
            "check_id": response.id,
            "claim_id": claim.id,
            "claim_text": text,
            "verdict": claim.verdict.value,
            "risk": claim.risk,
            "score": round(best_score, 4),
            "status": "accepted",
            "source": "auto",
            "embedding": embedding,
            "keywords": keywords,
            "topic": topic,
            "anchors": anchors,
        }

        if best_event is not None and best_score >= auto_threshold:
            attached = self._store.attach_event_member(
                best_event.id,
                **base,
                reason=self._match_reason(best_event, best_score, embedding),
            )
            if attached is None:
                self._create_event(base, reason="wydarzenie zniknęło w trakcie łączenia")
            return

        if best_event is not None and best_score >= review_threshold:
            relationship = await self._qualify(text, best_event)
            if relationship is not None:
                model = self._model_name()
                if relationship.relation == "same_event":
                    accepted = relationship.confidence >= self._settings.event_llm_accept_confidence
                    attached = self._store.attach_event_member(
                        best_event.id,
                        **{**base, "status": "accepted" if accepted else "proposed", "source": "llm"},
                        reason=relationship.reason or self._match_reason(best_event, best_score, embedding),
                    )
                    if attached is None:
                        self._create_event(base, reason="wydarzenie zniknęło w trakcie łączenia")
                    return
                if relationship.relation != "unrelated":
                    created = self._create_event(base, reason="nowe wydarzenie powiązane z istniejącym")
                    self._store.add_event_link(
                        src_event_id=created.id,
                        dst_event_id=best_event.id,
                        relation=relationship.relation,
                        score=relationship.confidence,
                        reason=relationship.reason,
                        evidence={
                            "claim": relationship.evidence_a,
                            "event": relationship.evidence_b,
                        },
                        model=model,
                        status="proposed",
                        origin_check_id=response.id,
                    )
                    return
                # "unrelated" oznacza, że podobieństwo było mylące.
                self._create_event(base, reason="model uznał podobieństwo za mylące")
                return

            # Bez kwalifikatora nie zgadujemy: kandydat czeka na decyzję człowieka.
            attached = self._store.attach_event_member(
                best_event.id,
                **{**base, "status": "proposed"},
                reason=self._match_reason(best_event, best_score, embedding),
            )
            if attached is None:
                self._create_event(base, reason="wydarzenie zniknęło w trakcie łączenia")
            return

        self._create_event(base, reason="brak dopasowania powyżej progu")

    def _create_event(self, base: dict, *, reason: str) -> EventOut:
        return self._store.create_event_with_member(
            title=base["claim_text"],
            topic=base["topic"],
            summary=base["claim_text"],
            keywords=base["keywords"],
            risk=base["risk"],
            check_id=base["check_id"],
            claim_id=base["claim_id"],
            claim_text=base["claim_text"],
            verdict=base["verdict"],
            score=base["score"],
            reason=reason,
            status="accepted",
            source=base["source"],
            embedding=base["embedding"],
            embedding_model=self._model_name(),
            anchors=base["anchors"],
        )

    # --- dopasowanie ---

    def _candidate_scores(
        self, text: str, embedding: list[float] | None, since: datetime
    ) -> list[tuple[EventRow, float]]:
        limit = self._settings.event_link_candidates
        found: dict[str, tuple[EventRow, float]] = {}
        if embedding:
            for event, _ in self._store.candidate_events(embedding, since, limit):
                found[event.id] = (event, 0.0)
        for event, _ in self._store.candidate_events(None, since, limit):
            found.setdefault(event.id, (event, 0.0))

        scored: list[tuple[EventRow, float]] = []
        for event, _ in found.values():
            if embedding and event.embedding:
                score = _cosine(embedding, event.embedding)
            else:
                haystack = " ".join(
                    [
                        event.title or "",
                        event.summary or "",
                        event.topic or "",
                        " ".join(event.keywords or []),
                    ]
                )
                score = jaccard(text, haystack)
            scored.append((event, max(0.0, min(1.0, score))))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def _thresholds(
        self, embedding: list[float] | None, event: EventRow | None
    ) -> tuple[float, float]:
        if embedding and event is not None and event.embedding:
            return (
                self._settings.event_link_auto_similarity,
                self._settings.event_link_review_similarity,
            )
        return (
            self._settings.event_link_auto_lexical,
            self._settings.event_link_review_lexical,
        )

    @staticmethod
    def _match_reason(event: EventRow, score: float, embedding: list[float] | None) -> str:
        kind = "semantyczne" if embedding and event.embedding else "leksykalne"
        return f"Automatyczne podobieństwo {kind}: {score:.2f}."

    # --- kwalifikator LLM ---

    async def _qualify(self, text: str, event: EventRow) -> EventRelationship | None:
        if not self._settings.event_llm_qualifier_enabled:
            return None
        provider = self._provider_getter()
        if provider is None:
            return None
        system, user = event_relation_prompts(text, event.title, event.summary)
        try:
            relationship, _usage = await provider.structured(
                system=system,
                user=user,
                schema=EventRelationship,
                effort="low",
            )
        except Exception:
            log.warning("mapa wydarzeń: kwalifikator LLM nie odpowiedział", exc_info=True)
            return None

        # Cytat musi naprawdę pochodzić z tekstu, inaczej obniżamy pewność.
        valid_a = self._quote_present(relationship.evidence_a, text)
        valid_b = self._quote_present(
            relationship.evidence_b, f"{event.title}\n{event.summary}"
        )
        if (relationship.evidence_a and not valid_a) or (
            relationship.evidence_b and not valid_b
        ):
            relationship = relationship.model_copy(
                update={
                    "confidence": min(relationship.confidence, 0.5),
                    "reason": f"{relationship.reason} (cytat niepotwierdzony)".strip(),
                }
            )
        elif relationship.relation in {"same_event", "follow_up", "contradiction"} and not (
            relationship.evidence_a.strip() and relationship.evidence_b.strip()
        ):
            # Bez dwóch dosłownych cytatów nie akceptujemy relacji automatycznie.
            relationship = relationship.model_copy(
                update={
                    "confidence": min(relationship.confidence, 0.6),
                    "reason": f"{relationship.reason} (brak cytatów)".strip(),
                }
            )
        if relationship.injection_detected:
            self._store.add_event(
                "prompt_injection",
                "event_qualifier",
                "wykryto polecenia w treści podczas łączenia wydarzeń",
            )
        return relationship

    @staticmethod
    def _quote_present(quote: str, source: str) -> bool:
        quote = normalize_for_match(quote or "").strip()
        if not quote:
            return True
        return quote in normalize_for_match(source or "")

    def _model_name(self) -> str | None:
        provider = self._provider_getter()
        return getattr(provider, "model", None) if provider else None

    async def _embed(self, text: str) -> list[float] | None:
        if self._embedder is None:
            return None
        try:
            vectors = await asyncio.to_thread(
                self._embedder.embed_documents, [truncate(text, 2000)]
            )
        except Exception:
            log.warning("mapa wydarzeń: embedding nie powstał", exc_info=True)
            return None
        return vectors[0] if vectors else None

    # --- ręczne przebudowanie ---

    async def rebuild(self, limit: int, reset: bool = True) -> tuple[int, int, int]:
        if not self._settings.event_graph_enabled:
            return 0, self._store.event_count(), 0
        if reset:
            self._store.clear_event_graph()
        results = await asyncio.to_thread(self._store.all_results)
        selected = list(reversed(results[:limit]))
        processed = 0
        skipped = 0
        for result in selected:
            if result.status != CheckStatus.COMPLETED:
                skipped += 1
                continue
            try:
                await self.ingest_check(result)
            except Exception:
                log.exception("mapa wydarzeń: nie udało się przetworzyć %s", result.id)
                skipped += 1
            else:
                processed += 1
        return processed, self._store.event_count(), skipped
