from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Notification


@login_required
def notification_list(request):
    """Liste les 50 dernières notifications et les marque comme lues."""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('ticket').order_by('-created_at')[:50]

    # Marque toutes comme lues en une seule requête
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True)

    return render(request, 'notifications/list.html', {
        'notifications': notifications
    })
