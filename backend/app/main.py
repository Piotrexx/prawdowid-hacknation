import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, checks
from app.config import Settings, get_settings
from app.core.cases import CaseLoop
from app.core.pipeline import VerificationService
from app.ingest.registry import source_names
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.retrieval.claims import ClaimRetriever
from app.retrieval.context import ContextIndex
from app.retrieval.corpus import CorpusStore
from app.retrieval.embeddings import Embedder, build_embedder
from app.security.ratelimit import RateLimiter
from app.store.db import Store
from app.store.models import EMBEDDING_DIM

log = logging.getLogger("prawdowid")
_PURGE_INTERVAL_S = 3600


def load_embedder(settings: Settings) -> Embedder | None:
    return build_embedder(settings)


def build_state(
    app: FastAPI,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
    bielik_provider: LLMProvider | None = None,
    embedder: Embedder | None = None,
    corpus: CorpusStore | None = None,
    retriever: ClaimRetriever | None = None,
    context: ContextIndex | None = None,
) -> None:
    """Składa zależności aplikacji. Testy podają tu własny model, embedder i korpus."""
    store = Store(settings.database_url)
    corpus = corpus or CorpusStore(store.engine)
    if settings.embedding_backend != "none" and settings.embedding_dim != EMBEDDING_DIM:
        raise ValueError(
            f"EMBEDDING_DIM={settings.embedding_dim} nie zgadza się z wymiarem kolumny "
            f"vector({EMBEDDING_DIM}) w bazie. Dla MVP wymiar jest stały."
        )
    if embedder is None and settings.embedding_backend != "none":
        embedder = build_embedder(settings)
    retriever = retriever or ClaimRetriever(settings, corpus, embedder)
    context = context or ContextIndex(corpus, embedder)
    cases = CaseLoop(settings, store, embedder)
    service = VerificationService(
        settings=settings,
        retriever=retriever,
        context=context,
        provider=provider,
        store=store,
        cases=cases,
        source_names=source_names(),
        retrieval_degraded=settings.embedding_backend != "none" and retriever.mode == "bm25",
        bielik_provider=bielik_provider,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.corpus = corpus
    app.state.embedder = embedder
    app.state.retriever = retriever
    app.state.context = context
    app.state.service = service
    app.state.llm_ready = provider is not None
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.ingest_running = False
    app.state.last_ingest = None


async def _purge_loop(app: FastAPI) -> None:
    while True:
        cutoff = datetime.now(UTC) - timedelta(days=app.state.settings.retention_days)
        deleted = await asyncio.to_thread(app.state.store.purge_older_than, cutoff)
        if deleted:
            log.info("retencja: usunięto %d sprawdzeń starszych niż %s", deleted, cutoff.date())
        await asyncio.sleep(_PURGE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Adresy żądań mogą zawierać parametry; nie logujemy ich na poziomie INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    embedder = await asyncio.to_thread(load_embedder, settings)
    provider = await asyncio.to_thread(build_provider, settings)
    await asyncio.to_thread(build_state, app, settings, provider=provider, embedder=embedder)
    log.info(
        "korpus: %s, wyszukiwanie: %s, model: %s, słowa kluczowe: %s",
        app.state.retriever.stats().model_dump(mode="json"),
        app.state.retriever.mode,
        settings.llm_model,
        settings.bielik_model if app.state.service._bielik_provider else "niedostępny",
    )
    purge = asyncio.create_task(_purge_loop(app))
    yield
    purge.cancel()
    with suppress(asyncio.CancelledError):
        await purge


def create_app(with_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="Prawdowid API",
        description=(
            "Weryfikacja informacji oparta na jawnym katalogu źródeł: twierdzenia są oceniane na podstawie "
            "cytatów zweryfikowanych w źródłach, a Google Fact Check Tools i podsumowanie modelu stanowią "
            "warstwę wspierającą. Jedna logika dla wszystkich kanałów."
        ),
        version="0.2.0",
        lifespan=lifespan if with_lifespan else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        # Numer sesji i zgoda jadą w ciasteczkach; bez tego przeglądarka ich nie wyśle.
        # Lista origins jest jawna (nigdy "*"), więc credentials są dozwolone.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Admin-Token"],
        expose_headers=["Retry-After", "Content-Disposition"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    for router in (checks.router, admin.router):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
