from django.shortcuts import render
from analytics.services.analytics_service import AnalyticsService


def home(request):
    AnalyticsService.track_event('PAGE_VIEW', request.user if request.user.is_authenticated else None, request)
    return render(request, 'public/home.html')


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
