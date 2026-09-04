from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Referral(models.Model):
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made',
        verbose_name=_('referrer'),
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_info',
        verbose_name=_('referred user'),
    )
    referral_level = models.IntegerField(
        verbose_name=_('referral level'),
    )
    parent_referral = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_referrals',
        verbose_name=_('parent referral'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('is active'),
    )

    class Meta:
        verbose_name = _('referral')
        verbose_name_plural = _('referrals')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['referrer', 'referred_user'],
                name='unique_referrer_referred_user',
            ),
        ]

    def __str__(self):
        return f"{self.referrer} -> {self.referred_user} (L{self.referral_level})"

    def get_level_1_referrer(self):
        current = self
        while current.parent_referral is not None:
            current = current.parent_referral
        return current.referrer

    def get_chain(self):
        chain = []
        current = self
        while current is not None:
            chain.append(current)
            current = current.parent_referral
        return list(reversed(chain))
