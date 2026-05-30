from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator

from .models import AuditLog


@login_required
def audit_log_list(request):
    """Journal d'audit complet — réservé aux administrateurs."""
    if not request.user.is_admin_role:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('dashboard:index')

    logs = AuditLog.objects.select_related('user').order_by('-timestamp')

    # Filtres optionnels
    action = request.GET.get('action', '')
    q      = request.GET.get('q', '').strip()
    if action:
        logs = logs.filter(action=action)
    if q:
        logs = logs.filter(object_repr__icontains=q)

    paginator = Paginator(logs, 50)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'audit/logs.html', {
        'page_obj': page,
        'actions':  AuditLog.Action.choices,
        'current_action': action,
        'q': q,
    })
