from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Journal d'audit immuable — hérité de DSI Diligences.
    Aucune mise à jour ou suppression permise (save() bloqué après création).
    """
    class Action(models.TextChoices):
        CREATE          = 'CREATE',          'Création'
        UPDATE          = 'UPDATE',          'Modification'
        DELETE          = 'DELETE',          'Suppression'
        STATUS_CHANGE   = 'STATUS_CHANGE',   'Changement de statut'
        ASSIGN          = 'ASSIGN',          'Assignation'
        ESCALATE        = 'ESCALATE',        'Escalade'
        SLA_BREACH      = 'SLA_BREACH',      'Breach SLA'
        COMMENT         = 'COMMENT',         'Commentaire'
        LOGIN           = 'LOGIN',           'Connexion'
        LOGOUT          = 'LOGOUT',          'Déconnexion'

    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='audit_logs'
    )
    action         = models.CharField(max_length=20, choices=Action.choices)
    content_type   = models.CharField(max_length=100, blank=True)
    object_id      = models.CharField(max_length=50, blank=True)
    object_repr    = models.CharField(max_length=255, blank=True)
    changes        = models.JSONField(default=dict, blank=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    user_agent     = models.CharField(max_length=255, blank=True)
    timestamp      = models.DateTimeField(auto_now_add=True)
    extra          = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Log d\'audit'
        verbose_name_plural = 'Logs d\'audit'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} — {self.action} {self.object_repr}"

    def save(self, *args, **kwargs):
        """Immuable : interdit toute modification après création."""
        if self.pk:
            raise PermissionError("AuditLog est immuable — aucune modification autorisée.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("AuditLog est immuable — aucune suppression autorisée.")
