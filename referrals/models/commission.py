from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Commission(models.Model):
    """Commission earned by a referrer from a referred user's machine revenue.

    Commissions are ONLY generated when a machine produces revenue.
    They are NEVER taken from deposits.

    Financial rule:
        revenue_amount = commission_L1 + commission_L2 + user_net_amount
        The machine's gross revenue is split: referrers get their %, user gets the rest.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        AVAILABLE = 'available', _('Available')
        CANCELLED = 'cancelled', _('Cancelled')
        REVOKED = 'revoked', _('Revoked')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commissions_earned',
        verbose_name=_('user (referrer)'),
    )
    source_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commissions_generated',
        verbose_name=_('source user (referred)'),
    )
    referral_level = models.IntegerField(
        verbose_name=_('referral level'),
    )
    ai_revenue = models.ForeignKey(
        'ai_services.AiRevenue',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='commissions',
        verbose_name=_('AI revenue source'),
        help_text=_('The revenue event that generated this commission.'),
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_('percentage'),
    )
    gross_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name=_('gross revenue'),
        help_text=_('The machine revenue before commissions.'),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('commission amount'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('status'),
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('paid at'),
    )
    ledger_entry = models.ForeignKey(
        'wallet.LedgerEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commissions',
        verbose_name=_('ledger entry'),
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
        verbose_name = _('commission')
        verbose_name_plural = _('commissions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='commission_user_status_idx'),
            models.Index(fields=['source_user'], name='commission_source_user_idx'),
            models.Index(fields=['status'], name='commission_status_idx'),
            models.Index(fields=['created_at'], name='commission_created_idx'),
        ]

    def __str__(self):
        return f"{self.user} - {self.amount} ({self.get_status_display()})"

    def approve(self):
        self.status = self.Status.APPROVED
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at', 'updated_at'])

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def revoke(self):
        self.status = self.Status.REVOKED
        self.save(update_fields=['status', 'updated_at'])
