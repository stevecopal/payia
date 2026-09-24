from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext as _

from ai_services.models import AiRental, AiRevenue
from analytics.services.analytics_service import AnalyticsService


def _static_partners():
    """Partenaires affichés en bandeau déroulant sur le home.

    Données statiques de démarrage : logos officiels provenant de Wikimedia
    Commons (crédits et mentions dans static/images/partners/CREDITS.txt).
    À remplacer par les partenaires réels de PAYIA (mêmes clés :
    name, tagline, logo, url).
    """
    return [
        {'name': 'Microsoft', 'tagline': _('Logiciels et cloud'),
         'logo': static('images/partners/microsoft.svg'),
         'url': 'https://www.microsoft.com'},
        {'name': 'NVIDIA', 'tagline': _('Calcul pour l’IA'),
         'logo': static('images/partners/nvidia.svg'),
         'url': 'https://www.nvidia.com'},
        {'name': 'Google Cloud', 'tagline': _('Infrastructure cloud'),
         'logo': static('images/partners/googlecloud.svg'),
         'url': 'https://cloud.google.com'},
        {'name': 'HUMAIN', 'tagline': _('Intelligence artificielle · Arabie saoudite'),
         'logo': static('images/partners/humain.svg'),
         'url': 'https://www.humain.ai'},
        {'name': 'stc', 'tagline': _('Télécoms et numérique · Arabie saoudite'),
         'logo': static('images/partners/stc.svg'),
         'url': 'https://www.stc.com.sa'},
    ]


def _static_testimonials():
    """Témoignages statiques (démo) affichés en bandeau déroulant sur le home.

    Portraits sous licence Pexels, libres d'usage (crédits dans
    static/images/testimonials/CREDITS.txt). Ton factuel et quotidien,
    sans promesse de rendement, cohérent avec la ligne de la section
    « Confiance ».
    Clés : name, initials, role, quote, rating (1-5), photo (optionnelle).
    """
    return [
        {
            'name': 'Moussa Ouédraogo',
            'initials': 'MO',
            'role': _('entrepreuneur'),
            'quote': _('Je me suis inscrit un dimanche soir, depuis mon téléphone. '
                       'J’ai vérifié le fonctionnement des cycles ligne par ligne avant de valider : '
                       'tout était écrit, sans zone d’ombre.'),
            'rating': 5,
            'photo': static('images/testimonials/moussa-ouedraogo.jpg'),
        },
        {
            'name': 'Sokhna Diop',
            'initials': 'SD',
            'role': _('Responsable relation clients '),
            'quote': _('L’interface est claire, même sur un vieux téléphone. '
                       'J’ai retrouvé l’historique de mes opérations tout de suite, sans appeler personne.'),
            'rating': 5,
            'photo': static('images/testimonials/sokhna-diop.jpg'),
        },
        {
            'name': 'Ibrahim Coulibaly',
            'initials': 'IC',
            'role': _('manager '),
            'quote': _('Ce que j’apprécie, c’est qu’on ne nous promette rien : on nous explique '
                       'le cadre, les durées, les conditions. Mon associé et moi avons lu avant '
                       'de nous engager, et tout était exactement comme annoncé.'),
            'rating': 5,
            'photo': static('images/testimonials/ibrahim-coulibaly.jpg'),
        },
        {
            'name': 'Nadia Hassan',
            'initials': 'NH',
            'role': _('Analyste comptable '),
            'quote': _('J’ai posé une question sur un relevé un mardi matin, '
                       'j’avais une réponse humaine avant midi. C’est ce genre de détail '
                       'qui fait la différence sur la durée.'),
            'rating': 5,
            'photo': static('images/testimonials/nadia-hassan.jpg'),
        },
        {
            'name': 'Marie-Josée Kouassi',
            'initials': 'MK',
            'role': _('Directrice administrative '),
            'quote': _('Je suis nos cycles depuis mon espace, tout est daté. '
                       'Quand j’ai eu un doute, le support a pris le temps de me répondre proprement, '
                       'pas avec une réponse automatique.'),
            'rating': 5,
            'photo': static('images/testimonials/marie-josee-kouassi.jpg'),
        },
    ]


def _landing_context():
    """Contexte de la landing : chiffres réels + activité réellement enregistrée.

    Aucune donnée marketing n'est fabriquée : les compteurs proviennent des
    modèles de l'application. `partners` et `testimonials` sont pour le moment
    des données statiques de démarrage (voir `_static_partners` et
    `_static_testimonials`), à remplacer par les éléments réels de l'entreprise.
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
        # Données statiques de démarrage (bandeaux déroulants du home).
        # Pour des éléments réels, remplacer le contenu de ces deux listes :
        # partners: [{'name': ..., 'tagline': ..., 'logo': ..., 'url': ...}, ...]
        # testimonials: [{'name': ..., 'initials': ..., 'role': ..., 'quote': ...,
        #                 'rating': ..., 'photo': ...}, ...]
        'partners': _static_partners(),
        'testimonials': _static_testimonials(),
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
