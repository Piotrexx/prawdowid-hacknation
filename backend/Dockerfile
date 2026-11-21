FROM python:3.13-slim

WORKDIR /app

# System dependencies for trafilatura/lxml and psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Pre-download the embedding model so the first check is not delayed by ~470 MB.
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN mkdir -p "$FASTEMBED_CACHE_PATH" && \
    .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Copy application code
COPY app/ ./app/
COPY db/ ./db/
COPY .env.example .env.example

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8000

# Run the application
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
