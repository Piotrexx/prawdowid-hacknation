FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for trafilatura and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY .env.example .env.example

# Katalog źródeł i korpus są częścią obrazu – bez nich usługa nie ma czego cytować.
COPY data/sources.yaml data/source_status.yaml ./data/
COPY data/corpus ./data/corpus

# Dane zmienne (baza, indeks embeddingów, pobrany model) trafiają na wolumen /app/var,
# żeby nie przesłaniać korpusu wbudowanego w obraz.
ENV DATABASE_URL=sqlite:////app/var/prawdowid.db \
    INDEX_DIR=/app/var/index \
    FASTEMBED_CACHE_PATH=/app/var/fastembed \
    HF_HOME=/app/var/huggingface \
    UV_CACHE_DIR=/app/var/uv-cache
RUN useradd --system --uid 10001 prawdowid \
    && mkdir -p /app/var /app/var/uv-cache \
    && chown -R prawdowid /app/var
USER prawdowid

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
