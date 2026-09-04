from django.urls import path
from notifications.views.notifications import (
    notification_list, notification_mark_read,
    notification_mark_all_read, message_list, message_detail,
)

urlpatterns = [
    path('', notification_list, name='notifications'),
    path('<int:pk>/read/', notification_mark_read, name='notification_mark_read'),
    path('read-all/', notification_mark_all_read, name='notification_mark_all_read'),
    path('messages/', message_list, name='message_list'),
    path('messages/<int:pk>/', message_detail, name='message_detail'),
]
