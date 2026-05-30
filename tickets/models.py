from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime


def generate_reference(ticket_type):
    """Génère INC-YYYY-NNNN ou REQ-YYYY-NNNN (même pattern que DLG-YYYY-NNNN)."""
    year = timezone.now().year
    prefix = ticket_type  # 'INC' ou 'REQ'
    last = (
        Ticket.objects.filter(type=ticket_type, reference__startswith=f"{prefix}-{year}-")
        .order_by('reference')
        .last()
    )
    if last:
        try:
            seq = int(last.reference.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}-{year}-{seq:04d}"


class Category(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent      = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Type(models.TextChoices):
        INCIDENT = 'INC', 'Incident'
        REQUEST  = 'REQ', 'Demande de service'

    class Status(models.TextChoices):
        NEW         = 'NEW',         'Nouveau'
        ASSIGNED    = 'ASSIGNED',    'Assigné'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        PENDING     = 'PENDING',     'En attente'
        RESOLVED    = 'RESOLVED',    'Résolu'
        CLOSED      = 'CLOSED',      'Clôturé'
        REOPENED    = 'REOPENED',    'Réouvert'

    class Priority(models.TextChoices):
        P1 = 'P1', 'P1 — Critique'
        P2 = 'P2', 'P2 — Élevée'
        P3 = 'P3', 'P3 — Normale'
        P4 = 'P4', 'P4 — Basse'

    class Source(models.TextChoices):
        PORTAL = 'PORTAL', 'Portail'
        EMAIL  = 'EMAIL',  'Email'
        PHONE  = 'PHONE',  'Téléphone'
        AGENT  = 'AGENT',  'Agent (saisie directe)'

    # ── Identité ─────────────────────────────────────────────────
    reference   = models.CharField(max_length=20, unique=True, editable=False)
    type        = models.CharField(max_length=3, choices=Type.choices, default=Type.INCIDENT)
    title       = models.CharField(max_length=255, verbose_name='Titre')
    description = models.TextField(verbose_name='Description')

    # ── Classification ────────────────────────────────────────────
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    priority    = models.CharField(max_length=2, choices=Priority.choices, default=Priority.P3)
    category    = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    source      = models.CharField(max_length=10, choices=Source.choices, default=Source.PORTAL)
    tags        = models.CharField(max_length=255, blank=True, help_text='Séparés par des virgules')

    # ── Acteurs ───────────────────────────────────────────────────
    requester   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='submitted_tickets', verbose_name='Demandeur'
    )
    assignee    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_tickets', verbose_name='Agent assigné'
    )

    # ── Timestamps ────────────────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at   = models.DateTimeField(null=True, blank=True)

    # ── Résolution ────────────────────────────────────────────────
    resolution_note = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference(self.type)
        # Horodatage résolution / clôture
        if self.status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status == self.Status.CLOSED and not self.closed_at:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────
    @property
    def is_open(self):
        return self.status not in (self.Status.RESOLVED, self.Status.CLOSED)

    @property
    def priority_color(self):
        return {'P1': 'danger', 'P2': 'warning', 'P3': 'primary', 'P4': 'secondary'}[self.priority]

    @property
    def status_color(self):
        mapping = {
            'NEW': 'secondary', 'ASSIGNED': 'info', 'IN_PROGRESS': 'primary',
            'PENDING': 'warning', 'RESOLVED': 'success', 'CLOSED': 'dark', 'REOPENED': 'danger',
        }
        return mapping.get(self.status, 'secondary')

    @property
    def age_hours(self):
        delta = timezone.now() - self.created_at
        return round(delta.total_seconds() / 3600, 1)

    @property
    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]


class TicketComment(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC   = 'PUBLIC',   'Visible par le demandeur'
        INTERNAL = 'INTERNAL', 'Interne (agents seulement)'

    ticket     = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    content    = models.TextField()
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.ticket.reference}"


class TicketAttachment(models.Model):
    ticket     = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file       = models.FileField(upload_to='tickets/attachments/%Y/%m/')
    filename   = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename
