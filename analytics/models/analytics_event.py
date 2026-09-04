from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalyticsEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('PAGE_VIEW', _('Page View')),
        ('REGISTRATION', _('Registration')),
        ('LOGIN', _('Login')),
        ('DEPOSIT_CREATED', _('Deposit Created')),
        ('DEPOSIT_APPROVED', _('Deposit Approved')),
        ('WITHDRAWAL_CREATED', _('Withdrawal Created')),
        ('WITHDRAWAL_COMPLETED', _('Withdrawal Completed')),
        ('AI_VIEWED', _('AI Viewed')),
        ('AI_RENTED', _('AI Rented')),
        ('REFERRAL_CREATED', _('Referral Created')),
    ]

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        verbose_name=_('event type'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events',
        verbose_name=_('user'),
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name=_('session ID'),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP address'),
    )
    user_agent = models.TextField(
        blank=True,
        default='',
        verbose_name=_('user agent'),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('metadata'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('analytics event')
        verbose_name_plural = _('analytics events')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        user_str = self.user or 'anonymous'
        return f'{self.event_type} - {user_str}'
