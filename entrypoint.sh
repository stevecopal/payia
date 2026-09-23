#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
# PAYIA — Entrypoint de PRODUCTION
#
#   1. Corrige les permissions des volumes Docker (créés en root au premier
#      montage d'un volume nommé).
#   2. Collecte les fichiers statiques → volume `payia_static` servi par Caddy.
#   3. Applique les migrations (SQLite dans le volume `payia_sqlite_data`).
#   4. Abandonne les privilèges (appuser) et exécute la commande demandée
#      (gunicorn, celery worker, celery beat, manage.py …).
#
# Variables d'environnement :
#   RUN_MIGRATIONS      "1" (défaut) → `manage.py migrate`
#   RUN_COLLECTSTATIC   "1" (défaut) → `manage.py collectstatic`
#   → mettre les deux à "0" pour les conteneurs Celery worker / beat :
#     les migrations et le collectstatic ne doivent s'exécuter qu'UNE fois.
# ═══════════════════════════════════════════════════════════════════════════
set -e

APP_USER="appuser"
VENV_PYTHON="/app/.venv/bin/python"

# Le venv doit primer dans le PATH (gunicorn, celery, …)
export PATH="/app/.venv/bin:$PATH"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-payia.settings}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
RUN_COLLECTSTATIC="${RUN_COLLECTSTATIC:-1}"

# ── 1/4 — Permissions des volumes ─────────────────────────────────────────
echo "=== [1/4] Permissions des volumes (data, media, staticfiles, logs) ==="
mkdir -p /app/data /app/media /app/staticfiles /app/logs
chown -R "$APP_USER:$APP_USER" \
    /app/data /app/media /app/staticfiles /app/logs

# ── 2/4 — Fichiers statiques (volume partagé, monté en :ro dans Caddy) ────
if [ "$RUN_COLLECTSTATIC" = "1" ]; then
    echo "=== [2/4] collectstatic ==="
    gosu "$APP_USER" "$VENV_PYTHON" manage.py collectstatic --noinput
else
    echo "=== [2/4] collectstatic ignoré (RUN_COLLECTSTATIC=$RUN_COLLECTSTATIC) ==="
fi

# ── 3/4 — Migrations ──────────────────────────────────────────────────────
if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "=== [3/4] migrate ==="
    gosu "$APP_USER" "$VENV_PYTHON" manage.py migrate --noinput
else
    echo "=== [3/4] migrate ignoré (RUN_MIGRATIONS=$RUN_MIGRATIONS) ==="
fi

# ── 4/4 — Application ─────────────────────────────────────────────────────
echo "=== [4/4] Démarrage : $* ==="
exec gosu "$APP_USER" env \
    PATH="$PATH" \
    HOME=/app \
    DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    "$@"
