from django.db import models
from django.utils.translation import gettext_lazy as _


class Permission(models.Model):
    codename = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('codename'),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('name'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('description'),
    )
    category = models.CharField(
        max_length=50,
        verbose_name=_('category'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        ordering = ['category', 'codename']

    def __str__(self):
        return self.codename
