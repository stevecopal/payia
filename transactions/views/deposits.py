import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from transactions.models import Deposit, PaymentMethod
from transactions.services.deposit_service import DepositService
from core.permissions import login_required_custom
from analytics.services.analytics_service import AnalyticsService


@login_required_custom
def deposit_create(request):
    if request.method == 'POST':
        step = request.POST.get('step', '1')

        if step == '1':
            payment_method_id = request.POST.get('payment_method', '')
            phone_digits = request.POST.get('phone_digits', '').strip()
            amount = request.POST.get('amount', '').strip()

            errors = {}
            if not payment_method_id:
                errors['payment_method'] = _('Veuillez choisir un moyen de paiement.')

            if not phone_digits:
                errors['phone_digits'] = _('Veuillez saisir votre numéro de téléphone.')
            elif not phone_digits.isdigit() or len(phone_digits) != 9 or not phone_digits.startswith('6'):
                errors['phone_digits'] = _('Numéro invalide. 9 chiffres commencant par 6.')

            if not amount:
                errors['amount'] = _('Veuillez saisir un montant.')
            else:
                try:
                    amount_dec = float(amount)
                    if amount_dec <= 0:
                        errors['amount'] = _('Le montant doit être supérieur à 0.')
                except (ValueError, TypeError):
                    errors['amount'] = _('Montant invalide.')

            if errors:
                payment_methods = PaymentMethod.objects.filter(is_active=True)
                return render(request, 'deposits/create.html', {
                    'step': 1,
                    'payment_methods': payment_methods,
                    'errors': errors,
                    'form_data': {
                        'payment_method_id': payment_method_id,
                        'phone_digits': phone_digits,
                        'amount': amount,
                    },
                })

            try:
                pm = PaymentMethod.objects.get(id=payment_method_id, is_active=True)
            except PaymentMethod.DoesNotExist:
                messages.error(request, _('Méthode de paiement invalide.'))
                return redirect('deposit_create')

            ussd_code = pm.generate_ussd_code(amount)
            request.session['deposit_data'] = {
                'payment_method_id': int(payment_method_id),
                'payment_method_name': pm.name,
                'phone_digits': phone_digits,
                'phone_number': f'+237{phone_digits}',
                'amount': amount,
                'reception_number': pm.phone_number,
                'reception_name': pm.reception_name or pm.phone_number,
                'ussd_code': ussd_code,
            }

            return render(request, 'deposits/create.html', {
                'step': 2,
                'deposit_data': request.session['deposit_data'],
            })

        elif step == '2':
            deposit_data = request.session.get('deposit_data')
            if not deposit_data:
                messages.error(request, _('Session expirée. Veuillez recommencer.'))
                return redirect('deposit_create')

            return render(request, 'deposits/create.html', {
                'step': 3,
                'deposit_data': deposit_data,
            })

        elif step == '3':
            deposit_data = request.session.get('deposit_data')
            if not deposit_data:
                messages.error(request, _('Session expirée. Veuillez recommencer.'))
                return redirect('deposit_create')

            transaction_id = request.POST.get('transaction_id', '').strip()
            tx_phone_digits = request.POST.get('tx_phone_digits', '').strip()

            errors = {}
            if not transaction_id:
                errors['transaction_id'] = _('Veuillez saisir l\'ID de transaction.')

            if not tx_phone_digits:
                errors['tx_phone_digits'] = _('Veuillez saisir le numéro utilisé.')
            elif not tx_phone_digits.isdigit() or len(tx_phone_digits) != 9 or not tx_phone_digits.startswith('6'):
                errors['tx_phone_digits'] = _('Numéro invalide. 9 chiffres commencant par 6.')

            if errors:
                return render(request, 'deposits/create.html', {
                    'step': 3,
                    'deposit_data': deposit_data,
                    'errors': errors,
                    'form_data': {
                        'transaction_id': transaction_id,
                        'tx_phone_digits': tx_phone_digits,
                    },
                })

            try:
                deposit = DepositService.create_deposit(
                    user=request.user,
                    amount=deposit_data['amount'],
                    payment_method_id=deposit_data['payment_method_id'],
                    transaction_id=transaction_id,
                    phone_number=f'+237{tx_phone_digits}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                AnalyticsService.track_event('DEPOSIT_CREATED', request.user, request)

                if 'deposit_data' in request.session:
                    del request.session['deposit_data']

                messages.success(request, _('Votre demande de dépôt a été envoyée et est en attente de validation.'))
                return redirect('deposit_detail', pk=deposit.pk)
            except ValueError as e:
                messages.error(request, str(e))
                return render(request, 'deposits/create.html', {
                    'step': 3,
                    'deposit_data': deposit_data,
                })

    payment_methods = PaymentMethod.objects.filter(is_active=True)
    return render(request, 'deposits/create.html', {
        'step': 1,
        'payment_methods': payment_methods,
    })


@login_required_custom
def deposit_detail(request, pk):
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)
    return render(request, 'deposits/detail.html', {'deposit': deposit})


@login_required_custom
def deposit_list(request):
    deposits = DepositService.get_user_deposits(request.user)
    status = request.GET.get('status', '')
    status_lower = status.lower()
    if status_lower:
        deposits = deposits.filter(status=status_lower)

    from django.core.paginator import Paginator
    paginator = Paginator(deposits, 15)
    page = request.GET.get('page', 1)
    deposits = paginator.get_page(page)

    return render(request, 'deposits/list.html', {'deposits': deposits, 'current_status': status_lower})
