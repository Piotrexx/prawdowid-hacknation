FROM python:3.13-slim

WORKDIR /app

# System dependencies for trafilatura/lxml, psycopg and audio decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies (including ingest connectors and local transcription).
RUN uv sync --frozen --no-dev --group ingest

# Pre-download the embedding model so the first check is not delayed.
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    WHISPER_CACHE_DIR=/app/.cache/whisper \
    HF_HOME=/app/.cache/huggingface \
    INGEST_CACHE_DIR=/app/var/ingest
RUN mkdir -p "$FASTEMBED_CACHE_PATH" "$WHISPER_CACHE_DIR" && \
    .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" && \
    .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/app/.cache/whisper')"

# Copy application code
COPY app/ ./app/
COPY db/ ./db/
COPY .env.example .env.example

# Zmienne dane (baza jest w PostgreSQL, tutaj trzymamy tylko cache modeli).
ENV DATABASE_URL=postgresql+psycopg://prawdowid:prawdowid@postgres:5432/prawdowid \
    UV_CACHE_DIR=/app/var/uv-cache
RUN useradd --system --uid 10001 prawdowid \
    && mkdir -p /app/var /app/var/uv-cache \
    && chown -R prawdowid /app/var /app/.cache
USER prawdowid

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
