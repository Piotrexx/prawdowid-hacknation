import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, checks
from app.catalog import load_catalog
from app.channels import sms
from app.config import Settings, get_settings
from app.core.cases import CaseLoop
from app.core.pipeline import VerificationService
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.retrieval.context import ContextCatalog
from app.retrieval.index import CorpusIndex, Embedder, FastEmbedEmbedder
from app.security.ratelimit import RateLimiter
from app.store.db import Store

log = logging.getLogger("prawdowid")
_PURGE_INTERVAL_S = 3600


def load_embedder(settings: Settings) -> Embedder | None:
    if settings.embeddings == "off":
        return None
    try:
        return FastEmbedEmbedder(settings.embedding_model)
    except Exception:
        # Brak modelu (np. pierwszy start bez sieci) nie może zatrzymać usługi – zostaje BM25.
        log.exception("nie udało się wczytać modelu embeddingów; wyszukiwanie tylko po słowach kluczowych")
        return None


def build_state(
    app: FastAPI,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
    embedder: Embedder | None = None,
    index: CorpusIndex | None = None,
) -> None:
    """Składa zależności aplikacji. Testy podają tu własny model, embedder i korpus."""
    index = index or CorpusIndex.load(settings.corpus_dir)
    if embedder is not None:
        index.attach_embeddings(embedder, settings.index_dir)
    store = Store(settings.database_url)
    catalog = load_catalog(settings.catalog_path)
    app.state.settings = settings
    app.state.index = index
    app.state.store = store
    app.state.llm_ready = provider is not None
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.service = VerificationService(
        settings=settings,
        index=index,
        context=ContextCatalog(index, settings.source_status_path),
        provider=provider,
        store=store,
        cases=CaseLoop(settings, store, index),
        source_names={s.id: s.name for s in catalog.sources},
        retrieval_degraded=settings.embeddings != "off" and index.mode == "bm25",
    )


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
    settings = get_settings()
    embedder = await asyncio.to_thread(load_embedder, settings)
    await asyncio.to_thread(build_state, app, settings, provider=build_provider(settings), embedder=embedder)
    log.info("korpus: %s, wyszukiwanie: %s", app.state.index.stats().model_dump(mode="json"), app.state.index.mode)
    purge = asyncio.create_task(_purge_loop(app))
    yield
    purge.cancel()
    with suppress(asyncio.CancelledError):
        await purge


def create_app(with_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="Prawdowid API",
        description="Weryfikacja informacji oparta na jawnym katalogu źródeł. Jedna logika dla wszystkich kanałów.",
        version="0.1.0",
        lifespan=lifespan if with_lifespan else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
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

    for router in (checks.router, sms.router, admin.router):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
