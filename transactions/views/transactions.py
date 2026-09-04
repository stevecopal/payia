from django.shortcuts import render
from core.permissions import login_required_custom
from transactions.models import Deposit, Withdrawal
from ai_services.models import AiRental


@login_required_custom
def transaction_list(request):
    tx_type = request.GET.get('type')

    transactions = []

    # Deposits
    if not tx_type or tx_type == 'deposit':
        for d in Deposit.objects.filter(user=request.user).select_related('payment_method').order_by('-created_at'):
            transactions.append({
                'type': 'deposit',
                'type_display': 'Dépôt',
                'icon': 'deposit',
                'amount': d.amount,
                'fee': None,
                'status': d.status,
                'status_display': d.get_status_display(),
                'description': f'Dépôt via {d.payment_method}',
                'detail': d.transaction_id or '',
                'date': d.created_at,
                'reference_id': d.pk,
                'url': f'/transactions/deposits/{d.pk}/',
            })

    # Withdrawals
    if not tx_type or tx_type == 'withdrawal':
        for w in Withdrawal.objects.filter(user=request.user).select_related('withdrawal_method').order_by('-created_at'):
            transactions.append({
                'type': 'withdrawal',
                'type_display': 'Retrait',
                'icon': 'withdrawal',
                'amount': -w.amount,
                'fee': w.fee,
                'status': w.status,
                'status_display': w.get_status_display(),
                'description': f'Retrait via {w.withdrawal_method}',
                'detail': w.withdrawal_number or '',
                'date': w.created_at,
                'reference_id': w.pk,
                'url': f'/transactions/withdrawals/{w.pk}/',
            })

    # AI Rentals (purchases)
    if not tx_type or tx_type == 'ai_purchase':
        for r in AiRental.objects.filter(user=request.user).select_related('offer').order_by('-created_at'):
            transactions.append({
                'type': 'ai_purchase',
                'type_display': 'Achat IA',
                'icon': 'ai',
                'amount': -r.amount_paid,
                'fee': None,
                'status': r.status,
                'status_display': r.get_status_display(),
                'description': f'{r.offer.name}',
                'detail': f'{r.offer.duration_days} jours',
                'date': r.created_at,
                'reference_id': r.pk,
                'url': '#',
            })

    transactions.sort(key=lambda x: x['date'], reverse=True)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(transactions, 20)
    page = request.GET.get('page', 1)
    transactions = paginator.get_page(page)

    return render(request, 'transactions/list.html', {
        'entries': transactions,
        'current_type': tx_type,
    })
