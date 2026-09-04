import json

from django.db import models
from django.utils.translation import gettext_lazy as _


class Setting(models.Model):
    SETTING_TYPE_CHOICES = [
        ('STRING', _('String')),
        ('INTEGER', _('Integer')),
        ('DECIMAL', _('Decimal')),
        ('BOOLEAN', _('Boolean')),
        ('JSON', _('JSON')),
    ]

    key = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('key'),
    )
    value = models.TextField(
        blank=True,
        default='',
        verbose_name=_('value'),
    )
    setting_type = models.CharField(
        max_length=10,
        choices=SETTING_TYPE_CHOICES,
        default='STRING',
        verbose_name=_('setting type'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('description'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('is active'),
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
        verbose_name = _('setting')
        verbose_name_plural = _('settings')
        ordering = ['key']

    def __str__(self):
        return self.key

    def get_value(self):
        if self.setting_type == 'INTEGER':
            return int(self.value)
        elif self.setting_type == 'DECIMAL':
            from decimal import Decimal, InvalidOperation
            try:
                return Decimal(self.value)
            except InvalidOperation:
                return Decimal('0')
        elif self.setting_type == 'BOOLEAN':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'JSON':
            try:
                return json.loads(self.value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return self.value

    def set_value(self, value):
        if self.setting_type == 'JSON':
            self.value = json.dumps(value)
        else:
            self.value = str(value)
        self.save(update_fields=['value', 'updated_at'])

    @classmethod
    def get_setting(cls, key, default=None):
        try:
            setting = cls.objects.get(key=key, is_active=True)
            return setting.get_value()
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_setting(cls, key, value, setting_type='STRING', description=''):
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': json.dumps(value) if setting_type == 'JSON' else str(value),
                'setting_type': setting_type,
                'description': description,
                'is_active': True,
            },
        )
        return setting
