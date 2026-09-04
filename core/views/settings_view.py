from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from core.permissions import login_required_custom


@login_required_custom
def settings_view(request):
    return render(request, 'profile/settings.html')


@login_required_custom
def security_settings(request):
    return render(request, 'profile/security.html')
