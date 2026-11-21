import hashlib
import hmac
import re

from fastapi import Header, HTTPException, Request

from app.config import Settings

# Nazwy muszą odpowiadać SESSION_COOKIE w frontend/src/lib/session.ts
# i CONSENT_COOKIE w frontend/src/lib/consent.ts.
SESSION_COOKIE = "prawdowid_session"
CONSENT_COOKIE = "prawdowid_privacy_consent"
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def session_from_cookie(request: Request) -> str | None:
    """Numer sesji z ciasteczka. Treść ciasteczka pochodzi od klienta, więc
    sprawdzamy format, zanim użyjemy go jako klucza w bazie."""
    value = request.cookies.get(SESSION_COOKIE)
    return value if value and _SESSION_RE.match(value) else None


def consent_from_cookie(request: Request) -> str | None:
    """Wersja polityki prywatności zaakceptowana przez klienta, według ciasteczka.
    To tylko wskazówka dla logów i diagnostyki – wiążący zapis jest w bazie."""
    value = request.cookies.get(CONSENT_COOKIE)
    return value[:32] if value else None


def enforce_rate_limit(request: Request) -> None:
    settings: Settings = request.app.state.settings
    address = request.client.host if request.client else "unknown"
    # Adres IP służy tylko jako klucz limitu w pamięci – w postaci skrótu, bez zapisu na dysk.
    key = hashlib.sha256(f"{settings.id_hash_salt.get_secret_value()}:{address}".encode()).hexdigest()
    retry_after = request.app.state.limiter.retry_after(key)
    if retry_after is not None:
        raise HTTPException(
            429,
            "Wysłano zbyt wiele zgłoszeń w krótkim czasie. Spróbuj ponownie za chwilę.",
            headers={"Retry-After": str(retry_after)},
        )


def require_admin(request: Request, x_admin_token: str = Header(default="")) -> None:
    expected = request.app.state.settings.admin_token
    if expected is None:
        raise HTTPException(503, "Panel moderatora jest wyłączony: ustaw ADMIN_TOKEN w konfiguracji.")
    if not hmac.compare_digest(x_admin_token.encode(), expected.get_secret_value().encode()):
        raise HTTPException(401, "Niepoprawny token.")
