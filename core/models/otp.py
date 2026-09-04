import hashlib
import secrets

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class OTP(models.Model):
    PURPOSE_CHOICES = [
        ('LOGIN', _('Login')),
        ('REGISTER', _('Register')),
        ('PASSWORD_RESET', _('Password Reset')),
    ]

    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='otps',
        verbose_name=_('user'),
    )
    code = models.CharField(
        max_length=64,
        verbose_name=_('code'),
    )
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        verbose_name=_('purpose'),
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name=_('is used'),
    )
    expires_at = models.DateTimeField(
        verbose_name=_('expires at'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )
    attempts = models.IntegerField(
        default=0,
        verbose_name=_('attempts'),
    )
    max_attempts = models.IntegerField(
        default=5,
        verbose_name=_('max attempts'),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP address'),
    )

    class Meta:
        verbose_name = _('OTP')
        verbose_name_plural = _('OTPs')
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP for {self.user.phone_number} ({self.purpose})'

    @staticmethod
    def generate_code():
        return ''.join(secrets.choice('0123456789') for _ in range(6))

    @staticmethod
    def hash_code(code):
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def create_for_user(cls, user, purpose, ip_address=None):
        raw_code = cls.generate_code()
        hashed_code = cls.hash_code(raw_code)
        otp = cls.objects.create(
            user=user,
            code=hashed_code,
            purpose=purpose,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            ip_address=ip_address,
        )
        return otp, raw_code

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        if self.is_used:
            return False
        if self.is_expired():
            return False
        if self.attempts >= self.max_attempts:
            return False
        return True

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])

    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])

    def verify(self, raw_code):
        if not self.is_valid():
            return False
        self.increment_attempts()
        hashed_input = self.hash_code(raw_code)
        if hashed_input == self.code:
            self.mark_used()
            return True
        return False
