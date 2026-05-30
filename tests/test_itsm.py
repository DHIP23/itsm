"""
Tests unitaires DSI ITSM
Couverture : US-IT01 à US-IT07

Lancer : python manage.py test tickets sla escalation notifications audit
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
import datetime

from tickets.models import Ticket, TicketComment, Category
from sla.models import SLAPolicy, SLATracker
from escalation.models import EscalationRule, EscalationEvent
from notifications.models import Notification
from audit.models import AuditLog

User = get_user_model()


# ══════════════════════════════════════════════════════════════════
# Fixtures partagées
# ══════════════════════════════════════════════════════════════════

class BaseITSMTest(TestCase):
    """Classe de base avec utilisateurs et données SLA préconfigurés."""

    @classmethod
    def setUpTestData(cls):
        # Utilisateurs
        cls.admin = User.objects.create_user(
            username='admin_test', password='pass1234!',
            role='ADMIN', first_name='Admin', last_name='DSI'
        )
        cls.manager = User.objects.create_user(
            username='manager_test', password='pass1234!',
            role='MANAGER', first_name='Marie', last_name='Manager'
        )
        cls.agent = User.objects.create_user(
            username='agent_test', password='pass1234!',
            role='AGENT', first_name='Alex', last_name='Agent'
        )
        cls.l2_agent = User.objects.create_user(
            username='l2_test', password='pass1234!',
            role='L2_AGENT', first_name='Laura', last_name='Expert'
        )
        cls.requester = User.objects.create_user(
            username='requester_test', password='pass1234!',
            role='REQUESTER', first_name='René', last_name='Requester'
        )

        # Catégorie
        cls.category = Category.objects.create(name='Réseau', is_active=True)

        # Politiques SLA
        SLAPolicy.objects.bulk_create([
            SLAPolicy(priority='P1', response_time=15,  resolution_time=240,  business_hours=False),
            SLAPolicy(priority='P2', response_time=60,  resolution_time=480,  business_hours=True),
            SLAPolicy(priority='P3', response_time=240, resolution_time=1440, business_hours=True),
            SLAPolicy(priority='P4', response_time=480, resolution_time=4320, business_hours=True),
        ])


# ══════════════════════════════════════════════════════════════════
# US-IT01 — Soumission ticket via portail
# ══════════════════════════════════════════════════════════════════

class TicketCreateTestCase(BaseITSMTest):

    def setUp(self):
        self.client = Client()

    def test_us_it01_requester_can_create_ticket(self):
        """US-IT01 : un REQUESTER peut soumettre un ticket via le portail."""
        self.client.login(username='requester_test', password='pass1234!')
        response = self.client.post(reverse('tickets:create'), {
            'type': 'INC',
            'title': 'Impossible de se connecter au VPN',
            'description': 'Depuis ce matin, le VPN refuse ma connexion.',
            'priority': 'P3',
            'source': 'PORTAL',
        })
        self.assertEqual(Ticket.objects.count(), 1)
        ticket = Ticket.objects.first()
        self.assertEqual(ticket.requester, self.requester)
        self.assertEqual(ticket.status, Ticket.Status.NEW)
        self.assertRedirects(response, reverse('tickets:detail', args=[ticket.pk]))

    def test_us_it01_reference_auto_generated(self):
        """US-IT01 : la référence INC-YYYY-NNNN est générée automatiquement."""
        self.client.login(username='requester_test', password='pass1234!')
        self.client.post(reverse('tickets:create'), {
            'type': 'INC', 'title': 'Test référence',
            'description': 'Description test.', 'priority': 'P2', 'source': 'PORTAL',
        })
        ticket = Ticket.objects.first()
        year = timezone.now().year
        self.assertTrue(ticket.reference.startswith(f'INC-{year}-'))
        self.assertEqual(len(ticket.reference.split('-')), 3)

    def test_us_it01_req_reference_prefix(self):
        """US-IT01 : une demande de service reçoit le préfixe REQ."""
        self.client.login(username='requester_test', password='pass1234!')
        self.client.post(reverse('tickets:create'), {
            'type': 'REQ', 'title': 'Demande accès serveur',
            'description': 'Besoin accès SSH serveur prod.', 'priority': 'P3', 'source': 'PORTAL',
        })
        ticket = Ticket.objects.first()
        self.assertTrue(ticket.reference.startswith('REQ-'))

    def test_us_it01_references_sequential(self):
        """US-IT01 : les références sont séquentielles dans la même année."""
        self.client.login(username='requester_test', password='pass1234!')
        for i in range(3):
            self.client.post(reverse('tickets:create'), {
                'type': 'INC', 'title': f'Ticket {i}',
                'description': 'Test.', 'priority': 'P3', 'source': 'PORTAL',
            })
        refs = list(Ticket.objects.order_by('created_at').values_list('reference', flat=True))
        year = timezone.now().year
        self.assertEqual(refs[0], f'INC-{year}-0001')
        self.assertEqual(refs[1], f'INC-{year}-0002')
        self.assertEqual(refs[2], f'INC-{year}-0003')

    def test_us_it01_unauthenticated_redirect(self):
        """US-IT01 : un utilisateur non connecté est redirigé vers login."""
        response = self.client.get(reverse('tickets:create'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('tickets:create')}")

    def test_us_it01_sla_tracker_created_on_ticket_creation(self):
        """US-IT01 : un SLATracker est créé automatiquement à la création du ticket."""
        self.client.login(username='requester_test', password='pass1234!')
        self.client.post(reverse('tickets:create'), {
            'type': 'INC', 'title': 'SLA auto test',
            'description': 'Vérification création SLATracker.', 'priority': 'P1', 'source': 'PORTAL',
        })
        ticket = Ticket.objects.first()
        self.assertTrue(hasattr(ticket, 'sla_tracker'))
        self.assertIsNotNone(ticket.sla_tracker.response_due)
        self.assertIsNotNone(ticket.sla_tracker.resolution_due)

    def test_us_it01_audit_log_created(self):
        """US-IT01 : un AuditLog de création est enregistré automatiquement."""
        self.client.login(username='requester_test', password='pass1234!')
        self.client.post(reverse('tickets:create'), {
            'type': 'INC', 'title': 'Audit test',
            'description': 'Test audit.', 'priority': 'P3', 'source': 'PORTAL',
        })
        self.assertTrue(AuditLog.objects.filter(action='CREATE', content_type='tickets.Ticket').exists())


# ══════════════════════════════════════════════════════════════════
# US-IT02 — Agent voit ses tickets assignés avec priorité
# ══════════════════════════════════════════════════════════════════

class TicketListAgentTestCase(BaseITSMTest):

    def setUp(self):
        self.client = Client()
        # Créer des tickets assignés et non assignés
        self.ticket_assigned = Ticket.objects.create(
            type='INC', title='Ticket assigné à agent',
            description='Test.', priority='P2',
            requester=self.requester, assignee=self.agent,
            status='ASSIGNED', source='PORTAL'
        )
        self.ticket_other = Ticket.objects.create(
            type='INC', title='Ticket assigné à autre',
            description='Test.', priority='P3',
            requester=self.requester, assignee=self.l2_agent,
            status='ASSIGNED', source='PORTAL'
        )
        self.ticket_unassigned = Ticket.objects.create(
            type='REQ', title='Ticket non assigné',
            description='Test.', priority='P4',
            requester=self.requester, status='NEW', source='PORTAL'
        )

    def test_us_it02_agent_sees_only_own_tickets(self):
        """US-IT02 : l'agent ne voit que ses tickets assignés."""
        self.client.login(username='agent_test', password='pass1234!')
        response = self.client.get(reverse('tickets:list'))
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context['page_obj'])
        self.assertIn(self.ticket_assigned, tickets)
        self.assertNotIn(self.ticket_other, tickets)
        self.assertNotIn(self.ticket_unassigned, tickets)

    def test_us_it02_manager_sees_all_tickets(self):
        """US-IT02 : le manager voit tous les tickets."""
        self.client.login(username='manager_test', password='pass1234!')
        response = self.client.get(reverse('tickets:list'))
        tickets = list(response.context['page_obj'])
        self.assertGreaterEqual(len(tickets), 3)

    def test_us_it02_requester_sees_only_own_tickets(self):
        """US-IT02 : le REQUESTER ne voit que ses propres tickets."""
        other_requester = User.objects.create_user(
            username='other_req', password='pass1234!', role='REQUESTER'
        )
        Ticket.objects.create(
            type='INC', title='Autre utilisateur', description='Test.',
            priority='P3', requester=other_requester, status='NEW', source='PORTAL'
        )
        self.client.login(username='requester_test', password='pass1234!')
        response = self.client.get(reverse('tickets:list'))
        for t in response.context['page_obj']:
            self.assertEqual(t.requester, self.requester)

    def test_us_it02_filter_by_priority(self):
        """US-IT02 : le filtre par priorité fonctionne."""
        self.client.login(username='manager_test', password='pass1234!')
        response = self.client.get(reverse('tickets:list') + '?priority=P2')
        for t in response.context['page_obj']:
            self.assertEqual(t.priority, 'P2')

    def test_us_it02_filter_by_status(self):
        """US-IT02 : le filtre par statut fonctionne."""
        self.client.login(username='manager_test', password='pass1234!')
        response = self.client.get(reverse('tickets:list') + '?status=NEW')
        for t in response.context['page_obj']:
            self.assertEqual(t.status, 'NEW')


# ══════════════════════════════════════════════════════════════════
# US-IT03 — Agent change le statut d'un ticket
# ══════════════════════════════════════════════════════════════════

class TicketStatusChangeTestCase(BaseITSMTest):

    def setUp(self):
        self.client = Client()
        self.ticket = Ticket.objects.create(
            type='INC', title='Test statut',
            description='Test.', priority='P2',
            requester=self.requester, assignee=self.agent,
            status='ASSIGNED', source='PORTAL'
        )

    def test_us_it03_agent_can_change_status(self):
        """US-IT03 : l'agent peut changer le statut."""
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:update_status', args=[self.ticket.pk]),
            {'status': 'IN_PROGRESS'}
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'IN_PROGRESS')

    def test_us_it03_status_change_creates_audit_log(self):
        """US-IT03 : le changement de statut crée un AuditLog."""
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:update_status', args=[self.ticket.pk]),
            {'status': 'IN_PROGRESS'}
        )
        self.assertTrue(AuditLog.objects.filter(
            action='STATUS_CHANGE',
            object_id=str(self.ticket.pk)
        ).exists())

    def test_us_it03_status_change_notifies_requester(self):
        """US-IT03 : le changement de statut notifie le demandeur."""
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:update_status', args=[self.ticket.pk]),
            {'status': 'RESOLVED', 'resolution_note': 'Problème résolu.'}
        )
        self.assertTrue(Notification.objects.filter(
            recipient=self.requester,
            ticket=self.ticket,
            type='STATUS_CHANGE'
        ).exists())

    def test_us_it03_resolved_sets_resolved_at(self):
        """US-IT03 : passer en RESOLVED horodate resolved_at."""
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:update_status', args=[self.ticket.pk]),
            {'status': 'RESOLVED', 'resolution_note': 'Résolu.'}
        )
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.resolved_at)

    def test_us_it03_requester_cannot_change_status(self):
        """US-IT03 : un REQUESTER ne peut pas changer le statut."""
        self.client.login(username='requester_test', password='pass1234!')
        self.client.post(
            reverse('tickets:update_status', args=[self.ticket.pk]),
            {'status': 'CLOSED'}
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'ASSIGNED')  # inchangé


# ══════════════════════════════════════════════════════════════════
# US-IT05 — Admin configure les politiques SLA
# ══════════════════════════════════════════════════════════════════

class SLAPolicyTestCase(BaseITSMTest):

    def test_us_it05_sla_policies_exist(self):
        """US-IT05 : les 4 politiques SLA P1-P4 existent."""
        for priority in ('P1', 'P2', 'P3', 'P4'):
            self.assertTrue(SLAPolicy.objects.filter(priority=priority, is_active=True).exists())

    def test_us_it05_sla_tracker_uses_correct_policy(self):
        """US-IT05 : le SLATracker utilise la politique correspondant à la priorité du ticket."""
        ticket = Ticket.objects.create(
            type='INC', title='SLA policy test', description='Test.',
            priority='P1', requester=self.requester, status='NEW', source='PORTAL'
        )
        tracker = ticket.sla_tracker
        self.assertEqual(tracker.policy.priority, 'P1')
        policy = SLAPolicy.objects.get(priority='P1')
        expected_response_due = ticket.created_at + timezone.timedelta(minutes=policy.response_time)
        diff = abs((tracker.response_due - expected_response_due).total_seconds())
        self.assertLess(diff, 5)  # moins de 5 secondes d'écart

    def test_us_it05_sla_due_dates_computed_correctly(self):
        """US-IT05 : les dates d'échéance SLA sont correctement calculées."""
        ticket = Ticket.objects.create(
            type='INC', title='SLA dates test', description='Test.',
            priority='P2', requester=self.requester, status='NEW', source='PORTAL'
        )
        tracker = ticket.sla_tracker
        policy = SLAPolicy.objects.get(priority='P2')
        self.assertIsNotNone(tracker.response_due)
        self.assertIsNotNone(tracker.resolution_due)
        # Résolution = création + 480 min pour P2
        expected_res = ticket.created_at + timezone.timedelta(minutes=policy.resolution_time)
        diff = abs((tracker.resolution_due - expected_res).total_seconds())
        self.assertLess(diff, 5)


# ══════════════════════════════════════════════════════════════════
# US-IT06 — Escalade automatique sur breach
# ══════════════════════════════════════════════════════════════════

class EscalationTestCase(BaseITSMTest):

    def setUp(self):
        self.rule = EscalationRule.objects.create(
            name='Escalade breach résolution',
            trigger=EscalationRule.Trigger.RESOLUTION_BREACH,
            target=self.manager,
            notify_via=EscalationRule.NotifyVia.IN_APP,
            is_active=True,
        )

    def test_us_it06_escalation_rule_created(self):
        """US-IT06 : la règle d'escalade est créée correctement."""
        self.assertEqual(EscalationRule.objects.filter(is_active=True).count(), 1)
        self.assertEqual(self.rule.target, self.manager)

    def test_us_it06_check_sla_command_detects_breach(self):
        """US-IT06 : la commande check_sla_breaches détecte et marque les breaches."""
        from django.core.management import call_command
        from io import StringIO

        # Créer un ticket P1 avec SLA expiré
        ticket = Ticket.objects.create(
            type='INC', title='Breach test', description='Test.',
            priority='P1', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        # Forcer l'échéance dans le passé
        tracker = ticket.sla_tracker
        tracker.resolution_due = timezone.now() - timezone.timedelta(hours=1)
        tracker.save()

        out = StringIO()
        call_command('check_sla_breaches', stdout=out)

        tracker.refresh_from_db()
        self.assertTrue(tracker.resolution_breached)

    def test_us_it06_escalation_event_created_on_breach(self):
        """US-IT06 : un EscalationEvent est créé lors d'un breach."""
        from django.core.management import call_command
        from io import StringIO

        ticket = Ticket.objects.create(
            type='INC', title='Escalade event test', description='Test.',
            priority='P1', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        tracker = ticket.sla_tracker
        tracker.resolution_due = timezone.now() - timezone.timedelta(hours=2)
        tracker.save()

        call_command('check_sla_breaches', stdout=StringIO())
        self.assertTrue(EscalationEvent.objects.filter(ticket=ticket).exists())

    def test_us_it06_escalation_notifies_manager(self):
        """US-IT06 : l'escalade crée une notification in-app pour le manager."""
        from django.core.management import call_command
        from io import StringIO

        ticket = Ticket.objects.create(
            type='INC', title='Notif escalade test', description='Test.',
            priority='P1', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        tracker = ticket.sla_tracker
        tracker.resolution_due = timezone.now() - timezone.timedelta(hours=1)
        tracker.save()

        call_command('check_sla_breaches', stdout=StringIO())
        self.assertTrue(Notification.objects.filter(
            recipient=self.manager, ticket=ticket, type='ESCALATION'
        ).exists())

    def test_us_it06_no_duplicate_escalation(self):
        """US-IT06 : une même escalade n'est pas déclenchée deux fois en 30 min."""
        from django.core.management import call_command
        from io import StringIO

        ticket = Ticket.objects.create(
            type='INC', title='Pas de doublon', description='Test.',
            priority='P1', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        tracker = ticket.sla_tracker
        tracker.resolution_due = timezone.now() - timezone.timedelta(hours=1)
        tracker.save()

        call_command('check_sla_breaches', stdout=StringIO())
        call_command('check_sla_breaches', stdout=StringIO())  # 2ème appel

        self.assertEqual(EscalationEvent.objects.filter(ticket=ticket).count(), 1)


# ══════════════════════════════════════════════════════════════════
# US-IT07 — Notifications sur changements
# ══════════════════════════════════════════════════════════════════

class NotificationTestCase(BaseITSMTest):

    def setUp(self):
        self.client = Client()
        self.ticket = Ticket.objects.create(
            type='INC', title='Test notifications',
            description='Test.', priority='P3',
            requester=self.requester, assignee=self.agent,
            status='ASSIGNED', source='PORTAL'
        )

    def test_us_it07_notification_on_assignment(self):
        """US-IT07 : l'agent reçoit une notification lors de l'assignation."""
        ticket2 = Ticket.objects.create(
            type='INC', title='Assignation test', description='Test.',
            priority='P3', requester=self.requester, status='NEW', source='PORTAL'
        )
        ticket2.assignee = self.agent
        ticket2.status = 'ASSIGNED'
        ticket2.save()
        self.assertTrue(Notification.objects.filter(
            recipient=self.agent, ticket=ticket2, type='ASSIGNED'
        ).exists())

    def test_us_it07_notification_on_public_comment(self):
        """US-IT07 : le demandeur reçoit une notification sur commentaire public."""
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:add_comment', args=[self.ticket.pk]),
            {'content': 'Nous analysons le problème.', 'visibility': 'PUBLIC'}
        )
        self.assertTrue(Notification.objects.filter(
            recipient=self.requester, ticket=self.ticket, type='COMMENT'
        ).exists())

    def test_us_it07_no_notification_on_internal_comment(self):
        """US-IT07 : le demandeur ne reçoit PAS de notification sur commentaire interne."""
        initial_count = Notification.objects.filter(
            recipient=self.requester, type='COMMENT'
        ).count()
        self.client.login(username='agent_test', password='pass1234!')
        self.client.post(
            reverse('tickets:add_comment', args=[self.ticket.pk]),
            {'content': 'Note interne confidentielle.', 'visibility': 'INTERNAL'}
        )
        final_count = Notification.objects.filter(
            recipient=self.requester, type='COMMENT'
        ).count()
        self.assertEqual(initial_count, final_count)

    def test_us_it07_notification_list_accessible(self):
        """US-IT07 : la liste des notifications est accessible."""
        self.client.login(username='requester_test', password='pass1234!')
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)

    def test_us_it07_notifications_marked_read_on_visit(self):
        """US-IT07 : les notifications sont marquées lues en visitant la liste."""
        Notification.objects.create(
            recipient=self.requester, ticket=self.ticket,
            type='STATUS_CHANGE', message='Ticket mis à jour.', is_read=False
        )
        self.client.login(username='requester_test', password='pass1234!')
        self.client.get(reverse('notifications:list'))
        unread = Notification.objects.filter(recipient=self.requester, is_read=False).count()
        self.assertEqual(unread, 0)


# ══════════════════════════════════════════════════════════════════
# Tests modèles — AuditLog immuabilité
# ══════════════════════════════════════════════════════════════════

class AuditLogImmutabilityTestCase(BaseITSMTest):

    def test_audit_log_cannot_be_updated(self):
        """AuditLog : la modification est interdite après création."""
        log = AuditLog.objects.create(
            action='CREATE', content_type='tickets.Ticket',
            object_id='1', object_repr='Test ticket'
        )
        log.object_repr = 'Modifié'
        with self.assertRaises(PermissionError):
            log.save()

    def test_audit_log_cannot_be_deleted(self):
        """AuditLog : la suppression est interdite."""
        log = AuditLog.objects.create(
            action='CREATE', content_type='tickets.Ticket',
            object_id='1', object_repr='Test ticket'
        )
        with self.assertRaises(PermissionError):
            log.delete()

    def test_audit_log_creation_succeeds(self):
        """AuditLog : la création fonctionne normalement."""
        log = AuditLog.objects.create(
            action='LOGIN', object_repr='admin_test'
        )
        self.assertIsNotNone(log.pk)
        self.assertIsNotNone(log.timestamp)


# ══════════════════════════════════════════════════════════════════
# Tests SLA — pause et reprise
# ══════════════════════════════════════════════════════════════════

class SLAPauseTestCase(BaseITSMTest):

    def test_sla_paused_when_ticket_pending(self):
        """SLA : le tracker est mis en pause quand le ticket passe en PENDING."""
        ticket = Ticket.objects.create(
            type='INC', title='SLA pause test', description='Test.',
            priority='P2', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        ticket.status = 'PENDING'
        ticket.save()
        ticket.sla_tracker.refresh_from_db()
        self.assertIsNotNone(ticket.sla_tracker.paused_at)

    def test_sla_resumed_when_ticket_back_in_progress(self):
        """SLA : la pause est levée quand le ticket repasse en IN_PROGRESS."""
        ticket = Ticket.objects.create(
            type='INC', title='SLA resume test', description='Test.',
            priority='P2', requester=self.requester,
            assignee=self.agent, status='IN_PROGRESS', source='PORTAL'
        )
        ticket.status = 'PENDING'
        ticket.save()

        ticket.status = 'IN_PROGRESS'
        ticket.save()

        ticket.sla_tracker.refresh_from_db()
        self.assertIsNone(ticket.sla_tracker.paused_at)
        self.assertGreater(ticket.sla_tracker.total_paused_minutes, -1)
