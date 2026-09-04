from django.db import models
from django.utils.translation import gettext_lazy as _


class AiModel(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        unique=True,
        verbose_name=_('slug'),
    )
    image = models.ImageField(
        upload_to='ai_models/',
        blank=True,
        default='',
        verbose_name=_('image'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('description'),
    )
    version = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name=_('version'),
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
        verbose_name = _('AI model')
        verbose_name_plural = _('AI models')
        ordering = ['name']

    def __str__(self):
        return self.name
