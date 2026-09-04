from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Commission(models.Model):

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
        verbose_name=_('user'),
    )
    source_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commissions_generated',
        verbose_name=_('source user'),
    )
    referral_level = models.IntegerField(
        verbose_name=_('referral level'),
    )
    source_transaction_type = models.CharField(
        max_length=50,
        verbose_name=_('source transaction type'),
    )
    source_transaction_id = models.PositiveIntegerField(
        verbose_name=_('source transaction ID'),
    )
    percentage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('percentage'),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('amount'),
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

    def __str__(self):
        return f"{self.user} - {self.amount} ({self.get_status_display()})"

    def approve(self):
        self.status = self.Status.APPROVED
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def revoke(self):
        self.status = self.Status.REVOKED
        self.save(update_fields=['status', 'updated_at'])
