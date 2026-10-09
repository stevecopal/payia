from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DepositAttempt(models.Model):
    """Une tentative de paiement en ligne (Tara Money) rattachee a un depot.

    La demande de depot (`Deposit`) est distincte de ses tentatives : un
    utilisateur peut reessayer un paiement echoue, expire ou abandonne sans
    jamais pouvoir crediter deux fois le meme depot.

    `reference` est l'identifiant unique envoye a Tara Money (productId) :
    c'est la reference de la tentative, unique par essai, utilisee par le
    webhook et par l'API de statut.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILURE = "failure", _("Failure")
        EXPIRED = "expired", _("Expired")

    class Channel(models.TextChoices):
        # Debit direct sur le numero Mobile Money (endpoint mobilepay Tara).
        MOMO = "momo", _("Mobile Money")
        WAVE = "wave", _("Wave")
        # Redirection vers la page de paiement Tara (lien/carte).
        CARD = "card", _("Payment link")

    PUSH_CHANNELS = (Channel.MOMO, Channel.WAVE)

    deposit = models.ForeignKey(
        "transactions.Deposit",
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name=_("deposit"),
    )
    reference = models.CharField(
        _("reference"),
        max_length=100,
        unique=True,
        help_text=_("Unique payment reference sent to Tara Money (productId)."),
    )
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Amount in XAF locked for this attempt."),
    )
    channel = models.CharField(
        _("channel"),
        max_length=12,
        choices=Channel.choices,
        default=Channel.CARD,
        help_text=_(
            "Payment channel chosen by the user: direct debit on the phone "
            "number or payment link."
        ),
    )
    network = models.CharField(
        _("network"),
        max_length=20,
        blank=True,
        default="",
        help_text=_("Tara Money network parameter (empty or 'wave')."),
    )
    vendor = models.CharField(
        _("vendor"),
        max_length=50,
        blank=True,
        default="",
        help_text=_("Operator identified by Tara Money (ex: ORANGE_CAMEROON)."),
    )
    launched_at = models.DateTimeField(
        _("launched at"),
        null=True,
        blank=True,
        help_text=_("Moment ou le debit direct a ete demande au prestataire."),
    )

    payment_id = models.CharField(
        _("payment id"),
        max_length=200,
        blank=True,
        default="",
        help_text=_("Provider payment identifier received in the webhook."),
    )
    pay_url = models.CharField(
        _("payment url"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("generalLink returned by Tara Money."),
    )
    links = models.JSONField(
        _("links"),
        default=dict,
        blank=True,
        help_text=_("All payment links returned by the provider."),
    )
    provider_payload = models.JSONField(
        _("provider payload"),
        default=dict,
        blank=True,
        help_text=_("Last verified payload received from the provider."),
    )
    failure_reason = models.CharField(
        _("failure reason"),
        max_length=300,
        blank=True,
        default="",
    )
    conflict = models.BooleanField(
        _("conflict"),
        default=False,
        help_text=_(
            "Payment confirmed by the provider but the deposit could not be "
            "credited automatically (manual reconciliation required)."
        ),
    )
    last_checked_at = models.DateTimeField(
        _("last checked at"),
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(
        _("verified at"),
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(_("expires at"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("deposit attempt")
        verbose_name_plural = _("deposit attempts")
        ordering = ["-created_at"]
        constraints = [
            # Une seule tentative peut passer en success par depot : garantie
            # de base de donnees contre tout double credit.
            models.UniqueConstraint(
                fields=["deposit"],
                condition=models.Q(status="success"),
                name="unique_success_attempt_per_deposit",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="attempt_status_created_idx"),
            models.Index(fields=["deposit", "status"], name="attempt_deposit_status_idx"),
            models.Index(fields=["expires_at"], name="attempt_expires_idx"),
        ]

    def __str__(self):
        return f"Attempt {self.reference} ({self.status}) — deposit #{self.deposit_id}"

    @property
    def is_terminal(self):
        return self.status in (
            self.Status.SUCCESS,
            self.Status.FAILURE,
            self.Status.EXPIRED,
        )

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at < timezone.now()

    @property
    def is_push(self):
        """Debit direct sur le numero (le lien de paiement n'est pas utilise)."""
        return self.channel in self.PUSH_CHANNELS


    def mark_success(self, payment_id="", payload=None, save=True):
        self.status = self.Status.SUCCESS
        if payment_id:
            self.payment_id = str(payment_id)
        if payload:
            self.provider_payload = payload
        self.verified_at = timezone.now()
        self.last_checked_at = self.verified_at
        if save:
            self.save(update_fields=[
                "status", "payment_id", "provider_payload",
                "verified_at", "last_checked_at", "updated_at",
            ])

    def mark_failure(self, reason="", payload=None, save=True):
        self.status = self.Status.FAILURE
        if reason:
            self.failure_reason = str(reason)[:300]
        if payload:
            self.provider_payload = payload
        self.verified_at = timezone.now()
        self.last_checked_at = self.verified_at
        if save:
            self.save(update_fields=[
                "status", "failure_reason", "provider_payload",
                "verified_at", "last_checked_at", "updated_at",
            ])

    def mark_expired(self, reason="", save=True):
        self.status = self.Status.EXPIRED
        if reason:
            self.failure_reason = str(reason)[:300]
        if save:
            self.save(update_fields=["status", "failure_reason", "updated_at"])

    def touch_checked(self, save=True):
        self.last_checked_at = timezone.now()
        if save:
            self.save(update_fields=["last_checked_at", "updated_at"])

    def amount_as_decimal(self):
        return Decimal(str(self.amount))
