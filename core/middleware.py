import time
import logging
from collections import defaultdict

from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('security')


class RateLimitStore:
    _store = defaultdict(list)

    @classmethod
    def get_requests(cls, key, window):
        now = time.time()
        cls._store[key] = [
            t for t in cls._store[key] if now - t < window
        ]
        return cls._store[key]

    @classmethod
    def add_request(cls, key):
        cls._store[key].append(time.time())

    @classmethod
    def clear(cls, key=None):
        if key:
            cls._store.pop(key, None)
        else:
            cls._store.clear()


class AuthRateLimitMiddleware(MiddlewareMixin):
    LOGIN_MAX = 10
    LOGIN_WINDOW = 900
    REGISTER_MAX = 3
    REGISTER_WINDOW = 3600
    OTP_MAX = 5
    OTP_WINDOW = 300
    PASSWORD_RESET_MAX = 3
    PASSWORD_RESET_WINDOW = 3600

    AUTH_PATHS = {
        'login': '/auth/login/',
        'register': '/auth/register/',
        'verify_otp': '/auth/verify-otp/',
        'password_reset': '/auth/password-reset/',
    }

    def _get_client_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def _is_auth_path(self, request, action):
        path = request.path.rstrip('/')
        target = self.AUTH_PATHS.get(action, '').rstrip('/')
        return path == target

    def _check_rate(self, key, max_requests, window):
        requests = RateLimitStore.get_requests(key, window)
        return len(requests) < max_requests

    def _record_request(self, key):
        RateLimitStore.add_request(key)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'POST':
            return None

        ip = self._get_client_ip(request)

        if self._is_auth_path(request, 'login'):
            key = f'login:{ip}'
            if not self._check_rate(key, self.LOGIN_MAX, self.LOGIN_WINDOW):
                logger.warning(f'Rate limit exceeded for login from IP: {ip}')
                from django.contrib import messages
                from django.utils.translation import gettext_lazy as _
                messages.error(
                    request,
                    _('Trop de tentatives. Réessayez dans 15 minutes.'),
                )
                return HttpResponseForbidden('Rate limit exceeded')
            RateLimitStore.add_request(key)

        elif self._is_auth_path(request, 'register'):
            key = f'register:{ip}'
            if not self._check_rate(key, self.REGISTER_MAX, self.REGISTER_WINDOW):
                logger.warning(f'Rate limit exceeded for register from IP: {ip}')
                from django.contrib import messages
                from django.utils.translation import gettext_lazy as _
                messages.error(
                    request,
                    _('Trop de comptes créés. Réessayez plus tard.'),
                )
                return HttpResponseForbidden('Rate limit exceeded')
            RateLimitStore.add_request(key)

        elif self._is_auth_path(request, 'verify_otp'):
            username = request.POST.get('username', '')
            key = f'otp:{ip}:{username}'
            if not self._check_rate(key, self.OTP_MAX, self.OTP_WINDOW):
                logger.warning(
                    f'Rate limit exceeded for OTP from IP: {ip}, user: {username}'
                )
                from django.contrib import messages
                from django.utils.translation import gettext_lazy as _
                messages.error(
                    request,
                    _('Trop de tentatives de vérification. Réessayez plus tard.'),
                )
                return HttpResponseForbidden('Rate limit exceeded')
            RateLimitStore.add_request(key)

        elif self._is_auth_path(request, 'password_reset'):
            key = f'password_reset:{ip}'
            if not self._check_rate(
                key, self.PASSWORD_RESET_MAX, self.PASSWORD_RESET_WINDOW
            ):
                logger.warning(
                    f'Rate limit exceeded for password reset from IP: {ip}'
                )
                from django.contrib import messages
                from django.utils.translation import gettext_lazy as _
                messages.error(
                    request,
                    _('Trop de demandes de réinitialisation. Réessayez plus tard.'),
                )
                return HttpResponseForbidden('Rate limit exceeded')
            RateLimitStore.add_request(key)

        return None
