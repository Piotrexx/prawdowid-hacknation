from collections import Counter
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile

from app.api.deps import enforce_rate_limit, session_from_cookie
from app.catalog import load_catalog
from app.core.pipeline import Submission, VerificationService
from app.retrieval.index import CorpusIndex
from app.schemas import (
    CheckRequest,
    CheckResponse,
    ConsentRequest,
    ConsentResponse,
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
    bielik = request.app.state.service._bielik_provider is not None
    return HealthResponse(
        status="ok" if configured and index.mode != "none" else "degraded",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model if settings.llm_provider != "none" else None,
        bielik_model=settings.bielik_model if bielik else None,
        llm_configured=configured,
        bielik_configured=bielik,
        google_factcheck_configured=settings.google_factcheck_api_key is not None,
        retrieval_mode=index.mode,
        corpus=index.stats(),
        processing_location=settings.processing_location,
        retention_days=settings.retention_days,
    )


@router.post("/checks", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_check(request: Request, payload: CheckRequest) -> CheckResponse:
    service: VerificationService = request.app.state.service
    # Numer sesji z ciasteczka, gdy nie podano go w treści żądania.
    session_id = payload.session_id or session_from_cookie(request)
    if payload.url and not payload.text:
        submission = Submission(channel="web", session_id=session_id, url=payload.url.strip())
    else:
        submission = Submission.from_message("web", session_id, payload.text or "")
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
    session = session_id or session_from_cookie(request)
    return await service.check(Submission(channel="web", session_id=session, image=data))


@router.get("/checks/{check_id}", response_model=CheckResponse)
def get_check(request: Request, check_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]) -> CheckResponse:
    found = request.app.state.store.get_check(check_id)
    if found is None:
        raise HTTPException(404, "Nie znaleziono sprawdzenia. Mogło zostać usunięte.")
    return found


@router.post("/consent", response_model=ConsentResponse)
def record_consent(request: Request, payload: ConsentRequest) -> ConsentResponse:
    """Zapisuje zgodę na politykę prywatności: identyfikator sesji, wersję polityki i czas.
    Nie zapisujemy tu żadnej treści sprawdzenia ani odpowiedzi modelu."""
    session_id = payload.session_id or session_from_cookie(request) or ""
    if not session_id:
        raise HTTPException(422, "Brak numeru sesji: podaj go w treści żądania albo w ciasteczku.")
    return request.app.state.store.record_consent(
        session_id, payload.policy_version, payload.accepted
    )


@router.get("/consent/{session_id}", response_model=ConsentResponse)
def get_consent(
    request: Request,
    session_id: Annotated[str, Path(pattern=_SESSION_PATTERN)],
    policy_version: str | None = None,
) -> ConsentResponse:
    settings = request.app.state.settings
    version = policy_version or settings.privacy_policy_version
    found = request.app.state.store.get_consent(session_id, version)
    if found is None:
        raise HTTPException(404, "Nie zapisano zgody dla tej sesji.")
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
