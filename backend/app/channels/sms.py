"""Demonstracyjny kanał SMS.

Adapter nie łączy się z żadnym operatorem: wiadomość przychodzi z symulatora w interfejsie WWW,
a odpowiedź trafia do skrzynki, którą symulator odczytuje. Ścieżka jest ta sama, co w każdym
kanale: wiadomość → VerificationService → odpowiedź, bez udziału człowieka.
"""

import hashlib
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from app.channels.render import render_text
from app.config import Settings
from app.core.pipeline import Submission, VerificationService
from app.schemas import SmsInbound, SmsThread
from app.security.pii import mask_pii
from app.store.db import Store

router = APIRouter(prefix="/channels/sms", tags=["kanał SMS (demo)"])

_BUSY = "Otrzymaliśmy od Ciebie dużo wiadomości. Spróbuj ponownie za minutę."


def peer_id(phone: str, settings: Settings) -> str:
    """Numeru telefonu nie zapisujemy – rozmowę identyfikuje skrót z solą."""
    digest = hashlib.sha256(f"{settings.id_hash_salt.get_secret_value()}:{phone.strip()}".encode()).hexdigest()
    return f"sms-{digest[:24]}"


def _require_enabled(settings: Settings) -> None:
    if settings.sms_mode != "demo":
        raise HTTPException(404, "Demonstracyjny kanał SMS jest wyłączony.")


async def _reply(request: Request, peer: str, text: str) -> None:
    service: VerificationService = request.app.state.service
    settings: Settings = request.app.state.settings
    result = await service.check(Submission.from_message("sms", peer, text))
    body = render_text(result, f"{settings.public_web_url.rstrip('/')}/sprawdzenie/{result.id}")
    request.app.state.store.add_sms(peer, "out", body, result.id)


@router.post("/messages", status_code=202, summary="Wiadomość przychodząca z symulatora")
async def receive(request: Request, background: BackgroundTasks, message: SmsInbound) -> dict[str, bool]:
    settings: Settings = request.app.state.settings
    _require_enabled(settings)
    store: Store = request.app.state.store
    peer = peer_id(message.phone, settings)
    store.add_sms(peer, "in", mask_pii(message.text)[0])
    if request.app.state.limiter.retry_after(peer) is not None:
        store.add_sms(peer, "out", _BUSY)
    else:
        # Sprawdzenie trwa do kilkudziesięciu sekund, więc biegnie po przyjęciu wiadomości –
        # tak jak w prawdziwym kanale, gdzie odpowiedź przychodzi osobną wiadomością.
        background.add_task(_reply, request, peer, message.text)
    return {"accepted": True}


@router.get("/demo/thread", response_model=SmsThread, summary="Rozmowa w symulatorze")
def demo_thread(request: Request, phone: Annotated[str, Query(min_length=3, max_length=64)]) -> SmsThread:
    settings: Settings = request.app.state.settings
    _require_enabled(settings)
    return SmsThread(messages=request.app.state.store.sms_thread(peer_id(phone, settings)))
