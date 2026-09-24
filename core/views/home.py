from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from ai_services.models import AiRental, AiRevenue
from analytics.services.analytics_service import AnalyticsService


def _landing_context():
    """Contexte de la landing : chiffres réels + activité réellement enregistrée.

    Aucune donnée marketing n'est fabriquée : tout provient des modèles
    de l'application. `partners` et `testimonials` restent vides tant
    qu'ils ne sont pas fournis par l'entreprise (aucun logo/témoignage inventé).
    """
    User = get_user_model()
    now = timezone.now()

    member_count = User.objects.filter(is_active=True).count()
    active_cycles = AiRental.objects.filter(status__iexact='active').count()
    distribution_count = AiRevenue.objects.filter(status__iexact='credited').count()

    stats = {
        'members': member_count,
        'active_cycles': active_cycles,
        'distributions': distribution_count,
    }

    # --- Activité réelle, anonymisée (ni nom, ni montant) ---
    events = []

    for joined in User.objects.filter(is_active=True).order_by('-date_joined').values_list('date_joined', flat=True)[:15]:
        events.append({
            'type': 'member',
            'label': _('Nouveau membre enregistré'),
            'ts': joined,
        })

    for created in AiRental.objects.filter(status__iexact='active').order_by('-created_at').values_list('created_at', flat=True)[:15]:
        events.append({
            'type': 'cycle_started',
            'label': _('Nouveau cycle enregistré'),
            'ts': created,
        })

    for ended in AiRental.objects.filter(status__iexact='expired').order_by('-updated_at').values_list('updated_at', flat=True)[:10]:
        events.append({
            'type': 'cycle_completed',
            'label': _('Cycle terminé'),
            'ts': ended,
        })

    for credited in AiRevenue.objects.filter(status__iexact='credited').order_by('-credited_at').values_list('credited_at', flat=True)[:10]:
        if credited is None:
            continue
        events.append({
            'type': 'distribution',
            'label': _('Distribution enregistrée'),
            'ts': credited,
        })

    events.sort(key=lambda e: e['ts'] or now, reverse=True)

    activity = [
        {
            'type': e['type'],
            'label': e['label'],
            'when': naturaltime(e['ts']) if e['ts'] else '',
        }
        for e in events[:8]
    ]

    # Sous-ensemble récent, utilisé par les notifications flottantes (home.js).
    fresh_cutoff = now - timedelta(days=14)
    activity_fresh = [
        {
            'type': e['type'],
            'label': e['label'],
            'when': naturaltime(e['ts']) if e['ts'] else '',
        }
        for e in events
        if e['ts'] is not None and e['ts'] >= fresh_cutoff
    ][:6]

    return {
        'landing_stats': stats,
        'landing_activity': activity,
        'landing_activity_fresh': activity_fresh,
        # Renseigner ces listes lorsque l'entreprise fournira les éléments réels :
        # partners: [{'name': ..., 'logo': ..., 'url': ...}, ...]
        # testimonials: [{'name': ..., 'role': ..., 'quote': ..., 'photo': ...}, ...]
        'partners': [],
        'testimonials': [],
    }


def home(request):
    AnalyticsService.track_event('PAGE_VIEW', request.user if request.user.is_authenticated else None, request)
    return render(request, 'public/home.html', _landing_context())


def about(request):
    return render(request, 'public/about.html')


def features(request):
    return render(request, 'public/features.html')


def ai_catalog_public(request):
    return render(request, 'public/ai.html')


def referral_page(request):
    return render(request, 'public/referral.html')


def faq(request):
    return render(request, 'public/faq.html')


def contact(request):
    return render(request, 'public/contact.html')


def download(request):
    return render(request, 'public/download.html')


def terms(request):
    return render(request, 'public/terms.html')


def privacy(request):
    return render(request, 'public/privacy.html')
