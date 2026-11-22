import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.deps import enforce_rate_limit
from app.core.image_check import ImageCheckService
from app.core.pipeline import VerificationService
from app.schemas import CheckRequest, CheckResponse, CheckStatus, HealthResponse
from app.store.db import Store

router = APIRouter(tags=["weryfikacja"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    service: VerificationService = request.app.state.service
    provider = service._provider
    bielik_provider = service._bielik_provider
    return HealthResponse(
        status="ok" if provider and bielik_provider else "degraded",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model if settings.llm_provider != "none" else None,
        bielik_model=settings.bielik_model if bielik_provider else None,
        llm_configured=provider is not None,
        bielik_configured=bielik_provider is not None,
        google_factcheck_configured=settings.google_factcheck_api_key is not None,
        processing_location=settings.processing_location,
        retention_days=settings.retention_days,
    )


@router.post("/checks", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_check(request: Request, payload: CheckRequest) -> CheckResponse:
    service: VerificationService = request.app.state.service
    parent = None
    if payload.parent_check_id:
        store: Store = request.app.state.store
        parent = store.get_check(payload.parent_check_id)
        if parent is None:
            raise HTTPException(404, "Nie znaleziono pytania, na które odpowiadasz. Wyślij treść jeszcze raz.")
        if parent.status != CheckStatus.NEEDS_CLARIFICATION or parent.clarification is None:
            raise HTTPException(409, "To sprawdzenie nie czeka na doprecyzowanie.")
    return await service.check(payload, parent)


_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@router.post("/checks/image", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_image_check(
    request: Request,
    file: Annotated[UploadFile, File(description="Zdjęcie JPEG, PNG, WebP lub GIF")],
    session_id: Annotated[str | None, Form()] = None,
) -> CheckResponse:
    """Sprawdza, czy zdjęcie nie zostało zmienione, porównując je z kopiami znalezionymi w sieci (Yandex, TinEye)."""
    limit = request.app.state.settings.image_max_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Zdjęcie jest za duże (maksymalnie {limit // (1024 * 1024)} MB).")
    if not data:
        raise HTTPException(422, "Nie przesłano zdjęcia.")
    if session_id is not None and not _SESSION_ID.match(session_id):
        raise HTTPException(422, "Niepoprawny identyfikator sesji.")
    service: ImageCheckService = request.app.state.image_service
    return await service.check(data, session_id)


@router.get("/checks/{check_id}", response_model=CheckResponse)
def get_check(request: Request, check_id: str) -> CheckResponse:
    store: Store = request.app.state.store
    result = store.get_check(check_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sprawdzenie nie zostało znalezione.")
    return result


@router.delete("/sessions/{session_id}")
def delete_session(request: Request, session_id: str) -> dict:
    store: Store = request.app.state.store
    deleted = store.delete_session(session_id)
    return {"deleted": deleted}