from collections import Counter
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile

from app.api.deps import enforce_rate_limit
from app.catalog import load_catalog
from app.core.pipeline import Submission, VerificationService
from app.retrieval.index import CorpusIndex
from app.schemas import (
    CheckRequest,
    CheckResponse,
    HealthResponse,
    SourceCatalogEntry,
    SourcesResponse,
)

router = APIRouter(tags=["weryfikacja"])
_SESSION_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings, index = request.app.state.settings, request.app.state.index
    configured = request.app.state.llm_ready
    return HealthResponse(
        status="ok" if configured and index.mode != "none" else "degraded",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model if settings.llm_provider != "none" else None,
        llm_configured=configured,
        retrieval_mode=index.mode,
        corpus=index.stats(),
        processing_location=settings.processing_location,
        retention_days=settings.retention_days,
    )


@router.post("/checks", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_check(request: Request, payload: CheckRequest) -> CheckResponse:
    service: VerificationService = request.app.state.service
    if payload.url and not payload.text:
        submission = Submission(channel="web", session_id=payload.session_id, url=payload.url.strip())
    else:
        submission = Submission.from_message("web", payload.session_id, payload.text or "")
    return await service.check(submission)


@router.post("/checks/image", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_image_check(
    request: Request,
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form(pattern=_SESSION_PATTERN)] = None,
) -> CheckResponse:
    limit = request.app.state.settings.image_max_bytes
    # Czytamy o jeden bajt więcej niż limit: wystarczy, by wykryć za duży plik bez ładowania całości.
    data = await file.read(limit + 1)
    service: VerificationService = request.app.state.service
    return await service.check(Submission(channel="web", session_id=session_id, image=data))


@router.get("/checks/{check_id}", response_model=CheckResponse)
def get_check(request: Request, check_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]) -> CheckResponse:
    found = request.app.state.store.get_check(check_id)
    if found is None:
        raise HTTPException(404, "Nie znaleziono sprawdzenia. Mogło zostać usunięte.")
    return found


@router.delete("/sessions/{session_id}")
def delete_session(request: Request, session_id: Annotated[str, Path(pattern=_SESSION_PATTERN)]) -> dict[str, int]:
    return {"deleted": request.app.state.store.delete_session(session_id)}


@router.get("/sources", response_model=SourcesResponse)
def sources(request: Request) -> SourcesResponse:
    index: CorpusIndex = request.app.state.index
    catalog = load_catalog(request.app.state.settings.catalog_path)
    counts = Counter(d.source_id for d in index.documents)
    newest: dict[str, date] = {}
    for doc in index.documents:
        if doc.published_at and (doc.source_id not in newest or doc.published_at > newest[doc.source_id]):
            newest[doc.source_id] = doc.published_at
    entries = [
        SourceCatalogEntry(
            **source.model_dump(exclude={"connector", "params"}),
            documents=counts.get(source.id, 0),
            newest=newest.get(source.id),
        )
        for source in catalog.sources
    ]
    return SourcesResponse(sources=entries, corpus=index.stats(), rules=catalog.rules)
