"""Kanał SMS / WhatsApp w formacie webhooka Twilio.

Tryb `demo` zapisuje odpowiedzi w skrzynce odczytywanej przez symulator w interfejsie WWW;
tryb `twilio` wysyła je przez API operatora. W obu trybach wiadomość przechodzi tę samą
ścieżkę: webhook → VerificationService → odpowiedź, bez udziału człowieka.
"""

import base64
import hashlib
import hmac
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query, Request, Response

from app.channels.render import render_text
from app.config import Settings
from app.core.pipeline import Submission, VerificationService
from app.schemas import SmsThread
from app.security.pii import mask_pii
from app.security.ratelimit import RateLimiter
from app.store.db import Store

log = logging.getLogger("sms")
router = APIRouter(prefix="/channels/sms", tags=["kanał SMS / WhatsApp"])

_TWIML_EMPTY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
_BUSY = "Otrzymaliśmy od Ciebie dużo wiadomości. Spróbuj ponownie za minutę."
_MEDIA_UNSUPPORTED = "W tym kanale przyjmujemy tekst i linki. Obraz sprawdzisz na stronie: {url}"


def peer_id(phone: str, settings: Settings) -> str:
    """Numeru telefonu nie zapisujemy – rozmowę identyfikuje skrót z solą."""
    digest = hashlib.sha256(f"{settings.id_hash_salt.get_secret_value()}:{phone.strip()}".encode()).hexdigest()
    return f"sms-{digest[:24]}"


def _valid_twilio_signature(settings: Settings, url: str, form: dict[str, str], signature: str) -> bool:
    payload = url + "".join(f"{k}{form[k]}" for k in sorted(form))
    digest = hmac.new(settings.twilio_auth_token.get_secret_value().encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


async def _send(request: Request, peer: str, phone: str, body: str, check_id: str | None = None) -> None:
    settings: Settings = request.app.state.settings
    if settings.sms_mode == "demo":
        request.app.state.store.add_sms(peer, "out", body, check_id)
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token.get_secret_value()),
                data={"To": phone, "From": settings.twilio_from, "Body": body[:1600]},
            )
        if response.status_code >= 300:
            log.warning("operator SMS odrzucił wiadomość (HTTP %s)", response.status_code)
    except httpx.HTTPError:
        log.warning("nie udało się wysłać odpowiedzi SMS")


async def _handle(request: Request, peer: str, phone: str, body: str) -> None:
    service: VerificationService = request.app.state.service
    settings: Settings = request.app.state.settings
    result = await service.check(Submission.from_message("sms", peer, body))
    text = render_text(result, f"{settings.public_web_url.rstrip('/')}/sprawdzenie/{result.id}")
    await _send(request, peer, phone, text, result.id)


@router.post("/webhook", summary="Wiadomość przychodząca (format Twilio)")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    sender: Annotated[str, Form(alias="From", min_length=3, max_length=64)],
    body: Annotated[str, Form(alias="Body", max_length=4000)] = "",
    num_media: Annotated[int, Form(alias="NumMedia")] = 0,
) -> Response:
    settings: Settings = request.app.state.settings
    if settings.sms_mode == "off":
        raise HTTPException(404, "Kanał SMS jest wyłączony.")
    if settings.sms_mode == "twilio":
        form = {k: str(v) for k, v in (await request.form()).items()}
        url = f"{settings.public_api_url.rstrip('/')}{request.url.path}"
        if not _valid_twilio_signature(settings, url, form, request.headers.get("X-Twilio-Signature", "")):
            request.app.state.store.add_event("invalid_webhook_signature", "sms", "odrzucono żądanie bez poprawnego podpisu")
            raise HTTPException(403, "Niepoprawny podpis żądania.")

    peer = peer_id(sender, settings)
    store: Store = request.app.state.store
    limiter: RateLimiter = request.app.state.limiter
    if settings.sms_mode == "demo":
        store.add_sms(peer, "in", mask_pii(body)[0])
    if limiter.retry_after(peer) is not None:
        background.add_task(_send, request, peer, sender, _BUSY)
    elif num_media > 0 and not body.strip():
        background.add_task(_send, request, peer, sender, _MEDIA_UNSUPPORTED.format(url=settings.public_web_url))
    else:
        # Twilio czeka na odpowiedź najwyżej 15 s, więc sprawdzenie biegnie po zwróceniu webhooka.
        background.add_task(_handle, request, peer, sender, body)
    return Response(_TWIML_EMPTY, media_type="application/xml")


@router.get("/demo/thread", response_model=SmsThread, summary="Rozmowa w symulatorze (tylko tryb demo)")
def demo_thread(request: Request, phone: Annotated[str, Query(min_length=3, max_length=64)]) -> SmsThread:
    settings: Settings = request.app.state.settings
    if settings.sms_mode != "demo":
        raise HTTPException(404, "Symulator jest dostępny tylko w trybie demonstracyjnym.")
    return SmsThread(messages=request.app.state.store.sms_thread(peer_id(phone, settings)))
