from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from .models import SLATracker, SLAPolicy


@login_required
def sla_dashboard(request):
    """Tableau de bord SLA — réservé aux managers et admins."""
    if not request.user.is_manager:
        messages.error(request, "Accès réservé aux managers et administrateurs.")
        return redirect('dashboard:index')

    trackers = SLATracker.objects.select_related(
        'ticket', 'ticket__assignee', 'ticket__requester', 'policy'
    ).filter(
        ticket__status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING', 'REOPENED']
    )

    breached = trackers.filter(
        Q(response_breached=True) | Q(resolution_breached=True)
    ).order_by('-ticket__priority', 'resolution_due')

    at_risk = trackers.filter(
        resolution_breached=False,
        resolution_due__isnull=False,
    ).order_by('resolution_due')[:15]

    policies = SLAPolicy.objects.filter(is_active=True).order_by('priority')

    return render(request, 'sla/sla_dashboard.html', {
        'breached':       breached,
        'at_risk':        at_risk,
        'policies':       policies,
        'total_breached': breached.count(),
    })
