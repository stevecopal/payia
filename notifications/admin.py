from django.contrib import admin
from .models import Notification, Message

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('user__phone_number', 'title', 'message')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'subject', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read')
    search_fields = ('recipient__phone_number', 'subject')
