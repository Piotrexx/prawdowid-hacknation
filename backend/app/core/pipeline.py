"""Jedyna ścieżka weryfikacji. Każdy kanał (obecnie WWW) woła `VerificationService.check`,
więc ten sam materiał daje ten sam wynik merytoryczny niezależnie od kanału.

Przebieg:
  wejście (tekst / URL / obraz / nagranie) → maskowanie PII i skan prompt injection
  → wydzielenie twierdzeń (model)
  → dla każdego twierdzenia: wyszukanie w korpusie (PostgreSQL + pgvector) + ocena + reguły werdyktu
     (cytat musi występować w źródle – `app/core/verdict.py`)
  → równolegle: słowa kluczowe (lokalny Bielik) i sprawdzenia z Google Fact Check Tools
  → podsumowanie całego materiału (model), spójne z ocenami twierdzeń
  → pętla informacji: nierozstrzygnięte twierdzenia do kolejki moderatora

Warstwa dowodowa (`claims`) jest rozstrzygająca. Słowa kluczowe, fact-checki i
podsumowanie (`verdict`) są warstwą wspierającą i nigdy nie nadpisują ocen twierdzeń.
"""

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

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.core.audio import AudioError, transcribe_audio
from app.core.cases import CaseLoop
from app.core.image_check import ImageCheckService, ImageInspection
from app.core.media import ImageError, prepare_image
from app.core.prompts import (
    BIELIK_KEYWORD_PROMPT,
    DEEPSEEK_VERDICT_PROMPT,
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
from app.retrieval.claims import ClaimRetriever
from app.retrieval.context import ContextIndex
from app.retrieval.corpus import CorpusDocument
from app.schemas import (
    VERDICT_LABELS,
    CheckMeta,
    CheckResponse,
    CheckStatus,
    ClaimResult,
    Clarification,
    ClarificationExchange,
    ClarifyingQuestion,
    FactCheckResult,
    ImageAnalysis,
    IncidentMatch,
    InputInfo,
    KeywordExtraction,
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
_FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
_FACTCHECK_KEYWORDS = 5
_FACTCHECK_RESULTS = 5
_MAX_KEYWORDS = 10
# Wejście dla Bielika: dłuższy tekst to dłuższe wczytywanie promptu na CPU, a tytuł i lead wystarczają na słowa kluczowe.
_BIELIK_INPUT_CHARS = 4000
_KEYWORD_SYSTEM = "Jesteś ekspertem ds. analizy mediów i wykrywania dezinformacji. Odpowiadasz wyłącznie obiektem JSON."
_NOT_A_VERDICT = "To problem techniczny, a nie wynik sprawdzenia."
_CLARIFY_INTRO = "Zanim sprawdzę, potrzebuję kilku szczegółów."
_CLARIFY_EXHAUSTED = (
    "Mimo doprecyzowania nie udało mi się ustalić, co dokładnie sprawdzić. "
    "Napisz nową wiadomość z konkretnym twierdzeniem: kto, co, kiedy i gdzie."
)
_MAX_QUESTIONS = 3
_MAX_OPTIONS = 5
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
# Linie ograniczeń dokładane przy analizie zdjęcia; przy trafieniu w cache podmieniamy je na świeże.
_IMAGE_LIMITATION_STARTS = (
    "Tekst z obrazu odczytał model",
    "Zdjęcie (bez metadanych EXIF)",
    "Porównanie wykrywa",
    "Obrazy z AI rozpoznajemy",
    "Różnica w jednym miejscu",
    "Nawet niezmienione zdjęcie",
    "Nie udało się sprawdzić, czy obraz",
)


@dataclass
class Submission:
    channel: str
    session_id: str | None = None
    text: str | None = None
    url: str | None = None
    image: bytes | None = None
    audio: bytes | None = None
    # Odpowiedź na pytanie doprecyzowujące: pierwotna treść + wszystkie dotychczasowe pytania i odpowiedzi.
    parent_check_id: str | None = None
    history: list[ClarificationExchange] = field(default_factory=list)

    @classmethod
    def from_message(cls, channel: str, session_id: str | None, message: str) -> "Submission":
        """Wiadomość będącą samym adresem traktujemy jako link do pobrania, resztę jako tekst."""
        message = message.strip()
        if _URL_RE.fullmatch(message):
            return cls(channel=channel, session_id=session_id, url=message)
        return cls(channel=channel, session_id=session_id, text=message)


class _Stop(Exception):
    """Kontrolowane zakończenie bez werdyktu: awaria, prośba o doprecyzowanie lub treść poza zakresem.

    save=False oznacza, że nie zapisujemy odpowiedzi do bazy (np. przy odrzuceniu
    zapytania przed analizą – nie zaśmiecamy bazy bezużytecznymi wpisami).
    """

    def __init__(self, status: CheckStatus, message: str, error_code: str | None = None, *, save: bool = True):
        super().__init__(message)
        self.status = status
        self.message = message
        self.error_code = error_code
        self.save = save


class _Summary(BaseModel):
    """Podsumowanie całego materiału. Nie zastępuje ocen twierdzeń."""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


@dataclass
class _Run:
    channel: str
    check_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    input: InputInfo = field(default_factory=lambda: InputInfo(kind="text", text=""))
    material: str = ""
    title: str = ""
    usage: Usage = field(default_factory=Usage)
    bielik_usage: Usage = field(default_factory=Usage)
    stages_ms: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, Warning] = field(default_factory=dict)
    incidents: dict[str, IncidentMatch] = field(default_factory=dict)
    events: list[tuple[str, str, str]] = field(default_factory=list)
    quotes_rejected: int = 0
    keywords: list[str] = field(default_factory=list)
    main_topic: str = ""
    fact_check_results: list[FactCheckResult] = field(default_factory=list)
    verdict: Verdict | None = None
    confidence: float | None = None
    justification: str | None = None
    # Wynik analizy zdjęcia (odwrotne wyszukiwanie, porównanie kopii, ślady AI).
    image_analysis: ImageAnalysis | None = None
    image_sources: list[SourceRef] = field(default_factory=list)
    image_limitations: list[str] = field(default_factory=list)
    # Nadpisanie werdyktu całego materiału, gdy samo zdjęcie jest dowodem fałszu.
    image_override: tuple[str, Verdict, float, str] | None = None
    # Słowa kluczowe z Bielika, liczone w tle; None, gdy nie zdążył, zawiódł albo nic nie znalazł.
    bielik_keywords: KeywordExtraction | None = None
    parent_check_id: str | None = None
    history: list[ClarificationExchange] = field(default_factory=list)
    clarification: Clarification | None = None
    clarification_skipped: bool = False

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
        retriever: ClaimRetriever,
        context: ContextIndex,
        provider: LLMProvider | None,
        store: Store,
        cases: CaseLoop,
        source_names: dict[str, str],
        retrieval_degraded: bool = False,
        bielik_provider: LLMProvider | None = None,
        image_checks: ImageCheckService | None = None,
    ):
        self._settings = settings
        self._retriever = retriever
        self._context = context
        self._provider = provider
        self._store = store
        self._cases = cases
        self._source_names = source_names
        self._retrieval_degraded = retrieval_degraded
        self._bielik_provider = bielik_provider or self._build_bielik()
        self._image_checks = image_checks
        # Cennik wybrany w panelu ma pierwszeństwo przed wartościami z `.env`.
        self._price_override: tuple[float | None, float | None] | None = None

    def set_provider(self, provider: LLMProvider | None) -> None:
        """Podmiana modelu w locie – panel nie wymaga restartu usługi."""
        self._provider = provider

    def set_price_override(self, prices: tuple[float | None, float | None] | None) -> None:
        self._price_override = prices

    def _build_bielik(self) -> LLMProvider | None:
        """Lokalny model do ekstrakcji słów kluczowych (Ollama/vLLM, API zgodne z OpenAI)."""
        settings = self._settings
        if not (settings.bielik_base_url and settings.bielik_model):
            return None
        try:
            from app.llm.openai_compat import OpenAICompatProvider

            return OpenAICompatProvider(
                model=settings.bielik_model,
                base_url=settings.bielik_base_url,
                api_key=settings.bielik_api_key.get_secret_value() if settings.bielik_api_key else None,
                timeout_s=settings.bielik_timeout_s,
                json_mode="json_object",
                max_tokens=settings.bielik_max_tokens,
            )
        except Exception:
            log.warning("nie udało się zainicjować lokalnego modelu słów kluczowych", exc_info=True)
            return None

    async def check(self, submission: Submission) -> CheckResponse:
        run = _Run(channel=submission.channel, parent_check_id=submission.parent_check_id, history=submission.history)
        cache_key = None
        _should_save = True
        original: CheckResponse | None = None
        try:
            response, cache_key, original = await self._verify(submission, run)
        except _Stop as stop:
            response = self._response(run, stop.status, status_message=stop.message, error_code=stop.error_code)
            _should_save = stop.save
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
            # Błąd techniczny nie jest wynikiem sprawdzenia – nie zaśmiecamy bazy.
            _should_save = False

        if original is not None:
            # Deduplikacja: ta treść była już sprawdzona — zwracamy ten sam wynik z inkrementem.
            updated = self._store.increment_check_count(original.id)
            log.info(
                json.dumps(
                    {
                        "check_id": original.id,
                        "channel": submission.channel,
                        "status": "deduplicated",
                        "request_count": (updated or original).request_count,
                    }
                )
            )
            return updated or original

        if _should_save:
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
                    "summary_verdict": response.verdict.value if response.verdict else None,
                    "confidence": response.confidence,
                    "keywords": response.keywords,
                    "factchecks": len(response.fact_check_results),
                    "duration_ms": response.meta.duration_ms,
                    "stages_ms": response.meta.stages_ms,
                    "tokens_in": response.meta.tokens_in,
                    "tokens_out": response.meta.tokens_out,
                    "bielik_tokens_in": response.meta.bielik_tokens_in,
                    "bielik_tokens_out": response.meta.bielik_tokens_out,
                    "cost_usd": response.meta.cost_usd,
                    "quotes_rejected": run.quotes_rejected,
                    "cached": response.meta.cached,
                    "parent_check_id": run.parent_check_id,
                    "clarification_round": response.clarification.round if response.clarification else 0,
                    "security_events": len(run.events),
                }
            )
        )
        return response

    # --- etapy ---

    async def _verify(self, submission: Submission, run: _Run) -> tuple[CheckResponse, str, CheckResponse | None]:
        started = time.perf_counter()
        await self._prepare_input(submission, run)
        run.mark("input", started)

        model = self._provider.model if self._provider else "none"
        fingerprint = f"{self._retriever.version}|{model}|{normalize_for_match(run.material)}"
        cache_key = hashlib.sha256(fingerprint.encode()).hexdigest()

        # Permanentna deduplikacja: ta sama treść → ten sam wynik, niezależnie od czasu.
        existing = self._store.find_by_cache_key(cache_key)
        if existing:
            return existing, cache_key, existing

        since = datetime.now(UTC) - timedelta(hours=self._settings.result_cache_hours)
        cached = self._store.find_cached(cache_key, since)
        if cached:
            claims, limitations = cached.claims, cached.limitations
            run.keywords, run.main_topic = cached.keywords, cached.main_topic
            run.fact_check_results = cached.fact_check_results
            run.verdict, run.confidence = cached.verdict, cached.confidence
            run.justification = cached.justification
            for match in cached.incident_matches:
                run.incidents.setdefault(match.incident_id, match)
            for warning in cached.warnings:
                # Ostrzeżenia zależne od sposobu zgłoszenia liczymy od nowa dla bieżącego kanału.
                if warning.code not in (
                    "pii_masked",
                    "image_limits",
                    "audio_limits",
                    "input_truncated",
                    "image_manipulation",
                    "image_edit_software",
                    "ai_generated",
                    "ai_edited",
                    "content_credentials",
                    "image_analysis_unavailable",
                ):
                    run.warn(warning.code, warning.message)
        else:
            claims, limitations = await self._assess_material(run)

        self._apply_image_verdict(run)
        limitations = self._with_image_limitations(limitations, run)

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
        return response, cache_key, None

    async def _prepare_input(self, submission: Submission, run: _Run) -> None:
        origin = "user_input"
        if submission.image is not None:
            origin = "image_text"
            raw = await self._read_image_with_inspection(submission.image, run)
        elif submission.audio is not None:
            origin = "audio_text"
            raw = await self._read_audio(submission.audio, run)
        elif submission.url:
            origin = "fetched_url"
            run.input = InputInfo(kind="url", text="", url=submission.url)
            self._add_url_context(submission.url, run)
            try:
                page = await fetch_page(submission.url, self._settings)
            except UrlFetchError as exc:
                raise _Stop(CheckStatus.ERROR, f"{exc.message} {_NOT_A_VERDICT}", exc.code) from exc
            run.input.title = page.title or None
            run.title = page.title or ""
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
        if run.history:
            # Odpowiedzi to też treść od użytkownika: maskowanie i skan jak dla reszty, ale w `input` zostaje oryginał.
            answers, masked = mask_pii(sanitize_untrusted(_clarification_section(run.history)))
            if masked:
                run.warn("pii_masked", "Przed analizą ukryliśmy dane wyglądające na osobowe (np. telefon, e-mail, PESEL).")
            run.material = f"{material}\n\n{answers}"
        found = scan_injection(run.material)
        if found:
            run.flag_injection(origin, "; ".join(found))

    def _add_url_context(self, url: str, run: _Run) -> None:
        status = self._context.source_status(url)
        if status:
            run.warnings.setdefault(status.code, status)
        for match in self._context.url_matches(url):
            run.incidents.setdefault(match.incident_id, match)

    async def _read_image_with_inspection(self, data: bytes, run: _Run) -> str:
        """Czyta tekst z obrazu i równolegle sprawdza, czy obraz był przerabiany.

        Analiza obrazu nie może zepsuć odczytu tekstu: jej awaria to tylko ostrzeżenie,
        a wynik (jeśli jest) wzmacnia werdykt całego materiału.
        """
        task = (
            asyncio.create_task(self._image_checks.inspect(data))
            if self._image_checks is not None
            else None
        )
        try:
            raw = await self._read_image(data, run)
        except _Stop:
            if task is not None:
                self._apply_image_inspection(run, await self._image_result(task))
            raise
        if task is not None:
            self._apply_image_inspection(run, await self._image_result(task))
        return raw

    @staticmethod
    async def _image_result(task: "asyncio.Task[ImageInspection]") -> ImageInspection:
        try:
            return await task
        except Exception:
            log.exception("analiza zdjęcia nie powiodła się")
            return ImageInspection(
                error_code="internal_error",
                error_message="Nie udało się sprawdzić, czy zdjęcie było przerabiane.",
            )

    @staticmethod
    def _apply_image_inspection(run: _Run, inspection: ImageInspection) -> None:
        if inspection.failed:
            run.warn(
                "image_analysis_unavailable",
                "Nie udało się sprawdzić, czy zdjęcie było przerabiane ani gdzie pojawiło się wcześniej. "
                + (inspection.error_message or ""),
            )
            return
        run.image_analysis = inspection.analysis
        run.image_sources = inspection.sources
        run.image_limitations = inspection.limitations
        for warning in inspection.warnings:
            run.warnings.setdefault(warning.code, warning)

        analysis = inspection.analysis
        ai = analysis.ai if analysis else None
        if inspection.verdict is None or inspection.confidence is None or not inspection.justification:
            return
        # Zdjęcie z generatora AI albo z doklejonym fragmentem jest samo w sobie dowodem fałszu.
        if (ai and ai.result == "ai_generated") or (
            analysis and analysis.assessment == "manipulation_suspected"
        ):
            run.image_override = ("replace", inspection.verdict, inspection.confidence, inspection.justification)
        elif ai and ai.result == "ai_edited":
            run.image_override = ("downgrade", inspection.verdict, 0.5, inspection.justification)

    @staticmethod
    def _apply_image_verdict(run: _Run) -> None:
        override = run.image_override
        if override is None:
            return
        mode, verdict, confidence, justification = override
        if mode == "replace":
            run.verdict, run.confidence, run.justification = verdict, confidence, justification
        elif run.verdict == Verdict.CONFIRMED:
            run.verdict = Verdict.INSUFFICIENT
            run.confidence = min(run.confidence if run.confidence is not None else 1.0, confidence)
            run.justification = justification

    @staticmethod
    def _with_image_limitations(limitations: list[str], run: _Run) -> list[str]:
        if run.input.kind != "image":
            return limitations
        # Wiersz o OCR jest wspólny dla wszystkich ścieżek, a ograniczenia analizy mogą być świeże
        # nawet przy trafieniu w cache – dlatego stare wpisy o zdjęciu podmieniamy.
        kept = [item for item in limitations if not item.startswith(_IMAGE_LIMITATION_STARTS)]
        items = [*kept, "Tekst z obrazu odczytał model – mógł się pomylić."]
        items.extend(run.image_limitations)
        if run.image_analysis is None:
            items.append("Nie udało się sprawdzić, czy obraz jest przerobiony ani gdzie pojawił się wcześniej.")
        return items

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

    async def _read_audio(self, data: bytes, run: _Run) -> str:
        try:
            transcript, metadata = await asyncio.to_thread(transcribe_audio, data, self._settings)
        except AudioError as exc:
            raise _Stop(
                CheckStatus.ERROR,
                f"Nie udało się przygotować transkrypcji nagrania. {_NOT_A_VERDICT} Możesz wkleić treść jako tekst.",
                exc.code,
            ) from exc
        run.input = InputInfo(kind="audio", text="", audio_metadata=metadata)
        run.warn(
            "audio_limits",
            "Nagranie zamieniamy na tekst lokalnie i nie zapisujemy dźwięku. "
            "Transkrypcja może zawierać błędy; sprawdź ją, zanim wyciągniesz wnioski.",
        )
        if not transcript.strip():
            raise _Stop(
                CheckStatus.NEEDS_CLARIFICATION,
                "Nie udało się rozpoznać mowy w nagraniu. Nagraj wyraźniejszy fragment albo wklej treść jako tekst.",
            )
        return transcript

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

    async def _bielik_keywords(self, run: _Run) -> None:
        """Słowa kluczowe z lokalnego Bielika, liczone w tle od początku sprawdzenia.

        Awaria, przekroczony czas albo pusta lista nie zatrzymują sprawdzenia – wtedy słowa kluczowe
        pochodzą z zapytań wygenerowanych przy wydzielaniu twierdzeń.
        """
        assert self._bielik_provider is not None
        started = time.perf_counter()
        prompt = BIELIK_KEYWORD_PROMPT.format(title=run.title or "Brak tytułu", text=run.material[:_BIELIK_INPUT_CHARS])
        try:
            extraction, usage = await asyncio.wait_for(
                self._bielik_provider.structured(
                    system=_KEYWORD_SYSTEM, user=prompt, schema=KeywordExtraction, effort="low"
                ),
                timeout=self._settings.bielik_keywords_timeout_s,
            )
        except (LLMError, TimeoutError) as exc:
            log.warning("słowa kluczowe z Bielika niedostępne: %s", getattr(exc, "code", "timeout"))
            return
        finally:
            run.mark("bielik", started)
        run.bielik_usage.add(usage)
        if any(k.strip() for k in extraction.keywords):
            run.bielik_keywords = extraction

    async def _assess_material(self, run: _Run) -> tuple[list[ClaimResult], list[str]]:
        # Bielik na CPU to najwolniejszy etap, a jego słowa kluczowe są potrzebne dopiero Google Fact Check
        # i podsumowaniu, więc liczy się w tle. O tym, czy jest co sprawdzać, decyduje wydzielanie twierdzeń.
        bielik = asyncio.create_task(self._bielik_keywords(run)) if self._bielik_provider else None
        try:
            return await self._assess_claims(run, bielik)
        finally:
            # Sprawdzenie zakończone wcześniej (np. treść poza zakresem): nie zajmujemy CPU następnym zgłoszeniom.
            if bielik is not None and not bielik.done():
                bielik.cancel()

    async def _assess_claims(
        self, run: _Run, bielik: "asyncio.Task[None] | None"
    ) -> tuple[list[ClaimResult], list[str]]:
        today = date.today()
        started = time.perf_counter()
        can_ask = len(run.history) < self._settings.clarification_max_rounds
        system, user = extract_prompts(run.material, today, self._settings.max_claims, allow_clarification=can_ask)
        extraction = await self._ask(run, system, user, Extraction, self._settings.llm_extract_effort)
        run.mark("extract", started)
        if extraction.injection_detected:
            run.flag_injection("model_flag", "model zgłosił polecenia w analizowanym materiale")
        if extraction.input_status == "needs_clarification":
            if can_ask:
                fallback = extraction.message or "Napisz dokładniej, którą informację mam sprawdzić."
                questions = _clean_questions(extraction.questions) or [ClarifyingQuestion(text=fallback)]
                self._clarify(run, questions, [m.strip() for m in extraction.missing if m.strip()][:5])
            # Limit pytań wyczerpany, a model mimo zakazu dopytuje: sprawdzamy, co się da, albo kończymy bez pytań.
            run.clarification_skipped = True
            if not extraction.claims:
                raise _Stop(CheckStatus.NEEDS_CLARIFICATION, _CLARIFY_EXHAUSTED)
        if extraction.input_status == "out_of_scope":
            raise _Stop(
                CheckStatus.OUT_OF_SCOPE,
                extraction.message or "W tej treści nie ma informacji, którą można sprawdzić w źródłach.",
                save=False,
            )
        extracted = extraction.claims[: self._settings.max_claims]
        if not extracted:
            raise _Stop(CheckStatus.NEEDS_CLARIFICATION, "Napisz dokładniej, którą informację mam sprawdzić.")

        # Warstwa dowodowa i warstwa wspierająca są niezależne, więc liczą się równolegle.
        started = time.perf_counter()
        claims_task = asyncio.gather(
            *(self._assess_claim(run, f"c{n}", claim, today) for n, claim in enumerate(extracted, 1)),
            return_exceptions=True,
        )
        outcomes, _ = await asyncio.gather(claims_task, self._gather_support(run, extracted, bielik))
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

        started = time.perf_counter()
        await self._summarize(run, claims)
        run.mark("summary", started)
        return claims, self._limitations(run, len(extraction.claims) > len(extracted))

    def _clarify(self, run: _Run, questions: list[ClarifyingQuestion], missing: list[str]) -> None:
        """Kończy sprawdzenie pytaniami do użytkownika. To nie jest werdykt."""
        run.clarification = Clarification(
            questions=questions,
            missing=missing,
            round=len(run.history) + 1,
            max_rounds=self._settings.clarification_max_rounds,
            history=run.history,
        )
        # Pełna treść pytań w komunikacie, żeby kanały bez obsługi `clarification` (np. bot) też je pokazały.
        listed = "\n".join(f"{n}. {q.text}" for n, q in enumerate(questions, 1))
        raise _Stop(CheckStatus.NEEDS_CLARIFICATION, f"{_CLARIFY_INTRO}\n{listed}")

    async def _assess_claim(
        self, run: _Run, claim_id: str, claim: ExtractedClaim, today: date
    ) -> tuple[ClaimResult, list[CorpusDocument]]:
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
            self._retriever.search, [claim.text, *claim.queries], self._settings.retrieval_top_k, today
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
                run.flag_injection("corpus_passage", f"{hit.passage.doc.doc_id}: {'; '.join(found)}")
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

    # --- warstwa wspierająca: słowa kluczowe + Google Fact Check Tools ---

    async def _gather_support(
        self, run: _Run, extracted: list[ExtractedClaim], bielik: "asyncio.Task[None] | None"
    ) -> None:
        started = time.perf_counter()
        if bielik is not None:
            await bielik  # ograniczone własnym limitem czasu, liczonym od początku sprawdzenia
        await self._extract_keywords(run, extracted)
        run.mark("keywords", started)
        started = time.perf_counter()
        await self._query_factcheck(run)
        run.mark("factcheck", started)

    async def _extract_keywords(self, run: _Run, extracted: list[ExtractedClaim]) -> None:
        """Słowa kluczowe z Bielika; bez lokalnego modelu z modelu zdalnego; w ostateczności zapytania z twierdzeń."""
        if run.bielik_keywords is not None:
            run.keywords = [k.strip() for k in run.bielik_keywords.keywords[:_MAX_KEYWORDS] if k.strip()]
            run.main_topic = run.bielik_keywords.main_topic
            return
        if self._bielik_provider is None and self._provider is not None:
            prompt = BIELIK_KEYWORD_PROMPT.format(title=run.title or "Brak tytułu", text=run.material[:_BIELIK_INPUT_CHARS])
            try:
                extraction, usage = await self._provider.structured(
                    system=_KEYWORD_SYSTEM, user=prompt, schema=KeywordExtraction, effort="low"
                )
            except LLMError as exc:
                log.warning("ekstrakcja słów kluczowych (%s): %s", self._provider.model, exc.code)
            else:
                run.usage.add(usage)
                run.keywords = [k.strip() for k in extraction.keywords[:_MAX_KEYWORDS] if k.strip()]
                run.main_topic = extraction.main_topic
                if run.keywords:
                    run.warn(
                        "keywords_degraded",
                        "Lokalny model słów kluczowych był niedostępny – słowa kluczowe wyekstraktował model zdalny.",
                    )
                    return
        # Bielik nie zdążył lub zawiódł: kolejne wywołanie modelu tylko by opóźniło wynik, a zapytania
        # z etapu wydzielania twierdzeń wystarczą, by odpytać Google Fact Check.
        run.keywords = list(dict.fromkeys(q.strip() for c in extracted for q in c.queries if q.strip()))[:_MAX_KEYWORDS]
        run.main_topic = run.main_topic or (extracted[0].text if extracted else "")
        if run.keywords:
            run.warn(
                "keywords_degraded",
                "Lokalny model słów kluczowych nie odpowiedział na czas – użyliśmy zapytań z etapu wydzielania twierdzeń.",
            )

    async def _query_factcheck(self, run: _Run) -> None:
        """Dopasowania z Google Fact Check Tools. To kontekst wspierający, nie dowód z katalogu źródeł."""
        api_key = self._settings.google_factcheck_api_key
        if not api_key or not run.keywords:
            return
        params = {
            "key": api_key.get_secret_value(),
            "query": " OR ".join(f'"{kw}"' for kw in run.keywords[:_FACTCHECK_KEYWORDS]),
            "pageSize": 10,
            "languageCode": "pl",
        }
        try:
            async with httpx.AsyncClient(timeout=self._settings.factcheck_timeout_s) as client:
                response = await client.get(_FACTCHECK_URL, params=params)
        except httpx.HTTPError as exc:
            log.warning("Google Fact Check – błąd połączenia: %s", exc)
            run.warn("factcheck_unavailable", "Nie udało się połączyć z bazą Google Fact Check Tools.")
            return
        if response.status_code == 429:
            run.warn("factcheck_unavailable", "Przekroczono limit zapytań do Google Fact Check Tools.")
            return
        if response.status_code >= 400:
            log.warning("Google Fact Check – błąd %s", response.status_code)
            run.warn("factcheck_unavailable", "Baza Google Fact Check Tools zwróciła błąd.")
            return

        for claim in response.json().get("claims", [])[:_FACTCHECK_RESULTS]:
            reviews = claim.get("claimReview") or []
            if not reviews:
                continue
            review = reviews[0]
            publisher = review.get("publisher") or {}
            run.fact_check_results.append(
                FactCheckResult(
                    claim=claim.get("text", ""),
                    claimant=claim.get("claimant"),
                    claim_date=claim.get("claimDate"),
                    claim_review_url=review.get("url", ""),
                    claim_review_title=review.get("title", ""),
                    publisher_name=publisher.get("name", ""),
                    publisher_site=publisher.get("site", ""),
                    rating=review.get("textualRating", ""),
                    textual_rating=review.get("textualRating"),
                    url=review.get("url") or None,
                )
            )

    async def _summarize(self, run: _Run, claims: list[ClaimResult]) -> None:
        """Podsumowanie całego materiału. Awaria nie unieważnia ocen twierdzeń."""
        if not claims or self._provider is None:
            return
        claims_context = "\n\nOceny twierdzeń (powstały na podstawie cytatów ze źródeł):\n" + "\n".join(
            f"{n}. {c.text}\n   Werdykt: {c.verdict_label} (siła dowodów: {c.strength.level})\n"
            f"   Uzasadnienie: {c.justification}"
            for n, c in enumerate(claims, 1)
        )
        if run.fact_check_results:
            factcheck_context = "\n\nZnalezione sprawdzenia faktów (Google Fact Check Tools):\n" + "\n".join(
                f"{n}. Twierdzenie: {fc.claim}\n   Źródło: {fc.publisher_name} ({fc.publisher_site})\n"
                f"   Ocena: {fc.rating}\n   Link: {fc.claim_review_url}"
                for n, fc in enumerate(run.fact_check_results, 1)
            )
        else:
            factcheck_context = "\n\nBrak znalezionych sprawdzeń faktów w Google Fact Check Tools."

        prompt = DEEPSEEK_VERDICT_PROMPT.format(
            title=run.title or "Brak tytułu",
            today=date.today().isoformat(),
            text=run.material[:10000],
            keywords=", ".join(run.keywords),
            main_topic=run.main_topic,
            claims_context=claims_context,
            factcheck_context=factcheck_context,
        )
        try:
            summary, usage = await self._provider.structured(
                system="Jesteś ekspertem ds. weryfikacji informacji i wykrywania dezinformacji. "
                "Podsumowujesz oceny twierdzeń. Odpowiadasz wyłącznie obiektem JSON.",
                user=prompt,
                schema=_Summary,
                effort="medium",
            )
        except LLMError as exc:
            log.warning("podsumowanie niedostępne: %s", exc.code)
            return
        run.usage.add(usage)
        run.verdict = _reconcile(summary.verdict, claims)
        run.confidence = summary.confidence if run.verdict == summary.verdict else min(summary.confidence, 0.5)
        run.justification = summary.justification

    # --- składanie odpowiedzi ---

    def _limitations(self, run: _Run, claims_truncated: bool) -> list[str]:
        built_at = self._retriever.built_at
        built = built_at.date().isoformat() if built_at else "nieznana data"
        items = [
            f"Odpowiedź opiera się wyłącznie na źródłach z korpusu Prawdowida (stan na {built}). Nowsze informacje mogły nie zostać uwzględnione.",
            "Uzasadnienie to interpretacja modelu językowego. Cytaty i linki pochodzą ze źródeł – przeczytaj je i oceń samodzielnie.",
        ]
        if run.fact_check_results:
            items.append("Sprawdzenia z Google Fact Check Tools to materiał pomocniczy – oceniły je zewnętrzne redakcje, nie Prawdowid.")
        else:
            items.append("Brak sprawdzeń w Google Fact Check Tools nie oznacza, że informacja jest prawdziwa.")
        if run.input.kind == "url":
            items.append("Sprawdziliśmy treść strony pobraną w chwili zgłoszenia. Strona mogła się później zmienić.")
        # Ograniczenia odczytu i analizy zdjęcia dokłada `_with_image_limitations`, gdy znamy jej wynik.
        if run.input.kind == "audio":
            items.append("Nagranie zostało zamienione na tekst lokalnie; transkrypcja może zawierać błędy. Nie oceniamy autentyczności nagrania.")
        if claims_truncated:
            items.append(f"Sprawdziliśmy {self._settings.max_claims} najważniejsze twierdzenia z tej treści.")
        if run.clarification_skipped:
            items.append("Mimo doprecyzowania nie było w pełni jasne, co sprawdzić. Sprawdziliśmy treść w obecnej postaci.")
        return items

    async def _related_materials(self, material: str) -> list[SourceRef]:
        docs = await asyncio.to_thread(self._retriever.related_materials, material, 5)
        return [source_ref(d, self._source_names.get(d.source_key, d.publisher)) for d in docs]

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
        clarification = run.clarification
        if clarification is None and run.history:
            clarification = Clarification(
                round=len(run.history), max_rounds=self._settings.clarification_max_rounds, history=run.history
            )
        override = self._price_override or (
            self._settings.llm_price_input_per_mtok,
            self._settings.llm_price_output_per_mtok,
        )
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
            verdict=run.verdict,
            verdict_label=VERDICT_LABELS[run.verdict] if run.verdict else None,
            confidence=run.confidence,
            justification=run.justification,
            keywords=run.keywords,
            main_topic=run.main_topic,
            fact_check_results=run.fact_check_results,
            source_articles=[*_used_sources(claims or []), *run.image_sources],
            limitations=limitations or [],
            image_analysis=run.image_analysis,
            parent_check_id=run.parent_check_id,
            clarification=clarification,
            meta=CheckMeta(
                duration_ms=int((time.perf_counter() - run.started) * 1000),
                stages_ms=run.stages_ms,
                provider=provider.name if provider else None,
                model=provider.model if provider else None,
                bielik_model=self._settings.bielik_model if self._bielik_provider else None,
                llm_calls=run.usage.calls,
                tokens_in=run.usage.input_tokens,
                tokens_out=run.usage.output_tokens,
                bielik_tokens_in=run.bielik_usage.input_tokens,
                bielik_tokens_out=run.bielik_usage.output_tokens,
                cost_usd=estimate_cost(provider.model, run.usage, override) if provider else None,
                retrieval_mode=self._retriever.mode,  # type: ignore[arg-type]
                corpus_version=self._retriever.version,
                processing_location=self._settings.processing_location,
                cached=cached,
                related_count=len(run.incidents),
                embedding_model=self._retriever.embedder.model if self._retriever.embedder else None,
            ),
        )


def _clarification_section(history: list[ClarificationExchange]) -> str:
    lines = ["Doprecyzowanie od użytkownika:"]
    for exchange in history:
        lines.extend(f"Pytanie: {question}" for question in exchange.questions)
        lines.append(f"Odpowiedź: {exchange.answer}")
    return "\n".join(lines)


def _clean_questions(questions: list[ClarifyingQuestion]) -> list[ClarifyingQuestion]:
    cleaned = []
    for question in questions:
        text = question.text.strip()
        if text:
            options = [o.strip() for o in question.options if o.strip()][:_MAX_OPTIONS]
            cleaned.append(ClarifyingQuestion(text=text, options=options))
    return cleaned[:_MAX_QUESTIONS]


def _used_sources(claims: list[ClaimResult]) -> list[SourceRef]:
    """Źródła, na których faktycznie oparto odpowiedź – do zapisu przebiegu (§3 wymagań).

    Bierzemy je z `evidence`, czyli z cytatów już zweryfikowanych w źródle, więc zapis
    pokazuje dokładnie to, co rozstrzygnęło werdykt. Jeden dokument cytowany przy kilku
    twierdzeniach pojawia się raz; kolejność jest stabilna (kolejność cytowania).
    """
    used: dict[str, SourceRef] = {}
    for claim in claims:
        for item in claim.evidence:
            used.setdefault(item.source.doc_id, item.source)
    return list(used.values())


def _reconcile(proposed: Verdict, claims: list[ClaimResult]) -> Verdict:
    """Podsumowanie nie może być mocniejsze niż oceny twierdzeń, z których wynika.

    Oceny twierdzeń powstają z cytatów zweryfikowanych w źródłach; podsumowanie jest
    tylko interpretacją modelu, więc nie wolno mu rozstrzygać tam, gdzie dowodów nie było.
    """
    decided = {c.verdict for c in claims} - {Verdict.NOT_VERIFIABLE}
    if not decided:
        # Same opinie i prognozy – nie ma czego podsumowywać poza tym stwierdzeniem.
        return Verdict.NOT_VERIFIABLE
    if decided == {Verdict.INSUFFICIENT}:
        return Verdict.INSUFFICIENT
    if proposed in (Verdict.CONFIRMED, Verdict.FALSE) and proposed not in decided:
        # Model rozstrzyga mocniej niż dowody – schodzimy do oceny wprowadzającej w błąd
        # albo do wstrzymania się, zależnie od tego, co faktycznie wyszło z dowodów.
        return Verdict.MISLEADING if Verdict.MISLEADING in decided else Verdict.INSUFFICIENT
    return proposed


def _summary(claims: list[ClaimResult]) -> str:
    counts = Counter(c.verdict for c in claims)
    parts = ", ".join(f"{VERDICT_LABELS[v].lower()} – {n}" for v, n in counts.items())
    return f"Liczba sprawdzonych twierdzeń: {len(claims)}. Wyniki: {parts}."
