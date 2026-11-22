# Discord bot — Prawdowid

Jedna komenda: `/fact-check`, z trzema opcjami (`tekst`, `url`, `zdjecie`) — podaj
dokładnie jedną. Bot woła ten sam backend co strona WWW (`/api/v1/checks`,
`/api/v1/checks/image`), automatycznie rejestruje zgodę na politykę prywatności
(wymagana przez backend przed zapisem wyniku) i odpowiada embedem z werdyktem,
pewnością, podsumowaniem i linkiem do pełnej analizy na stronie.

## Konfiguracja (`.env`)

```
DISCORD_TOKEN=   # token bota z Discord Developer Portal
CLIENT_ID=       # Application ID
GUILD_ID=        # (opcjonalnie) ID serwera do szybkiego rejestrowania komend podczas developmentu
API_URL=http://localhost:8000   # backend FastAPI, bez /api/v1
FRONTEND_URL=http://localhost:3000   # do budowania linku do pełnej analizy
```

## Uruchomienie

```bash
npm install
npm run deploy   # rejestruje /fact-check (na serwerze z GUILD_ID albo globalnie)
npm run dev      # start w trybie dev (tsx watch)
# albo produkcyjnie:
npm run build && npm start
```

Backend (`cd ../backend && uvicorn app.main:app`) musi działać pod `API_URL`.
