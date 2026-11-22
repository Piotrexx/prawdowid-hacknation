#!/usr/bin/env python
"""Tworzy konto superużytkownika panelu moderatora.

Użycie (z katalogu `backend`):
    uv run python scripts/create_superuser.py --email admin@prawdowid.pl
    uv run python scripts/create_superuser.py --email admin@prawdowid.pl --password '...'

Bez `--password` hasło startowe zostanie wygenerowane i wypisane na ekranie.
Skrypt wypisuje też jednorazowy link, który od razu loguje do panelu.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.security import passwords  # noqa: E402
from app.store.db import Store  # noqa: E402
from app.store.moderators import ModeratorStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Konto superużytkownika Prawdowidu")
    parser.add_argument("--email", required=True, help="adres e-mail nowego konta")
    parser.add_argument("--name", default="Superużytkownik", help="nazwa wyświetlana")
    parser.add_argument("--password", default=None, help="hasło (bez tego zostanie wygenerowane)")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="nie otwieraj panelu w przeglądarce (sam link zostanie wypisany)",
    )
    parser.add_argument(
        "--no-link",
        action="store_true",
        help="nie twórz jednorazowego linku logowania",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = Store(settings.database_url)
    moderators = ModeratorStore(store.engine)
    try:
        account, created, generated = moderators.bootstrap_superuser(
            args.email, args.password, args.name
        )
    except (ValueError, passwords.WeakPassword) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2

    if created:
        print(f"Utworzono konto superużytkownika: {account.email}")
        if generated:
            print(f"Hasło startowe: {generated}")
            print("Zapisz je teraz – nie będzie pokazane ponownie.")
    else:
        print(f"Konto {account.email} już istnieje – nie zmieniam hasła.")

    if args.no_link:
        return 0

    link = moderators.login_link(
        account.id,
        base_url=settings.public_base_url,
        hours=settings.moderator_session_hours,
    )
    print()
    print("Panel możesz otworzyć bez wpisywania hasła:")
    print(link)
    if not args.no_open:
        opened = False
        try:
            opened = webbrowser.open(link)
        except Exception:
            opened = False
        if not opened:
            print("Nie udało się otworzyć przeglądarki – skopiuj link powyżej.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
