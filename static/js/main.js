// PAYIA - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // Toast auto-dismiss
    document.querySelectorAll('.toast-notification').forEach(function(toast) {
        toast.classList.remove('translate-x-full', 'opacity-0');
        toast.classList.add('translate-x-0', 'opacity-100');
        setTimeout(function() {
            toast.classList.add('translate-x-full', 'opacity-0');
            setTimeout(function() { toast.remove(); }, 300);
        }, 5000);
    });

    // Confirm dialogs
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Copy to clipboard
    document.querySelectorAll('[data-copy]').forEach(function(el) {
        el.addEventListener('click', function() {
            const text = this.dataset.copy;
            navigator.clipboard.writeText(text).then(function() {
                const originalText = el.textContent;
                el.textContent = 'Copié !';
                setTimeout(function() { el.textContent = originalText; }, 2000);
            });
        });
    });

    // OTP input auto-focus
    const otpInputs = document.querySelectorAll('input[name="code"]');
    otpInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            if (this.value.length === 6) {
                this.closest('form').submit();
            }
        });
    });

    // Sidebar toggle for dashboard
    const openSidebar = document.getElementById('open-sidebar');
    const closeSidebar = document.getElementById('close-sidebar');
    const sidebar = document.getElementById('sidebar');

    if (openSidebar && sidebar) {
        openSidebar.addEventListener('click', function() {
            sidebar.classList.remove('-translate-x-full');
        });
    }
    if (closeSidebar && sidebar) {
        closeSidebar.addEventListener('click', function() {
            sidebar.classList.add('-translate-x-full');
        });
    }
});
