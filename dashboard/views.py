from django.shortcuts import render, redirect
from django.utils import timezone
from core.permissions import login_required_custom
from wallet.services.wallet_service import WalletService
from ai_services.services.ai_service import AiService
from referrals.services.referral_service import ReferralService
from notifications.services.notification_service import NotificationService


def _cycle_progress(rental):
    if not (rental and rental.start_date and rental.end_date):
        return None
    total_days = max((rental.end_date - rental.start_date).days, 1)
    elapsed_days = max((timezone.now() - rental.start_date).days, 0)
    remaining_days = max(total_days - elapsed_days, 0)
    percent = min(int(elapsed_days * 100 / total_days), 100)
    return {
        'total_days': total_days,
        'elapsed_days': min(elapsed_days, total_days),
        'remaining_days': remaining_days,
        'percent': percent,
    }


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

    machines = []
    for rental in active_rentals:
        machines.append({
            'rental': rental,
            'progress': _cycle_progress(rental),
        })

    return render(request, 'dashboard/index.html', {
        'wallet': wallet,
        'active_rentals': active_rentals,
        'machines': machines,
        'machine_count': len(machines),
        'referral_stats': referral_stats,
        'unread_notifications': unread_notifications,
        'profile': profile,
        'recent_notifications': recent_notifications,
    })
