import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Path, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import CONSENT_COOKIE, enforce_rate_limit, session_from_cookie
from app.config import Settings
from app.core.pipeline import Submission, VerificationService
from app.retrieval.claims import ClaimRetriever
from app.schemas import (
    ArchiveOut,
    ArchiveRequest,
    CheckRequest,
    CheckResponse,
    ConsentRequest,
    ConsentResponse,
    HealthResponse,
)
from app.notifications import send_check_to_discord
from app.textutil import truncate

router = APIRouter(tags=["weryfikacja"])
_SESSION_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


def _session(request: Request, explicit: str | None) -> str:
    session = explicit or session_from_cookie(request)
    # Ciasteczko pochodzi od klienta: zły format ignorujemy i zaczynamy nową sesję.
    return session or uuid.uuid4().hex


def _require_consent(request: Request, session_id: str) -> None:
    settings: Settings = request.app.state.settings
    version = settings.privacy_policy_version
    if request.cookies.get(CONSENT_COOKIE) == version:
        return
    consent = request.app.state.store.get_consent(session_id, version)
    if consent and consent.accepted:
        return
    raise HTTPException(
        428,
        "Przed zapisaniem sprawdzenia zaakceptuj politykę prywatności. "
        f"Wymagana wersja: {version}.",
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    service: VerificationService = request.app.state.service
    retriever: ClaimRetriever = request.app.state.retriever
    corpus = request.app.state.corpus
    configured = service._provider is not None
    bielik = service._bielik_provider is not None
    documents = corpus.count()
    return HealthResponse(
        status="ok" if configured and retriever.mode != "none" else "degraded",
        llm_provider=service._provider.name if service._provider else settings.llm_provider,
        llm_model=service._provider.model if service._provider else None,
        bielik_model=settings.bielik_model if bielik else None,
        llm_configured=configured,
        bielik_configured=bielik,
        google_factcheck_configured=settings.google_factcheck_api_key is not None,
        retrieval_mode=retriever.mode,  # type: ignore[arg-type]
        corpus=retriever.stats(),
        processing_location=settings.processing_location,
        retention_days=settings.retention_days,
        corpus_ready=documents > 0,
        corpus_documents=documents,
        embedding_model=settings.embedding_model if settings.embedding_backend != "none" else None,
    )


@router.post("/checks", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_check(
    request: Request, payload: CheckRequest, background_tasks: BackgroundTasks
) -> CheckResponse:
    service: VerificationService = request.app.state.service
    settings: Settings = request.app.state.settings
    session_id = _session(request, payload.session_id)
    _require_consent(request, session_id)
    if payload.url and not payload.text:
        submission = Submission(channel="web", session_id=session_id, url=payload.url.strip())
    else:
        submission = Submission.from_message("web", session_id, payload.text or "")
    result = await service.check(submission)
    background_tasks.add_task(send_check_to_discord, result, settings)
    return result


@router.post("/checks/image", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_image_check(
    request: Request,
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    session_id: Annotated[str | None, Form(pattern=_SESSION_PATTERN)] = None,
) -> CheckResponse:
    settings: Settings = request.app.state.settings
    data = await file.read(settings.image_max_bytes + 1)
    session = _session(request, session_id)
    _require_consent(request, session)
    service: VerificationService = request.app.state.service
    result = await service.check(Submission(channel="web", session_id=session, image=data))
    background_tasks.add_task(send_check_to_discord, result, settings)
    return result


@router.post("/checks/audio", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def create_audio_check(
    request: Request,
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    session_id: Annotated[str | None, Form(pattern=_SESSION_PATTERN)] = None,
) -> CheckResponse:
    settings: Settings = request.app.state.settings
    data = await file.read(settings.audio_max_bytes + 1)
    session = _session(request, session_id)
    _require_consent(request, session)
    service: VerificationService = request.app.state.service
    result = await service.check(Submission(channel="web", session_id=session, audio=data))
    background_tasks.add_task(send_check_to_discord, result, settings)
    return result


class DemoMessage(BaseModel):
    """Adapter demonstracyjnego drugiego kanału: ta sama logika co WWW."""

    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("/channels/demo", response_model=CheckResponse, dependencies=[Depends(enforce_rate_limit)])
async def demo_channel(
    request: Request, payload: DemoMessage, background_tasks: BackgroundTasks
) -> CheckResponse:
    """Drugi kanał demonstracyjny. Woła dokładnie tę samą ścieżkę weryfikacji,
    więc wynik merytoryczny dla tego samego zgłoszenia jest spójny z WWW."""
    service: VerificationService = request.app.state.service
    settings: Settings = request.app.state.settings
    session_id = _session(request, payload.session_id)
    _require_consent(request, session_id)
    result = await service.check(Submission.from_message("demo", session_id, payload.message.strip()))
    background_tasks.add_task(send_check_to_discord, result, settings)
    return result


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


@router.post("/archive", response_model=ArchiveOut, dependencies=[Depends(enforce_rate_limit)])
def create_archive(request: Request, payload: ArchiveRequest) -> ArchiveOut:
    settings: Settings = request.app.state.settings
    if not settings.archive_enabled:
        raise HTTPException(503, "Kontrolowana archiwizacja jest wyłączona w tej konfiguracji.")
    session = _session(request, payload.session_id)
    _require_consent(request, session)
    store = request.app.state.store
    check = store.get_check(payload.check_id)
    if check is None:
        raise HTTPException(404, "Nie znaleziono sprawdzenia do zarchiwizowania.")
    if store.get_check_session(payload.check_id) not in (None, session):
        raise HTTPException(403, "To sprawdzenie należy do innej sesji.")
    material = check.input.text or check.input.title or ""
    excerpt = truncate(material, settings.archive_max_chars)
    if not excerpt:
        raise HTTPException(422, "To sprawdzenie nie zawiera materiału, który można zarchiwizować.")
    return store.create_archive(
        check_id=payload.check_id,
        session_id=session,
        url=check.input.url,
        title=check.input.title,
        excerpt=excerpt,
        content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
        legal_basis=settings.archive_legal_basis,
        retention_days=settings.archive_retention_days,
    )


@router.get("/archive/{archive_id}", response_model=ArchiveOut)
def get_archive(request: Request, archive_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]) -> ArchiveOut:
    row = request.app.state.store.get_archive(archive_id)
    if row is None:
        raise HTTPException(404, "Nie ma takiego materiału archiwalnego.")
    session = session_from_cookie(request)
    if row.check_id and request.app.state.store.get_check_session(row.check_id) not in (None, session):
        raise HTTPException(403, "Ten materiał należy do innej sesji.")
    return row


@router.delete("/archive/{archive_id}")
def delete_archive(request: Request, archive_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]) -> dict[str, bool]:
    store = request.app.state.store
    row = store.get_archive(archive_id)
    if row is None:
        raise HTTPException(404, "Nie ma takiego materiału archiwalnego.")
    session = session_from_cookie(request)
    if row.check_id and store.get_check_session(row.check_id) not in (None, session):
        raise HTTPException(403, "Ten materiał należy do innej sesji.")
    return {"deleted": store.delete_archive(archive_id)}
