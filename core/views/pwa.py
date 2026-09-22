"""
Vues PWA : service worker et page hors ligne.

Le service worker DOIT être servi depuis la racine du domaine (`/sw.js`)
pour bénéficier du scope maximal. Il est lu depuis `static/sw.js` et
servi avec `Cache-Control: no-cache` afin que le navigateur détecte
chaque nouvelle version.

La page hors ligne (`static/offline.html`) est aussi exposée via `/offline/`
au cas où le service worker n'est pas encore actif.
"""
from pathlib import Path

from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / 'static'


def _read_static(filename):
    return (STATIC_DIR / filename).read_text(encoding='utf-8')


@require_GET
@cache_control(no_cache=True, must_revalidate=True)
def service_worker(request):
    """Sert /sw.js depuis la racine (scope PWA maximal)."""
    return HttpResponse(
        _read_static('sw.js'),
        content_type='application/javascript',
    )


@require_GET
@cache_control(public=True, max_age=3600)
def manifest(request):
    """Sert /manifest.json depuis la racine."""
    return HttpResponse(
        _read_static('manifest.json'),
        content_type='application/manifest+json',
    )


@require_GET
@cache_control(public=True, max_age=0, must_revalidate=True)
def offline(request):
    """Fallback hors ligne : page statique sans header ni footer."""
    html = _read_static('offline.html')
    return HttpResponse(html, content_type='text/html; charset=utf-8')
