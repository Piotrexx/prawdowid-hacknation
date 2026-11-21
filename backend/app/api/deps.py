import hashlib
import hmac

from fastapi import Header, HTTPException, Request

from app.config import Settings


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
