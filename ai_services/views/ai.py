import json
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from ai_services.models import AiOffer, AiCategory, AiModel, AiRental, AiRevenue
from ai_services.services.ai_service import AiService
from core.permissions import login_required_custom
from analytics.services.analytics_service import AnalyticsService


def ai_catalog(request):
    offers = AiOffer.objects.filter(is_active=True).select_related('ai_model', 'category')

    category_slug = request.GET.get('category')
    if category_slug:
        offers = offers.filter(category__slug=category_slug)

    model_slug = request.GET.get('model')
    if model_slug:
        offers = offers.filter(ai_model__slug=model_slug)

    min_price = request.GET.get('min_price')
    if min_price:
        offers = offers.filter(price__gte=min_price)

    max_price = request.GET.get('max_price')
    if max_price:
        offers = offers.filter(price__lte=max_price)

    sort = request.GET.get('sort', '')
    if sort == 'price_asc':
        offers = offers.order_by('price')
    elif sort == 'price_desc':
        offers = offers.order_by('-price')
    elif sort == 'newest':
        offers = offers.order_by('-created_at')
    elif sort == 'duration':
        offers = offers.order_by('duration_days')
    else:
        offers = offers.order_by('-is_featured', '-total_rentals')

    categories = AiCategory.objects.filter(is_active=True)
    models = AiModel.objects.filter(is_active=True)

    return render(request, 'ai/catalog.html', {
        'offers': offers,
        'categories': categories,
        'models': models,
    })


def ai_offer_detail(request, slug):
    offer = get_object_or_404(
        AiOffer.objects.select_related('ai_model', 'category'),
        slug=slug, is_active=True
    )
    AnalyticsService.track_event('AI_VIEWED', request.user if request.user.is_authenticated else None, request)

    can_rent = False
    has_active_rental = False
    if request.user.is_authenticated:
        from wallet.services.wallet_service import WalletService
        wallet = WalletService.get_wallet(request.user)
        can_rent = wallet.available_balance >= offer.price
        has_active_rental = AiService.get_active_rentals(request.user).filter(offer=offer).exists()

    return render(request, 'ai/detail.html', {
        'offer': offer,
        'can_rent': can_rent,
        'has_active_rental': has_active_rental,
    })


@login_required_custom
def ai_rent(request, slug):
    offer = get_object_or_404(AiOffer, slug=slug, is_active=True)

    if request.method == 'POST':
        try:
            rental = AiService.rent_offer(request.user, offer.pk)
            AnalyticsService.track_event('AI_RENTED', request.user, request, {'offer_id': offer.pk})
            messages.success(request, _('Offre IA louée avec succès !'))
            return redirect('ai_my_rentals')
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('ai_offer_detail', slug=slug)


@login_required_custom
def ai_my_rentals(request):
    rentals = AiService.get_user_rentals(request.user)
    active = rentals.filter(status=AiRental.Status.ACTIVE).select_related('offer')
    expired = rentals.filter(status=AiRental.Status.EXPIRED)

    now = timezone.now()
    active_data = []
    for rental in active:
        next_payment_at = rental.next_payment_at
        if next_payment_at and next_payment_at <= now:
            next_payment_at = None

        active_data.append({
            'rental': rental,
            'next_payment_at': next_payment_at,
            'next_payment_ts': int(next_payment_at.timestamp() * 1000) if next_payment_at else 0,
            'end_ts': int(rental.end_date.timestamp() * 1000),
        })

    return render(request, 'ai/my_rentals.html', {
        'active_data': active_data,
        'expired_rentals': expired,
    })


@login_required_custom
def ai_rental_detail(request, pk):
    rental = get_object_or_404(
        AiRental.objects.select_related('offer', 'offer__ai_model'),
        pk=pk, user=request.user
    )
    offer = rental.offer

    frequency_labels = {
        'daily': _('Quotidien'),
        'weekly': _('Hebdomadaire'),
        'monthly': _('Mensuel'),
    }
    revenue_type_labels = {
        'fixed': _('Fixe'),
        'percentage': _('Pourcentage'),
        'variable': _('Variable'),
    }

    now = timezone.now()
    next_payment_at = rental.next_payment_at
    if next_payment_at and next_payment_at <= now:
        next_payment_at = None

    interval = AiService.FREQUENCY_INTERVALS.get(
        offer.revenue_frequency, timedelta(days=1)
    ) if hasattr(AiService, 'FREQUENCY_INTERVALS') else timedelta(days=1)

    from ai_services.services.ai_service import FREQUENCY_INTERVALS
    interval = FREQUENCY_INTERVALS.get(offer.revenue_frequency, timedelta(days=1))

    total_periods = int((rental.end_date - rental.start_date) / interval) if interval.total_seconds() > 0 else 0
    payments_received = rental.payment_count
    payments_remaining = max(0, total_periods - payments_received)

    revenue_per_period = rental.earning_amount if rental.earning_amount else offer.get_expected_revenue()

    remaining_total = (rental.end_date - now).total_seconds()
    remaining_days = int(remaining_total // 86400)
    remaining_hours = int((remaining_total % 86400) // 3600)
    remaining_minutes = int((remaining_total % 3600) // 60)

    payment_progress = 0
    if total_periods > 0:
        payment_progress = min(100, int(payments_received * 100 / total_periods))

    context = {
        'rental': rental,
        'offer': offer,
        'frequency_label': frequency_labels.get(offer.revenue_frequency, offer.revenue_frequency),
        'revenue_type_label': revenue_type_labels.get(offer.revenue_type, offer.revenue_type),
        'revenue_per_period': revenue_per_period,
        'next_payment': next_payment_at,
        'next_payment_timestamp': int(next_payment_at.timestamp() * 1000) if next_payment_at else 0,
        'now_timestamp': int(now.timestamp() * 1000),
        'end_timestamp': int(rental.end_date.timestamp() * 1000),
        'start_timestamp': int(rental.start_date.timestamp() * 1000),
        'payments_received': payments_received,
        'payments_remaining': payments_remaining,
        'total_periods': total_periods,
        'payment_progress': payment_progress,
        'remaining_days': remaining_days,
        'remaining_hours': remaining_hours,
        'remaining_minutes': remaining_minutes,
    }
    return render(request, 'ai/rental_detail.html', context)


@login_required_custom
@require_GET
def ai_rental_sync(request, pk):
    rental = get_object_or_404(
        AiRental.objects.select_related('offer'),
        pk=pk, user=request.user
    )
    now = timezone.now()

    return JsonResponse({
        'rental_id': rental.pk,
        'status': rental.status,
        'next_payment_at': rental.next_payment_at.isoformat() if rental.next_payment_at else None,
        'next_payment_ts': int(rental.next_payment_at.timestamp() * 1000) if rental.next_payment_at else 0,
        'last_payment_at': rental.last_payment_at.isoformat() if rental.last_payment_at else None,
        'payment_count': rental.payment_count,
        'total_revenue_earned': str(rental.total_revenue_earned),
        'earning_amount': str(rental.earning_amount),
        'end_date': rental.end_date.isoformat(),
        'now': now.isoformat(),
        'now_ts': int(now.timestamp() * 1000),
    })
