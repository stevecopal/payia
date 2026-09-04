from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from transactions.forms.withdrawal import WithdrawalForm
from transactions.services.withdrawal_service import WithdrawalService
from transactions.models import Withdrawal
from core.permissions import login_required_custom


@login_required_custom
def withdrawal_create(request):
    try:
        profile = request.user.profile
        if not profile.is_profile_complete:
            messages.warning(request, _('Veuillez compléter votre profil avant de faire un retrait.'))
            return redirect('profile_complete')
        if not profile.withdrawal_phone_number:
            messages.warning(request, _('Veuillez renseigner votre numéro de retrait.'))
            return redirect('withdrawal_info')
    except Exception:
        messages.warning(request, _('Veuillez compléter votre profil.'))
        return redirect('profile_complete')
    
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            try:
                withdrawal = WithdrawalService.create_withdrawal(
                    user=request.user,
                    amount=form.cleaned_data['amount'],
                    payment_method_id=form.cleaned_data['payment_method'].pk,
                    withdrawal_number=form.cleaned_data['withdrawal_number'],
                    withdrawal_account_name=form.cleaned_data.get('withdrawal_account_name', ''),
                    note=form.cleaned_data.get('note', ''),
                )
                messages.success(request, _('Votre demande de retrait a été soumise.'))
                return redirect('withdrawal_detail', pk=withdrawal.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = WithdrawalForm()
    
    from transactions.models import PaymentMethod
    from wallet.services.wallet_service import WalletService
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    wallet = WalletService.get_wallet(request.user)
    return render(request, 'withdrawals/create.html', {
        'form': form,
        'payment_methods': payment_methods,
        'wallet': wallet,
    })


@login_required_custom
def withdrawal_detail(request, pk):
    withdrawal = get_object_or_404(Withdrawal, pk=pk, user=request.user)
    return render(request, 'withdrawals/detail.html', {'withdrawal': withdrawal})


@login_required_custom
def withdrawal_list(request):
    withdrawals = WithdrawalService.get_user_withdrawals(request.user)
    status = request.GET.get('status', '')
    status_lower = status.lower()
    if status_lower:
        withdrawals = withdrawals.filter(status=status_lower)
    
    from django.core.paginator import Paginator
    paginator = Paginator(withdrawals, 15)
    page = request.GET.get('page', 1)
    withdrawals = paginator.get_page(page)
    
    return render(request, 'withdrawals/list.html', {'withdrawals': withdrawals, 'current_status': status_lower})
