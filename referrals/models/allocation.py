from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ReferralAllocation(models.Model):
    """Traceable record of a referral commission allocated from a deposit.

    Each allocation represents a portion of a deposit amount that was
    directed to a referrer as a commission. This is NOT a new creation
    of funds -- it is an allocation FROM the source deposit amount.

    Financial invariant:
        deposit.amount == deposit.referral_commission_total + deposit.productive_amount
        where referral_commission_total == SUM(ReferralAllocation.amount for this deposit)
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        CANCELLED = 'cancelled', _('Cancelled')
        REVERSED = 'reversed', _('Reversed')

    deposit = models.ForeignKey(
        'transactions.Deposit',
        on_delete=models.CASCADE,
        related_name='referral_allocations',
        verbose_name=_('deposit'),
    )
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_allocations_received',
        verbose_name=_('beneficiary (referrer)'),
    )
    source_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_allocations_generated',
        verbose_name=_('source user (depositor)'),
    )
    referral_level = models.PositiveIntegerField(
        verbose_name=_('referral level'),
    )
    base_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('base amount'),
        help_text=_('The deposit amount used as the basis for this commission calculation.'),
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_('percentage'),
        help_text=_('The referral rate percentage applied.'),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('commission amount'),
        help_text=_('The actual commission amount allocated (base_amount * percentage / 100).'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('status'),
    )
    commission = models.ForeignKey(
        'referrals.Commission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocations',
        verbose_name=_('commission'),
    )
    ledger_entry = models.ForeignKey(
        'wallet.LedgerEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_allocations',
        verbose_name=_('ledger entry'),
    )
    reference = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('reference'),
        help_text=_('Unique reference: DEP-{deposit_id}-LVL-{level}'),
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
        verbose_name = _('referral allocation')
        verbose_name_plural = _('referral allocations')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['deposit', 'referral_level'],
                name='unique_allocation_per_deposit_level',
            ),
        ]
        indexes = [
            models.Index(fields=['beneficiary', 'status'], name='alloc_beneficiary_status_idx'),
            models.Index(fields=['deposit', 'status'], name='alloc_deposit_status_idx'),
            models.Index(fields=['reference'], name='alloc_reference_idx'),
        ]

    def __str__(self):
        return (
            f"Allocation #{self.pk}: {self.amount} "
            f"(L{self.referral_level}) -> {self.beneficiary}"
        )

    def approve(self):
        self.status = self.Status.APPROVED
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def reverse(self):
        self.status = self.Status.REVERSED
        self.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def generate_reference(deposit_id, level):
        return f"DEP-{deposit_id}-LVL-{level}"
