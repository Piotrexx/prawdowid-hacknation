import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.config import Settings

# Nazwy muszą odpowiadać SESSION_COOKIE w frontend/src/lib/session.ts
# i CONSENT_COOKIE w frontend/src/lib/consent.ts.
SESSION_COOKIE = "prawdowid_session"
CONSENT_COOKIE = "prawdowid_privacy_consent"
MODERATOR_COOKIE = "prawdowid_moderator"
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@dataclass(frozen=True)
class ModeratorPrincipal:
    """Zalogowany moderator. `id` jest puste tylko dla zgodności z tokenem technicznym."""

    id: int | None
    email: str
    display_name: str
    role: str
    via_token: bool = False

    @property
    def is_superuser(self) -> bool:
        return self.role == "superuser"


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


def moderator_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    cookie = request.cookies.get(MODERATOR_COOKIE)
    return cookie or None


def _token_principal(request: Request, x_admin_token: str) -> ModeratorPrincipal | None:
    expected = request.app.state.settings.admin_token
    if expected is None or not x_admin_token:
        return None
    if not hmac.compare_digest(x_admin_token.encode(), expected.get_secret_value().encode()):
        return None
    return ModeratorPrincipal(
        id=None,
        email="admin-token",
        display_name="Token techniczny",
        role="superuser",
        via_token=True,
    )


def moderator_principal(request: Request) -> ModeratorPrincipal | None:
    token = moderator_token_from_request(request)
    if token:
        store = getattr(request.app.state, "moderator_store", None)
        if store is not None:
            row = store.resolve_session(token)
            if row is not None:
                return ModeratorPrincipal(
                    id=row.id,
                    email=row.email,
                    display_name=row.display_name,
                    role=row.role,
                )
    return None


def require_moderator(
    request: Request,
    x_admin_token: str = Header(default=""),
) -> ModeratorPrincipal:
    principal = moderator_principal(request)
    if principal is not None:
        return principal
    # Zachowujemy dotychczasowy token techniczny: klienci API i testy działają bez zmian.
    principal = _token_principal(request, x_admin_token)
    if principal is not None:
        return principal
    if not moderator_token_from_request(request) and request.app.state.settings.admin_token is None:
        raise HTTPException(
            503, "Panel moderatora jest wyłączony: ustaw ADMIN_TOKEN w konfiguracji."
        )
    raise HTTPException(401, "Zaloguj się do panelu moderatora.")


def require_superuser(
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> ModeratorPrincipal:
    if not principal.is_superuser:
        raise HTTPException(403, "Ta operacja wymaga uprawnień superużytkownika.")
    return principal


def enforce_rate_limit(request: Request) -> None:
    settings: Settings = request.app.state.settings
    address = request.client.host if request.client else "unknown"
    # Adres IP służy tylko jako klucz limitu w pamięci – w postaci skrótu, bez zapisu na dysk.
    key = hashlib.sha256(
        f"{settings.id_hash_salt.get_secret_value()}:{address}".encode()
    ).hexdigest()
    retry_after = request.app.state.limiter.retry_after(key)
    if retry_after is not None:
        raise HTTPException(
            429,
            "Wysłano zbyt wiele zgłoszeń w krótkim czasie. Spróbuj ponownie za chwilę.",
            headers={"Retry-After": str(retry_after)},
        )


# Zgodność ze starymi importami: panel i testy nadal mogą używać `require_admin`.
require_admin = require_moderator
