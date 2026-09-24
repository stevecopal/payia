// PAYIA - JS de l'espace client (application)
// Confirm, copy, OTP — la navigation est gérée par le template (états actifs serveur).

document.addEventListener('DOMContentLoaded', function () {
    // Confirm dialogs
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Copy to clipboard
    document.querySelectorAll('[data-copy]').forEach(function (el) {
        el.addEventListener('click', function () {
            const text = this.dataset.copy;
            navigator.clipboard.writeText(text).then(function () {
                const originalText = el.textContent;
                el.textContent = 'Copié !';
                setTimeout(function () { el.textContent = originalText; }, 2000);
            });
        });
    });

    // OTP input auto-submit
    document.querySelectorAll('input[name="code"]').forEach(function (input) {
        input.addEventListener('input', function () {
            if (this.value.length === 6) {
                this.closest('form').submit();
            }
        });
    });
});
