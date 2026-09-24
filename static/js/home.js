// PAYIA — Interactivité de la page d'accueil
// Responsabilités : révélations au scroll, état actif de la navigation,
// compteurs, notifications d'activité, FAQ, médias.
// La logique générale de la navbar (menu mobile, état au scroll) vit dans nav.js.

(function () {
    'use strict';

    var doc = document;
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    function onReady(fn) {
        if (doc.readyState !== 'loading') {
            fn();
        } else {
            doc.addEventListener('DOMContentLoaded', fn);
        }
    }

    function prefersReducedMotion() {
        return reduceMotion.matches;
    }

    /* ============================================================
       1. Révélations au scroll (IntersectionObserver)
       ============================================================ */
    var Reveal = {
        init: function () {
            var elements = doc.querySelectorAll('[data-reveal]');
            if (!elements.length) return;

            if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
                elements.forEach(function (el) { el.classList.add('is-visible'); });
                return;
            }

            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        observer.unobserve(entry.target);
                    }
                });
            }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });

            elements.forEach(function (el) { observer.observe(el); });
        }
    };

    /* ============================================================
       2. Navigation — état actif de la section courante
       ============================================================ */
    var ActiveSection = {
        init: function () {
            var links = doc.querySelectorAll('[data-nav-section]');
            if (!links.length || !('IntersectionObserver' in window)) return;

            var sections = [];
            links.forEach(function (link) {
                var section = doc.getElementById(link.getAttribute('data-nav-section'));
                if (section) sections.push(section);
            });
            if (!sections.length) return;

            var visible = {};

            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    visible[entry.target.id] = entry.isIntersecting ? entry.intersectionRatio : 0;
                });

                var bestId = null;
                var bestRatio = 0;
                Object.keys(visible).forEach(function (id) {
                    if (visible[id] > bestRatio) {
                        bestRatio = visible[id];
                        bestId = id;
                    }
                });

                links.forEach(function (link) {
                    var active = bestId !== null && link.getAttribute('data-nav-section') === bestId;
                    link.classList.toggle('is-active', active);
                    if (active) {
                        link.setAttribute('aria-current', 'true');
                    } else {
                        link.removeAttribute('aria-current');
                    }
                });
            }, { rootMargin: '-30% 0px -50% 0px', threshold: [0, 0.25, 0.5, 1] });

            sections.forEach(function (section) { observer.observe(section); });
        }
    };

    /* ============================================================
       3. Compteurs de la section "Activité"
       ============================================================ */
    var Counters = {
        init: function () {
            var counters = doc.querySelectorAll('[data-count]');
            if (!counters.length) return;

            function animate(el) {
                var target = parseInt(el.getAttribute('data-count'), 10);
                if (isNaN(target)) return;

                if (prefersReducedMotion() || target === 0) {
                    el.textContent = String(target);
                    return;
                }

                var duration = 1100;
                var start = null;

                function step(ts) {
                    if (start === null) start = ts;
                    var progress = Math.min((ts - start) / duration, 1);
                    var eased = 1 - Math.pow(1 - progress, 3);
                    el.textContent = String(Math.round(eased * target));
                    if (progress < 1) {
                        window.requestAnimationFrame(step);
                    } else {
                        el.textContent = String(target);
                    }
                }

                el.textContent = '0';
                window.requestAnimationFrame(step);
            }

            if (!('IntersectionObserver' in window)) {
                counters.forEach(animate);
                return;
            }

            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        animate(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.6 });

            counters.forEach(function (el) { observer.observe(el); });
        }
    };

    /* ============================================================
       4. FAQ — accordéon accessible
       ============================================================ */
    var Faq = {
        init: function () {
            doc.querySelectorAll('[data-faq-item]').forEach(function (item) {
                var trigger = item.querySelector('.faq-trigger');
                if (!trigger) return;

                trigger.addEventListener('click', function () {
                    var isOpen = item.classList.contains('is-open');
                    item.classList.toggle('is-open', !isOpen);
                    trigger.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
                });
            });
        }
    };

    /* ============================================================
       5. Notifications d'activité flottantes
       Alimentées par #lp-activity-data (JSON fourni par le backend).
       Discrètes, non bloquantes, désactivées en mouvement réduit
       ou en l'absence de données.
       ============================================================ */
    var ActivityToasts = {
        MAX_TOASTS: 4,
        VISIBLE_MS: 5200,
        GAP_MS: 2800,
        FIRST_DELAY_MS: 4500,

        init: function () {
            var stack = doc.getElementById('lp-toast-stack');
            if (!stack) return;

            var dataEl = doc.getElementById('lp-activity-data');
            if (!dataEl || prefersReducedMotion()) {
                stack.remove();
                return;
            }

            var events;
            try {
                events = JSON.parse(dataEl.textContent || '[]');
            } catch (e) {
                stack.remove();
                return;
            }
            if (!Array.isArray(events) || !events.length) {
                stack.remove();
                return;
            }

            var limit = Math.min(ActivityToasts.MAX_TOASTS, events.length);
            var shown = 0;

            function showToast(event) {
                var toast = doc.createElement('div');
                toast.className = 'lp-toast rounded-xl border border-white/10 bg-black/90 backdrop-blur-md px-4 py-3 shadow-lg shadow-black/40';

                var row = doc.createElement('div');
                row.className = 'flex items-start gap-3';

                var dot = doc.createElement('span');
                dot.className = 'mt-[7px] h-2 w-2 shrink-0 rounded-full bg-green-400';

                var body = doc.createElement('div');
                body.className = 'min-w-0';

                var label = doc.createElement('p');
                label.className = 'text-sm text-white/90';
                label.textContent = event.label || '';

                var when = doc.createElement('p');
                when.className = 'mt-0.5 text-xs text-gray-500';
                when.textContent = event.when || '';

                body.appendChild(label);
                body.appendChild(when);
                row.appendChild(dot);
                row.appendChild(body);
                toast.appendChild(row);
                stack.appendChild(toast);

                window.requestAnimationFrame(function () {
                    window.requestAnimationFrame(function () {
                        toast.classList.add('is-in');
                    });
                });

                window.setTimeout(function () {
                    toast.classList.add('is-out');
                    window.setTimeout(function () {
                        if (toast.parentNode) toast.parentNode.removeChild(toast);
                    }, 500);
                    scheduleNext();
                }, ActivityToasts.VISIBLE_MS);
            }

            function scheduleNext() {
                if (shown >= limit) {
                    window.setTimeout(function () {
                        if (stack && !stack.children.length) stack.remove();
                    }, 800);
                    return;
                }
                window.setTimeout(run, ActivityToasts.GAP_MS);
            }

            function run() {
                if (doc.hidden) {
                    window.setTimeout(run, 4000);
                    return;
                }
                showToast(events[shown]);
                shown += 1;
            }

            window.setTimeout(run, ActivityToasts.FIRST_DELAY_MS);
        }
    };

    /* ============================================================
       6. Médias — état de chargement du hero, secours sur erreur
       ============================================================ */
    var Media = {
        init: function () {
            var heroImg = doc.querySelector('[data-hero-img]');
            var heroMedia = doc.querySelector('.hero-media');

            if (heroImg && heroMedia) {
                var markLoaded = function () { heroMedia.classList.add('is-loaded'); };
                if (heroImg.complete) {
                    markLoaded();
                } else {
                    heroImg.addEventListener('load', markLoaded, { once: true });
                    heroImg.addEventListener('error', markLoaded, { once: true });
                }
            }

            doc.querySelectorAll('img').forEach(function (img) {
                img.addEventListener('error', function () {
                    img.style.visibility = 'hidden';
                }, { once: true });
            });
        }
    };

    /* ============================================================ */
    onReady(function () {
        if (!doc.body.classList.contains('home-page')) return;

        Reveal.init();
        ActiveSection.init();
        Counters.init();
        Faq.init();
        ActivityToasts.init();
        Media.init();
    });
})();
