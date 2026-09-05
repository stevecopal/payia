document.addEventListener('DOMContentLoaded', function () {

    // ========== IMAGE ==========
    var img = document.querySelector('.hero-bg-image');
    if (img) {
        setTimeout(function () { img.classList.add('hero-img-in'); }, 100);
        setTimeout(function () {
            img.classList.remove('hero-img-in');
            img.style.opacity = '0.5';
            img.classList.add('hero-img-loop');
        }, 1200);

        // Mouse parallax (desktop)
        if (window.innerWidth >= 768) {
            var raf = null, tx = 0, ty = 0, cx = 0, cy = 0;
            document.addEventListener('mousemove', function (e) {
                tx = (e.clientX / window.innerWidth - 0.5) * 25;
                ty = (e.clientY / window.innerHeight - 0.5) * 25;
                if (!raf) raf = requestAnimationFrame(updateParallax);
            });
            function updateParallax() {
                cx += (tx - cx) * 0.07;
                cy += (ty - cy) * 0.07;
                if (img.classList.contains('hero-img-loop')) {
                    img.style.transform =
                        'translate(' + cx + 'px,' + cy + 'px) ' +
                        'rotate(' + (cx * 0.03) + 'deg) ' +
                        'scale(' + (1.02 + Math.abs(cx) * 0.001) + ')';
                }
                raf = requestAnimationFrame(updateParallax);
            }
        }
    }

    // ========== PARTICLES ==========
    var pc = document.getElementById('heroParticles');
    if (pc) {
        var n = window.innerWidth < 768 ? 16 : 28;
        for (var i = 0; i < n; i++) {
            var d = document.createElement('div');
            d.className = 'hero-particle';
            var s = Math.random() * 4 + 2;
            var dur = Math.random() * 10 + 8;
            var del = Math.random() * 12;
            var dr = (Math.random() - 0.5) * 100;
            var op = Math.random() * 0.4 + 0.3;
            d.style.cssText =
                'width:' + s + 'px;height:' + s + 'px;' +
                'left:' + (Math.random() * 100) + '%;bottom:-10px;' +
                '--p-d:' + dr + 'px;--p-o:' + op + ';' +
                'animation:heroParticleRise ' + dur + 's linear ' + del + 's infinite;' +
                'box-shadow:0 0 ' + (s * 3) + 'px rgba(0,255,106,' + (op * 0.6) + ');';
            pc.appendChild(d);
        }
    }

    // ========== TEXT ANIMATION SEQUENCE ==========
    var tagline   = document.querySelector('.hero-tagline');
    var typeLine  = document.querySelector('.hero-type-text');
    var cursor    = document.querySelector('.hero-type-cursor');
    var payia     = document.querySelector('.hero-payia');
    var underline = document.querySelector('.hero-underline');
    var subtitle  = document.querySelector('.hero-subtitle');
    var cta       = document.querySelector('.hero-cta');

    var seqDelay = 300; // start delay

    function startSequence() {
        // 1) Tagline pops in
        setTimeout(function () {
            if (tagline) tagline.classList.add('hero-anim');
        }, seqDelay);

        // 2) Typewriter "Investissez dans l'avenir avec"
        setTimeout(function () {
            if (typeLine) {
                typeLine.style.maxWidth = '0';
                typeLine.style.opacity = '1';
                typeLine.classList.add('hero-anim');
            }
            if (cursor) cursor.classList.remove('hero-cursor-off');
        }, seqDelay + 500);

        // 3) After typewriter finishes → hide cursor → drop PAYIA
        var typeDuration = 1200;
        setTimeout(function () {
            if (cursor) cursor.classList.add('hero-cursor-off');
            if (payia) payia.classList.add('hero-anim');
        }, seqDelay + 500 + typeDuration);

        // 4) Underline grows
        setTimeout(function () {
            if (underline) underline.classList.add('hero-anim');
        }, seqDelay + 500 + typeDuration + 400);

        // 5) Subtitle scales in + breathes
        setTimeout(function () {
            if (subtitle) subtitle.classList.add('hero-anim');
        }, seqDelay + 500 + typeDuration + 800);

        // 6) CTA button appears
        setTimeout(function () {
            if (cta) cta.classList.add('hero-anim');
        }, seqDelay + 500 + typeDuration + 1200);
    }

    // First run
    startSequence();

    // Loop every 10s
    setInterval(function () {
        // Reset all
        [tagline, typeLine, payia, underline, subtitle, cta].forEach(function (el) {
            if (!el) return;
            el.classList.remove('hero-anim');
            el.style.opacity = '';
            el.style.transform = '';
            el.style.maxWidth = '';
        });
        if (cursor) cursor.classList.remove('hero-cursor-off');

        // Re-trigger
        setTimeout(startSequence, 300);
    }, 10000);

    // ========== SCROLL REVEAL (other elements) ==========
    var fadeEls = document.querySelectorAll('.hero-fade');
    if (fadeEls.length && 'IntersectionObserver' in window) {
        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (en.isIntersecting) {
                    en.target.classList.add('visible');
                    obs.unobserve(en.target);
                }
            });
        }, { threshold: 0.15 });
        fadeEls.forEach(function (e) { obs.observe(e); });
    }
});
