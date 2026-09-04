from django.urls import path
from support.views.support import (
    support_ticket_list, support_ticket_create,
    support_ticket_detail, support_ticket_close,
)

urlpatterns = [
    path('', support_ticket_list, name='support_list'),
    path('create/', support_ticket_create, name='support_create'),
    path('<int:pk>/', support_ticket_detail, name='support_ticket_detail'),
    path('<int:pk>/close/', support_ticket_close, name='support_ticket_close'),
]
