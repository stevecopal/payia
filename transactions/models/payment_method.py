from decimal import Decimal

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class PaymentMethod(models.Model):
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), unique=True, max_length=100)
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("is active"), default=True)
    phone_number = models.CharField(
        _("reception phone number"),
        max_length=20,
        blank=True,
        default='',
        help_text=_('Mobile Money phone number used to receive deposits (e.g. 690123456).'),
    )
    reception_name = models.CharField(
        _("reception name"),
        max_length=150,
        blank=True,
        default='',
        help_text=_('Name displayed to users when receiving payment (e.g. John Mobile Money).'),
    )
    ussd_template = models.CharField(
        _("USSD template"),
        max_length=200,
        blank=True,
        default='',
        help_text=_('USSD code template with {amount} placeholder. E.g. *126*14*5555*{amount}#'),
    )
    instructions = models.TextField(
        _("instructions"),
        blank=True,
        help_text=_("Payment instructions shown to users."),
    )
    requires_proof = models.BooleanField(_("requires proof"), default=True)
    requires_transaction_id = models.BooleanField(
        _("requires transaction id"),
        default=True,
    )
    min_amount = models.DecimalField(
        _("minimum amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_amount = models.DecimalField(
        _("maximum amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    fee_percentage = models.DecimalField(
        _("fee percentage"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    fee_fixed = models.DecimalField(
        _("fixed fee"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    icon = models.CharField(_("icon"), max_length=50, blank=True)
    display_order = models.IntegerField(_("display order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("payment method")
        verbose_name_plural = _("payment methods")
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def calculate_fee(self, amount):
        amount = Decimal(str(amount))
        percentage_fee = (self.fee_percentage / Decimal("100")) * amount
        total_fee = percentage_fee + self.fee_fixed
        return total_fee.quantize(Decimal("0.01"))

    def generate_ussd_code(self, amount):
        if not self.ussd_template:
            return ''
        amount_str = str(int(Decimal(str(amount))))
        if '{amount}' in self.ussd_template:
            return self.ussd_template.replace('{amount}', amount_str)
        if self.ussd_template.endswith('#'):
            return self.ussd_template[:-1] + '*' + amount_str + '#'
        return self.ussd_template + '*' + amount_str
