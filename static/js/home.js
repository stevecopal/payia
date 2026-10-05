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
                toast.className = 'lp-toast rounded-xl border border-gray-200 bg-white backdrop-blur-md px-4 py-3 shadow-lg shadow-gray-300';

                var row = doc.createElement('div');
                row.className = 'flex items-start gap-3';

                var dot = doc.createElement('span');
                dot.className = 'mt-[7px] h-2 w-2 shrink-0 rounded-full bg-green-400';

                var body = doc.createElement('div');
                body.className = 'min-w-0';

                var label = doc.createElement('p');
                label.className = 'text-sm text-gray-700';
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

            this.initLazyVideos();
        },

        initLazyVideos: function () {
            var videos = doc.querySelectorAll('video[data-lazy-video][data-src]');
            if (!videos.length) return;

            function loadAndPlay(video) {
                if (video.dataset.loaded) return;
                video.dataset.loaded = '1';
                video.src = video.dataset.src;
                video.addEventListener('canplay', function () {
                    video.classList.remove('opacity-0');
                    video.classList.add('opacity-100');
                }, { once: true });
                video.play().catch(function () { /* autoplay bloqué : l'image reste visible */ });
            }

            if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
                videos.forEach(function (video) { video.removeAttribute('data-src'); });
                return;
            }

            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        loadAndPlay(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            }, { rootMargin: '200px 0px', threshold: 0.01 });

            videos.forEach(function (video) { observer.observe(video); });
        }
    };

    /* ============================================================
       7. Hero — visuel IA : réseau neuronal animé (canvas)
       Panneau décoratif (aria-hidden) : la boucle s'arrête hors écran
       ou en onglet masqué, et se réduit à une image fixe en mouvement
       réduit. Aucune requête réseau, aucune dépendance externe.
       ============================================================ */
    var HeroNet = {
        init: function () {
            var canvas = doc.querySelector('[data-hero-canvas]');
            if (!canvas || typeof canvas.getContext !== 'function') return;

            var ctx = canvas.getContext('2d');
            var host = canvas.parentNode;
            if (!ctx || !host) return;

            var dpr = Math.min(window.devicePixelRatio || 1, 2);
            var width = 0;
            var height = 0;
            var nodes = [];
            var pulses = [];
            var core = null;
            var maxDist = 110;
            var rafId = null;
            var running = false;
            var inView = true;
            var elapsed = 0;
            var lastTs = 0;
            var spawnAcc = 0;

            function seed() {
                var count = Math.round(Math.min(58, Math.max(24, (width * height) / 15000)));
                nodes = [];
                for (var i = 0; i < count; i += 1) {
                    nodes.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        vx: (Math.random() - 0.5) * 0.16,
                        vy: (Math.random() - 0.5) * 0.16,
                        r: 1.6 + Math.random() * 1.7,
                        hot: Math.random() < 0.24
                    });
                }

                maxDist = Math.max(70, Math.min(150, Math.min(width, height) * 0.3));

                var cx = width / 2;
                var cy = height / 2;
                var best = 0;
                var bestD = Infinity;
                for (var j = 0; j < nodes.length; j += 1) {
                    var d = (nodes[j].x - cx) * (nodes[j].x - cx) + (nodes[j].y - cy) * (nodes[j].y - cy);
                    if (d < bestD) {
                        bestD = d;
                        best = j;
                    }
                }
                core = nodes[best];
                core.hot = true;
                core.r = 4;
                core.vx *= 0.3;
                core.vy *= 0.3;
                pulses = [];
            }

            function resize() {
                var rect = host.getBoundingClientRect();
                var w = Math.max(1, Math.round(rect.width));
                var h = Math.max(1, Math.round(rect.height));
                if (w === width && h === height) return;

                width = w;
                height = h;
                canvas.width = Math.round(w * dpr);
                canvas.height = Math.round(h * dpr);
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                seed();
                render(0, true);
            }

            function update(dt) {
                for (var i = 0; i < nodes.length; i += 1) {
                    var n = nodes[i];
                    n.x += n.vx * dt;
                    n.y += n.vy * dt;
                    if (n.x < 0) {
                        n.x = 0;
                        n.vx *= -1;
                    } else if (n.x > width) {
                        n.x = width;
                        n.vx *= -1;
                    }
                    if (n.y < 0) {
                        n.y = 0;
                        n.vy *= -1;
                    } else if (n.y > height) {
                        n.y = height;
                        n.vy *= -1;
                    }
                }
            }

            function spawnPulse() {
                if (pulses.length >= 7 || nodes.length < 2) return;
                for (var attempt = 0; attempt < 14; attempt += 1) {
                    var a = Math.floor(Math.random() * nodes.length);
                    var b = Math.floor(Math.random() * nodes.length);
                    if (a === b) continue;
                    var dx = nodes[a].x - nodes[b].x;
                    var dy = nodes[a].y - nodes[b].y;
                    var d = Math.sqrt(dx * dx + dy * dy);
                    if (d > 1 && d < maxDist * 1.7) {
                        pulses.push({ a: a, b: b, t: 0, speed: 0.006 + Math.random() * 0.008 });
                        return;
                    }
                }
            }

            function render(dt, still) {
                ctx.clearRect(0, 0, width, height);
                if (!still) update(dt);

                var i;
                var j;
                var a;
                var b;

                /* Connexions du réseau */
                ctx.lineWidth = 1;
                for (i = 0; i < nodes.length; i += 1) {
                    a = nodes[i];
                    for (j = i + 1; j < nodes.length; j += 1) {
                        b = nodes[j];
                        var dx = a.x - b.x;
                        var dy = a.y - b.y;
                        var d = Math.sqrt(dx * dx + dy * dy);
                        if (d > maxDist) continue;
                        var alpha = 1 - d / maxDist;
                        ctx.strokeStyle = (a.hot || b.hot)
                            ? 'rgba(0, 196, 124, ' + (alpha * 0.5).toFixed(3) + ')'
                            : 'rgba(17, 24, 39, ' + (alpha * 0.16).toFixed(3) + ')';
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.stroke();
                    }
                }

                /* Impulsions de signal le long des connexions */
                for (i = pulses.length - 1; i >= 0; i -= 1) {
                    var p = pulses[i];
                    a = nodes[p.a];
                    b = nodes[p.b];
                    if (!a || !b) {
                        pulses.splice(i, 1);
                        continue;
                    }
                    if (!still) {
                        p.t += p.speed * dt;
                        if (p.t >= 1) {
                            pulses.splice(i, 1);
                            continue;
                        }
                    }
                    var px = a.x + (b.x - a.x) * p.t;
                    var py = a.y + (b.y - a.y) * p.t;
                    ctx.save();
                    ctx.shadowColor = 'rgba(0, 250, 154, 0.9)';
                    ctx.shadowBlur = 8;
                    ctx.fillStyle = 'rgba(0, 200, 128, 0.95)';
                    ctx.beginPath();
                    ctx.arc(px, py, 2.6, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }

                /* Nœuds */
                for (i = 0; i < nodes.length; i += 1) {
                    var n = nodes[i];
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
                    if (n.hot) {
                        ctx.fillStyle = '#00C47C';
                        ctx.fill();
                        ctx.lineWidth = 1;
                        ctx.strokeStyle = 'rgba(9, 9, 11, 0.32)';
                        ctx.stroke();
                    } else {
                        ctx.fillStyle = 'rgba(24, 24, 27, 0.8)';
                        ctx.fill();
                    }
                }

                /* Cœur du réseau : halo pulsé + anneau tournant */
                if (core) {
                    var t = still ? 0 : elapsed;
                    var beat = 4 + Math.sin(t / 420) * 2.5;
                    ctx.lineWidth = 1.5;
                    ctx.strokeStyle = 'rgba(0, 250, 154, 0.55)';
                    ctx.beginPath();
                    ctx.arc(core.x, core.y, core.r + 9 + beat, 0, Math.PI * 2);
                    ctx.stroke();

                    ctx.save();
                    ctx.setLineDash([4, 7]);
                    ctx.lineDashOffset = -t / 30;
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = 'rgba(9, 9, 11, 0.35)';
                    ctx.beginPath();
                    ctx.arc(core.x, core.y, core.r + 17, 0, Math.PI * 2);
                    ctx.stroke();
                    ctx.restore();
                }

                /* Balayage vertical discret (façon scanner IA) */
                if (!still) {
                    var y = ((elapsed % 9000) / 9000) * (height + 140) - 70;
                    var grad = ctx.createLinearGradient(0, y - 60, 0, y + 60);
                    grad.addColorStop(0, 'rgba(0, 250, 154, 0)');
                    grad.addColorStop(0.5, 'rgba(0, 250, 154, 0.12)');
                    grad.addColorStop(1, 'rgba(0, 250, 154, 0)');
                    ctx.fillStyle = grad;
                    ctx.fillRect(0, y - 60, width, 120);
                }
            }

            function frame(ts) {
                rafId = null;
                if (!running) return;
                if (!lastTs) lastTs = ts;
                var dt = Math.min(2.5, (ts - lastTs) / 16.667);
                lastTs = ts;
                elapsed += dt * 16.667;
                spawnAcc += dt * 16.667;
                if (spawnAcc > 420) {
                    spawnAcc = 0;
                    spawnPulse();
                }
                render(dt, false);
                rafId = window.requestAnimationFrame(frame);
            }

            function start() {
                if (running || !inView || doc.hidden || prefersReducedMotion()) return;
                running = true;
                lastTs = 0;
                rafId = window.requestAnimationFrame(frame);
            }

            function stop() {
                running = false;
                if (rafId !== null) {
                    window.cancelAnimationFrame(rafId);
                    rafId = null;
                }
            }

            resize();

            if ('ResizeObserver' in window) {
                new ResizeObserver(resize).observe(host);
            } else {
                window.addEventListener('resize', resize);
            }

            if ('IntersectionObserver' in window) {
                new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        inView = entry.isIntersecting;
                        if (inView) {
                            start();
                        } else {
                            stop();
                        }
                    });
                }, { threshold: 0.05 }).observe(host);
            }

            doc.addEventListener('visibilitychange', function () {
                if (doc.hidden) {
                    stop();
                } else {
                    start();
                }
            });

            start();
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
        HeroNet.init();
    });
})();
