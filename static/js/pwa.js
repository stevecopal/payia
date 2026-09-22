/* =====================================================================
   PAYIA PWA — registration + installation + statut réseau
   - Enregistre le service worker
   - Bouton "Installer" visible quand l'app est installable
   - Modal d'installation : appelle prompt() du beforeinstallprompt
   - Instructions manuelles (iOS / navigateurs sans prompt natif)
   - Boutons masqués automatiquement quand l'app est installée
   - Redirige vers /offline/ quand la connexion est perdue
   ===================================================================== */
(function () {
    'use strict';

    var deferredPrompt = null;
    var INSTALL_DISMISS_KEY = 'payia_pwa_install_dismissed';
    var dismissCooldownMs = 3 * 24 * 60 * 60 * 1000; // 3 jours

    /* ---------------------------------------------------------------
       1) Enregistrement du service worker
       --------------------------------------------------------------- */
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker.register('/sw.js').catch(function (err) {
                console.warn('[PWA] Service worker registration failed:', err);
            });
        });
    }

    /* ---------------------------------------------------------------
       2) Détection de l'installation
       --------------------------------------------------------------- */
    function isStandalone() {
        return window.matchMedia('(display-mode: standalone)').matches
            || window.matchMedia('(display-mode: fullscreen)').matches
            || window.matchMedia('(display-mode: minimal-ui)').matches
            || window.navigator.standalone === true;
    }

    function isIos() {
        return /iphone|ipad|ipod/i.test(navigator.userAgent)
            || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    }

    function wasRecentlyDismissed() {
        try {
            var ts = parseInt(localStorage.getItem(INSTALL_DISMISS_KEY), 10);
            return ts && (Date.now() - ts) < dismissCooldownMs;
        } catch (e) {
            return false;
        }
    }

    function showInstallButtons() {
        document.querySelectorAll('[data-pwa-install]').forEach(function (el) {
            el.classList.remove('hidden');
            /* Le bouton utilise hidden + inline-flex : on force l'affichage
               en repassant sur la classe d'affichage d'origine. */
            el.style.display = '';
        });
    }

    function hideInstallButtons() {
        document.querySelectorAll('[data-pwa-install]').forEach(function (el) {
            el.classList.add('hidden');
            el.style.display = 'none';
        });
    }

    function updateInstallUi() {
        if (isStandalone()) {
            /* App déjà installée : plus aucun bouton nulle part */
            hideInstallButtons();
            return;
        }
        if (deferredPrompt && !wasRecentlyDismissed()) {
            showInstallButtons();
        }
    }

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        if (!wasRecentlyDismissed()) {
            showInstallButtons();
        }
    });

    window.addEventListener('appinstalled', function () {
        deferredPrompt = null;
        hideInstallButtons();
        closeModal('pwaInstallModal');
        try { localStorage.removeItem(INSTALL_DISMISS_KEY); } catch (e) {}
    });

    /* Si l'app est déjà installée, on masque tout dès le chargement. */
    if (isStandalone()) {
        document.addEventListener('DOMContentLoaded', hideInstallButtons);
    }

    /* ---------------------------------------------------------------
       3) Modal d'installation
       --------------------------------------------------------------- */
    function openModal(id) {
        var m = document.getElementById(id);
        if (!m) return;
        m.classList.remove('hidden');
        m.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }

    function closeModal(id) {
        var m = document.getElementById(id);
        if (!m) return;
        m.classList.add('hidden');
        m.classList.remove('flex');
        document.body.style.overflow = '';
    }

    function markDismissed() {
        try { localStorage.setItem(INSTALL_DISMISS_KEY, String(Date.now())); } catch (e) {}
    }

    function showManualInstructions() {
        var ios = document.getElementById('pwaManualIos');
        var other = document.getElementById('pwaManualOther');
        if (!ios || !other) return;
        if (isIos()) {
            ios.classList.remove('hidden');
        } else {
            other.classList.remove('hidden');
        }
    }

    function hideManualInstructions() {
        ['pwaManualIos', 'pwaManualOther'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    }

    /* Clic sur "Installer maintenant" :
       - prompt natif disponible -> on le lance
       - sinon -> instructions manuelles (iOS / menu navigateur) */
    function handleInstallConfirm() {
        if (deferredPrompt) {
            var prompt = deferredPrompt;
            deferredPrompt = null;
            prompt.prompt();
            prompt.userChoice.then(function (choice) {
                if (choice && choice.outcome === 'dismissed') {
                    markDismissed();
                }
                /* Dans tous les cas on ferme le modal et on masque les
                   boutons : soit l'app est installée, soit refusée. */
                closeModal('pwaInstallModal');
                hideInstallButtons();
                hideManualInstructions();
            }).catch(function () {
                closeModal('pwaInstallModal');
            });
        } else {
            /* Pas de beforeinstallprompt (iOS Safari, certains navigateurs) :
               on affiche les instructions manuelles dans le modal. */
            showManualInstructions();
        }
    }

    document.addEventListener('click', function (e) {
        var trigger = e.target.closest('[data-pwa-install]');
        if (trigger) {
            e.preventDefault();
            hideManualInstructions();
            openModal('pwaInstallModal');
            return;
        }
        if (e.target.closest('[data-pwa-install-confirm]')) {
            e.preventDefault();
            handleInstallConfirm();
            return;
        }
        if (e.target.closest('[data-pwa-install-cancel]')) {
            e.preventDefault();
            markDismissed();
            hideManualInstructions();
            closeModal('pwaInstallModal');
            return;
        }
        /* Clic sur l'overlay (fond du modal) : fermer */
        var modal = document.getElementById('pwaInstallModal');
        if (modal && !modal.classList.contains('hidden') && e.target === modal) {
            closeModal('pwaInstallModal');
        }
    });

    /* ---------------------------------------------------------------
       4) Statut réseau : bascule vers /offline/ en cas de coupure
       --------------------------------------------------------------- */
    function isOfflinePage() {
        return window.location.pathname.indexOf('/offline/') === 0;
    }

    window.addEventListener('offline', function () {
        if (!isOfflinePage()) {
            window.location.href = '/offline/';
        }
    });

    window.addEventListener('online', function () {
        if (isOfflinePage()) {
            window.location.href = '/';
        }
    });

    /* Mise à jour de l'UI au chargement */
    document.addEventListener('DOMContentLoaded', updateInstallUi);
})();
