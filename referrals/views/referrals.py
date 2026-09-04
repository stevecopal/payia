from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from referrals.services.referral_service import ReferralService
from referrals.models import Referral, Commission
from core.permissions import login_required_custom


@login_required_custom
def referral_dashboard(request):
    stats = ReferralService.get_referral_stats(request.user)
    referral_code = ReferralService.get_referral_code(request.user)
    referral_link = ReferralService.get_referral_link(request.user, request)

    referrals = Referral.objects.filter(
        referrer=request.user, is_active=True
    ).select_related('referred_user').order_by('-created_at')

    referrals_with_data = []
    for ref in referrals:
        user = ref.referred_user
        has_deposit = Commission.objects.filter(
            source_user=user, source_transaction_type='DEPOSIT_COMPLETED'
        ).exists()
        total_revenue = Commission.objects.filter(
            user=request.user, source_user=user
        ).aggregate(total=Sum('amount'))['total'] or 0
        referrals_with_data.append({
            'referral': ref,
            'has_deposit': has_deposit,
            'total_revenue': total_revenue,
        })

    commissions = Commission.objects.filter(
        user=request.user
    ).select_related('source_user').order_by('-created_at')[:20]

    total_commissions = Commission.objects.filter(
        user=request.user, status__in=['approved', 'available']
    ).aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'referrals/dashboard.html', {
        'stats': stats,
        'referral_code': referral_code,
        'referral_link': referral_link,
        'referrals_with_data': referrals_with_data,
        'commissions': commissions,
        'total_commissions': total_commissions,
    })


def referral_register(request, code):
    if request.user.is_authenticated:
        messages.info(request, _('Vous êtes déjà connecté.'))
        return redirect('dashboard')

    from core.models import User
    if not User.objects.filter(referral_code=code, is_active=True).exists():
        messages.error(request, _('Code de parrainage invalide.'))
        return redirect('register')

    request.session['referral_code'] = code
    messages.info(request, _('Code de parrainage enregistré. Créez votre compte pour continuer.'))
    return redirect('register')
