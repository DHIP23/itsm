from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Ticket, TicketComment, TicketAttachment
from .forms import TicketCreateForm, TicketUpdateForm, CommentForm, AssignForm
from audit.models import AuditLog


@login_required
def ticket_list(request):
    """US-IT01 (liste) + US-IT02 : vue filtrée selon le rôle."""
    qs = Ticket.objects.select_related('requester', 'assignee', 'category').prefetch_related('sla_tracker')

    # Filtrage par rôle
    user = request.user
    if user.is_requester:
        qs = qs.filter(requester=user)
    elif user.is_agent:
        qs = qs.filter(assignee=user)
    # Managers et admins voient tout

    # Filtres GET
    status   = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    type_    = request.GET.get('type', '')
    q        = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if type_:
        qs = qs.filter(type=type_)
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))

    # Tri
    sort = request.GET.get('sort', '-created_at')
    allowed_sorts = ['created_at', '-created_at', 'priority', '-priority', 'status']
    if sort in allowed_sorts:
        qs = qs.order_by(sort)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'tickets/ticket_list.html', {
        'page_obj': page,
        'statuses': Ticket.Status.choices,
        'priorities': Ticket.Priority.choices,
        'types': Ticket.Type.choices,
        'current_filters': {'status': status, 'priority': priority, 'type': type_, 'q': q, 'sort': sort},
    })


@login_required
def ticket_detail(request, pk):
    """US-IT03 : détail ticket avec commentaires et SLA."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('requester', 'assignee', 'category', 'sla_tracker__policy'),
        pk=pk
    )
    # Requester ne voit que ses propres tickets
    if request.user.is_requester and ticket.requester != request.user:
        messages.error(request, "Accès non autorisé.")
        return redirect('tickets:list')

    comments = ticket.comments.select_related('author').all()
    if request.user.is_requester:
        comments = comments.filter(visibility='PUBLIC')

    comment_form = CommentForm()
    assign_form  = AssignForm(instance=ticket) if request.user.can_manage_tickets else None

    return render(request, 'tickets/ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'comment_form': comment_form,
        'assign_form': assign_form,
        'attachments': ticket.attachments.all(),
        'escalations': ticket.escalations.select_related('rule', 'notified').all(),
    })


@login_required
def ticket_create(request):
    """US-IT01 : création ticket par tout utilisateur authentifié."""
    if request.method == 'POST':
        form = TicketCreateForm(request.POST, request.FILES)
        # ── AJOUT TEMPORAIRE DE DEBUG ──────────────────
        if not form.is_valid():
            print("=== ERREURS FORMULAIRE ===")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            print("=== FIN ERREURS ===")
        # ──────────────────────────────────────────────
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            # Agents peuvent saisir directement (source AGENT)
            if request.user.can_manage_tickets:
                ticket.source = form.cleaned_data.get('source', Ticket.Source.PORTAL)
            else:
                ticket.source = Ticket.Source.PORTAL
            ticket.save()
            # 🔥 DEBUG
            print("✅ Ticket créé :", ticket.pk)
            # Pièces jointes
            for f in request.FILES.getlist('attachments'):
                TicketAttachment.objects.create(
                    ticket=ticket, uploaded_by=request.user,
                    file=f, filename=f.name
                )
               
            messages.success(request, f"Ticket {ticket.reference} créé avec succès.")
            return redirect('tickets:detail', pk=ticket.pk)
    else:
        form = TicketCreateForm()

    return render(request, 'tickets/ticket_create.html', {'form': form})


@login_required
def ticket_update_status(request, pk):
    """US-IT03 : changement de statut par un agent."""
    if not request.user.can_manage_tickets:
        messages.error(request, "Permission insuffisante.")
        return redirect('tickets:detail', pk=pk)

    ticket = get_object_or_404(Ticket, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        resolution_note = request.POST.get('resolution_note', '')

        if new_status not in dict(Ticket.Status.choices):
            messages.error(request, "Statut invalide.")
            return redirect('tickets:detail', pk=pk)

        ticket.status = new_status
        if resolution_note:
            ticket.resolution_note = resolution_note
        ticket.save()  # signal post_save gère l'audit + notifs

        messages.success(request, f"Statut mis à jour : {ticket.get_status_display()}")

    return redirect('tickets:detail', pk=pk)


@login_required
@require_POST
def ticket_assign(request, pk):
    """Assignation d'un ticket à un agent."""
    if not request.user.can_manage_tickets:
        return JsonResponse({'error': 'Permission insuffisante'}, status=403)

    ticket = get_object_or_404(Ticket, pk=pk)
    form = AssignForm(request.POST, instance=ticket)
    if form.is_valid():
        ticket = form.save(commit=False)
        if ticket.status == Ticket.Status.NEW:
            ticket.status = Ticket.Status.ASSIGNED
        ticket.save()
        messages.success(request, f"Ticket assigné à {ticket.assignee}.")
    else:
        messages.error(request, "Erreur lors de l'assignation.")

    return redirect('tickets:detail', pk=pk)


@login_required
@require_POST
def add_comment(request, pk):
    """Ajout d'un commentaire sur un ticket."""
    ticket = get_object_or_404(Ticket, pk=pk)

    # Requester ne peut commenter que ses propres tickets
    if request.user.is_requester and ticket.requester != request.user:
        messages.error(request, "Accès non autorisé.")
        return redirect('tickets:list')

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        # Les requesters ne peuvent poster qu'en PUBLIC
        if request.user.is_requester:
            comment.visibility = 'PUBLIC'
        comment.save()  # signal gère l'audit
        messages.success(request, "Commentaire ajouté.")

    return redirect('tickets:detail', pk=pk)
