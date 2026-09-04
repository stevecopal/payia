from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        'support.SupportTicket',
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('ticket'),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_messages',
        verbose_name=_('sender'),
    )
    message = models.TextField(
        verbose_name=_('message'),
    )
    attachment = models.FileField(
        upload_to='support_attachments/',
        blank=True,
        default='',
        verbose_name=_('attachment'),
    )
    is_internal_note = models.BooleanField(
        default=False,
        verbose_name=_('is internal note'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )

    class Meta:
        verbose_name = _('support message')
        verbose_name_plural = _('support messages')
        ordering = ['created_at']

    def __str__(self):
        return f'Message on ticket #{self.ticket_id} by {self.sender}'

    def mark_read(self):
        self.ticket.last_reply_at = timezone.now()
        self.ticket.save(update_fields=['last_reply_at'])
