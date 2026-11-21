# Prawdowid – frontend

Samodzielna aplikacja Next.js (App Router, TypeScript, Tailwind CSS). Przeglądarka łączy się bezpośrednio z backendem FastAPI.

Prototyp hackathonowy. Nie jest oficjalną usługą.

## Wymagania

- Node.js 20.9 lub nowszy
- npm

## Instalacja

```bash
npm install
```

## Konfiguracja

Skopiuj plik z przykładem i w razie potrzeby zmień adres backendu:

```bash
cp .env.example .env.local
```

| Zmienna               | Domyślnie               | Opis                                      |
| --------------------- | ----------------------- | ----------------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Adres backendu, bez końcowego ukośnika.   |

Wartość jest wpisywana w kod podczas budowania. Po zmianie uruchom ponownie `npm run dev` albo `npm run build`.

Backend musi zezwalać w CORS na adres frontendu oraz udostępniać nagłówki `Retry-After` i `Content-Disposition`.

## Uruchomienie

```bash
npm run dev
```

Aplikacja działa pod adresem http://localhost:3000.

## Budowanie i kontrola jakości

```bash
npm run build      # wersja produkcyjna
npm run start      # serwer wersji produkcyjnej (port 3000)
npm run lint       # ESLint
npx tsc --noEmit   # kontrola typów (po `npm run build` lub `npx next typegen`)
```

## Strony

| Adres               | Co zawiera                                                              |
| ------------------- | ----------------------------------------------------------------------- |
| `/`                 | Sprawdzanie treści: tekst, link albo zrzut ekranu.                      |
| `/sprawdzenie/[id]` | Zapisany wynik sprawdzenia (stały link).                                |
| `/zrodla`           | Katalog źródeł, zasady kwalifikowania, statystyki zbioru.               |
| `/o-systemie`       | Jak to działa: zakres, oceny, prywatność, użycie AI, stan serwera.      |
| `/sms`              | Symulator kanału SMS (wymaga trybu demonstracyjnego).                   |
| `/moderator`        | Panel moderatora: sprawy, statystyki, zdarzenia, zgłoszenia, eksport.   |

## Układ kodu

- `src/app` – strony i układ główny.
- `src/components` – komponenty pogrupowane według stron (`check`, `result`, `sms`, `sources`, `moderator`, `about`) oraz wspólne (`ui`, `layout`).
- `src/lib` – typy zgodne z `backend/app/schemas.py`, klient API, formatowanie, etykiety.
- `public` – logo.
