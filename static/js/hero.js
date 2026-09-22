document.addEventListener('DOMContentLoaded', function () {
    var isHome = document.querySelector('[data-home-hero]');
    if (!isHome) return;

    // ========== BACKGROUND FADE IN ==========
    var bg = document.querySelector('.hero-bg');
    if (bg) {
        setTimeout(function () { bg.classList.add('hero-bg-visible'); }, 200);
    }

    // ========== PARTICLES ==========
    var pc = document.getElementById('heroParticles');
    if (pc) {
        var count = window.innerWidth < 768 ? 18 : 30;
        for (var i = 0; i < count; i++) {
            var d = document.createElement('div');
            d.className = 'hero-particle';
            var size = Math.random() * 3 + 1.5;
            var dur = Math.random() * 14 + 10;
            var del = Math.random() * 10;
            var drift = (Math.random() - 0.5) * 80;
            var op = Math.random() * 0.35 + 0.2;
            d.style.cssText =
                'width:' + size + 'px;height:' + size + 'px;' +
                'left:' + (Math.random() * 100) + '%;bottom:-10px;' +
                '--p-d:' + drift + 'px;--p-o:' + op + ';' +
                'animation:particleFloat ' + dur + 's linear ' + del + 's infinite;' +
                'box-shadow:0 0 ' + (size * 3) + 'px rgba(0,255,106,' + (op * 0.5) + ');';
            pc.appendChild(d);
        }
    }

    // ========== MOUSE PARALLAX (desktop only) ==========
    if (window.innerWidth >= 768 && bg) {
        var mx = 0, my = 0, cx = 0, cy = 0;
        document.addEventListener('mousemove', function (e) {
            mx = (e.clientX / window.innerWidth - 0.5) * 18;
            my = (e.clientY / window.innerHeight - 0.5) * 18;
        });
        (function animLoop() {
            cx += (mx - cx) * 0.05;
            cy += (my - cy) * 0.05;
            bg.style.transform = 'translate(' + cx + 'px,' + cy + 'px)';
            requestAnimationFrame(animLoop);
        })();
    }

    // ========== SEQUENTIAL REVEAL ==========
    var status   = document.querySelector('[data-hero-status]');
    var typeEl   = document.querySelector('[data-hero-type]');
    var cursor   = document.querySelector('[data-hero-cursor]');
    var brand    = document.querySelector('[data-hero-brand]');
    var line     = document.querySelector('[data-hero-line]');
    var subtitle = document.querySelector('[data-hero-subtitle]');
    var cta      = document.querySelector('[data-hero-cta]');
    var stats    = document.querySelector('[data-hero-stats]');

    function reveal(el, delay) {
        if (!el) return;
        setTimeout(function () { el.classList.add('hero-visible'); }, delay);
    }

    // Start sequence
    var base = 400;
    reveal(status, base);
    reveal(line, base + 1800);
    reveal(subtitle, base + 2000);
    reveal(cta, base + 2300);
    reveal(stats, base + 2600);

    // Typewriter
    if (typeEl) {
        setTimeout(function () {
            typeEl.classList.add('hero-typing');
            if (cursor) cursor.classList.add('hero-cursor-active');
        }, base + 200);

        var text = typeEl.textContent;
        var typeDur = text.length * 55 + 400;
        setTimeout(function () {
            if (cursor) cursor.classList.remove('hero-cursor-active');
        }, base + 200 + typeDur);
    }

    // Brand drop
    reveal(brand, base + 1400);
});
