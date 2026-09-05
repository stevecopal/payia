from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .payment_method import PaymentMethod


class Deposit(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", _("Pending Review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        COMPLETED = "completed", _("Completed")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deposits",
        verbose_name=_("user"),
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
    )
    referral_commission_total = models.DecimalField(
        _("referral commission total"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_('Total referral commissions deducted from this deposit.'),
    )
    productive_amount = models.DecimalField(
        _("productive amount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_('Amount available for AI revenue calculations after referral commissions.'),
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="deposits",
        verbose_name=_("payment method"),
    )
    transaction_id = models.CharField(
        _("transaction id"),
        max_length=200,
        blank=True,
    )
    phone_number = models.CharField(
        _("transaction phone number"),
        max_length=20,
        blank=True,
        default='',
        help_text=_('Phone number used to make the Mobile Money transaction.'),
    )
    reception_number = models.CharField(
        _("reception number"),
        max_length=20,
        blank=True,
        default='',
        help_text=_('Mobile Money number used to receive the deposit.'),
    )
    ussd_code = models.CharField(
        _("USSD code"),
        max_length=200,
        blank=True,
        default='',
        help_text=_('Generated USSD code used for this deposit.'),
    )
    proof = models.ImageField(
        _("proof"),
        upload_to="deposit_proofs/",
        blank=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
    )
    admin_note = models.TextField(_("admin note"), blank=True)
    rejection_reason = models.TextField(_("rejection reason"), blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_deposits",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        _("ip address"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("deposit")
        verbose_name_plural = ("deposits")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "transaction_id"],
                condition=~models.Q(status="rejected"),
                name="unique_user_transaction_id_non_rejected",
            ),
        ]

    def __str__(self):
        return f"Deposit #{self.pk} — {self.user} — {self.amount}"

    def approve(self, admin_user):
        if self.status != self.Status.PENDING_REVIEW:
            raise ValueError("Only pending deposits can be approved.")

        self.status = self.Status.APPROVED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ])

    def reject(self, admin_user, reason=""):
        if self.status != self.Status.PENDING_REVIEW:
            raise ValueError("Only pending deposits can be rejected.")

        self.status = self.Status.REJECTED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "updated_at",
        ])

    def complete(self):
        if self.status != self.Status.APPROVED:
            raise ValueError("Only approved deposits can be completed.")

        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=[
            "status",
            "completed_at",
            "updated_at",
        ])
