FROM python:3.11-slim

WORKDIR /app

# System deps: psycopg build + Playwright Chromium runtime libs
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Playwright Chromium browser
RUN uv run playwright install chromium

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Two workers double the in-flight request ceiling on a single replica.
# Azure Container Apps runs on 1 vCPU + 2 GiB; two workers fit comfortably.
# Startup operations (alembic migrations via pg_try_advisory_lock, init_db,
# _seed_pdf_sources upserts, SearchService ensure_index) are all idempotent
# and lock-protected, so the worker fork race is safe.
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
