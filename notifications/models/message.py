from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('INDIVIDUAL', _('Individual')),
        ('GROUP', _('Group')),
        ('BROADCAST', _('Broadcast')),
        ('AI_USERS', _('AI Users')),
        ('REFERRALS', _('Referrals')),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_messages',
        verbose_name=_('sender'),
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name=_('recipient'),
    )
    subject = models.CharField(
        max_length=200,
        verbose_name=_('subject'),
    )
    body = models.TextField(
        verbose_name=_('body'),
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('is read'),
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('read at'),
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default='INDIVIDUAL',
        verbose_name=_('message type'),
    )
    group_filter = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name=_('group filter'),
    )
    is_system_message = models.BooleanField(
        default=False,
        verbose_name=_('is system message'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subject} -> {self.recipient}'

    def mark_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
