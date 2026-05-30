from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
import datetime

from tickets.models import Ticket
from sla.models import SLATracker


@login_required
def dashboard(request):
    """US-IT04 : tableau de bord KPIs avec données pour Chart.js."""
    user = request.user
    now  = timezone.now()

    # Base queryset selon rôle
    if user.is_requester:
        qs = Ticket.objects.filter(requester=user)
    elif user.is_agent:
        qs = Ticket.objects.filter(assignee=user)
    else:
        qs = Ticket.objects.all()

    # ── KPIs principaux ──────────────────────────────────────────
    total_open   = qs.filter(status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING', 'REOPENED']).count()
    total_closed = qs.filter(status__in=['RESOLVED', 'CLOSED']).count()
    total_today  = qs.filter(created_at__date=now.date()).count()
    p1_open      = qs.filter(priority='P1', status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']).count()

    # SLA en breach
    breached_response   = SLATracker.objects.filter(
        ticket__in=qs, response_breached=True, ticket__status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']
    ).count()
    breached_resolution = SLATracker.objects.filter(
        ticket__in=qs, resolution_breached=True, ticket__status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING']
    ).count()

    # Tickets non assignés
    unassigned = qs.filter(assignee__isnull=True, status='NEW').count()

    # ── Données graphiques (7 derniers jours) ────────────────────
    labels, incidents_data, requests_data = [], [], []
    for i in range(6, -1, -1):
        day = (now - datetime.timedelta(days=i)).date()
        labels.append(day.strftime('%d/%m'))
        incidents_data.append(qs.filter(type='INC', created_at__date=day).count())
        requests_data.append(qs.filter(type='REQ', created_at__date=day).count())

    # Répartition par statut
    status_counts = (
        qs.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )
    status_labels = [s['status'] for s in status_counts]
    status_values = [s['count'] for s in status_counts]

    # Répartition par priorité
    priority_counts = (
        qs.filter(status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING'])
        .values('priority')
        .annotate(count=Count('id'))
        .order_by('priority')
    )

    # Tickets récents
    recent_tickets = qs.select_related('requester', 'assignee').order_by('-created_at')[:8]

    return render(request, 'dashboard/dashboard.html', {
        # KPIs
        'total_open':           total_open,
        'total_closed':         total_closed,
        'total_today':          total_today,
        'p1_open':              p1_open,
        'breached_response':    breached_response,
        'breached_resolution':  breached_resolution,
        'unassigned':           unassigned,
        # Chart.js
        'chart_labels':         labels,
        'chart_incidents':      incidents_data,
        'chart_requests':       requests_data,
        'status_labels':        status_labels,
        'status_values':        status_values,
        'priority_counts':      list(priority_counts),
        # Tableau
        'recent_tickets':       recent_tickets,
        'now':                  now,
    })


@login_required
def dashboard_data_api(request):
    """API JSON pour rafraîchissement Chart.js côté client (polling)."""
    qs = Ticket.objects.all()
    if request.user.is_requester:
        qs = qs.filter(requester=request.user)
    elif request.user.is_agent:
        qs = qs.filter(assignee=request.user)

    data = {
        'total_open':    qs.filter(status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING']).count(),
        'total_closed':  qs.filter(status__in=['RESOLVED', 'CLOSED']).count(),
        'p1_open':       qs.filter(priority='P1', status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']).count(),
        'breached':      SLATracker.objects.filter(
            ticket__in=qs,
            resolution_breached=True,
            ticket__status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING']
        ).count(),
    }
    return JsonResponse(data)
