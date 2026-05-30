from django.db import models
from django.conf import settings


class EscalationRule(models.Model):
    class Trigger(models.TextChoices):
        RESPONSE_BREACH    = 'RESPONSE_BREACH',   'Breach délai de réponse'
        RESOLUTION_BREACH  = 'RESOLUTION_BREACH', 'Breach délai de résolution'
        PRIORITY_CHANGE    = 'PRIORITY_CHANGE',   'Changement de priorité P1/P2'
        UNASSIGNED_TIMEOUT = 'UNASSIGNED_TIMEOUT','Non assigné après délai'

    class NotifyVia(models.TextChoices):
        EMAIL  = 'EMAIL',  'Email'
        IN_APP = 'IN_APP', 'Notification in-app'
        BOTH   = 'BOTH',   'Email + In-app'

    name       = models.CharField(max_length=100)
    trigger    = models.CharField(max_length=30, choices=Trigger.choices)
    priority   = models.CharField(max_length=2, blank=True, help_text='Laisser vide = toutes priorités')
    target     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='escalation_targets', verbose_name='Destinataire escalade'
    )
    notify_via = models.CharField(max_length=10, choices=NotifyVia.choices, default=NotifyVia.BOTH)
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Règle d\'escalade'
        verbose_name_plural = 'Règles d\'escalade'

    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()})"


class EscalationEvent(models.Model):
    """Historique immuable de chaque escalade déclenchée."""
    ticket     = models.ForeignKey('tickets.Ticket', on_delete=models.CASCADE, related_name='escalations')
    rule       = models.ForeignKey(EscalationRule, null=True, on_delete=models.SET_NULL)
    trigger    = models.CharField(max_length=30)
    notified   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='received_escalations'
    )
    message    = models.TextField()
    sent_at    = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Événement d\'escalade'
        verbose_name_plural = 'Événements d\'escalade'
        ordering = ['-sent_at']

    def __str__(self):
        return f"Escalade {self.ticket.reference} → {self.notified}"
