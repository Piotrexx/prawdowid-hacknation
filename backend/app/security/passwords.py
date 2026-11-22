"""Hasła i tokeny sesji moderatorów.

Bez zewnętrznych zależności: PBKDF2-HMAC-SHA256 z biblioteki standardowej.
Format zapisu w bazie: `pbkdf2_sha256$<iteracje>$<sól_hex>$<skrót_hex>`.
"""

import hashlib
import hmac
import re
import secrets
import unicodedata

ALGORITHM = "pbkdf2_sha256"
# OWASP (2026) zaleca ≥600 000 iteracji dla PBKDF2-HMAC-SHA256.
ITERATIONS = 600_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 10
# Token sesji: 32 bajty losowe → 43 znaki base64url. W bazie trzymamy tylko jego skrót.
TOKEN_BYTES = 32

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")
# Znaki czytelne w obie strony (bez 0/O, 1/l/I) – hasło startowe jest przepisywane z konsoli.
_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%?*"


class WeakPassword(ValueError):
    """Hasło nie spełnia minimalnych wymagań."""


def normalize_email(email: str) -> str:
    """Adres w jednej postaci, żeby `Jan@Example.COM` i `jan@example.com` były tym samym kontem."""
    return unicodedata.normalize("NFKC", email).strip().lower()


def valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email))) and len(email) <= 254


def check_password_strength(password: str) -> None:
    """Minimalne wymagania. Rzuca `WeakPassword` z komunikatem dla człowieka."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(f"Hasło musi mieć co najmniej {MIN_PASSWORD_LENGTH} znaków.")
    if len(password.encode()) > 1024:
        raise WeakPassword("Hasło jest zbyt długie (maksymalnie 1024 bajty).")
    if password.strip() != password:
        raise WeakPassword("Hasło nie może zaczynać się ani kończyć spacją.")
    classes = (
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    )
    if sum(classes) < 3:
        raise WeakPassword(
            "Hasło musi zawierać znaki z co najmniej trzech grup: małe litery, wielkie litery, cyfry, znaki specjalne."
        )


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    """Skrót hasła gotowy do zapisu w bazie. Nie waliduje siły – to robi `check_password_strength`."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Porównanie w stałym czasie. Brak skrótu (konto bez hasła) to zawsze odmowa."""
    if not encoded:
        return False
    try:
        algorithm, raw_iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(raw_iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def needs_rehash(encoded: str | None) -> bool:
    """True, gdy skrót pochodzi ze starszych (słabszych) parametrów i warto go odświeżyć."""
    if not encoded:
        return False
    parts = encoded.split("$", 3)
    if len(parts) != 4 or parts[0] != ALGORITHM:
        return True
    try:
        return int(parts[1]) < ITERATIONS
    except ValueError:
        return True


def generate_password(length: int = 18) -> str:
    """Hasło startowe dla konta zakładanego przez administratora.

    Pętla gwarantuje, że wynik przejdzie `check_password_strength` – losowy ciąg
    bardzo rzadko, ale może nie trafić trzech grup znaków.
    """
    while True:
        candidate = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        try:
            check_password_strength(candidate)
        except WeakPassword:
            continue
        return candidate


def new_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_fingerprint(token: str) -> str:
    """Skrót tokenu sesji. W bazie nie trzymamy tokenu w jawnej postaci."""
    return hashlib.sha256(token.encode()).hexdigest()
