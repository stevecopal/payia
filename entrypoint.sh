#!/bin/sh
set -e

APP_USER="appuser"
VENV_PYTHON="/app/.venv/bin/python"

export PATH="/app/.venv/bin:$PATH"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-payia.settings}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
RUN_COLLECTSTATIC="${RUN_COLLECTSTATIC:-1}"

# ── 1/4 — Permissions des volumes ─────────────────────────────────────────
echo "=== [1/4] Permissions des volumes (media, staticfiles, logs) ==="
mkdir -p /app/media /app/staticfiles /app/logs
chown -R "$APP_USER:$APP_USER" /app/media /app/staticfiles /app/logs

# ── 2/4 — Attente de la disponibilité de PostgreSQL ──────────────────────
if [ -n "$DB_HOST" ]; then
    echo "=== [2/4] Attente de la base de données PostgreSQL ($DB_HOST:$DB_PORT)... ==="
    until "$VENV_PYTHON" -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('${DB_HOST:-payia_db}', ${DB_PORT:-5432}))" 2>/dev/null; do
        echo "PostgreSQL n'est pas encore prêt, nouvelle tentative dans 2 secondes..."
        sleep 2
    done
    echo "PostgreSQL est en ligne et accessible !"
fi

# ── 3/4 — Fichiers statiques et Migrations ────────────────────────────────
if [ "$RUN_COLLECTSTATIC" = "1" ]; then
    echo "=== [3/4] Execution de collectstatic ==="
    gosu "$APP_USER" "$VENV_PYTHON" manage.py collectstatic --noinput
fi

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "=== [3/4] Execution des migrations ==="
    gosu "$APP_USER" "$VENV_PYTHON" manage.py migrate --noinput
fi

# ── 4/4 — Démarrage de l'application ─────────────────────────────────────
echo "=== [4/4] Démarrage de la commande : $* ==="
exec gosu "$APP_USER" env \
    PATH="$PATH" \
    HOME=/app \
    DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    "$@"