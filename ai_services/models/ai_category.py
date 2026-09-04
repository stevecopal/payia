from django.db import models
from django.utils.translation import gettext_lazy as _


class AiCategory(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        unique=True,
        verbose_name=_('slug'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('description'),
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_('display order'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('is active'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('AI category')
        verbose_name_plural = _('AI categories')
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name
