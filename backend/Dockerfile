FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-cache

COPY app ./app
COPY data/sources.yaml data/source_status.yaml ./data/
COPY data/corpus ./data/corpus

# Dane zmienne (baza, indeks, pobrany model embeddingów) trafiają na wolumen /app/var.
ENV DATABASE_URL=sqlite:////app/var/prawdowid.db \
    INDEX_DIR=/app/var/index \
    FASTEMBED_CACHE_PATH=/app/var/fastembed \
    HF_HOME=/app/var/huggingface \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --system --uid 10001 prawdowid && mkdir -p /app/var && chown prawdowid /app/var
USER prawdowid

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
