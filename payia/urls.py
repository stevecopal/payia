from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import admin_panel


def handler403(request, exception=None):
    from django.shortcuts import render
    return render(request, 'base/403.html', status=403)

def handler404(request, exception=None):
    from django.shortcuts import render
    return render(request, 'base/404.html', status=404)

def handler500(request):
    from django.shortcuts import render
    return render(request, 'base/500.html', status=500)


urlpatterns = [
    path('django-admin/', admin.site.urls),
    
    path('i18n/', include('django.conf.urls.i18n')),
    
    path('', include('core.urls')),
    path('wallet/', include('wallet.urls')),
    path('transactions/', include('transactions.urls')),
    path('services/ai/', include('ai_services.urls')),
    path('referrals/', include('referrals.urls')),
    path('notifications/', include('notifications.urls')),
    path('support/', include('support.urls')),
    path('dashboard/', include('dashboard.urls')),
    
    path('admin-panel/', admin_panel.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/users/', admin_panel.admin_users, name='admin_users'),
    path('admin-panel/users/<int:pk>/', admin_panel.admin_user_detail, name='admin_user_detail'),
    path('admin-panel/users/<int:pk>/toggle-suspend/', admin_panel.admin_user_toggle_suspend, name='admin_user_toggle_suspend'),
    path('admin-panel/deposits/', admin_panel.admin_deposits, name='admin_deposits'),
    path('admin-panel/deposits/<int:pk>/', admin_panel.admin_deposit_detail, name='admin_deposit_detail'),
    path('admin-panel/deposits/<int:pk>/approve/', admin_panel.admin_deposit_approve, name='admin_deposit_approve'),
    path('admin-panel/deposits/<int:pk>/reject/', admin_panel.admin_deposit_reject, name='admin_deposit_reject'),
    path('admin-panel/withdrawals/', admin_panel.admin_withdrawals, name='admin_withdrawals'),
    path('admin-panel/withdrawals/<int:pk>/', admin_panel.admin_withdrawal_detail, name='admin_withdrawal_detail'),
    path('admin-panel/withdrawals/<int:pk>/approve/', admin_panel.admin_withdrawal_approve, name='admin_withdrawal_approve'),
    path('admin-panel/withdrawals/<int:pk>/reject/', admin_panel.admin_withdrawal_reject, name='admin_withdrawal_reject'),
    path('admin-panel/ai/models/', admin_panel.admin_ai_models, name='admin_ai_models'),
    path('admin-panel/ai/models/create/', admin_panel.admin_ai_model_create, name='admin_ai_model_create'),
    path('admin-panel/ai/models/<int:pk>/edit/', admin_panel.admin_ai_model_edit, name='admin_ai_model_edit'),
    path('admin-panel/ai/models/<int:pk>/delete/', admin_panel.admin_ai_model_delete, name='admin_ai_model_delete'),
    path('admin-panel/ai/offers/', admin_panel.admin_ai_offers, name='admin_ai_offers'),
    path('admin-panel/ai/offers/create/', admin_panel.admin_ai_offer_create, name='admin_ai_offer_create'),
    path('admin-panel/ai/offers/<int:pk>/edit/', admin_panel.admin_ai_offer_edit, name='admin_ai_offer_edit'),
    path('admin-panel/ai/offers/<int:pk>/delete/', admin_panel.admin_ai_offer_delete, name='admin_ai_offer_delete'),
    path('admin-panel/referrals/', admin_panel.admin_referrals, name='admin_referrals'),
    path('admin-panel/commissions/', admin_panel.admin_commissions, name='admin_commissions'),
    path('admin-panel/notifications/', admin_panel.admin_notifications, name='admin_notifications'),
    path('admin-panel/notifications/create/', admin_panel.admin_notification_create, name='admin_notification_create'),
    path('admin-panel/messages/', admin_panel.admin_messages, name='admin_messages'),
    path('admin-panel/support/', admin_panel.admin_support, name='admin_support'),
    path('admin-panel/support/<int:pk>/', admin_panel.admin_support_ticket_detail, name='admin_support_ticket_detail'),
    path('admin-panel/statistics/', admin_panel.admin_statistics, name='admin_statistics'),
    path('admin-panel/audit/', admin_panel.admin_audit, name='admin_audit'),
    path('admin-panel/settings/', admin_panel.admin_settings, name='admin_settings'),
    path('admin-panel/payment-methods/', admin_panel.admin_payment_methods, name='admin_payment_methods'),
    path('admin-panel/payment-methods/create/', admin_panel.admin_payment_method_create, name='admin_payment_method_create'),
    path('admin-panel/payment-methods/<int:pk>/edit/', admin_panel.admin_payment_method_edit, name='admin_payment_method_edit'),
    path('admin-panel/payment-methods/<int:pk>/delete/', admin_panel.admin_payment_method_delete, name='admin_payment_method_delete'),
    path('admin-panel/export/deposits/', admin_panel.admin_export_deposits, name='admin_export_deposits'),
    path('admin-panel/export/withdrawals/', admin_panel.admin_export_withdrawals, name='admin_export_withdrawals'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler403 = handler403
handler404 = handler404
handler500 = handler500
