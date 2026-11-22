"""Pipeline wykrywania fake news: URL/tekst -> trafilatura -> Bielik (keywords + doprecyzowanie) -> Google Fact Check -> DeepSeek (verdict)."""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.core.prompts import BIELIK_KEYWORD_PROMPT, CLARITY_PROMPT, DEEPSEEK_VERDICT_PROMPT
from app.llm.base import LLMError, LLMProvider, T, Usage, estimate_cost
from app.llm.factory import build_provider
from app.schemas import (
    CheckMeta,
    Clarification,
    ClarityCheck,
    ClarificationExchange,
    ClarifyingQuestion,
    CheckRequest,
    CheckResponse,
    CheckStatus,
    FactCheckResult,
    InputInfo,
    KeywordExtraction,
    VerdictLabel,
)
from app.security.urlfetch import UrlFetchError, fetch_page
from app.store.db import Store
from app.textutil import truncate

log = logging.getLogger("check")

_STORED_PAGE_CHARS = 1500
_MIN_TEXT_WORDS = 4
_MAX_QUESTIONS = 3
_MAX_OPTIONS = 5
_CLARIFY_INTRO = "Zanim sprawdzę, potrzebuję kilku szczegółów."
_SHORT_TEXT_QUESTION = ClarifyingQuestion(
    text="Jakie konkretnie twierdzenie mam sprawdzić? Napisz, kto co powiedział albo co się wydarzyło – a jeśli wiesz, to także kiedy i gdzie."
)
_NOT_A_VERDICT = "To problem techniczny, a nie wynik sprawdzenia."
_LLM_MESSAGES = {
    "llm_not_configured": f"Usługa nie ma teraz dostępu do modelu językowego, więc nie mogę ocenić tej treści. {_NOT_A_VERDICT}",
    "llm_unavailable": f"Nie mogę teraz połączyć się z modelem językowym, więc nie sprawdzę tej treści. {_NOT_A_VERDICT} Spróbuj ponownie za chwilę.",
    "llm_rate_limited": f"Usługa jest chwilowo przeciążona. {_NOT_A_VERDICT} Spróbuj ponownie za kilka minut.",
    "llm_refused": "Model językowy odmówił przetworzenia tej treści, więc nie mogę jej sprawdzić. To ograniczenie techniczne, a nie wynik sprawdzenia.",
    "llm_bad_output": f"Model językowy zwrócił niepełną odpowiedź. {_NOT_A_VERDICT} Spróbuj ponownie.",
    "bielik_not_configured": f"Model Bielik nie jest skonfigurowany. {_NOT_A_VERDICT}",
    "bielik_unavailable": f"Nie mogę połączyć się z modelem Bielik. {_NOT_A_VERDICT} Sprawdź czy Ollama/vLLM działa.",
    "factcheck_not_configured": f"Google Fact Check API nie jest skonfigurowane. {_NOT_A_VERDICT}",
    "factcheck_unavailable": f"Nie mogę połączyć się z Google Fact Check API. {_NOT_A_VERDICT} Spróbuj ponownie za chwilę.",
}


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
    input: InputInfo = field(default_factory=lambda: InputInfo(kind="url", text="", url=""))
    article_title: str = ""
    article_text: str = ""
    article_url: str = ""
    usage: Usage = field(default_factory=Usage)
    bielik_usage: Usage = field(default_factory=Usage)
    stages_ms: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    events: list[tuple[str, str, str]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    main_topic: str = ""
    fact_check_results: list[FactCheckResult] = field(default_factory=list)
    verdict: VerdictLabel | None = None
    confidence: float | None = None
    justification: str | None = None
    parent_check_id: str | None = None
    history: list[ClarificationExchange] = field(default_factory=list)
    clarification: Clarification | None = None
    clarification_skipped: bool = False

    def mark(self, stage: str, since: float) -> None:
        self.stages_ms[stage] = self.stages_ms.get(stage, 0) + int((time.perf_counter() - since) * 1000)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class _VerdictOnly(BaseModel):
    """Schema dla werdyktu od DeepSeek."""
    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


class VerificationService:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider | None,
        store: Store,
    ):
        self._settings = settings
        self._provider = provider
        self._store = store
        self._bielik_provider: LLMProvider | None = None
        self._init_bielik()

    def _init_bielik(self) -> None:
        """Inicjalizuje providera Bielik (Ollama/vLLM compatibile z OpenAI API)."""
        if self._settings.bielik_base_url and self._settings.bielik_model:
            try:
                from app.llm.openai_compat import OpenAICompatProvider
                self._bielik_provider = OpenAICompatProvider(
                    model=self._settings.bielik_model,
                    base_url=self._settings.bielik_base_url,
                    api_key=self._settings.bielik_api_key.get_secret_value() if self._settings.bielik_api_key else None,
                    timeout_s=self._settings.bielik_timeout_s,
                    json_mode="json_object",
                )
            except Exception as e:
                log.warning("Nie udało się zainicjować Bielik: %s", e)

    async def check(self, request: CheckRequest, parent: CheckResponse | None = None) -> CheckResponse:
        """`parent` to sprawdzenie z pytaniem doprecyzowującym, na które `request.text` jest odpowiedzią."""
        run = _Run(channel="web")
        cache_key = None
        try:
            response, cache_key = await self._verify(request, run, parent)
        except _Stop as stop:
            response = self._response(run, stop.status, status_message=stop.message, error_code=stop.error_code)
        except Exception:
            log.exception("nieoczekiwany błąd sprawdzenia %s", run.check_id)
            response = self._response(
                run,
                CheckStatus.ERROR,
                status_message=f"Wystąpił nieoczekiwany błąd. {_NOT_A_VERDICT} Spróbuj ponownie.",
                error_code="internal_error",
            )
        self._store.save_check(response, request.session_id, cache_key)
        for kind, origin, detail in run.events:
            self._store.add_event(kind, origin, detail, response.id)
        log.info(
            json.dumps(
                {
                    "check_id": response.id,
                    "channel": response.channel,
                    "status": response.status.value,
                    "error_code": response.error_code,
                    "verdict": response.verdict.value if response.verdict else None,
                    "confidence": response.confidence,
                    "duration_ms": response.meta.duration_ms,
                    "stages_ms": response.meta.stages_ms,
                    "tokens_in": response.meta.tokens_in,
                    "tokens_out": response.meta.tokens_out,
                    "bielik_tokens_in": run.bielik_usage.input_tokens,
                    "bielik_tokens_out": run.bielik_usage.output_tokens,
                    "cost_usd": response.meta.cost_usd,
                    "cached": response.meta.cached,
                    "parent_check_id": run.parent_check_id,
                    "clarification_round": response.clarification.round if response.clarification else 0,
                    "security_events": len(run.events),
                }
            )
        )
        return response

    async def _verify(
        self, request: CheckRequest, run: _Run, parent: CheckResponse | None
    ) -> tuple[CheckResponse, str]:
        started = time.perf_counter()
        url, text = request.url, request.text

        # Odpowiedź na pytanie: sprawdzamy pierwotną treść, a odpowiedzi dokładamy jako kontekst.
        if parent is not None:
            asked = parent.clarification or Clarification()
            run.parent_check_id = parent.id
            run.history = [
                *asked.history,
                ClarificationExchange(questions=[q.text for q in asked.questions], answer=(text or "").strip()),
            ]
            if parent.input.kind == "url":
                url, text = parent.input.url, None
            else:
                url, text = None, parent.input.text

        # 1. Pobierz i wyekstrahuj treść artykułu (trafilatura) albo przyjmij wklejony tekst
        if url:
            await self._fetch_article(url, run)
        else:
            self._use_text(text or "", run)
        run.mark("fetch", started)

        if run.input.kind == "text" and not run.history and len(run.article_text.split()) < _MIN_TEXT_WORDS:
            self._ask(run, [_SHORT_TEXT_QUESTION], ["konkretne twierdzenie"])

        # 2. Słowa kluczowe (Bielik) i ocena, czy wiadomo, co sprawdzać – równolegle. Gdy trzeba dopytać,
        # pytanie wraca od razu, a słowa kluczowe są zbędne (po odpowiedzi sprawdzamy od nowa).
        keywords = asyncio.create_task(self._extract_keywords(run))
        try:
            clarity = await self._check_clarity(run)
            if clarity is not None and clarity.needs_clarification:
                questions = self._clean_questions(clarity.questions)
                if questions:
                    if len(run.history) < self._settings.clarification_max_rounds:
                        self._ask(run, questions, [m for m in clarity.missing if m.strip()][:5])
                    run.clarification_skipped = True
            await keywords
        finally:
            if not keywords.done():
                keywords.cancel()
            elif not keywords.cancelled():
                keywords.exception()  # błąd już obsłużony albo zbędny – bez ostrzeżenia o nieodebranym wyjątku
        run.mark("keywords", started)

        # 3. Zapytanie do Google Fact Check Tools API
        await self._query_factcheck(run)
        run.mark("factcheck", started)

        # 4. Werdykt przez DeepSeek
        await self._get_verdict(run)
        run.mark("verdict", started)

        # Cache key
        answers = [exchange.answer for exchange in run.history]
        source = run.article_url or hashlib.sha256(run.article_text.encode()).hexdigest()
        fingerprint = f"{source}|{self._provider.model if self._provider else 'none'}|{run.keywords}|{answers}"
        cache_key = hashlib.sha256(fingerprint.encode()).hexdigest()

        response = self._response(run, CheckStatus.COMPLETED, cached=False)
        return response, cache_key

    def _use_text(self, text: str, run: _Run) -> None:
        """Wiadomość wklejona przez użytkownika – sprawdzamy ją bez pobierania czegokolwiek z sieci."""
        run.article_text = text.strip()
        run.input = InputInfo(kind="text", text=run.article_text, url="")

    def _clean_questions(self, questions: list[ClarifyingQuestion]) -> list[ClarifyingQuestion]:
        cleaned = []
        for question in questions:
            text = question.text.strip()
            if not text:
                continue
            options = [option.strip() for option in question.options if option.strip()][:_MAX_OPTIONS]
            cleaned.append(ClarifyingQuestion(text=text, options=options))
        return cleaned[:_MAX_QUESTIONS]

    def _ask(self, run: _Run, questions: list[ClarifyingQuestion], missing: list[str]) -> None:
        """Kończy sprawdzenie pytaniem do użytkownika. To nie jest werdykt."""
        run.clarification = Clarification(
            questions=questions,
            missing=missing,
            round=len(run.history) + 1,
            max_rounds=self._settings.clarification_max_rounds,
            history=run.history,
        )
        # Pełna treść pytań w komunikacie, żeby kanały bez obsługi `clarification` (np. bot) też je pokazały.
        listed = "\n".join(f"{i}. {q.text}" for i, q in enumerate(questions, 1))
        raise _Stop(CheckStatus.NEEDS_CLARIFICATION, f"{_CLARIFY_INTRO}\n{listed}")

    def _clarification_context(self, run: _Run) -> str:
        if not run.history:
            return ""
        lines = ["", "Doprecyzowanie od użytkownika:"]
        for exchange in run.history:
            for question in exchange.questions:
                lines.append(f"Pytanie: {question}")
            lines.append(f"Odpowiedź: {exchange.answer}")
        return "\n".join(lines) + "\n"

    async def _fetch_article(self, url: str, run: _Run) -> None:
        """Pobiera artykuł i ekstrahuje treść używając trafilatura."""
        try:
            page = await fetch_page(url, self._settings)
        except UrlFetchError as exc:
            raise _Stop(CheckStatus.ERROR, f"{exc.message} {_NOT_A_VERDICT}", exc.code) from exc

        run.article_url = url
        run.article_title = page.title or ""
        run.article_text = page.text

        if not run.article_text.strip():
            raise _Stop(CheckStatus.ERROR, "Nie udało się wyekstrahować treści z tego artykułu.", "url_no_content")

        # Przygotuj input info dla odpowiedzi
        run.input = InputInfo(
            kind="url",
            text=truncate(run.article_text, _STORED_PAGE_CHARS),
            url=url,
            title=run.article_title or None,
        )

    async def _check_clarity(self, run: _Run) -> ClarityCheck | None:
        """Czy wiadomo, które twierdzenie sprawdzić. Awaria modelu nie zatrzymuje sprawdzenia."""
        choice = self._settings.clarification_model
        provider = {"llm": self._provider, "bielik": self._bielik_provider}.get(choice)
        if provider is None:
            return None
        try:
            result, usage = await provider.structured(
                system="Pomagasz ustalić, co dokładnie użytkownik chce sprawdzić. Odpowiadasz wyłącznie obiektem JSON.",
                user=CLARITY_PROMPT.format(
                    title=run.article_title or "Brak tytułu",
                    text=run.article_text[:8000],
                    clarifications=self._clarification_context(run),
                ),
                schema=ClarityCheck,
                effort="low",
            )
        except LLMError as exc:
            log.warning("ocena doprecyzowania (%s) niedostępna: %s (%s)", choice, exc.code, exc)
            return None
        (run.bielik_usage if provider is self._bielik_provider else run.usage).add(usage)
        return result

    async def _extract_keywords(self, run: _Run) -> KeywordExtraction:
        """Używa Bielik 4.5B Instruct do ekstrakcji słów kluczowych z tytułu i treści.
        Jeśli Bielik nie jest dostępny, używa DeepSeek jako fallback."""
        if self._bielik_provider is None and self._provider is None:
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES["bielik_not_configured"], "bielik_not_configured")
        provider = self._bielik_provider or self._provider
        if provider is None:
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES["bielik_not_configured"], "bielik_not_configured")

        # Prompt w polsku - tylko po polsku
        user_prompt = BIELIK_KEYWORD_PROMPT.format(
            title=run.article_title or "Brak tytułu",
            text=run.article_text[:8000],  # Limit kontekstu
            clarifications=self._clarification_context(run),
        )

        try:
            extraction, usage = await provider.structured(
                system="Jesteś ekspertem ds. analizy mediów i wykrywania dezinformacji. Odpowiadasz wyłącznie obiektem JSON.",
                user=user_prompt,
                schema=KeywordExtraction,
                effort="low",
            )
        except LLMError as exc:
            log.warning("Bielik/keyword błąd: %s (%s)", exc.code, exc)
            # If Bielik failed and we have a fallback (DeepSeek), try it instead of stopping.
            if provider is self._bielik_provider and self._provider is not None:
                log.warning("Bielik niedostępny – używam DeepSeek jako fallback dla ekstrakcji słów kluczowych")
                run.add_warning("Lokalny model Bielik był niedostępny – słowa kluczowe zostały wyekstrahowane przez DeepSeek.")
                try:
                    extraction, usage = await self._provider.structured(
                        system="Jesteś ekspertem ds. analizy mediów i wykrywania dezinformacji. Odpowiadasz wyłącznie obiektem JSON.",
                        user=user_prompt,
                        schema=KeywordExtraction,
                        effort="low",
                    )
                except LLMError as exc2:
                    log.warning("DeepSeek fallback/keyword błąd: %s (%s)", exc2.code, exc2)
                    raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES.get(exc2.code, _LLM_MESSAGES["llm_unavailable"]), exc2.code) from exc2
                run.usage.add(usage)
                run.keywords = extraction.keywords[:10]
                run.main_topic = extraction.main_topic
                if not run.keywords:
                    run.add_warning("Nie udało się wyekstrahować słów kluczowych z artykułu.")
                return extraction
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES.get(exc.code, _LLM_MESSAGES["bielik_unavailable"]), exc.code) from exc

        if self._bielik_provider is not None:
            run.bielik_usage.add(usage)
        else:
            run.usage.add(usage)
        run.keywords = extraction.keywords[:10]  # Max 10 słów kluczowych
        run.main_topic = extraction.main_topic

        if not run.keywords:
            run.add_warning("Nie udało się wyekstrahować słów kluczowych z artykułu.")
        return extraction

    async def _query_factcheck(self, run: _Run) -> None:
        """Zapytuje Google Fact Check Tools API o sprawdzenia powiązane ze słowami kluczowymi."""
        api_key = self._settings.google_factcheck_api_key
        if not api_key:
            run.add_warning("Google Fact Check API nie jest skonfigurowane - pomijam weryfikację zewnętrzną.")
            return

        # Budujemy zapytanie ze słów kluczowych
        query = " OR ".join(f'"{kw}"' for kw in run.keywords[:5])
        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        params = {
            "key": api_key.get_secret_value(),
            "query": query,
            "pageSize": 10,
            "languageCode": "pl",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.warning("Google Fact Check API błąd połączenia: %s", exc)
            run.add_warning("Nie udało się połączyć z Google Fact Check API.")
            return

        if response.status_code == 429:
            run.add_warning("Przekroczono limit zapytań do Google Fact Check API.")
            return
        if response.status_code >= 400:
            log.warning("Google Fact Check API błąd %s: %s", response.status_code, response.text)
            run.add_warning("Błąd Google Fact Check API.")
            return

        data = response.json()
        claims = data.get("claims", [])

        # Bierzemy top 5
        for claim in claims[:5]:
            claim_review = claim.get("claimReview", [])
            if not claim_review:
                continue
            review = claim_review[0]  # Pierwsza recenzja
            publisher = review.get("publisher", {})
            result = FactCheckResult(
                claim=claim.get("text", ""),
                claimant=claim.get("claimant"),
                claim_date=claim.get("claimDate"),
                claim_review_url=review.get("url", ""),
                claim_review_title=review.get("title", ""),
                publisher_name=publisher.get("name", ""),
                publisher_site=publisher.get("site", ""),
                rating=review.get("textualRating", ""),
                textual_rating=review.get("textualRating"),
                url=claim.get("claimReview", [{}])[0].get("url", ""),
            )
            run.fact_check_results.append(result)

        if not run.fact_check_results:
            run.add_warning("Nie znaleziono powiązanych sprawdzeń faktów w Google Fact Check.")

    async def _get_verdict(self, run: _Run) -> None:
        """Używa DeepSeek do oceny czy artykuł to fake news na podstawie danych."""
        if self._provider is None:
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES["llm_not_configured"], "llm_not_configured")

        # Przygotuj kontekst z fakt-checków
        factcheck_context = ""
        if run.fact_check_results:
            factcheck_context = "\n\nZnalezione sprawdzenia faktów (Google Fact Check Tools):\n"
            for i, fc in enumerate(run.fact_check_results, 1):
                factcheck_context += (
                    f"{i}. Twierdzenie: {fc.claim}\n"
                    f"   Źródło: {fc.publisher_name} ({fc.publisher_site})\n"
                    f"   Ocena: {fc.rating}\n"
                    f"   Link: {fc.claim_review_url}\n"
                )
        else:
            factcheck_context = "\n\nBrak znalezionych sprawdzeń faktów w Google Fact Check Tools."

        user_prompt = DEEPSEEK_VERDICT_PROMPT.format(
            title=run.article_title or "Brak tytułu",
            text=run.article_text[:10000],
            keywords=", ".join(run.keywords),
            main_topic=run.main_topic,
            factcheck_context=factcheck_context,
            clarifications=self._clarification_context(run),
        )

        try:
            verdict, usage = await self._provider.structured(
                system="Jesteś ekspertem ds. weryfikacji informacji i wykrywania dezinformacji. "
                       "Analizujesz artykuły pod kątem fake news. Odpowiadasz wyłącznie obiektem JSON.",
                user=user_prompt,
                schema=_VerdictOnly,
                effort="medium",
            )
        except LLMError as exc:
            log.warning("DeepSeek błąd: %s (%s)", exc.code, exc)
            raise _Stop(CheckStatus.ERROR, _LLM_MESSAGES.get(exc.code, _LLM_MESSAGES["llm_unavailable"]), exc.code) from exc

        run.usage.add(usage)
        run.verdict = verdict.verdict
        run.confidence = verdict.confidence
        run.justification = verdict.justification

    def _response(
        self,
        run: _Run,
        status: CheckStatus,
        *,
        status_message: str | None = None,
        error_code: str | None = None,
        cached: bool = False,
    ) -> CheckResponse:
        provider = self._provider
        override = (self._settings.llm_price_input_per_mtok, self._settings.llm_price_output_per_mtok)
        clarification = run.clarification
        if clarification is None and run.history:
            clarification = Clarification(
                round=len(run.history), max_rounds=self._settings.clarification_max_rounds, history=run.history
            )
        if run.input.kind == "text":
            source_note = "Analiza opiera się wyłącznie na tekście wklejonym przez użytkownika."
        else:
            source_note = "Analiza opiera się na treści artykułu pobranej w momencie sprawdzenia. Strona mogła się później zmienić."
        limitations = [
            source_note,
            "Werdykt to interpretacja modelu językowego opartego na dostępnych sprawdzeniach faktów.",
            "Brak sprawdzeń w Google Fact Check nie oznacza, że informacja jest prawdziwa.",
        ]
        if run.clarification_skipped:
            limitations.append(
                "Mimo doprecyzowania nie było w pełni jasne, które twierdzenie sprawdzić. Sprawdziłem treść w obecnej postaci."
            )
        return CheckResponse(
            id=run.check_id,
            created_at=datetime.now(UTC),
            channel=run.channel,
            status=status,
            status_message=status_message,
            error_code=error_code,
            input=run.input,
            verdict=run.verdict,
            verdict_label=run.verdict.value if run.verdict else None,
            confidence=run.confidence,
            justification=run.justification,
            keywords=run.keywords,
            main_topic=run.main_topic,
            fact_check_results=run.fact_check_results,
            source_articles=[],
            limitations=limitations,
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
                cost_usd=estimate_cost(provider.model, run.usage, override) if provider else None,
                processing_location=self._settings.processing_location,
                cached=cached,
            ),
        )