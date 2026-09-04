from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Role(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_('slug'),
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
    permissions = models.ManyToManyField(
        'core.Permission',
        blank=True,
        related_name='roles',
        verbose_name=_('permissions'),
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
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
