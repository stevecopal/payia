from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentEvent(models.Model):
    event_id = models.CharField(
        _("event id"),
        max_length=200,
        unique=True,
    )
    provider = models.CharField(_("provider"), max_length=100)
    event_type = models.CharField(_("event type"), max_length=100)
    payload = models.JSONField(_("payload"))
    processed = models.BooleanField(_("processed"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("payment event")
        verbose_name_plural = _("payment events")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}:{self.event_type} ({self.event_id})"

    def mark_processed(self):
        self.processed = True
        self.save(update_fields=["processed"])
