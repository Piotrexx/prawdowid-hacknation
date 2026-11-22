"""Pętla informacji: nierozstrzygnięte twierdzenia trafiają do kolejki moderatora,
a podobne zgłoszenia są grupowane w jedną sprawę."""

import asyncio
import logging
import math

import httpx

from app.config import Settings
from app.retrieval.embeddings import Embedder
from app.schemas import CaseOut, ClaimResult, ModeratorCaseInfo
from app.store.db import Store
from app.textutil import jaccard

log = logging.getLogger("cases")

_SAME_CASE_COSINE = 0.8
_SAME_CASE_JACCARD = 0.55
RECOMMENDED_MESSAGE = (
    "Zalecamy przekazanie tej sprawy do sprawdzenia przez człowieka. "
    "Zgłoszenie nie zostało przekazane automatycznie."
)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class CaseLoop:
    def __init__(self, settings: Settings, store: Store, embedder: Embedder | None):
        self._settings = settings
        self._store = store
        self._embedder = embedder
        # Wyszukanie podobnej sprawy i jej utworzenie muszą być atomowe, inaczej dwa
        # równoległe zgłoszenia tej samej treści założyłyby dwie sprawy.
        self._lock = asyncio.Lock()

    def _find_similar(self, claim_text: str, cases: list[CaseOut]) -> CaseOut | None:
        if not cases:
            return None
        if self._embedder is not None:
            vectors = self._embedder.embed_documents([claim_text, *(c.claim_text for c in cases)])
            scores = [_cosine(vectors[0], vector) for vector in vectors[1:]]
            threshold = _SAME_CASE_COSINE
        else:
            scores = [jaccard(claim_text, c.claim_text) for c in cases]
            threshold = _SAME_CASE_JACCARD
        best = max(range(len(cases)), key=scores.__getitem__)
        return cases[best] if scores[best] >= threshold else None

    async def _notify(self, case: CaseOut, url: str) -> bool:
        """Powiadamia osobę wskazaną przez administratora (webhook). Zwraca, czy faktycznie doręczono."""
        text = (
            f"Prawdowid: sprawa nr {case.id} wymaga uwagi (ryzyko: {case.risk}, zgłoszeń: {case.occurrences}). "
            f"Twierdzenie: {case.claim_text}"
        )
        delivered = False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # `text` rozumie Slack, `content` Discord – jeden format dla obu.
                response = await client.post(url, json={"text": text, "content": text})
            delivered = response.status_code < 300
        except httpx.HTTPError:
            log.warning("nie udało się doręczyć powiadomienia o sprawie %s", case.id)
        self._store.add_event(
            "moderator_notification", f"case:{case.id}", "doręczono na webhook" if delivered else "nie doręczono (błąd webhooka)"
        )
        if delivered:
            self._store.update_case(case.id, notified=True)
        return delivered

    async def register(self, claims: list[ClaimResult], channel: str, check_id: str) -> ModeratorCaseInfo:
        if not claims:
            return ModeratorCaseInfo()
        if not self._settings.case_loop_enabled:
            return ModeratorCaseInfo(state="recommended", message=RECOMMENDED_MESSAGE)
        try:
            outcomes = [await self._register_one(c, channel, check_id) for c in claims]
        except Exception:
            # Nie wolno twierdzić, że sprawa została przekazana, jeśli zapis się nie udał.
            log.exception("nie udało się zapisać sprawy moderatora")
            return ModeratorCaseInfo(state="recommended", message=RECOMMENDED_MESSAGE)
        state, case, notified = outcomes[0]
        if state == "created":
            message = f"Nie udało się tego rozstrzygnąć, więc zgłoszenie trafiło do kolejki moderatora (sprawa nr {case.id})."
        else:
            message = (
                f"Podobne zgłoszenie już czeka w kolejce moderatora (sprawa nr {case.id}, "
                f"liczba zgłoszeń: {case.occurrences}). Dopisaliśmy Twoje."
            )
        if notified:
            message += " Moderator został powiadomiony."
        return ModeratorCaseInfo(
            state=state, case_id=case.id, occurrences=case.occurrences, notified=notified, message=message
        )

    async def _register_one(self, claim: ClaimResult, channel: str, check_id: str) -> tuple[str, CaseOut, bool]:
        async with self._lock:
            similar = self._find_similar(claim.text, self._store.open_cases())
            if similar:
                state, case = "updated", self._store.bump_case(similar.id, claim.risk, channel, check_id)
            else:
                state, case = "created", self._store.create_case(claim.text, claim.risk, channel, check_id)
        due = case.risk == "high" or case.occurrences >= self._settings.case_notify_threshold
        webhook = self._settings.moderator_webhook_url
        # Bez webhooka sprawa jest widoczna tylko w panelu – nie udajemy powiadomienia.
        if due and webhook and case.notified_at is None:
            return state, case, await self._notify(case, webhook)
        return state, case, case.notified_at is not None
