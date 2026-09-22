/* =====================================================================
   PAYIA Service Worker
   Stratégie : réseau d'abord, cache très léger (app shell statique),
   fallback offline.html pour toute navigation hors ligne.
   Aucun contenu applicatif (HTML) n'est mis en cache.
   ===================================================================== */

const VERSION = 'payia-v1';
const OFFLINE_URL = '/offline/';

/* App shell minimal : uniquement ce dont l'app a réellement besoin
   pour démarrer et afficher la page offline en cas de coupure. */
const PRECACHE_URLS = [
    OFFLINE_URL,
    '/static/css/output.css',
    '/static/icons/192.png',
    '/static/icons/512.png',
    '/static/icons/maskable-192.png',
    '/static/icons/maskable-512.png',
    '/static/icons/apple-touch-icon.png',
    '/static/icons/favicon-32.png',
    '/static/icons/favicon-16.png',
];

/* Install : précache léger, activation immédiate */
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(VERSION)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

/* Activate : purge des anciennes versions de cache */
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const { request } = event;

    /* Uniquement les GET (jamais POST/CSRF/admin) */
    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    /* Même origine uniquement */
    if (url.origin !== self.location.origin) return;

    /* 1) Navigation (pages HTML) : réseau d'abord, offline.html en secours */
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request)
                .then((response) => response)
                .catch(() =>
                    caches.match(OFFLINE_URL).then(
                        (cached) => cached || new Response(
                            '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>PAYIA - Hors ligne</title></head><body style="background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><p>Vous êtes hors ligne.</p></body></html>',
                            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
                        )
                    )
                )
        );
        return;
    }

    /* 2) Static (css/js/img/icons) : stale-while-revalidate, cache léger */
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then((cached) => {
                const fetchPromise = fetch(request)
                    .then((response) => {
                        if (response && response.ok) {
                            const clone = response.clone();
                            caches.open(VERSION).then((cache) => cache.put(request, clone));
                        }
                        return response;
                    })
                    .catch(() => cached);
                return cached || fetchPromise;
            })
        );
        return;
    }

    /* 3) Tout le reste (API, pages, média) : réseau direct, pas de cache.
          En cas d'échec pour une requête de même origine, on tente offline. */
    event.respondWith(
        fetch(request).catch(() =>
            request.headers.get('accept')?.includes('text/html')
                ? caches.match(OFFLINE_URL)
                : Response.error()
        )
    );
});
