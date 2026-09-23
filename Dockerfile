# syntax=docker/dockerfile:1

# ═══════════════════════════════════════════════════════════════════════════
# PAYIA — Dockerfile de PRODUCTION (PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════

# ── Stage 1 — Compilation Front-end (Tailwind CSS) ─────────────────────────
FROM node:20-alpine AS assets

WORKDIR /build

COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci --no-audit --no-fund

COPY static ./static
COPY templates ./templates

RUN npm run build:css \
    && test -s /build/static/css/output.css


# ── Stage 2 — Builder Python via uv ─────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dépendances système pour Pillow et drivers PostgreSQL (libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev


# ── Stage 3 — Runtime Image Finale ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app \
    DJANGO_SETTINGS_MODULE=payia.settings

# Bibliothèques runtime : libpq5 pour PostgreSQL, Pillow, gosu
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libwebp7 \
        gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 \
        --home-dir /app --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser . /app/
COPY --from=assets --chown=appuser:appuser /build/static/css/output.css /app/static/css/output.css
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media /app/logs \
    && chown -R appuser:appuser /app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["gunicorn", "payia.wsgi:application", \
     "--bind=0.0.0.0:8000", \
     "--workers=3", \
     "--timeout=120", \
     "--graceful-timeout=30", \
     "--max-requests=1000", \
     "--max-requests-jitter=100", \
     "--access-logfile=-", \
     "--error-logfile=-", \
     "--log-level=info"]