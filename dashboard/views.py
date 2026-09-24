from django.shortcuts import render, redirect
from django.utils import timezone
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

    recent_notifications = NotificationService.get_notifications(request.user)[:5]

    primary_rental = active_rentals.first() if active_rentals else None
    cycle_progress = None
    if primary_rental and primary_rental.start_date and primary_rental.end_date:
        total_days = max((primary_rental.end_date - primary_rental.start_date).days, 1)
        elapsed_days = max((timezone.now() - primary_rental.start_date).days, 0)
        remaining_days = max(total_days - elapsed_days, 0)
        percent = min(int(elapsed_days * 100 / total_days), 100)
        cycle_progress = {
            'total_days': total_days,
            'elapsed_days': min(elapsed_days, total_days),
            'remaining_days': remaining_days,
            'percent': percent,
        }

    return render(request, 'dashboard/index.html', {
        'wallet': wallet,
        'active_rentals': active_rentals,
        'referral_stats': referral_stats,
        'unread_notifications': unread_notifications,
        'profile': profile,
        'recent_notifications': recent_notifications,
        'primary_rental': primary_rental,
        'cycle_progress': cycle_progress,
    })
