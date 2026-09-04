from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .wallet import Wallet


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        DEPOSIT = "deposit", _("Deposit")
        WITHDRAWAL = "withdrawal", _("Withdrawal")
        AI_PURCHASE = "ai_purchase", _("AI Purchase")
        AI_REVENUE = "ai_revenue", _("AI Revenue")
        REFERRAL_COMMISSION = "referral_commission", _("Referral Commission")
        BONUS = "bonus", _("Bonus")
        REFUND = "refund", _("Refund")
        ADJUSTMENT = "adjustment", _("Adjustment")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        verbose_name=_("user"),
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        verbose_name=_("wallet"),
    )
    entry_type = models.CharField(
        _("entry type"),
        max_length=30,
        choices=EntryType.choices,
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
    )
    balance_before = models.DecimalField(
        _("balance before"),
        max_digits=12,
        decimal_places=2,
    )
    balance_after = models.DecimalField(
        _("balance after"),
        max_digits=12,
        decimal_places=2,
    )
    reference_type = models.CharField(
        _("reference type"),
        max_length=100,
        blank=True,
    )
    reference_id = models.PositiveIntegerField(
        _("reference id"),
        null=True,
        blank=True,
    )
    description = models.TextField(_("description"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("ledger entry")
        verbose_name_plural = _("ledger entries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"], name="ledger_entry_user_idx"),
            models.Index(fields=["wallet"], name="ledger_entry_wallet_idx"),
            models.Index(fields=["entry_type"], name="ledger_entry_type_idx"),
            models.Index(fields=["created_at"], name="ledger_entry_created_idx"),
        ]

    def __str__(self):
        return (
            f"{self.get_entry_type_display()}: {self.amount} "
            f"({self.balance_before} → {self.balance_after})"
        )
