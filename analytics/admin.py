from django.contrib import admin
from .models import AnalyticsEvent

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'ip_address', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('user__phone_number',)
    readonly_fields = ('event_type', 'user', 'session_id', 'ip_address', 'user_agent', 'metadata', 'created_at')
    
    def has_add_permission(self, request):
        return False
