from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    actor = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('actor'),
    )
    action = models.CharField(
        max_length=100,
        verbose_name=_('action'),
    )
    target_type = models.CharField(
        max_length=100,
        verbose_name=_('target type'),
    )
    target_id = models.CharField(
        max_length=50,
        verbose_name=_('target ID'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('description'),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP address'),
    )
    user_agent = models.TextField(
        blank=True,
        default='',
        verbose_name=_('user agent'),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('metadata'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('audit log')
        verbose_name_plural = _('audit logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor']),
            models.Index(fields=['action']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        actor_display = self.actor.phone_number if self.actor else 'system'
        return f'{actor_display} - {self.action} - {self.target_type}:{self.target_id}'

    @classmethod
    def log(cls, actor, action, target_type, target_id, description='',
            ip_address=None, user_agent='', metadata=None):
        return cls.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )
