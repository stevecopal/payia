from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
        verbose_name=_("user"),
    )
    available_balance = models.DecimalField(
        _("available balance"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    pending_balance = models.DecimalField(
        _("pending balance"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    total_deposited = models.DecimalField(
        _("total deposited"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    total_withdrawn = models.DecimalField(
        _("total withdrawn"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    total_earnings = models.DecimalField(
        _("total earnings"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    referral_earnings = models.DecimalField(
        _("referral earnings"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    is_active = models.BooleanField(_("is active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("wallet")
        verbose_name_plural = _("wallets")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Wallet of {self.user} — {self.available_balance}"

    def credit(self, amount, description="", reference_type="", reference_id=None):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            balance_before = wallet.available_balance
            wallet.available_balance += amount
            wallet.total_earnings += amount
            wallet.save(update_fields=[
                "available_balance",
                "total_earnings",
                "updated_at",
            ])

            from wallet.models.ledger_entry import LedgerEntry

            LedgerEntry.objects.create(
                user=wallet.user,
                wallet=wallet,
                entry_type=LedgerEntry.EntryType.DEPOSIT,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.available_balance,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
            )

        self.refresh_from_db()
        return self.available_balance

    def debit(self, amount, description="", reference_type="", reference_id=None):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be positive.")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if wallet.available_balance < amount:
                raise ValueError("Insufficient balance.")

            balance_before = wallet.available_balance
            wallet.available_balance -= amount
            wallet.total_withdrawn += amount
            wallet.save(update_fields=[
                "available_balance",
                "total_withdrawn",
                "updated_at",
            ])

            from wallet.models.ledger_entry import LedgerEntry

            LedgerEntry.objects.create(
                user=wallet.user,
                wallet=wallet,
                entry_type=LedgerEntry.EntryType.WITHDRAWAL,
                amount=-amount,
                balance_before=balance_before,
                balance_after=wallet.available_balance,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
            )

        self.refresh_from_db()
        return self.available_balance

    def reserve(self, amount):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Reserve amount must be positive.")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if wallet.available_balance < amount:
                raise ValueError("Insufficient available balance to reserve.")

            wallet.available_balance -= amount
            wallet.pending_balance += amount
            wallet.save(update_fields=[
                "available_balance",
                "pending_balance",
                "updated_at",
            ])

        self.refresh_from_db()
        return self.available_balance

    def release(self, amount):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Release amount must be positive.")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if wallet.pending_balance < amount:
                raise ValueError("Insufficient pending balance to release.")

            wallet.pending_balance -= amount
            wallet.available_balance += amount
            wallet.save(update_fields=[
                "pending_balance",
                "available_balance",
                "updated_at",
            ])

        self.refresh_from_db()
        return self.available_balance
