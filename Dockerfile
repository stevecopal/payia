# syntax=docker/dockerfile:1

# ═══════════════════════════════════════════════════════════════════════════
# PAYIA — Dockerfile de PRODUCTION (build multi-stage)
#
#   Stage 1 « assets »  : compile Tailwind CSS  → static/css/output.css
#   Stage 2 « builder » : installe le venv Python avec uv (--frozen, --no-dev)
#   Stage 3 « runtime » : image finale minimale, exécutée via gosu en appuser
#
# Build :
#   docker build -t payia-app:latest .
#
# Le conteneur démarre en ROOT uniquement pour corriger les permissions des
# volumes montés (data / media / staticfiles / logs), puis abandonne ses
# privilèges (gosu appuser) — voir entrypoint.sh.
# ═══════════════════════════════════════════════════════════════════════════


# ───────────────────────────────────────────────────────────────────────────
# Stage 1 — Assets front : compilation de Tailwind CSS
# ───────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS assets

WORKDIR /build

# Copiées seules → la couche `npm ci` reste en cache tant que les
# dépendances Node ne changent pas.
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci --no-audit --no-fund

# Sources scannées par Tailwind :
#   content: ["./templates/**/*.html", "./static/js/**/*.js"]
COPY static ./static
COPY templates ./templates

# Génère static/css/output.css (build:css → tailwindcss --minify)
RUN npm run build:css \
    && test -s /build/static/css/output.css


# ───────────────────────────────────────────────────────────────────────────
# Stage 2 — Builder : dépendances Python via uv
# ───────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dépendances système utiles à la compilation (Pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Client uv officiel
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 1) Dépendances seules → couche mise en cache (invalidée uniquement si
#    pyproject.toml / uv.lock changent)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Code source + synchronisation finale du venv
COPY . .
RUN uv sync --frozen --no-dev


# ───────────────────────────────────────────────────────────────────────────
# Stage 3 — Image finale (runtime)
# ───────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app \
    DJANGO_SETTINGS_MODULE=payia.settings

# Bibliothèques runtime (Pillow) + gosu (descente de privilèges)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libwebp7 \
        gosu \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur applicatif non privilégié (uid/gid fixés pour des volumes
# aux permissions prévisibles)
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 \
        --home-dir /app --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Virtualenv issu du builder (mêmes chemins → les shebangs restent valides)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Code applicatif
COPY --chown=appuser:appuser . /app/

# CSS compilé par le stage « assets » (écrase un éventuel fichier obsolète
# présent dans le contexte de build)
COPY --from=assets --chown=appuser:appuser \
     /build/static/css/output.css /app/static/css/output.css

# Entrypoint
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh

# Répertoires de travail (points de montage des volumes) + droits
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/data /app/staticfiles /app/media /app/logs \
    && chown -R appuser:appuser /app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

# Gunicorn (surchargeable via la variable GUNICORN_CMD_ARGS si besoin)
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
