from django.conf import settings
from django.core.cache import cache
from notifications.models import Notification

def global_context(request):
    context = {
        'site_name': 'PAYIA',
        'site_description': 'Plateforme IA et Finance',
    }
    if request.user.is_authenticated:
        cache_key = f'unread_notif_{request.user.pk}'
        unread_notifications = cache.get(cache_key)
        if unread_notifications is None:
            unread_notifications = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()
            cache.set(cache_key, unread_notifications, 30)
        context['unread_notifications_count'] = unread_notifications
        try:
            from notifications.services.notification_service import NotificationService
            context['unread_commission_count'] = NotificationService.get_unread_commission_count(request.user)
        except Exception:
            context['unread_commission_count'] = 0
        try:
            profile = request.user.profile
            context['profile_status'] = profile.profile_status
        except Exception:
            context['profile_status'] = 'PENDING'
    return context
