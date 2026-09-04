from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .payment_method import PaymentMethod


class Withdrawal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        UNDER_REVIEW = "under_review", _("Under Review")
        APPROVED = "approved", _("Approved")
        PROCESSING = "processing", _("Processing")
        COMPLETED = "completed", _("Completed")
        REJECTED = "rejected", _("Rejected")
        CANCELLED = "cancelled", _("Cancelled")
        FAILED = "failed", _("Failed")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdrawals",
        verbose_name=_("user"),
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
    )
    fee = models.DecimalField(
        _("fee"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    net_amount = models.DecimalField(
        _("net amount"),
        max_digits=12,
        decimal_places=2,
    )
    withdrawal_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="withdrawals",
        verbose_name=_("withdrawal method"),
    )
    withdrawal_number = models.CharField(
        _("withdrawal number"),
        max_length=200,
    )
    withdrawal_account_name = models.CharField(
        _("withdrawal account name"),
        max_length=200,
        blank=True,
    )
    external_reference = models.CharField(
        _("external reference"),
        max_length=200,
        blank=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_note = models.TextField(_("admin note"), blank=True)
    rejection_reason = models.TextField(_("rejection reason"), blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_withdrawals",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        _("ip address"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("withdrawal")
        verbose_name_plural = _("withdrawals")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Withdrawal #{self.pk} — {self.user} — {self.net_amount}"

    def approve(self, admin_user):
        if self.status not in (self.Status.PENDING, self.Status.UNDER_REVIEW):
            raise ValueError("Only pending or under-review withdrawals can be approved.")

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
        if self.status not in (self.Status.PENDING, self.Status.UNDER_REVIEW):
            raise ValueError("Only pending or under-review withdrawals can be rejected.")

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

    def process(self, admin_user):
        if self.status != self.Status.APPROVED:
            raise ValueError("Only approved withdrawals can be processed.")

        self.status = self.Status.PROCESSING
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status",
            "processed_at",
            "updated_at",
        ])

    def complete(self, admin_user):
        if self.status != self.Status.PROCESSING:
            raise ValueError("Only processing withdrawals can be completed.")

        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=[
            "status",
            "completed_at",
            "updated_at",
        ])
