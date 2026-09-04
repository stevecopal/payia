from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from notifications.models import Notification, Message
from notifications.services.notification_service import NotificationService
from core.permissions import login_required_custom


@login_required_custom
def notification_list(request):
    notifications = NotificationService.get_notifications(request.user)
    filter_type = request.GET.get('filter', '')
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    
    from django.core.paginator import Paginator
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications = paginator.get_page(page)
    
    return render(request, 'notifications/list.html', {'notifications': notifications, 'filter_type': filter_type})


@login_required_custom
def notification_mark_read(request, pk):
    if request.method == 'POST':
        NotificationService.mark_read(pk, request.user)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
    return redirect('notifications')


@login_required_custom
def notification_mark_all_read(request):
    if request.method == 'POST':
        NotificationService.mark_all_read(request.user)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
    return redirect('notifications')


@login_required_custom
def message_list(request):
    messages_list = NotificationService.get_user_messages(request.user)
    from django.core.paginator import Paginator
    paginator = Paginator(messages_list, 20)
    page = request.GET.get('page', 1)
    messages_list = paginator.get_page(page)
    return render(request, 'messages/list.html', {'messages': messages_list})


@login_required_custom
def message_detail(request, pk):
    msg = get_object_or_404(Message, pk=pk, recipient=request.user)
    if not msg.is_read:
        msg.is_read = True
        msg.read_at = msg.created_at
        msg.save(update_fields=['is_read', 'read_at'])
    return render(request, 'messages/detail.html', {'message': msg})
