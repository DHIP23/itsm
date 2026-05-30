from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings

from tickets.models import Ticket, TicketComment
from sla.models import SLAPolicy, SLATracker
from audit.models import AuditLog
from notifications.models import Notification


# ── Mémoire des états précédents ─────────────────────────────────
_ticket_prev = {}


@receiver(pre_save, sender=Ticket)
def ticket_pre_save(sender, instance, **kwargs):
    """Mémorise l'état précédent pour comparaison dans post_save."""
    if instance.pk:
        try:
            old = Ticket.objects.get(pk=instance.pk)
            _ticket_prev[instance.pk] = {
                'status': old.status,
                'priority': old.priority,
                'assignee_id': old.assignee_id,
            }
        except Ticket.DoesNotExist:
            pass


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    """
    À la création : génère le SLATracker.
    À la modification : audit des changements + notifications.
    """
    if created:
        _create_sla_tracker(instance)
        AuditLog.objects.create(
            action=AuditLog.Action.CREATE,
            content_type='tickets.Ticket',
            object_id=str(instance.pk),
            object_repr=str(instance),
            extra={'reference': instance.reference, 'type': instance.type},
        )
        return

    prev = _ticket_prev.pop(instance.pk, {})
    changes = {}

    # Changement de statut
    if prev.get('status') != instance.status:
        changes['status'] = {'from': prev.get('status'), 'to': instance.status}
        AuditLog.objects.create(
            action=AuditLog.Action.STATUS_CHANGE,
            content_type='tickets.Ticket',
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes=changes,
        )
        # Notifier le demandeur
        Notification.objects.create(
            recipient=instance.requester,
            ticket=instance,
            type=Notification.Type.STATUS_CHANGE,
            message=f"Votre ticket {instance.reference} est passé au statut : {instance.get_status_display()}",
        )
        # Pause / reprise SLA
        _handle_sla_pause(instance, prev.get('status'))

    # Changement d'assignation
    if prev.get('assignee_id') != instance.assignee_id and instance.assignee:
        AuditLog.objects.create(
            action=AuditLog.Action.ASSIGN,
            content_type='tickets.Ticket',
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes={'assignee': {'from': prev.get('assignee_id'), 'to': instance.assignee_id}},
        )
        Notification.objects.create(
            recipient=instance.assignee,
            ticket=instance,
            type=Notification.Type.ASSIGNED,
            message=f"Le ticket {instance.reference} vous a été assigné.",
        )
        # Enregistre la 1ère réponse SLA si pas encore fait
        _record_first_response(instance)

    # Changement de priorité
    if prev.get('priority') != instance.priority:
        AuditLog.objects.create(
            action=AuditLog.Action.UPDATE,
            content_type='tickets.Ticket',
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes={'priority': {'from': prev.get('priority'), 'to': instance.priority}},
        )
        # Recalcule le SLA si la priorité change
        _recalculate_sla(instance)


@receiver(post_save, sender=TicketComment)
def comment_post_save(sender, instance, created, **kwargs):
    """Audit + notification + 1ère réponse SLA sur 1er commentaire agent."""
    if not created:
        return
    AuditLog.objects.create(
        action=AuditLog.Action.COMMENT,
        content_type='tickets.TicketComment',
        object_id=str(instance.pk),
        object_repr=f"Commentaire sur {instance.ticket.reference}",
    )
    # Notifier le demandeur si commentaire public d'un agent
    if (
        instance.visibility == 'PUBLIC'
        and instance.author != instance.ticket.requester
    ):
        Notification.objects.create(
            recipient=instance.ticket.requester,
            ticket=instance.ticket,
            type=Notification.Type.COMMENT,
            message=f"Nouveau commentaire sur votre ticket {instance.ticket.reference}.",
        )
    # Enregistre 1ère réponse SLA
    _record_first_response(instance.ticket, actor=instance.author)


# ── Helpers SLA ──────────────────────────────────────────────────

def _create_sla_tracker(ticket):
    try:
        policy = SLAPolicy.objects.get(priority=ticket.priority, is_active=True)
    except SLAPolicy.DoesNotExist:
        policy = None
    now = timezone.now()
    tracker = SLATracker.objects.create(
        ticket=ticket,
        policy=policy,
        response_due=now + timezone.timedelta(minutes=policy.response_time) if policy else None,
        resolution_due=now + timezone.timedelta(minutes=policy.resolution_time) if policy else None,
    )
    return tracker


def _recalculate_sla(ticket):
    try:
        tracker = ticket.sla_tracker
        policy = SLAPolicy.objects.get(priority=ticket.priority, is_active=True)
        tracker.policy = policy
        now = timezone.now()
        if not tracker.first_response_at:
            tracker.response_due = ticket.created_at + timezone.timedelta(minutes=policy.response_time)
        tracker.resolution_due = ticket.created_at + timezone.timedelta(minutes=policy.resolution_time)
        tracker.save()
    except (SLATracker.DoesNotExist, SLAPolicy.DoesNotExist):
        pass


def _record_first_response(ticket, actor=None):
    try:
        tracker = ticket.sla_tracker
        if not tracker.first_response_at:
            tracker.first_response_at = timezone.now()
            tracker.save(update_fields=['first_response_at', 'updated_at'])
    except SLATracker.DoesNotExist:
        pass


def _handle_sla_pause(ticket, old_status):
    """Pause le SLA quand PENDING, reprend sinon."""
    try:
        tracker = ticket.sla_tracker
        if ticket.status == 'PENDING' and not tracker.paused_at:
            tracker.paused_at = timezone.now()
            tracker.save(update_fields=['paused_at', 'updated_at'])
        elif old_status == 'PENDING' and tracker.paused_at:
            # Calcule la durée de pause et l'ajoute au total
            paused_minutes = int((timezone.now() - tracker.paused_at).total_seconds() / 60)
            tracker.total_paused_minutes += paused_minutes
            # Décale les échéances
            delta = timezone.timedelta(minutes=paused_minutes)
            if tracker.response_due:
                tracker.response_due += delta
            if tracker.resolution_due:
                tracker.resolution_due += delta
            tracker.paused_at = None
            tracker.save()
    except SLATracker.DoesNotExist:
        pass
