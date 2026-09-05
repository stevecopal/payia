from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .ai_offer import AiOffer
from .ai_rental import AiRental


class AiRevenue(models.Model):

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CREDITED = 'credited', _('Credited')
        CANCELLED = 'cancelled', _('Cancelled')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_revenues',
        verbose_name=_('user'),
    )
    rental = models.ForeignKey(
        AiRental,
        on_delete=models.CASCADE,
        related_name='revenues',
        verbose_name=_('rental'),
    )
    offer = models.ForeignKey(
        AiOffer,
        on_delete=models.CASCADE,
        related_name='revenues',
        verbose_name=_('offer'),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('amount'),
    )
    payment_reference = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('payment reference'),
    )
    period_start = models.DateTimeField(
        verbose_name=_('period start'),
    )
    period_end = models.DateTimeField(
        verbose_name=_('period end'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('status'),
    )
    credited_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('credited at'),
    )
    ledger_entry = models.ForeignKey(
        'wallet.LedgerEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_revenues',
        verbose_name=_('ledger entry'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('AI revenue')
        verbose_name_plural = _('AI revenues')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_reference'], name='revenue_payment_ref_idx'),
            models.Index(fields=['rental', 'status'], name='revenue_rental_status_idx'),
        ]

    def __str__(self):
        return f"{self.user} - {self.amount} ({self.payment_reference})"

    @staticmethod
    def generate_payment_reference(rental_id, payment_count):
        return f"RENTAL-{rental_id}-CYCLE-{payment_count}"

    def credit(self):
        self.status = self.Status.CREDITED
        self.credited_at = timezone.now()
        self.save(update_fields=['status', 'credited_at'])
