import logging

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import admin_panel
from core.views.pwa import service_worker, manifest as pwa_manifest, offline as pwa_offline


logger = logging.getLogger(__name__)


def _render_error_page(template_name):
    """Rend une page d'erreur SANS contexte, donc sans context processor.

    Indispensable quand DEBUG=False : les pages 403/404/500 doivent rester
    affichables même si la base de données, les sessions ou le cache sont
    indisponibles. Or les context processors `global_context` (compteurs de
    notifications) et `auth` (session) interrogent la base : les exécuter ici
    rejouerait l'erreur qui a provoqué la page d'erreur elle-même.
    """
    from django.template.loader import render_to_string
    return render_to_string(template_name)


def handler403(request, exception=None):
    from django.http import HttpResponseForbidden
    return HttpResponseForbidden(_render_error_page('base/403.html'))


def handler404(request, exception=None):
    from django.http import HttpResponseNotFound
    return HttpResponseNotFound(_render_error_page('base/404.html'))


# Ultime filet de sécurité : si le template du 500 est introuvable ou cassé,
# on renvoie quand même une réponse HTML plutôt qu'une page vide.
_FALLBACK_500 = (
    '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
    '<title>PAYIA - Erreur serveur</title></head>'
    '<body style="margin:0;height:100vh;display:flex;align-items:center;'
    'justify-content:center;background:#000;color:#fff;font-family:monospace">'
    '<p>Une erreur est survenue. Merci de réessayer dans un instant.</p>'
    '</body></html>'
)


def handler500(request):
    from django.http import HttpResponseServerError
    try:
        html = _render_error_page('base/500.html')
    except Exception:
        logger.exception('Rendu de base/500.html impossible')
        html = _FALLBACK_500
    return HttpResponseServerError(html)


urlpatterns = [
    path('django-admin/', admin.site.urls),

    # PWA
    path('sw.js', service_worker, name='service_worker'),
    path('manifest.json', pwa_manifest, name='manifest'),
    path('offline/', pwa_offline, name='offline'),
    
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
    path('admin-panel/withdrawals/<int:pk>/complete/', admin_panel.admin_withdrawal_complete, name='admin_withdrawal_complete'),
    path('admin-panel/withdrawals/<int:pk>/reject/', admin_panel.admin_withdrawal_reject, name='admin_withdrawal_reject'),
    path('admin-panel/ai/models/', admin_panel.admin_ai_models, name='admin_ai_models'),
    path('admin-panel/ai/models/create/', admin_panel.admin_ai_model_create, name='admin_ai_model_create'),
    path('admin-panel/ai/models/<int:pk>/edit/', admin_panel.admin_ai_model_edit, name='admin_ai_model_edit'),
    path('admin-panel/ai/models/<int:pk>/delete/', admin_panel.admin_ai_model_delete, name='admin_ai_model_delete'),
    path('admin-panel/ai/offers/', admin_panel.admin_ai_offers, name='admin_ai_offers'),
    path('admin-panel/ai/offers/create/', admin_panel.admin_ai_offer_create, name='admin_ai_offer_create'),
    path('admin-panel/ai/offers/<int:pk>/edit/', admin_panel.admin_ai_offer_edit, name='admin_ai_offer_edit'),
    path('admin-panel/ai/offers/<int:pk>/delete/', admin_panel.admin_ai_offer_delete, name='admin_ai_offer_delete'),
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
