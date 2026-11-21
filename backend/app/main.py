import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, checks
from app.config import Settings, get_settings
from app.core.pipeline import VerificationService
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.retrieval.corpus import CorpusStore
from app.retrieval.embeddings import build_embedder
from app.retrieval.service import RetrievalService
from app.store.db import Store
from app.store.models import EMBEDDING_DIM

log = logging.getLogger("prawdowid")
_PURGE_INTERVAL_S = 3600


def build_state(
    app: FastAPI,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
) -> None:
    """Składa zależności aplikacji. Testy podają tu własny model."""
    store = Store(settings.database_url)
    corpus = CorpusStore(store.engine)
    if settings.embedding_backend != "none" and settings.embedding_dim != EMBEDDING_DIM:
        raise ValueError(
            f"EMBEDDING_DIM={settings.embedding_dim} nie zgadza się z wymiarem kolumny "
            f"vector({EMBEDDING_DIM}) w bazie. Dla MVP wymiar jest stały."
        )
    embedder = build_embedder(settings)
    retriever = RetrievalService(settings, corpus, embedder)
    app.state.settings = settings
    app.state.store = store
    app.state.corpus = corpus
    app.state.retriever = retriever
    app.state.embedder = embedder
    app.state.ingest_running = False
    app.state.limiter = None  # Will be set after service creation
    app.state.service = VerificationService(
        settings=settings,
        provider=provider,
        store=store,
        retriever=retriever,
    )
    # Update limiter with service reference
    from app.security.ratelimit import RateLimiter
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)


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
    provider = await asyncio.to_thread(build_provider, settings)
    await asyncio.to_thread(build_state, app, settings, provider=provider)
    log.info("Usługa uruchomiona. LLM: %s, Bielik: %s", settings.llm_model, settings.bielik_model)
    purge = asyncio.create_task(_purge_loop(app))
    yield
    purge.cancel()
    with suppress(asyncio.CancelledError):
        await purge


def create_app(with_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="Prawdowid API",
        description="Wykrywanie fake news: URL -> trafilatura -> Bielik (keywords) -> Google Fact Check -> DeepSeek (verdict)",
        version="0.2.0",
        lifespan=lifespan if with_lifespan else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
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

    app.include_router(checks.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    return app


app = create_app()
