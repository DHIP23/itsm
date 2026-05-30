"""
Management command : check_sla_breaches
Usage : python manage.py check_sla_breaches
Planifier via cron (toutes les 5 minutes) :
    */5 * * * * /path/to/.venv/bin/python /path/to/manage.py check_sla_breaches
Ou via celery beat si Celery est configuré.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from sla.models import SLATracker
from audit.models import AuditLog
from notifications.models import Notification
from escalation.models import EscalationRule, EscalationEvent


class Command(BaseCommand):
    help = 'Vérifie les breaches SLA et déclenche les escalades automatiques.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Affiche les breaches sans modifier la base ni envoyer de notifications.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        checked = 0
        breached_new = 0
        escalated = 0

        self.stdout.write(f"\n[{now:%Y-%m-%d %H:%M:%S}] Vérification SLA{' (DRY RUN)' if dry_run else ''}...")

        # Tickets encore ouverts avec un tracker SLA
        trackers = SLATracker.objects.select_related(
            'ticket', 'ticket__assignee', 'ticket__requester', 'policy'
        ).filter(
            ticket__status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING', 'REOPENED']
        )

        for tracker in trackers:
            checked += 1
            ticket = tracker.ticket
            changed = False

            # ── Breach réponse ────────────────────────────────────
            if (
                tracker.response_due
                and not tracker.response_breached
                and not tracker.first_response_at
                and now > tracker.response_due
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ BREACH RÉPONSE : {ticket.reference} | {ticket.get_priority_display()} | "
                        f"Échéance : {tracker.response_due:%H:%M}"
                    )
                )
                if not dry_run:
                    tracker.response_breached = True
                    changed = True
                    # Audit
                    AuditLog.objects.create(
                        action=AuditLog.Action.SLA_BREACH,
                        content_type='tickets.Ticket',
                        object_id=str(ticket.pk),
                        object_repr=str(ticket),
                        changes={'breach_type': 'response', 'priority': ticket.priority},
                    )
                    # Escalade
                    escalated += self._trigger_escalation(
                        ticket, EscalationRule.Trigger.RESPONSE_BREACH
                    )
                breached_new += 1

            # ── Breach résolution ─────────────────────────────────
            if (
                tracker.resolution_due
                and not tracker.resolution_breached
                and not ticket.resolved_at
                and now > tracker.resolution_due
            ):
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ BREACH RÉSOLUTION : {ticket.reference} | {ticket.get_priority_display()} | "
                        f"Échéance : {tracker.resolution_due:%H:%M} | "
                        f"Agent : {ticket.assignee or 'Non assigné'}"
                    )
                )
                if not dry_run:
                    tracker.resolution_breached = True
                    changed = True
                    AuditLog.objects.create(
                        action=AuditLog.Action.SLA_BREACH,
                        content_type='tickets.Ticket',
                        object_id=str(ticket.pk),
                        object_repr=str(ticket),
                        changes={'breach_type': 'resolution', 'priority': ticket.priority},
                    )
                    escalated += self._trigger_escalation(
                        ticket, EscalationRule.Trigger.RESOLUTION_BREACH
                    )
                breached_new += 1

            # ── Warning à 80% du délai (alerte préventive) ───────
            if (
                tracker.resolution_due
                and not tracker.resolution_breached
                and not ticket.resolved_at
                and tracker.policy
            ):
                total_minutes = tracker.policy.resolution_time
                elapsed = (now - ticket.created_at).total_seconds() / 60 - tracker.total_paused_minutes
                pct = elapsed / total_minutes * 100 if total_minutes else 0
                if 80 <= pct < 100:
                    rem = tracker.resolution_remaining_minutes
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚡ ALERTE 80% : {ticket.reference} — {rem}min restantes"
                        )
                    )
                    if not dry_run and ticket.assignee:
                        # Notif in-app si pas déjà envoyée récemment
                        recent = Notification.objects.filter(
                            ticket=ticket,
                            type=Notification.Type.SLA_WARNING,
                            created_at__gte=now - timezone.timedelta(minutes=30)
                        ).exists()
                        if not recent:
                            Notification.objects.create(
                                recipient=ticket.assignee,
                                ticket=ticket,
                                type=Notification.Type.SLA_WARNING,
                                message=(
                                    f"Alerte SLA : le ticket {ticket.reference} atteint 80% "
                                    f"de son délai de résolution ({rem}min restantes)."
                                ),
                            )

            if changed and not dry_run:
                tracker.save(update_fields=['response_breached', 'resolution_breached', 'updated_at'])

        # ── Rapport final ─────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(f"  Trackers vérifiés  : {checked}")
        self.stdout.write(
            self.style.ERROR(f"  Nouveaux breaches  : {breached_new}") if breached_new
            else self.style.SUCCESS(f"  Nouveaux breaches  : {breached_new}")
        )
        self.stdout.write(f"  Escalades envoyées : {escalated}")
        self.stdout.write("─" * 50 + "\n")

    def _trigger_escalation(self, ticket, trigger_type):
        """Déclenche les règles d'escalade correspondantes. Retourne le nombre d'escalades créées."""
        rules = EscalationRule.objects.filter(
            trigger=trigger_type,
            is_active=True,
        ).filter(
            # Filtre par priorité si spécifiée dans la règle
            priority__in=['', ticket.priority]
        ).select_related('target')

        count = 0
        for rule in rules:
            # Évite les doublons : pas d'escalade identique dans les 30 dernières minutes
            recent = EscalationEvent.objects.filter(
                ticket=ticket,
                rule=rule,
                sent_at__gte=timezone.now() - timezone.timedelta(minutes=30)
            ).exists()
            if recent:
                continue

            message = (
                f"[DSI ITSM] Escalade — {rule.get_trigger_display()}\n"
                f"Ticket : {ticket.reference} — {ticket.title}\n"
                f"Priorité : {ticket.get_priority_display()}\n"
                f"Statut : {ticket.get_status_display()}\n"
                f"Agent : {ticket.assignee or 'Non assigné'}\n"
                f"Demandeur : {ticket.requester}\n"
            )

            event = EscalationEvent.objects.create(
                ticket=ticket,
                rule=rule,
                trigger=trigger_type,
                notified=rule.target,
                message=message,
            )

            # Notification in-app
            if rule.notify_via in ('IN_APP', 'BOTH'):
                Notification.objects.create(
                    recipient=rule.target,
                    ticket=ticket,
                    type=Notification.Type.ESCALATION,
                    message=f"Escalade SLA — {ticket.reference} : {rule.get_trigger_display()}",
                )

            # Email
            if rule.notify_via in ('EMAIL', 'BOTH'):
                try:
                    send_mail(
                        subject=f"[ITSM] Escalade SLA — {ticket.reference}",
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[rule.target.email],
                        fail_silently=False,
                    )
                    event.email_sent = True
                    event.save(update_fields=['email_sent'])
                except Exception as e:
                    self.stderr.write(f"Email non envoyé pour {ticket.reference}: {e}")

            # Audit
            AuditLog.objects.create(
                action=AuditLog.Action.ESCALATE,
                content_type='tickets.Ticket',
                object_id=str(ticket.pk),
                object_repr=str(ticket),
                changes={
                    'escalation_rule': rule.name,
                    'notified': str(rule.target),
                    'trigger': trigger_type,
                },
            )

            count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"    → Escalade déclenchée : {rule.name} → {rule.target}"
                )
            )

        return count
