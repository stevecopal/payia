// PAYIA — Navigation des pages publiques (navbar, menu mobile, état au scroll)
// Chargé par templates/base/public.html sur toutes les pages publiques.

(function () {
    'use strict';

    function onReady(fn) {
        if (document.readyState !== 'loading') {
            fn();
        } else {
            document.addEventListener('DOMContentLoaded', fn);
        }
    }

    onReady(function () {
        var header = document.querySelector('[data-public-nav]');
        if (!header) return;

        var toggle = header.querySelector('[data-nav-toggle]');
        var menu = header.querySelector('[data-nav-menu]');
        var iconOpen = toggle ? toggle.querySelector('[data-icon-open]') : null;
        var iconClose = toggle ? toggle.querySelector('[data-icon-close]') : null;

        // ---------- Menu mobile ----------
        function setMenu(open) {
            if (!toggle || !menu) return;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            toggle.setAttribute('aria-label', open ? toggle.dataset.labelClose : toggle.dataset.labelOpen);
            menu.classList.toggle('is-open', open);
            if (iconOpen) iconOpen.classList.toggle('hidden', open);
            if (iconClose) iconClose.classList.toggle('hidden', !open);
        }

        if (toggle && menu) {
            toggle.addEventListener('click', function () {
                setMenu(toggle.getAttribute('aria-expanded') !== 'true');
            });

            menu.addEventListener('click', function (e) {
                if (e.target.closest('a')) setMenu(false);
            });

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') setMenu(false);
            });

            document.addEventListener('click', function (e) {
                if (!header.contains(e.target)) setMenu(false);
            });

            window.addEventListener('resize', function () {
                if (window.innerWidth >= 1024) setMenu(false);
            });
        }

        // ---------- État de la navbar au scroll ----------
        // Sur la home, la navbar reste "sur le hero" puis se solidifie
        // lorsqu'on quitte le hero. Ailleurs, après un léger scroll.
        var hero = document.querySelector('[data-hero]');
        var ticking = false;

        function updateNavState() {
            ticking = false;
            var limit = 24;
            if (hero) {
                limit = Math.max(hero.offsetTop + hero.offsetHeight - header.offsetHeight, 40);
            }
            header.classList.toggle('is-scrolled', window.scrollY >= limit);
        }

        function onScroll() {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(updateNavState);
            }
        }

        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', onScroll);
        updateNavState();
    });
})();
