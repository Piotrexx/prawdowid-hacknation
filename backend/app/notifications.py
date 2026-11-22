"""Powiadomienia moderatorów: Discord, e-mail i Web Push.

Wszystkie kanały są opcjonalne i niezależne. Błąd jednego kanału nie może
przerwać zapisu komentarza ani zablokować pozostałych powiadomień.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from app.config import Settings
from app.schemas import CommentOut, ModeratorOut, PushPublicKeyOut
from app.store.db import Store
from app.store.moderators import ModeratorStore

log = logging.getLogger("notifications")

_VAPID_SETTING = "push.vapid"
_PUSH_TTL = 120


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class _CommentContext:
    title: str
    body: str
    link: str
    case_id: int | None
    article_id: int | None


class NotificationService:
    def __init__(self, settings: Settings, store: Store, moderators: ModeratorStore):
        self._settings = settings
        self._store = store
        self._moderators = moderators
        self._private_key: ec.EllipticCurvePrivateKey | None = None
        self.public_key: str | None = None
        try:
            self._load_vapid_keys()
        except Exception:
            log.warning("nie udało się przygotować kluczy Web Push", exc_info=True)

    # --- konfiguracja ---

    @property
    def email_available(self) -> bool:
        return bool(self._settings.smtp_host and (self._settings.smtp_from or self._settings.smtp_user))

    @property
    def push_available(self) -> bool:
        return self._private_key is not None and bool(self.public_key)

    @property
    def discord_available(self) -> bool:
        return bool(self._settings.moderator_webhook_url)

    def public_key_out(self) -> PushPublicKeyOut:
        return PushPublicKeyOut(
            public_key=self.public_key or "", configured=self.push_available
        )

    def _load_vapid_keys(self) -> None:
        private_value = self._settings.vapid_private_key
        public_value = self._settings.vapid_public_key
        if private_value:
            key = self._parse_private_key(private_value)
            self._private_key = key
            self.public_key = public_value or _b64url(
                key.public_key().public_bytes(
                    serialization.Encoding.X962,
                    serialization.PublicFormat.UncompressedPoint,
                )
            )
            return
        stored = self._store.get_setting(_VAPID_SETTING) or {}
        stored_private = stored.get("private")
        if stored_private:
            key = self._parse_private_key(stored_private)
            self._private_key = key
            self.public_key = stored.get("public") or _b64url(
                key.public_key().public_bytes(
                    serialization.Encoding.X962,
                    serialization.PublicFormat.UncompressedPoint,
                )
            )
            return
        key = ec.generate_private_key(ec.SECP256R1())
        self._private_key = key
        self.public_key = _b64url(
            key.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        raw_private = key.private_numbers().private_value.to_bytes(32, "big")
        self._store.set_setting(
            _VAPID_SETTING,
            {"private": _b64url(raw_private), "public": self.public_key},
            "system",
        )
        log.info("wygenerowano parę kluczy VAPID dla powiadomień Web Push")

    @staticmethod
    def _parse_private_key(value: str) -> ec.EllipticCurvePrivateKey:
        if value.startswith("-----BEGIN"):
            key = serialization.load_pem_private_key(value.encode(), password=None)
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise ValueError("Klucz VAPID nie jest kluczem EC.")
            return key
        raw = _b64url_decode(value.strip())
        return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())

    # --- wejście z API ---

    async def comment_added(self, comment: CommentOut) -> None:
        """Wywoływane po zapisaniu komentarza. Wysyła powiadomienie przy progu z profilu."""
        try:
            total = self._moderators.count_comments(
                case_id=comment.case_id, article_id=comment.article_id
            )
            recipients = [
                moderator
                for moderator in self._moderators.list_moderators()
                if moderator.is_active and moderator.id != comment.moderator_id
            ]
            due = [
                moderator
                for moderator in recipients
                if total >= moderator.comment_notify_threshold
                and total == moderator.comment_notify_threshold
            ]
            if not due:
                return
            context = self._context(comment, total)
            results = await asyncio.gather(
                *(self._deliver(moderator, context) for moderator in due),
                return_exceptions=True,
            )
            delivered = [
                channel
                for result in results
                if isinstance(result, list)
                for channel in result
            ]
            if delivered:
                target = (
                    f"case:{comment.case_id}"
                    if comment.case_id is not None
                    else f"article:{comment.article_id}"
                )
                self._store.add_event(
                    "moderator_notification",
                    target,
                    f"komentarz nr {total}: wysłano {', '.join(sorted(set(delivered)))}",
                )
        except Exception:
            log.warning("nie udało się rozesłać powiadomień o komentarzu", exc_info=True)

    def _context(self, comment: CommentOut, total: int) -> _CommentContext:
        if comment.case_id is not None:
            title = f"Nowy komentarz do sprawy nr {comment.case_id} ({total}.)"
        else:
            label = comment.article_title or f"artykułu nr {comment.article_id}"
            title = f"Nowy komentarz do {label}"
        author = comment.author_name or comment.author_email
        body = f"{author}: {comment.body[:400]}"
        link = f"{self._settings.public_base_url.rstrip('/')}/moderator"
        return _CommentContext(
            title=title,
            body=body,
            link=link,
            case_id=comment.case_id,
            article_id=comment.article_id,
        )

    async def _deliver(self, moderator: ModeratorOut, context: _CommentContext) -> list[str]:
        channels: list[tuple[str, object]] = []
        if moderator.notify_discord:
            channels.append(("discord", self._send_discord(moderator, context)))
        if moderator.notify_email:
            channels.append(("e-mail", self._send_email(moderator, context)))
        if moderator.notify_push:
            channels.append(("push", self._send_push_to_moderator(moderator, context)))
        if not channels:
            return []
        delivered: list[str] = []
        for name, coroutine in channels:
            try:
                ok = await coroutine  # type: ignore[misc]
                if ok:
                    delivered.append(name)
            except Exception:
                log.warning("kanał powiadomień %s zawiódł dla %s", name, moderator.email, exc_info=True)
        return delivered

    # --- Discord ---

    async def _send_discord(self, moderator: ModeratorOut, context: _CommentContext) -> bool:
        url = moderator.discord_webhook_url or self._settings.moderator_webhook_url
        if not url:
            return False
        text = f"**{context.title}**\n{context.body}\n{context.link}"
        if len(text) > 1900:
            text = text[:1900] + "…"
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, json={"content": text, "text": text})
        if response.status_code >= 300:
            log.warning("Discord odrzucił powiadomienie: %s", response.status_code)
        return response.status_code < 300

    # --- e-mail ---

    async def _send_email(self, moderator: ModeratorOut, context: _CommentContext) -> bool:
        if not self.email_available:
            return False
        return await asyncio.to_thread(self._send_email_sync, moderator, context)

    def _send_email_sync(self, moderator: ModeratorOut, context: _CommentContext) -> bool:
        settings = self._settings
        message = EmailMessage()
        message["Subject"] = f"[Prawdowid] {context.title}"
        message["From"] = settings.smtp_from or settings.smtp_user or "prawdowid@localhost"
        message["To"] = moderator.email
        message.set_content(
            f"{context.title}\n\n{context.body}\n\nZobacz w panelu: {context.link}\n"
        )
        if settings.smtp_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=12
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12)
        try:
            client.ehlo()
            if settings.smtp_starttls and not settings.smtp_ssl:
                client.starttls()
                client.ehlo()
            if settings.smtp_user and settings.smtp_password:
                client.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            client.send_message(message)
            return True
        finally:
            try:
                client.quit()
            except smtplib.SMTPException:
                client.close()

    # --- Web Push (bez ładunku: service worker pokazuje komunikat i link) ---

    def _vapid_header(self, endpoint: str) -> str | None:
        if self._private_key is None or self.public_key is None:
            return None
        parts = urlsplit(endpoint)
        origin = f"{parts.scheme}://{parts.netloc}"
        header = _b64url(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
        now = int(time.time())
        claims = _b64url(
            json.dumps(
                {
                    "aud": origin,
                    "exp": now + 12 * 3600,
                    "sub": self._settings.vapid_subject,
                }
            ).encode()
        )
        signing_input = f"{header}.{claims}".encode()
        der_signature = self._private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_signature)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return f"vapid t={header}.{claims}.{_b64url(signature)}, k={self.public_key}"

    async def _send_push_to_moderator(
        self, moderator: ModeratorOut, context: _CommentContext
    ) -> bool:
        if moderator.id is None or not self.push_available:
            return False
        subscriptions = self._moderators.list_push_subscriptions(moderator.id)
        results = await asyncio.gather(
            *(self._send_push(sub.endpoint) for sub in subscriptions),
            return_exceptions=True,
        )
        return any(result is True for result in results)

    async def _send_push(self, endpoint: str) -> bool:
        authorization = self._vapid_header(endpoint)
        if authorization is None:
            return False
        headers = {
            "Authorization": authorization,
            "TTL": str(_PUSH_TTL),
            "Urgency": "normal",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(endpoint, content=b"", headers=headers)
        if response.status_code in (404, 410):
            # Subskrypcja wygasła – usuwamy ją, żeby nie próbować w kółko.
            self._moderators.delete_push_subscription(endpoint)
            return False
        if response.status_code >= 300:
            log.warning("usługa push odrzuciła powiadomienie: %s", response.status_code)
            return False
        self._moderators.touch_push_subscription(endpoint)
        return True
