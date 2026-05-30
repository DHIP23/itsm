from django.db import models
from django.utils import timezone
import datetime


class SLAPolicy(models.Model):
    """Politique SLA par priorité — configurée via admin."""
    class Priority(models.TextChoices):
        P1 = 'P1', 'P1 — Critique'
        P2 = 'P2', 'P2 — Élevée'
        P3 = 'P3', 'P3 — Normale'
        P4 = 'P4', 'P4 — Basse'

    priority         = models.CharField(max_length=2, choices=Priority.choices, unique=True)
    response_time    = models.PositiveIntegerField(help_text='Délai de 1ère réponse (minutes)')
    resolution_time  = models.PositiveIntegerField(help_text='Délai de résolution (minutes)')
    business_hours   = models.BooleanField(default=True, help_text='Calculer en heures ouvrées seulement')
    is_active        = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Politique SLA'
        verbose_name_plural = 'Politiques SLA'
        ordering = ['priority']

    def __str__(self):
        return f"SLA {self.priority} — Réponse: {self.response_time}min / Résolution: {self.resolution_time}min"


class SLATracker(models.Model):
    """Suivi SLA en temps réel pour chaque ticket. Créé automatiquement via signal."""
    ticket               = models.OneToOneField('tickets.Ticket', on_delete=models.CASCADE, related_name='sla_tracker')
    policy               = models.ForeignKey(SLAPolicy, null=True, on_delete=models.SET_NULL)

    # Dates d'échéance
    response_due         = models.DateTimeField(null=True, blank=True)
    resolution_due       = models.DateTimeField(null=True, blank=True)

    # Horodatage réelle de 1ère réponse
    first_response_at    = models.DateTimeField(null=True, blank=True)

    # Flags de breach (mis à jour par tâche périodique ou signal)
    response_breached    = models.BooleanField(default=False)
    resolution_breached  = models.BooleanField(default=False)

    # Pause SLA quand ticket en PENDING
    paused_at            = models.DateTimeField(null=True, blank=True)
    total_paused_minutes = models.PositiveIntegerField(default=0)

    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Suivi SLA'
        verbose_name_plural = 'Suivis SLA'

    def __str__(self):
        return f"SLA Tracker — {self.ticket.reference}"

    def check_breaches(self):
        """Vérifie et met à jour les flags de breach. Appelé par la tâche périodique."""
        now = timezone.now()
        changed = False
        if self.response_due and not self.response_breached:
            if not self.first_response_at and now > self.response_due:
                self.response_breached = True
                changed = True
        if self.resolution_due and not self.resolution_breached:
            if not self.ticket.resolved_at and now > self.resolution_due:
                self.resolution_breached = True
                changed = True
        if changed:
            self.save(update_fields=['response_breached', 'resolution_breached', 'updated_at'])
        return changed

    @property
    def response_remaining_minutes(self):
        if not self.response_due or self.first_response_at:
            return None
        delta = self.response_due - timezone.now()
        return max(0, int(delta.total_seconds() / 60))

    @property
    def resolution_remaining_minutes(self):
        if not self.resolution_due or self.ticket.resolved_at:
            return None
        delta = self.resolution_due - timezone.now()
        return max(0, int(delta.total_seconds() / 60))

    @property
    def response_sla_percent(self):
        """Pourcentage du délai de réponse écoulé (0–100+)."""
        if not self.response_due or not self.policy:
            return 0
        total = self.policy.response_time
        elapsed = total - (self.response_remaining_minutes or 0)
        return min(round(elapsed / total * 100), 100) if total else 0

    @property
    def resolution_sla_percent(self):
        if not self.resolution_due or not self.policy:
            return 0
        total = self.policy.resolution_time
        elapsed = total - (self.resolution_remaining_minutes or 0)
        return min(round(elapsed / total * 100), 100) if total else 0
