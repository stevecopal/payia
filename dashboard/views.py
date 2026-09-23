from django.shortcuts import render, redirect
from django.db.models import Sum
from decimal import Decimal
from core.permissions import login_required_custom
from wallet.services.wallet_service import WalletService
from ai_services.services.ai_service import AiService
from referrals.services.referral_service import ReferralService
from notifications.services.notification_service import NotificationService


@login_required_custom
def dashboard_view(request):
    if request.user.is_superuser or (
        hasattr(request.user, 'role') and request.user.role
        and request.user.role.slug in ('admin', 'super-admin')
    ):
        return redirect('admin_dashboard')

    wallet = WalletService.sync_totals(request.user)
    active_rentals = AiService.get_active_rentals(request.user)
    referral_stats = ReferralService.get_referral_stats(request.user)
    unread_notifications = NotificationService.get_unread_count(request.user)

    profile = request.user.profile

    recent_notifications = NotificationService.get_notifications(request.user, unread_only=True)[:5]

    return render(request, 'dashboard/index.html', {
        'wallet': wallet,
        'active_rentals': active_rentals,
        'referral_stats': referral_stats,
        'unread_notifications': unread_notifications,
        'profile': profile,
        'recent_notifications': recent_notifications,
    })
