from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import enforce_rate_limit
from app.core.pipeline import VerificationService
from app.schemas import CheckRequest, CheckResponse, HealthResponse

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