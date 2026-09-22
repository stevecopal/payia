from django.shortcuts import render
from django.db.models import Sum
from decimal import Decimal
from core.permissions import login_required_custom
from wallet.services.wallet_service import WalletService
from wallet.models import LedgerEntry
from referrals.models import Commission


@login_required_custom
def wallet_view(request):
    wallet = WalletService.sync_totals(request.user)

    ai_revenue_total = LedgerEntry.objects.filter(
        user=request.user, entry_type__in=['ai_revenue', 'AI_REVENUE']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    referral_total = Commission.objects.filter(
        user=request.user, status__in=['approved', 'available']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    ledger_entries = LedgerEntry.objects.filter(
        user=request.user
    ).select_related('wallet').order_by('-created_at')[:20]

    return render(request, 'wallet/wallet.html', {
        'wallet': wallet,
        'ai_revenue_total': ai_revenue_total,
        'referral_total': referral_total,
        'ledger_entries': ledger_entries,
    })


@login_required_custom
def ledger_view(request):
    wallet = WalletService.sync_totals(request.user)
    entries = LedgerEntry.objects.filter(
        user=request.user
    ).select_related('wallet').order_by('-created_at')
    
    entry_type = request.GET.get('type')
    if entry_type:
        entries = entries.filter(entry_type=entry_type)
    
    from django.core.paginator import Paginator
    paginator = Paginator(entries, 20)
    page = request.GET.get('page', 1)
    entries = paginator.get_page(page)
    
    return render(request, 'wallet/ledger.html', {'wallet': wallet, 'entries': entries})
