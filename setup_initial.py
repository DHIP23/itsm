#!/usr/bin/env python
"""
setup_initial.py — Script de démarrage DSI ITSM
Exécuter UNE SEULE FOIS après la première migration.

Usage :
    python setup_initial.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsi_itsm.settings')

# Ajouter le répertoire du projet au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from sla.models import SLAPolicy
from tickets.models import Category
from escalation.models import EscalationRule

User = get_user_model()

print("\n=== DSI ITSM — Initialisation ===\n")

# ── Politiques SLA ────────────────────────────────────────────────
print("→ Création des politiques SLA...")
sla_data = [
    ('P1', 15,  240,  False),
    ('P2', 60,  480,  True),
    ('P3', 240, 1440, True),
    ('P4', 480, 4320, True),
]
for priority, response, resolution, bh in sla_data:
    obj, created = SLAPolicy.objects.get_or_create(
        priority=priority,
        defaults={
            'response_time': response,
            'resolution_time': resolution,
            'business_hours': bh,
            'is_active': True,
        }
    )
    status = "créé" if created else "déjà existant"
    print(f"   SLA {priority} — réponse {response}min / résolution {resolution}min [{status}]")

# ── Catégories ────────────────────────────────────────────────────
print("\n→ Création des catégories...")
categories = [
    'Réseau', 'Messagerie', 'Matériel',
    'Applications métier', 'Sécurité', 'Demande de service',
]
for name in categories:
    obj, created = Category.objects.get_or_create(name=name, defaults={'is_active': True})
    status = "créé" if created else "déjà existant"
    print(f"   {name} [{status}]")

# ── Utilisateurs de démonstration ─────────────────────────────────
print("\n→ Création des utilisateurs de démonstration...")
demo_users = [
    ('admin',     'admin@dsi.ci',     'Admin123!', 'ADMIN',     'Admin',  'DSI'),
    ('manager',   'manager@dsi.ci',   'Pass123!',  'MANAGER',   'Marie',  'Manager'),
    ('agent1',    'agent1@dsi.ci',    'Pass123!',  'AGENT',     'Kofi',   'Agent N1'),
    ('agent2',    'agent2@dsi.ci',    'Pass123!',  'L2_AGENT',  'Aminata','Expert N2'),
    ('demandeur', 'demand@dsi.ci',    'Pass123!',  'REQUESTER', 'René',   'Demandeur'),
]
for username, email, password, role, first, last in demo_users:
    if not User.objects.filter(username=username).exists():
        u = User.objects.create_user(
            username=username, email=email, password=password,
            role=role, first_name=first, last_name=last,
            is_staff=(role == 'ADMIN'), is_superuser=(role == 'ADMIN'),
        )
        print(f"   {username} ({role}) — mot de passe : {password}")
    else:
        print(f"   {username} [{role}] — déjà existant")

# ── Règles d'escalade de base ─────────────────────────────────────
print("\n→ Création des règles d'escalade...")
try:
    manager_user = User.objects.get(username='manager')
    rules = [
        ('Breach réponse P1/P2', 'RESPONSE_BREACH',   'P1', 'BOTH'),
        ('Breach résolution P1', 'RESOLUTION_BREACH',  'P1', 'BOTH'),
        ('Breach résolution P2', 'RESOLUTION_BREACH',  'P2', 'IN_APP'),
        ('Non assigné urgent',   'UNASSIGNED_TIMEOUT', 'P1', 'BOTH'),
    ]
    for name, trigger, priority, notify_via in rules:
        obj, created = EscalationRule.objects.get_or_create(
            name=name,
            defaults={
                'trigger': trigger, 'priority': priority,
                'target': manager_user, 'notify_via': notify_via, 'is_active': True,
            }
        )
        status = "créé" if created else "déjà existant"
        print(f"   {name} [{status}]")
except User.DoesNotExist:
    print("   [SKIP] Utilisateur manager introuvable.")

print("\n✓ Initialisation terminée !")
print("\nAccès à l'application :")
print("  → http://localhost:8000/")
print("  → Admin Django : http://localhost:8000/admin/")
print("  → Compte admin : admin / Admin123!\n")
