from django.db import models
from django.conf import settings


class Notification(models.Model):
    class Type(models.TextChoices):
        STATUS_CHANGE = 'STATUS_CHANGE', 'Changement de statut'
        ASSIGNED      = 'ASSIGNED',      'Assignation'
        COMMENT       = 'COMMENT',       'Nouveau commentaire'
        SLA_WARNING   = 'SLA_WARNING',   'Alerte SLA'
        ESCALATION    = 'ESCALATION',    'Escalade'
        RESOLVED      = 'RESOLVED',      'Résolu'

    recipient  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    ticket     = models.ForeignKey(
        'tickets.Ticket', null=True, blank=True, on_delete=models.CASCADE,
        related_name='notifications'
    )
    type       = models.CharField(max_length=20, choices=Type.choices)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif {self.type} → {self.recipient}"

    @property
    def icon(self):
        icons = {
            'STATUS_CHANGE': 'bi-arrow-repeat',
            'ASSIGNED':      'bi-person-check',
            'COMMENT':       'bi-chat-dots',
            'SLA_WARNING':   'bi-exclamation-triangle',
            'ESCALATION':    'bi-arrow-up-circle',
            'RESOLVED':      'bi-check-circle',
        }
        return icons.get(self.type, 'bi-bell')
