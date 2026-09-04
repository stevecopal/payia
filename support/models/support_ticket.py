from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SupportTicket(models.Model):
    CATEGORY_CHOICES = [
        ('GENERAL', _('General')),
        ('DEPOSIT', _('Deposit')),
        ('WITHDRAWAL', _('Withdrawal')),
        ('AI', _('AI')),
        ('REFERRAL', _('Referral')),
        ('ACCOUNT', _('Account')),
        ('TECHNICAL', _('Technical')),
        ('OTHER', _('Other')),
    ]

    PRIORITY_CHOICES = [
        ('LOW', _('Low')),
        ('MEDIUM', _('Medium')),
        ('HIGH', _('High')),
        ('URGENT', _('Urgent')),
    ]

    STATUS_CHOICES = [
        ('OPEN', _('Open')),
        ('IN_PROGRESS', _('In Progress')),
        ('WAITING_USER', _('Waiting for User')),
        ('RESOLVED', _('Resolved')),
        ('CLOSED', _('Closed')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets',
        verbose_name=_('user'),
    )
    subject = models.CharField(
        max_length=200,
        verbose_name=_('subject'),
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name=_('category'),
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        verbose_name=_('priority'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        verbose_name=_('status'),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name=_('assigned to'),
    )
    last_reply_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('last reply at'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('updated at'),
    )

    class Meta:
        verbose_name = _('support ticket')
        verbose_name_plural = _('support tickets')
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} - {self.subject}'

    def close(self):
        self.status = 'CLOSED'
        self.save(update_fields=['status', 'updated_at'])

    def assign(self, user):
        self.assigned_to = user
        self.status = 'IN_PROGRESS'
        self.save(update_fields=['assigned_to', 'status', 'updated_at'])

    def set_priority(self, priority):
        self.priority = priority
        self.save(update_fields=['priority', 'updated_at'])
