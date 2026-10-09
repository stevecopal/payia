import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from transactions.models import Deposit, PaymentMethod
from transactions.services.deposit_service import DepositService
from transactions.services.online_deposit_service import OnlineDepositService
from core.permissions import login_required_custom
from core.models import Setting
from analytics.services.analytics_service import AnalyticsService


ONLINE_PREFIX = 'online:'


def _online_channels():
    """Moyens de paiement Tara Money proposes a l'utilisateur."""
    if not OnlineDepositService.is_available():
        return []
    return OnlineDepositService.available_channels()


def _manual_payment_methods():
    """Methodes de paiement historiques (hors Tara Money en ligne)."""
    return (
        OnlineDepositService.filter_available(
            PaymentMethod.objects.filter(is_active=True)
        )
        .exclude(slug=OnlineDepositService.PAYMENT_METHOD_SLUG)
    )


def _min_deposit_value():
    try:
        return str(Setting.objects.get(key='minimum_deposit').value)
    except Setting.DoesNotExist:
        return '2500'


def _deposit_form_context(**extra):
    """Contexte commun du formulaire de depot (etape 1)."""
    context = {
        'step': 1,
        'online_channels': _online_channels(),
        'payment_methods': _manual_payment_methods(),
        'min_deposit': _min_deposit_value(),
    }
    context.update(extra)
    return context


@login_required_custom
def deposit_create(request):
    if request.method == 'POST':
        step = request.POST.get('step', '1')

        if step == '1':
            selection = request.POST.get('payment_method', '').strip()
            phone_digits = request.POST.get('phone_digits', '').strip()
            amount = request.POST.get('amount', '').strip()

            # Un moyen Tara Money est identifie par `online:<canal>` ; les
            # methodes historiques restent identifiees par leur identifiant.
            is_online = selection.startswith(ONLINE_PREFIX)
            online_channel = selection[len(ONLINE_PREFIX):] if is_online else ''

            errors = {}
            pm = None

            if not selection:
                errors['payment_method'] = _('Veuillez choisir un moyen de paiement.')
            elif is_online:
                if online_channel not in OnlineDepositService.CHANNELS:
                    errors['payment_method'] = _('Moyen de paiement Tara Money invalide.')
            else:
                pm = (
                    PaymentMethod.objects.filter(id=selection, is_active=True).first()
                    if selection.isdigit() else None
                )
                if pm is None:
                    errors['payment_method'] = _('Méthode de paiement invalide.')

            if not phone_digits:
                errors['phone_digits'] = _('Veuillez saisir votre numéro de téléphone.')
            elif not phone_digits.isdigit() or len(phone_digits) != 9 or not phone_digits.startswith('6'):
                errors['phone_digits'] = _('Numéro invalide. 9 chiffres commencant par 6.')

            amount_dec = None
            if not amount:
                errors['amount'] = _('Veuillez saisir un montant.')
            else:
                try:
                    amount_dec = Decimal(amount)
                    if amount_dec <= 0:
                        errors['amount'] = _('Le montant doit être supérieur à 0.')
                    elif amount_dec != amount_dec.to_integral_value():
                        errors['amount'] = _('Le montant doit être un nombre entier de XAF.')
                except (ValueError, TypeError):
                    errors['amount'] = _('Montant invalide.')

            if not errors:
                if is_online:
                    min_amount, max_amount = OnlineDepositService.get_deposit_limits()
                    if max_amount is not None and amount_dec > max_amount:
                        errors['amount'] = _('Le montant maximum est {amount} XAF.').format(amount=max_amount)
                    elif min_amount is not None and amount_dec < min_amount:
                        errors['amount'] = _('Le montant minimum de dépôt est {amount} XAF.').format(
                            amount=min_amount
                        )
                else:
                    if pm.max_amount and amount_dec > pm.max_amount:
                        errors['amount'] = _('Le montant maximum est {amount} XAF.').format(amount=pm.max_amount)

                    try:
                        min_deposit_limit = Decimal(Setting.objects.get(key='minimum_deposit').value)
                    except Setting.DoesNotExist:
                        min_deposit_limit = Decimal('2500')
                    if amount_dec < min_deposit_limit:
                        errors['amount'] = _('Le montant minimum de dépôt est {amount} XAF.').format(
                            amount=min_deposit_limit
                        )

            if errors:
                return render(request, 'deposits/create.html', _deposit_form_context(
                    errors=errors,
                    form_data={
                        'payment_method_id': selection,
                        'phone_digits': phone_digits,
                        'amount': amount,
                    },
                ))

            if is_online:
                # Paiement automatique Tara Money : le serveur cree le depot
                # puis demande le debit (Mobile Money / Wave) ou genere le lien
                # securise. Aucun credit n'est decide par le navigateur.
                try:
                    deposit, attempt, pay_url = OnlineDepositService.initiate(
                        user=request.user,
                        amount=amount_dec,
                        phone_number=f'+237{phone_digits}',
                        channel=online_channel,
                        ip_address=request.META.get('REMOTE_ADDR'),
                    )
                except ValueError as e:
                    messages.error(request, str(e))
                    return redirect('deposit_create')

                AnalyticsService.track_event('DEPOSIT_CREATED', request.user, request)
                if 'deposit_data' in request.session:
                    del request.session['deposit_data']

                if pay_url:
                    # Wave / carte : redirection vers la page de paiement Tara.
                    return redirect(pay_url)

                # Debit direct : la demande part sur le telephone du payeur et
                # la confirmation arrive par webhook. On affiche la page du
                # depot, qui interroge le serveur jusqu'au credit.
                messages.info(request, _(
                    'Une demande de paiement a été envoyée sur votre téléphone. '
                    'Validez-la puis revenez ici : votre compte sera crédité '
                    'automatiquement dès confirmation du paiement.'
                ))
                return redirect('deposit_detail', pk=deposit.pk)

            ussd_code = pm.generate_ussd_code(amount)
            request.session['deposit_data'] = {
                'payment_method_id': int(selection),
                'payment_method_name': pm.name,
                'phone_digits': phone_digits,
                'phone_number': f'+237{phone_digits}',
                'amount': amount,
                'reception_number': pm.phone_number,
                'reception_name': pm.reception_name or pm.phone_number,
                'ussd_code': ussd_code,
                'min_deposit': _min_deposit_value(),
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

    return render(request, 'deposits/create.html', _deposit_form_context())


@login_required_custom
def deposit_detail(request, pk):
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)
    from transactions.views.online_deposits import render_deposit_detail
    return render_deposit_detail(request, deposit)


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
