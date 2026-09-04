from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from support.forms.support import SupportTicketForm, SupportReplyForm
from support.services.support_service import SupportService
from support.models import SupportTicket
from core.permissions import login_required_custom


@login_required_custom
def support_ticket_list(request):
    tickets = SupportService.get_user_tickets(request.user)
    return render(request, 'support/list.html', {'tickets': tickets})


@login_required_custom
def support_ticket_create(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = SupportService.create_ticket(
                user=request.user,
                subject=form.cleaned_data['subject'],
                category=form.cleaned_data['category'],
                message=form.cleaned_data['message'],
                priority=form.cleaned_data['priority'],
                attachment=form.cleaned_data.get('attachment'),
            )
            messages.success(request, _('Ticket créé avec succès.'))
            return redirect('support_ticket_detail', pk=ticket.pk)
    else:
        form = SupportTicketForm()
    return render(request, 'support/create.html', {'form': form})


@login_required_custom
def support_ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk, user=request.user)
    ticket_messages = ticket.messages.all().select_related('sender')
    
    if request.method == 'POST':
        form = SupportReplyForm(request.POST, request.FILES)
        if form.is_valid():
            SupportService.reply_to_ticket(
                ticket_id=ticket.pk,
                sender=request.user,
                message=form.cleaned_data['message'],
                is_internal_note=False,
                attachment=form.cleaned_data.get('attachment'),
            )
            messages.success(request, _('Réponse envoyée.'))
            return redirect('support_ticket_detail', pk=ticket.pk)
    else:
        form = SupportReplyForm()
    
    return render(request, 'support/detail.html', {
        'ticket': ticket,
        'ticket_messages': ticket_messages,
        'form': form,
    })


@login_required_custom
def support_ticket_close(request, pk):
    if request.method == 'POST':
        SupportService.close_ticket(pk, request.user)
        messages.success(request, _('Ticket fermé.'))
    return redirect('support_ticket_list')
