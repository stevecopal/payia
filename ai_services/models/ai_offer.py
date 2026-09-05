from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .ai_category import AiCategory
from .ai_model import AiModel


class AiOffer(models.Model):

    class RevenueFrequency(models.TextChoices):
        DAILY = 'daily', _('Daily')
        WEEKLY = 'weekly', _('Weekly')
        MONTHLY = 'monthly', _('Monthly')

    class RevenueType(models.TextChoices):
        FIXED = 'fixed', _('Fixed')
        PERCENTAGE = 'percentage', _('Percentage')
        VARIABLE = 'variable', _('Variable')

    name = models.CharField(
        max_length=200,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        unique=True,
        verbose_name=_('slug'),
    )
    ai_model = models.ForeignKey(
        AiModel,
        on_delete=models.CASCADE,
        related_name='offers',
        verbose_name=_('AI model'),
    )
    category = models.ForeignKey(
        AiCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers',
        verbose_name=_('category'),
    )
    description = models.TextField(
        verbose_name=_('description'),
    )
    image = models.ImageField(
        upload_to='ai_images/',
        blank=True,
        default='',
        verbose_name=_('image'),
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('price'),
    )
    duration_days = models.IntegerField(
        verbose_name=_('duration (days)'),
    )
    revenue_frequency = models.CharField(
        max_length=20,
        choices=RevenueFrequency.choices,
        verbose_name=_('revenue frequency'),
    )
    revenue_type = models.CharField(
        max_length=20,
        choices=RevenueType.choices,
        verbose_name=_('revenue type'),
    )
    revenue_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('revenue value'),
    )
    revenue_metric = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name=_('revenue metric'),
    )
    conditions = models.TextField(
        blank=True,
        default='',
        verbose_name=_('conditions'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('is active'),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_('is featured'),
    )
    total_rentals = models.IntegerField(
        default=0,
        verbose_name=_('total rentals'),
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_('display order'),
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
        verbose_name = _('AI offer')
        verbose_name_plural = _('AI offers')
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def can_rent(self, user):
        from .ai_rental import AiRental

        return not AiRental.objects.filter(
            user=user,
            offer=self,
            status=AiRental.Status.ACTIVE,
        ).exists()

    def get_expected_revenue(self):
        if self.revenue_type == self.RevenueType.FIXED:
            return self.revenue_value
        if self.revenue_type == self.RevenueType.PERCENTAGE:
            return self.price * self.revenue_value / Decimal('100')
        return self.revenue_value

    def get_expected_revenue_for_amount(self, amount):
        """Calculate expected revenue based on a given capital amount.

        This allows using the productive_amount (after referral commissions)
        instead of the full offer price for revenue calculations.
        """
        amount = Decimal(str(amount))
        if self.revenue_type == self.RevenueType.FIXED:
            return self.revenue_value
        if self.revenue_type == self.RevenueType.PERCENTAGE:
            return amount * self.revenue_value / Decimal('100')
        return self.revenue_value
