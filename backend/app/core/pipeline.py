"""Jedyna ścieżka weryfikacji. Każdy kanał (obecnie WWW) woła `VerificationService.check`,
więc ten sam materiał daje ten sam wynik merytoryczny niezależnie od kanału."""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.catalog import Document
from app.config import Settings
from app.core.cases import CaseLoop
from app.core.media import ImageError, prepare_image
from app.core.prompts import (
    OCR_SYSTEM,
    ClaimAssessment,
    ExtractedClaim,
    Extraction,
    ImageReading,
    assess_prompts,
    extract_prompts,
)
from app.core.verdict import decide, source_ref, unassessed
from app.llm.base import ImageInput, LLMError, LLMProvider, T, Usage, estimate_cost
from app.retrieval.context import ContextCatalog
from app.retrieval.index import CorpusIndex
from app.schemas import (
    VERDICT_LABELS,
    CheckMeta,
    CheckResponse,
    CheckStatus,
    ClaimResult,
    IncidentMatch,
    InputInfo,
    ModeratorCaseInfo,
    SourceRef,
    Verdict,
    Warning,
)
from app.security.injection import sanitize_untrusted, scan_injection
from app.security.pii import mask_pii
from app.security.urlfetch import UrlFetchError, fetch_page
from app.store.db import Store
from app.textutil import normalize_for_match, truncate

log = logging.getLogger("check")

_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_STORED_PAGE_CHARS = 1500
_NOT_A_VERDICT = "To problem techniczny, a nie wynik sprawdzenia."
_LLM_MESSAGES = {
    "llm_not_configured": f"Usługa nie ma teraz dostępu do modelu językowego, więc nie mogę ocenić tej treści. {_NOT_A_VERDICT}",
    "llm_unavailable": f"Nie mogę teraz połączyć się z modelem językowym, więc nie sprawdzę tej treści. {_NOT_A_VERDICT} Spróbuj ponownie za chwilę.",
    "llm_rate_limited": f"Usługa jest chwilowo przeciążona. {_NOT_A_VERDICT} Spróbuj ponownie za kilka minut.",
    "llm_refused": "Model językowy odmówił przetworzenia tej treści, więc nie mogę jej sprawdzić. To ograniczenie techniczne, a nie wynik sprawdzenia.",
    "llm_bad_output": f"Model językowy zwrócił niepełną odpowiedź. {_NOT_A_VERDICT} Spróbuj ponownie.",
}
_INJECTION_WARNINGS = {
    "corpus_passage": "W jednym ze źródeł wykryliśmy tekst wyglądający na polecenie dla systemu. Został zignorowany.",
}
_INJECTION_DEFAULT = "W przesłanej treści wykryliśmy polecenia skierowane do systemu. Zostały zignorowane i nie wpłynęły na wynik."


@dataclass
class Submission:
    channel: str
    session_id: str | None = None
    text: str | None = None
    url: str | None = None
    image: bytes | None = None

    @classmethod
    def from_message(cls, channel: str, session_id: str | None, message: str) -> "Submission":
        """Wiadomość będąca samym adresem traktujemy jako link do pobrania, resztę jako tekst."""
        message = message.strip()
        if _URL_RE.fullmatch(message):
            return cls(channel=channel, session_id=session_id, url=message)
        return cls(channel=channel, session_id=session_id, text=message)


class _Stop(Exception):
    """Kontrolowane zakończenie bez werdyktu: awaria, prośba o doprecyzowanie lub treść poza zakresem."""

    def __init__(self, status: CheckStatus, message: str, error_code: str | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.error_code = error_code


@dataclass
class _Run:
    channel: str
    check_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    input: InputInfo = field(default_factory=lambda: InputInfo(kind="text", text=""))
    material: str = ""
    usage: Usage = field(default_factory=Usage)
    stages_ms: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, Warning] = field(default_factory=dict)
    incidents: dict[str, IncidentMatch] = field(default_factory=dict)
    events: list[tuple[str, str, str]] = field(default_factory=list)
    quotes_rejected: int = 0

    def warn(self, code: str, message: str) -> None:
        self.warnings.setdefault(code, Warning(code=code, message=message))

    def flag_injection(self, origin: str, detail: str) -> None:
        self.events.append(("prompt_injection", origin, detail))
        self.warn("injection_detected", _INJECTION_WARNINGS.get(origin, _INJECTION_DEFAULT))

    def mark(self, stage: str, since: float) -> None:
        self.stages_ms[stage] = self.stages_ms.get(stage, 0) + int((time.perf_counter() - since) * 1000)


class VerificationService:
    def __init__(
        self,
        settings: Settings,
        index: CorpusIndex,
        context: ContextCatalog,
        provider: LLMProvider | None,
        store: Store,
        cases: CaseLoop,
        source_names: dict[str, str],
        retrieval_degraded: bool = False,
    ):
        self._settings = settings
        self._index = index
        self._context = context
        self._provider = provider
        self._store = store
        self._cases = cases
        self._source_names = source_names
        self._retrieval_degraded = retrieval_degraded

    async def check(self, submission: Submission) -> CheckResponse:
        run = _Run(channel=submission.channel)
        cache_key = None
        try:
            response, cache_key = await self._verify(submission, run)
        except _Stop as stop:
            response = self._response(run, stop.status, status_message=stop.message, error_code=stop.error_code)
            if (stop.error_code or "").startswith("llm_") and run.material:
                response.related_materials = await self._related_materials(run.material)
        except Exception:
            log.exception("nieoczekiwany błąd sprawdzenia %s", run.check_id)
            response = self._response(
                run,
                CheckStatus.ERROR,
                status_message=f"Wystąpił nieoczekiwany błąd. {_NOT_A_VERDICT} Spróbuj ponownie.",
                error_code="internal_error",
            )
        self._store.save_check(response, submission.session_id, cache_key)
        for kind, origin, detail in run.events:
            self._store.add_event(kind, origin, detail, response.id)
        log.info(
            json.dumps(
                {
                    "check_id": response.id,
                    "channel": response.channel,
                    "status": response.status.value,
                    "error_code": response.error_code,
                    "verdicts": [c.verdict.value for c in response.claims],
                    "duration_ms": response.meta.duration_ms,
                    "stages_ms": response.meta.stages_ms,
                    "tokens_in": response.meta.tokens_in,
                    "tokens_out": response.meta.tokens_out,
                    "cost_usd": response.meta.cost_usd,
                    "quotes_rejected": run.quotes_rejected,
                    "cached": response.meta.cached,
                    "security_events": len(run.events),
                }
            )
        )
        return response

    # --- etapy ---

    async def _verify(self, submission: Submission, run: _Run) -> tuple[CheckResponse, str]:
        started = time.perf_counter()
        await self._prepare_input(submission, run)
        run.mark("input", started)

        model = self._provider.model if self._provider else "none"
        fingerprint = f"{self._index.version}|{model}|{normalize_for_match(run.material)}"
        cache_key = hashlib.sha256(fingerprint.encode()).hexdigest()
        since = datetime.now(UTC) - timedelta(hours=self._settings.result_cache_hours)
        cached = self._store.find_cached(cache_key, since)
        if cached:
            claims, limitations = cached.claims, cached.limitations
            for match in cached.incident_matches:
                run.incidents.setdefault(match.incident_id, match)
            for warning in cached.warnings:
                # Ostrzeżenia zależne od sposobu zgłoszenia liczymy od nowa dla bieżącego kanału.
                if warning.code not in ("pii_masked", "image_limits", "input_truncated"):
                    run.warn(warning.code, warning.message)
        else:
            claims, limitations = await self._assess_material(run)

        unresolved = sorted(
            (c for c in claims if c.verdict == Verdict.INSUFFICIENT), key=lambda c: c.risk != "high"
        )
        moderator_case = await self._cases.register(unresolved, run.channel, run.check_id)
        response = self._response(
            run,
            CheckStatus.COMPLETED,
            summary=_summary(claims),
            claims=claims,
            moderator_case=moderator_case,
            limitations=limitations,
            cached=cached is not None,
        )
        return response, cache_key

    async def _prepare_input(self, submission: Submission, run: _Run) -> None:
        origin = "user_input"
        if submission.image is not None:
            origin = "image_text"
            raw = await self._read_image(submission.image, run)
        elif submission.url:
            origin = "fetched_url"
            run.input = InputInfo(kind="url", text="", url=submission.url)
            self._add_url_context(submission.url, run)
            try:
                page = await fetch_page(submission.url, self._settings)
            except UrlFetchError as exc:
                raise _Stop(CheckStatus.ERROR, f"{exc.message} {_NOT_A_VERDICT}", exc.code) from exc
            run.input.title = page.title or None
            raw = f"{page.title}\n\n{page.text}" if page.title else page.text
        else:
            raw = submission.text or ""
            linked = _URL_RE.search(raw)
            if linked:
                self._add_url_context(linked.group(0).rstrip(".,)"), run)

        material, masked = mask_pii(sanitize_untrusted(raw).strip())
        if masked:
            run.warn("pii_masked", "Przed analizą ukryliśmy dane wyglądające na osobowe (np. telefon, e-mail, PESEL).")
        if len(material) > self._settings.max_input_chars:
            material = material[: self._settings.max_input_chars]
            run.warn("input_truncated", "Treść była bardzo długa – przeanalizowaliśmy tylko jej początek.")
        run.material = material
        # Dla stron WWW zapisujemy tylko początek treści (minimalizacja danych, prawa autorskie).
        run.input.text = truncate(material, _STORED_PAGE_CHARS) if run.input.kind == "url" else material
        if not material:
            raise _Stop(CheckStatus.NEEDS_CLARIFICATION, "Wklej treść wiadomości albo link, który chcesz sprawdzić.")
        found = scan_injection(material)
        if found:
            run.flag_injection(origin, "; ".join(found))

    def _add_url_context(self, url: str, run: _Run) -> None:
        status = self._context.source_status(url)
        if status:
            run.warnings.setdefault(status.code, status)
        for match in self._context.url_matches(url):
            run.incidents.setdefault(match.incident_id, match)

    async def _read_image(self, data: bytes, run: _Run) -> str:
        try:
            image, media_type, metadata = await asyncio.to_thread(prepare_image, data, self._settings.image_max_bytes)
        except ImageError as exc:
            raise _Stop(CheckStatus.ERROR, f"{exc.message} {_NOT_A_VERDICT}", exc.code) from exc
        run.input = InputInfo(kind="image", text="", image_metadata=metadata)
        run.warn(
            "image_limits",
            "Odczytujemy tylko tekst widoczny na obrazie. Nie sprawdzamy, czy obraz jest przerobiony, "
            "ani gdzie pojawił się wcześniej. Obrazu nie zapisujemy.",
        )
        try:
            reading = await self._ask(
                run, OCR_SYSTEM, "Odczytaj załączony obraz.", ImageReading, "low", [ImageInput(image, media_type)]
            )
        except _Stop as stop:
            # Awaria odczytu obrazu to osobny, jawnie nazwany problem techniczny.
            raise _Stop(
                CheckStatus.ERROR,
                f"Odczyt tekstu z obrazu jest teraz niedostępny. {_NOT_A_VERDICT} Możesz wkleić treść jako tekst.",
                "ocr_unavailable",
            ) from stop
        if reading.injection_detected:
            run.flag_injection("image_text", "model zgłosił polecenia w tekście obrazu")
        if not reading.readable or not reading.text.strip():
            raise _Stop(
                CheckStatus.NEEDS_CLARIFICATION,
                "Nie udało się odczytać tekstu z tego obrazu. Wklej treść jako tekst albo dodaj wyraźniejszy zrzut ekranu.",
            )
        dates = ", ".join(reading.visible_dates)
        return reading.text + (f"\n\nDaty widoczne na obrazie: {dates}" if dates else "")

    async def _ask(
        self, run: _Run, system: str, user: str, schema: type[T], effort: str, images: list[ImageInput] | None = None
    ) -> T:
        if self._provider is None:
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES["llm_not_configured"], "llm_not_configured")
        try:
            output, usage = await self._provider.structured(
                system=system, user=user, schema=schema, effort=effort, images=images
            )
        except LLMError as exc:
            log.warning("model językowy: %s (%s)", exc.code, exc)
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES.get(exc.code, _LLM_MESSAGES["llm_unavailable"]), exc.code) from exc
        run.usage.add(usage)
        return output

    async def _assess_material(self, run: _Run) -> tuple[list[ClaimResult], list[str]]:
        today = date.today()
        started = time.perf_counter()
        system, user = extract_prompts(run.material, today, self._settings.max_claims)
        extraction = await self._ask(run, system, user, Extraction, self._settings.llm_extract_effort)
        run.mark("extract", started)
        if extraction.injection_detected:
            run.flag_injection("model_flag", "model zgłosił polecenia w analizowanym materiale")
        if extraction.input_status == "needs_clarification":
            raise _Stop(
                CheckStatus.NEEDS_CLARIFICATION,
                extraction.message or "Napisz dokładniej, którą informację mam sprawdzić.",
            )
        if extraction.input_status == "out_of_scope":
            raise _Stop(
                CheckStatus.OUT_OF_SCOPE,
                extraction.message or "W tej treści nie ma informacji, którą można sprawdzić w źródłach.",
            )
        extracted = extraction.claims[: self._settings.max_claims]
        if not extracted:
            raise _Stop(CheckStatus.NEEDS_CLARIFICATION, "Napisz dokładniej, którą informację mam sprawdzić.")

        started = time.perf_counter()
        outcomes = await asyncio.gather(
            *(self._assess_claim(run, f"c{n}", claim, today) for n, claim in enumerate(extracted, 1)),
            return_exceptions=True,
        )
        run.mark("verify", started)
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome
        claims = [claim for claim, _ in outcomes]

        for claim, documents in outcomes:
            if documents:
                matches = await asyncio.to_thread(self._context.content_matches, claim.text, documents)
                for match in matches:
                    run.incidents.setdefault(match.incident_id, match)
        if any(e.archival for c in claims for e in c.evidence):
            run.warn(
                "archival_material",
                f"Część źródeł jest starsza niż {self._settings.archival_days} dni. Sprawdź, czy są nadal aktualne.",
            )
        if self._retrieval_degraded:
            run.warn("retrieval_degraded", "Wyszukiwanie działało w trybie uproszczonym (tylko słowa kluczowe), więc mogło pominąć część źródeł.")
        return claims, self._limitations(run, len(extraction.claims) > len(extracted))

    async def _assess_claim(
        self, run: _Run, claim_id: str, claim: ExtractedClaim, today: date
    ) -> tuple[ClaimResult, list[Document]]:
        if claim.kind != "fakt":
            return (
                unassessed(
                    claim_id,
                    claim.text,
                    claim.risk,
                    Verdict.NOT_VERIFIABLE,
                    "To opinia albo prognoza, a nie stwierdzenie faktu. Nie da się jej potwierdzić ani obalić na podstawie źródeł.",
                ),
                [],
            )
        hits = await asyncio.to_thread(
            self._index.search, [claim.text, *claim.queries], self._settings.retrieval_top_k, today
        )
        if not hits:
            return (
                unassessed(
                    claim_id,
                    claim.text,
                    claim.risk,
                    Verdict.INSUFFICIENT,
                    "W naszych źródłach nie ma materiałów na ten temat, więc nie rozstrzygam.",
                    "W katalogu źródeł nie znaleźliśmy żadnych materiałów dotyczących tego twierdzenia.",
                ),
                [],
            )
        for hit in hits:
            found = scan_injection(hit.passage.text)
            if found:
                run.flag_injection("corpus_passage", f"{hit.passage.doc.id}: {'; '.join(found)}")
        system, user = assess_prompts(claim.text, hits, today)
        assessment = await self._ask(run, system, user, ClaimAssessment, self._settings.llm_assess_effort)
        if assessment.injection_detected:
            run.flag_injection("model_flag", f"model zgłosił polecenia przy ocenie twierdzenia {claim_id}")
        result, rejected = decide(
            claim_id=claim_id,
            claim_text=claim.text,
            risk=claim.risk,
            assessment=assessment,
            hits=hits,
            source_names=self._source_names,
            today=today,
            archival_days=self._settings.archival_days,
        )
        run.quotes_rejected += rejected
        return result, [h.passage.doc for h in hits]

    # --- składanie odpowiedzi ---

    def _limitations(self, run: _Run, claims_truncated: bool) -> list[str]:
        built = self._index.built_at.date().isoformat() if self._index.built_at else "nieznana data"
        items = [
            f"Odpowiedź opiera się wyłącznie na źródłach z katalogu Prawdowida (stan na {built}). Nowsze informacje mogły nie zostać uwzględnione.",
            "Uzasadnienie to interpretacja modelu językowego. Cytaty i linki pochodzą ze źródeł – przeczytaj je i oceń samodzielnie.",
        ]
        if run.input.kind == "url":
            items.append("Sprawdziliśmy treść strony pobraną w chwili zgłoszenia. Strona mogła się później zmienić.")
        if run.input.kind == "image":
            items.append("Tekst z obrazu odczytał model – mógł się pomylić. Nie oceniamy autentyczności obrazu.")
        if claims_truncated:
            items.append(f"Sprawdziliśmy {self._settings.max_claims} najważniejsze twierdzenia z tej treści.")
        return items

    async def _related_materials(self, material: str) -> list[SourceRef]:
        hits = await asyncio.to_thread(self._index.search, [material[:500]], 5)
        docs = {h.passage.doc.id: h.passage.doc for h in hits}
        return [source_ref(d, self._source_names.get(d.source_id, d.publisher)) for d in docs.values()]

    def _response(
        self,
        run: _Run,
        status: CheckStatus,
        *,
        status_message: str | None = None,
        error_code: str | None = None,
        summary: str | None = None,
        claims: list[ClaimResult] | None = None,
        moderator_case: ModeratorCaseInfo | None = None,
        limitations: list[str] | None = None,
        cached: bool = False,
    ) -> CheckResponse:
        provider = self._provider
        override = (self._settings.llm_price_input_per_mtok, self._settings.llm_price_output_per_mtok)
        return CheckResponse(
            id=run.check_id,
            created_at=datetime.now(UTC),
            channel=run.channel,
            status=status,
            status_message=status_message,
            error_code=error_code,
            input=run.input,
            summary=summary,
            claims=claims or [],
            warnings=list(run.warnings.values()),
            incident_matches=list(run.incidents.values()),
            moderator_case=moderator_case or ModeratorCaseInfo(),
            limitations=limitations or [],
            meta=CheckMeta(
                duration_ms=int((time.perf_counter() - run.started) * 1000),
                stages_ms=run.stages_ms,
                provider=provider.name if provider else None,
                model=provider.model if provider else None,
                llm_calls=run.usage.calls,
                tokens_in=run.usage.input_tokens,
                tokens_out=run.usage.output_tokens,
                cost_usd=estimate_cost(provider.model, run.usage, override) if provider else None,
                retrieval_mode=self._index.mode,
                corpus_version=self._index.version,
                processing_location=self._settings.processing_location,
                cached=cached,
            ),
        )


def _summary(claims: list[ClaimResult]) -> str:
    counts = Counter(c.verdict for c in claims)
    parts = ", ".join(f"{VERDICT_LABELS[v].lower()} – {n}" for v, n in counts.items())
    return f"Liczba sprawdzonych twierdzeń: {len(claims)}. Wyniki: {parts}."
