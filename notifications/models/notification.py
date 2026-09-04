from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('DEPOSIT_SUBMITTED', _('Deposit Submitted')),
        ('DEPOSIT_APPROVED', _('Deposit Approved')),
        ('DEPOSIT_REJECTED', _('Deposit Rejected')),
        ('WITHDRAWAL_REQUESTED', _('Withdrawal Requested')),
        ('WITHDRAWAL_APPROVED', _('Withdrawal Approved')),
        ('WITHDRAWAL_REJECTED', _('Withdrawal Rejected')),
        ('WITHDRAWAL_COMPLETED', _('Withdrawal Completed')),
        ('AI_ACTIVATED', _('AI Activated')),
        ('AI_EXPIRED', _('AI Expired')),
        ('COMMISSION_RECEIVED', _('Commission Received')),
        ('NEW_REFERRAL', _('New Referral')),
        ('SECURITY_ALERT', _('Security Alert')),
        ('SYSTEM_MESSAGE', _('System Message')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('user'),
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPE_CHOICES,
        verbose_name=_('notification type'),
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('title'),
    )
    message = models.TextField(
        verbose_name=_('message'),
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('is read'),
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('read at'),
    )
    link = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name=_('link'),
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
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.user} - {self.title}'

    def mark_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])

    @staticmethod
    def mark_all_read(user):
        Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
