from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import enforce_rate_limit
from app.core.pipeline import VerificationService
from app.schemas import CheckRequest, CheckResponse, HealthResponse
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
    return await service.check(payload)


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