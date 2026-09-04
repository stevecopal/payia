from django.contrib import admin
from .models import SupportTicket, SupportMessage

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'category', 'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'category', 'priority')
    search_fields = ('user__phone_number', 'subject')

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'sender', 'is_internal_note', 'created_at')
    list_filter = ('is_internal_note',)
    search_fields = ('sender__phone_number', 'message')
