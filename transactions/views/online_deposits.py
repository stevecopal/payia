"""Vues du parcours de depot en ligne (Tara Money) + webhook.

Toutes les decisions financieres sont prises cote serveur : la redirection
du navigateur ne fait que declencher une **verification aupres de Tara
Money**, jamais un credit direct.
"""

import logging

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from analytics.services.analytics_service import AnalyticsService
from core.permissions import login_required_custom
from transactions.models import Deposit
from transactions.services.online_deposit_service import OnlineDepositService

logger = logging.getLogger('transactions')
security_logger = logging.getLogger('security')

MAX_VERIFY_PER_MINUTE = 30
MAX_RETRY_PER_10_MIN = 10
MAX_WEBHOOK_PER_MINUTE = 120


def build_detail_context(deposit):
    """Contexte partage par toutes les vues de detail d'un depot."""
    is_online = deposit.payment_method.slug == OnlineDepositService.PAYMENT_METHOD_SLUG
    attempts = [
        {
            'reference': a.reference,
            'status': a.status,
            'conflict': a.conflict,
            'created_at': a.created_at,
            'expires_at': a.expires_at,
            'failure_reason': a.failure_reason,
        }
        for a in deposit.attempts.all()[:10]
    ]
    pending = deposit.status == Deposit.Status.PENDING_REVIEW
    return {
        'deposit': deposit,
        'is_online': is_online,
        'attempts': attempts,
        'can_retry': is_online and pending and OnlineDepositService.is_available(),
        'poll_status': is_online and pending,
    }


def render_deposit_detail(request, deposit, **extra):
    context = build_detail_context(deposit)
    context.update(extra)
    return render(request, 'deposits/detail.html', context)


@login_required_custom
def deposit_payment_result(request, pk):
    """URL de retour apres paiement : verification cote prestataire."""
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)
    outcome = None

    if deposit.status == Deposit.Status.PENDING_REVIEW and deposit.attempts.exists():
        if OnlineDepositService.allow_request(
            'verify', str(request.user.pk), MAX_VERIFY_PER_MINUTE, 60
        ):
            latest = deposit.attempts.order_by('-created_at').first()
            outcome = OnlineDepositService.verify_attempt(
                latest.reference, source='return_url'
            )
            _apply_outcome_message(request, deposit, outcome)
        else:
            messages.info(request, _('Veuillez patienter quelques secondes avant de revérifier.'))

    return render_deposit_detail(
        request, deposit, payment_result=outcome, just_returned=True
    )


@login_required_custom
def deposit_status_json(request, pk):
    """Statut en temps reel (le serveur consulte Tara Money, jamais le JS)."""
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)
    context = build_detail_context(deposit)
    return JsonResponse({
        'deposit_status': deposit.status,
        'completed': deposit.status == Deposit.Status.COMPLETED,
        'rejected': deposit.status == Deposit.Status.REJECTED,
        'attempts': [
            {
                'reference': a['reference'],
                'status': a['status'],
                'conflict': a['conflict'],
            }
            for a in context['attempts']
        ],
        'can_retry': context['can_retry'],
    })


@login_required_custom
@require_POST
def deposit_verify(request, pk):
    """Bouton « Verifier le paiement » : interroge Tara Money."""
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)

    if deposit.status != Deposit.Status.PENDING_REVIEW:
        messages.info(request, _('Ce dépôt est déjà traité.'))
        return render_deposit_detail(request, deposit)

    if not OnlineDepositService.allow_request(
        'verify', str(request.user.pk), MAX_VERIFY_PER_MINUTE, 60
    ):
        messages.warning(request, _('Trop de vérifications. Réessayez dans une minute.'))
        return render_deposit_detail(request, deposit)

    latest = deposit.attempts.order_by('-created_at').first()
    if latest is None:
        messages.warning(request, _('Aucune tentative de paiement en cours.'))
        return render_deposit_detail(request, deposit)

    outcome = OnlineDepositService.verify_attempt(latest.reference, source='manual_check')
    _apply_outcome_message(request, deposit, outcome)
    return render_deposit_detail(request, deposit, payment_result=outcome)


@login_required_custom
@require_POST
def deposit_retry_payment(request, pk):
    """Nouvelle tentative de paiement pour un depot toujours en attente."""
    deposit = get_object_or_404(Deposit, pk=pk, user=request.user)

    if not OnlineDepositService.allow_request(
        'retry', str(request.user.pk), MAX_RETRY_PER_10_MIN, 600
    ):
        messages.warning(request, _('Trop de tentatives. Réessayez dans quelques minutes.'))
        return render_deposit_detail(request, deposit)

    try:
        attempt, pay_url = OnlineDepositService.retry(deposit, request.user)
        AnalyticsService.track_event('DEPOSIT_CREATED', request.user, request)
        messages.success(request, _('Nouveau lien de paiement généré.'))
        return HttpResponseRedirect(pay_url)
    except ValueError as exc:
        messages.error(request, str(exc))
        return render_deposit_detail(request, deposit)


def _apply_outcome_message(request, deposit, outcome):
    if outcome == 'credited':
        messages.success(request, _('Paiement confirmé. Votre portefeuille a été crédité.'))
    elif outcome == 'already_credited':
        messages.success(request, _('Ce dépôt a déjà été crédité.'))
    elif outcome == 'failed':
        messages.error(request, _('Le paiement a échoué. Vous pouvez réessayer.'))
    elif outcome == 'pending':
        messages.info(request, _('Paiement toujours en attente. Réessayez dans quelques instants.'))
    elif outcome == 'throttled':
        messages.info(request, _('Vérification récente. Réessayez dans quelques secondes.'))
    elif outcome == 'unverified':
        messages.warning(
            request,
            _('Vérification impossible pour le moment. Aucun crédit effectué, réessayez plus tard.'),
        )
    elif outcome == 'amount_mismatch':
        security_logger.warning(
            'Montant incoherent signale pour le depot %s (aucun credit).', deposit.pk
        )
        messages.error(
            request,
            _('Le montant reçu ne correspond pas à la demande. Contactez le support.'),
        )
    elif outcome == 'conflict':
        messages.warning(
            request,
            _('Paiement reçu mais crédit en attente de vérification manuelle. Contactez le support.'),
        )


@csrf_exempt
@require_POST
def tara_webhook(request):
    """Notification Tara Money (sans CSRF : authentifiee par jeton + statut API)."""
    if not OnlineDepositService.allow_request(
        'webhook', request.META.get('REMOTE_ADDR', 'unknown'),
        MAX_WEBHOOK_PER_MINUTE, 60
    ):
        return JsonResponse({'detail': 'rate_limited'}, status=429)

    status_code, payload = OnlineDepositService.handle_webhook(request)
    return JsonResponse(payload, status=status_code)
