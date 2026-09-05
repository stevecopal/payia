from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .ai_offer import AiOffer


class AiRental(models.Model):

    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        EXPIRED = 'expired', _('Expired')
        CANCELLED = 'cancelled', _('Cancelled')
        SUSPENDED = 'suspended', _('Suspended')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_rentals',
        verbose_name=_('user'),
    )
    offer = models.ForeignKey(
        AiOffer,
        on_delete=models.CASCADE,
        related_name='rentals',
        verbose_name=_('offer'),
    )
    start_date = models.DateTimeField(
        verbose_name=_('start date'),
    )
    end_date = models.DateTimeField(
        verbose_name=_('end date'),
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('amount paid'),
    )
    productive_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name=_('productive amount'),
        help_text=_('The capital base used for revenue calculations, after referral commissions.'),
    )
    earning_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_('earning amount per period'),
    )
    next_payment_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('next payment at'),
    )
    last_payment_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('last payment at'),
    )
    payment_count = models.IntegerField(
        default=0,
        verbose_name=_('payment count'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_('status'),
    )
    total_revenue_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_('total revenue earned'),
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
        verbose_name = _('AI rental')
        verbose_name_plural = _('AI rentals')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'offer', 'start_date'],
                name='unique_user_offer_start',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'next_payment_at'], name='rental_status_next_payment_idx'),
            models.Index(fields=['user', 'status'], name='rental_user_status_idx'),
        ]

    def __str__(self):
        return f"{self.user} - {self.offer}"

    def is_expired(self):
        return timezone.now() >= self.end_date

    def extend(self, days):
        from datetime import timedelta
        self.end_date += timedelta(days=days)
        self.save(update_fields=['end_date', 'updated_at'])

    def deactivate(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
