# Wdrożenie Prawdowida na AWS (demo / pilotaż)

Ten dokument opisuje wdrożenie **całego projektu** na jednej instancji
**Amazon Lightsail 16 GB** w regionie **Frankfurt (eu-central-1)**:

```
Internet :443 ──► Caddy (Let's Encrypt, jeden origin)
                    ├── /api/*  ──► backend:8000   (FastAPI + PostgreSQL/pgvector + klient Ollamy)
                    └── /*      ──► frontend:3000  (Next.js)
                  backend ──► postgres:5432        (pgvector)
                  backend ──► ollama:11434         (Bielik)
                  discord-bot ──► backend:8000     (opcjonalnie)
```

Publiczne są tylko porty **80/443**. Baza, API, frontend i Ollama nie mają
opublikowanych portów. Caddy obsługuje TLS i trasowanie po ścieżce, dzięki czemu
przeglądarka i backend są w jednym origin i ciasteczka `SameSite=Lax` działają.

**Koszt:** ~84 USD/mies. za instancję 16 GB (ok. 2,76 USD/dzień). Tydzień
demo to ok. **19 USD**, dwa tygodnie ok. **39 USD**. Kredyt 120 USD pokrywa demo
z dużym zapasem oraz ok. **1,4 miesiąca** pracy 24/7.

---

## Ważne: plan Free i kredyt 120 USD

- Lightsail jest objęty kredytami zarówno w planie Free, jak i Paid.
- Konto w planie **Free** zamyka się po 6 miesiącach **albo po wyczerpaniu
  kredytów** — nie zostawiaj instancji włączonej „na wszelki wypadek”.
- Jeśli konsola nie pozwala wybrać planu **16 GB** na koncie Free, masz dwie
  opcje:
  1. **Przejdź na plan Paid** — niewykorzystane kredyty pozostają dostępne
     (do 12 miesięcy od rejestracji), a limit typów instancji znika.
  2. **Zostań na Free i użyj mniejszej maszyny**:
     - **Lightsail 8 GB** (44 USD/mies., 2 vCPU / 8 GB) z modelem `Q4_K_M`,
       albo
     - **EC2 `m7i-flex.large`** (2 vCPU / 8 GB, największy typ dopuszczony
       w planie Free) z modelem `Q4_K_M` i 4 GB swap.
     Ten sam `docker-compose.prod.yml` i `Caddyfile` działają bez zmian; różni się
     tylko sposób utworzenia maszyny i firewall (security group zamiast Lightsail).
     Szczegóły w sekcji [Fallback 8 GB](#fallback-8-gb--plan-free).
- Sprawdź w **Billing → Credits** saldo, datę wygaśnięcia i ewentualne
  ograniczenia kredytu. VAT (23% w PL) może być doliczany osobno.

---

## 0. Wymagania

- Repozytorium na GitHubie (prywatne może być — użyj deploy key) albo archiwum
  wgrane na serwer przez `scp`.
- Domena (np. `prawdowid.example.com`) **albo** darmowa subdomena DuckDNS.
- Klucz API DeepSeek (wymagany do weryfikacji).
- Opcjonalnie: klucz Google Fact Check Tools, token bota Discord.

---

## 1. Utwórz instancję Lightsail

**Konsola:** Lightsail → Create instance

- Region: **Frankfurt (eu-central-1)**
- Platform: **Linux/Unix**
- Blueprint: **OS only → Ubuntu 24.04 LTS**
- Plan: **16 GB** (4 vCPU / 16 GB / 320 GB SSD / 6 TB transferu)
- Nazwa: `prawdowid`

**CLI (odpowiednik):**

```bash
# Sprawdź dostępne identyfikatory planu i blueprintu:
aws lightsail get-bundles --region eu-central-1 \
  --query "bundles[?ramSizeInGb==\`16\`].[bundleId,price,ramSizeInGb]" --output table

aws lightsail get-blueprints --region eu-central-1 \
  --query "blueprints[?contains(name,'Ubuntu 24')].[blueprintId,name]" --output table

aws lightsail create-instances --region eu-central-1 \
  --instance-names prawdowid \
  --availability-zone eu-central-1a \
  --blueprint-id <BLUEPRINT_ID> \
  --bundle-id <BUNDLE_ID> \
  --tags key=Name,value=prawdowid
```

---

## 2. Statyczny IP i firewall

W konsoli Lightsail:

- **Networking → Static IP** → utwórz i **przypisz** do instancji.
  Dzięki temu restart nie zmienia adresu, a DNS i certyfikat pozostają ważne.
- **Networking → IPv4 Firewall**:
  - **80/tcp** — wymagane przez Let's Encrypt,
  - **443/tcp** — HTTPS,
  - **443/udp** — opcjonalnie HTTP/3,
  - **22/tcp** — ogranicz do swojego adresu IP. Nie zamykaj go, dopóki nie
    sprawdzisz, że terminal w przeglądarce Lightsail działa bez tego portu.

CLI:

```bash
aws lightsail allocate-static-ip --region eu-central-1 --static-ip-name prawdowid-ip
aws lightsail attach-static-ip --region eu-central-1 \
  --static-ip-name prawdowid-ip --instance-name prawdowid

aws lightsail open-instance-public-ports --region eu-central-1 \
  --instance-name prawdowid \
  --port-info fromPort=443,toPort=443,protocol=TCP

aws lightsail open-instance-public-ports --region eu-central-1 \
  --instance-name prawdowid \
  --port-info fromPort=443,toPort=443,protocol=UDP
```

---

## 3. DNS

- Własna domena: rekord **A** `prawdowid.example.com → <statyczny IP>`.
  Nie dodawaj rekordu AAAA, jeśli instancja nie ma IPv6.
- DuckDNS: subdomena `prawdowid.duckdns.org → <statyczny IP>`.
- Jeśli używasz Cloudflare, podczas pierwszego uruchomienia ustaw rekord jako
  **DNS only** (szara chmurka), inaczej Let's Encrypt HTTP-01 może nie zadziałać.

Sprawdź przed startem Caddy:

```bash
nslookup prawdowid.example.com
```

Adres musi wskazywać statyczny IP instancji.

---

## 4. Bootstrap serwera

Połącz się przez terminal Lightsail albo:

```bash
ssh -i ~/prawdowid-key.pem ubuntu@<IP>
```

Zainstaluj git, pobierz kod i uruchom skrypt bootstrap:

```bash
sudo apt-get update && sudo apt-get install -y git

sudo mkdir -p /opt/prawdowid
sudo chown "$USER:$USER" /opt/prawdowid
git clone https://github.com/<twoje-konto>/prawdowid-hacknation.git /opt/prawdowid

cd /opt/prawdowid
bash scripts/bootstrap-server.sh
```

Skrypt instaluje Dockera + `docker compose`, `git`, `jq`, `curl` i tworzy
4 GB swap. Po zakończeniu **wyloguj się i zaloguj ponownie** (albo wykonaj
`newgrp docker`), żeby grupa `docker` zaczęła działać.

Sprawdź:

```bash
docker compose version
free -h
```

---

## 5. Sekrety i pliki środowiskowe

```bash
cd /opt/prawdowid

cp .env.production.example .env
cp deploy/backend.env.example backend/.env
cp deploy/discord-bot.env.example discord-bot/.env   # tylko jeśli używasz bota

chmod 600 .env backend/.env discord-bot/.env

# Wygeneruj hasła i sekrety:
openssl rand -hex 24   # POSTGRES_PASSWORD
openssl rand -hex 32   # ADMIN_TOKEN
openssl rand -hex 32   # ID_HASH_SALT
```

Uzupełnij `.env`:

```dotenv
DOMAIN=prawdowid.example.com
ACME_EMAIL=admin@example.com
POSTGRES_DB=prawdowid
POSTGRES_USER=prawdowid
POSTGRES_PASSWORD=<openssl rand -hex 24>
BIELIK_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
```

Uzupełnij `backend/.env`:

- `LLM_API_KEY` — klucz DeepSeek,
- `ADMIN_TOKEN` — wygenerowany sekret,
- `ID_HASH_SALT` — wygenerowany sekret (nie zmieniaj później),
- `MODERATOR_BOOTSTRAP_PASSWORD` — mocne hasło startowe,
- `GOOGLE_FACTCHECK_API_KEY` — opcjonalnie.

Nie ustawiaj w `backend/.env` zmiennych `DATABASE_URL`, `BIELIK_BASE_URL`,
`BIELIK_MODEL`, `CORS_ORIGINS`, `PUBLIC_BASE_URL` ani `FORWARDED_ALLOW_IPS` —
`docker-compose.prod.yml` nadpisuje je spójnie z hasłem bazy i domeną.

> **Najczęstszy błąd:** brak `BIELIK_MODEL` albo `BIELIK_BASE_URL` inny niż
> `http://ollama:11434/v1`. Wtedy `backend/app/core/pipeline.py` odrzuca każde
> sprawdzenie jako „brak informacji do weryfikacji”, mimo że `/health` odpowiada.

---

## 6. Build i start

```bash
cd /opt/prawdowid
docker compose -f docker-compose.prod.yml up -d --build
```

Pierwszy build trwa zwykle 20–40 minut (pakiety systemowe, `uv sync`, modele
FastEmbed i Whisper, `next build`). Ollama dociąga Bielika (3–5 GB) przy
pierwszym starcie; backend czeka, aż model będzie dostępny.

Podgląd:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f ollama
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f caddy
```

Sprawdź model:

```bash
docker compose -f docker-compose.prod.yml exec ollama ollama list
```

Docelowo `backend` i `frontend` mają status `healthy`, a `caddy` działa.

---

## 7. Ingest i weryfikacja

Zbuduj korpus:

```bash
bash scripts/ingest.sh
```

Sprawdź zdrowie (skrypt sprawdza `status`, `bielik_configured` i niepusty korpus):

```bash
bash scripts/smoke-test.sh
```

Ręcznie, jeśli wolisz:

```bash
set -a; source .env; set +a
curl -fsS "https://${DOMAIN}/api/v1/health" | jq
```

Oczekiwane:

- `"status": "ok"`
- `"bielik_configured": true`
- `"corpus_documents"` > 0
- `"retrieval_mode": "pgvector"`

Otwórz `https://<DOMAIN>`, zaakceptuj politykę prywatności i sprawdź **krótkie**
twierdzenie. Panel moderatora: `https://<DOMAIN>/moderator`, publiczna mapa:
`https://<DOMAIN>/mapa`.

> Do demo używaj krótkich tekstów, nie długich artykułów ani URL. Bielik jest
> wywoływany dwa razy na sprawdzenie z promptami do 4 000 i 8 000 znaków; na
> 4 współdzielonych vCPU długi materiał może zbliżyć się do limitu 180 s.

---

## 8. Bot Discord (opcjonalnie)

Uzupełnij `discord-bot/.env` (`DISCORD_TOKEN`, `CLIENT_ID`, opcjonalnie `GUILD_ID`)
i uruchom profil `bot`:

```bash
docker compose -f docker-compose.prod.yml --profile bot up -d
docker compose -f docker-compose.prod.yml logs -f discord-bot
```

Bez `GUILD_ID` rejestracja globalnej komendy `/fact-check` może potrwać do godziny.
Jeśli bot nie jest potrzebny, pomiń ten krok — nie zostanie zbudowany ani uruchomiony.

---

## 9. Eksploatacja

```bash
# logi
docker compose -f docker-compose.prod.yml logs --tail=200 backend

# restart jednej usługi
docker compose -f docker-compose.prod.yml restart backend

# aktualizacja kodu
cd /opt/prawdowid
git pull
docker compose -f docker-compose.prod.yml up -d --build

# kopia bazy
bash scripts/backup.sh

# odtworzenie bazy z kopii (nadpisuje bieżącą bazę)
bash scripts/restore.sh backups/prawdowid-2026-11-22-0400.sql.gz

# powłoka bazy
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U prawdowid -d prawdowid

# miejsce na dysku
df -h
docker system df
```

Codzienny ingest przez cron (`crontab -e`):

```cron
0 4 * * * cd /opt/prawdowid && bash scripts/ingest.sh >> /var/log/prawdowid-ingest.log 2>&1
```

W konsoli Lightsail włącz **automatic snapshots** (7 ostatnich, 0,05 USD/GB-mies.,
przyrostowo). To najprostsza kopia całej maszyny — kod, baza, modele i certyfikaty.

Kontenery wracają po restarcie dzięki `restart: unless-stopped` i włączonemu
Dockerowi. Po `sudo reboot` sprawdź `docker compose ps`.

---

## 10. Sprzątanie po demo

1. Zrób snapshot, jeśli chcesz odtworzyć środowisko później.
2. **Usuń instancję** — Lightsail nalicza opłaty także za zatrzymaną maszynę.
3. Zwolnij **statyczny IP**.
4. Usuń snapshot, jeśli nie jest potrzebny.
5. Sprawdź **Billing → Credits**.

Tydzień demo to ok. 19 USD, dwa tygodnie ok. 39 USD. Miesiąc pracy 24/7 to
ok. 87 USD (instancja + snapshoty).

---

## Rozwiązywanie problemów

| Objaw | Przyczyna | Rozwiązanie |
|---|---|---|
| Każde sprawdzenie: „brak informacji do weryfikacji” | Bielik nieosiągalny lub zły model | `BIELIK_BASE_URL=http://ollama:11434/v1`, poprawny `BIELIK_MODEL`, `ollama list` |
| 502 z Caddy | frontend/backend jeszcze nie wystartował | `docker compose ps`, logi usługi |
| Brak certyfikatu | zły DNS lub zamknięte 80/443 | `nslookup`, firewall Lightsail, Cloudflare „DNS only” |
| Wszyscy dostają limit 10/min | brak przekazywania realnego IP | `FORWARDED_ALLOW_IPS=*` w compose, restart backendu |
| Build zabity / OOM | brak swapu lub za mało RAM | 4 GB swap, `free -h`, przebuduj |
| `uv sync --frozen` błąd | `uv.lock` niezgodny z `pyproject.toml` | lokalnie `uv lock`, commit, ponowny build |
| `npm ci` błąd | brak/zły `package-lock.json` | commit lockfile, przebuduj frontend |
| Błąd logowania do bazy | hasło w `.env` inne niż w `DATABASE_URL` | oba pochodzą z `POSTGRES_PASSWORD`; nie wpisuj `DATABASE_URL` ręcznie |
| Wyszukiwanie obrazów zawsze zawodzi | Yandex/TinEye blokują IP AWS | `IMAGE_SEARCH_ENGINES=` i restart |
| Pierwsze sprawdzenie wolne | ładowanie FastEmbed/Whisper | rozgrzej usługę przed demo |
| Brak miejsca | stare obrazy/logi | `docker system prune -f` (nie usuwa wolumenów) |
| Domena z AAAA nie działa | brak IPv6 na instancji | usuń rekord AAAA |

---

## Fallback 8 GB / plan Free

Jeśli nie możesz uruchomić Lightsail 16 GB, masz dwie drogi:

- **Lightsail 8 GB** (44 USD/mies., 2 vCPU / 8 GB) — najprościej, reszta kroków
  bez zmian.
- **EC2 `m7i-flex.large`** (2 vCPU / 8 GB) — jeśli Lightsail 8 GB też jest
  niedostępny. Utwórz go w `eu-central-1` z Ubuntu 24.04, 60 GB gp3, Elastic IP
  i security group zezwalającą na 80/443. Compose i Caddyfile bez zmian.

Niezależnie od wyboru:

1. W `.env` ustaw lżejszy model:
   ```dotenv
   BIELIK_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q4_K_M
   ```
2. Zostaw 4 GB swap i nie uruchamiaj ingestu w trakcie demo.
3. Buduj usługi **kolejno**, żeby nie zabić pamięci:
   ```bash
   COMPOSE_PARALLEL_LIMIT=1 docker compose -f docker-compose.prod.yml build
   docker compose -f docker-compose.prod.yml up -d
   ```
4. Jeśli tag `Q4_K_M` nie istnieje, sprawdź dostępne tagi:
   ```bash
   docker compose -f docker-compose.prod.yml exec ollama ollama list
   # albo:
   docker compose -f docker-compose.prod.yml exec ollama ollama pull <tag>
   ```
5. Alternatywnie przejdź na plan Paid i wróć do 16 GB — kredyty pozostają ważne
   do 12 miesięcy od rejestracji.

Na 8 GB `OLLAMA_KEEP_ALIVE=-1` nadal działa (model Q4 to ok. 3 GB), ale miej
zapas: jeden użytkownik i krótkie teksty.

---

## Bezpieczeństwo — lista kontrolna

- [ ] Publiczne tylko 80/443; SSH (22) ograniczony do twojego IP.
- [ ] `.env`, `backend/.env`, `discord-bot/.env` mają `chmod 600` i nie są w gicie.
- [ ] `ADMIN_TOKEN` i `ID_HASH_SALT` to losowe wartości; `ID_HASH_SALT` się nie zmienia.
- [ ] Hasło startowe moderatora usunięte z `backend/.env` po pierwszym logowaniu.
- [ ] Snapshoty włączone; wiesz, jak odtworzyć instancję.
- [ ] `PRIVACY_POLICY_VERSION` zgodne z `frontend/src/lib/consent.ts` (domyślnie OK).
- [ ] Pamiętasz, że DeepSeek przetwarza treść poza EOG — jeśli to wymóg formalny,
      zmień `LLM_PROVIDER`/`LLM_BASE_URL` na dostawcę w EOG i przelicz koszt.
- [ ] Po demo instancja usunięta, statyczny IP zwolniony.

---

## Pliki wdrożeniowe w repozytorium

| Plik | Rola |
|---|---|
| `docker-compose.prod.yml` | produkcyjny stos: Postgres, Ollama, backend, frontend, Caddy, bot (profil) |
| `Caddyfile` | TLS, HSTS, `/api/*` → backend, reszta → frontend |
| `.env.production.example` | zmienne Compose: domena, e-mail ACME, hasło bazy, model Bielika |
| `deploy/backend.env.example` | sekrety backendu (LLM, tokeny, konto moderatora) |
| `deploy/discord-bot.env.example` | token bota i identyfikatory Discord |
| `scripts/bootstrap-server.sh` | Docker, compose, swap, narzędzia na świeżej Ubuntu |
| `scripts/ingest.sh` | jednorazowy/cykliczny ingest źródeł |
| `scripts/backup.sh` | `pg_dump` do `backups/` z retencją |
| `scripts/restore.sh` | odtworzenie bazy z kopii |
| `scripts/smoke-test.sh` | test po wdrożeniu: health, Bielik, korpus |
