from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN      = 'ADMIN',      'Administrateur'
        MANAGER    = 'MANAGER',    'Manager DSI'
        AGENT      = 'AGENT',      'Agent N1'
        L2_AGENT   = 'L2_AGENT',  'Agent N2 (Expert)'
        REQUESTER  = 'REQUESTER',  'Demandeur'

    role       = models.CharField(max_length=20, choices=Role.choices, default=Role.REQUESTER)
    department = models.CharField(max_length=100, blank=True)
    phone      = models.CharField(max_length=20, blank=True)
    avatar     = models.ImageField(upload_to='avatars/', null=True, blank=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # ── Helpers de rôle ──────────────────────────────────────────
    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)

    @property
    def is_agent(self):
        return self.role in (self.Role.AGENT, self.Role.L2_AGENT)

    @property
    def is_requester(self):
        return self.role == self.Role.REQUESTER

    @property
    def can_manage_tickets(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER, self.Role.AGENT, self.Role.L2_AGENT)
