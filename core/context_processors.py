from django.conf import settings
from notifications.models import Notification

def global_context(request):
    context = {
        'site_name': 'PAYIA',
        'site_description': 'Plateforme IA et Finance',
    }
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        context['unread_notifications_count'] = unread_notifications
        try:
            profile = request.user.profile
            context['profile_complete'] = profile.is_profile_complete
        except Exception:
            context['profile_complete'] = False
    return context
