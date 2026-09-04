from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

def user_passes_test_custom(test_func, redirect_url='/', message_text=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if test_func(request):
                return view_func(request, *args, **kwargs)
            if message_text:
                messages.error(request, message_text)
            return redirect(redirect_url)
        return wrapper
    return decorator

def login_required_custom(view_func):
    return user_passes_test_custom(
        lambda r: r.user.is_authenticated,
        redirect_url='/auth/login/',
        message_text=_('Vous devez être connecté pour accéder à cette page.')
    )(view_func)

def admin_required(view_func):
    def check(request, *args, **kwargs):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.slug in ['admin', 'super-admin'])
        )
    return user_passes_test_custom(
        check,
        redirect_url='/',
        message_text=_('Accès réservé aux administrateurs.')
    )(view_func)

def super_admin_required(view_func):
    def check(request, *args, **kwargs):
        return request.user.is_authenticated and request.user.is_superuser
    return user_passes_test_custom(
        check,
        redirect_url='/',
        message_text=_('Accès réservé aux super administrateurs.')
    )(view_func)

def has_permission(perm_codename):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/auth/login/')
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if hasattr(request.user, 'role') and request.user.role:
                if request.user.role.permissions.filter(codename=perm_codename).exists():
                    return view_func(request, *args, **kwargs)
            messages.error(request, _('Vous n\'avez pas la permission nécessaire.'))
            return redirect('/')
        return wrapper
    return decorator

def profile_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/auth/login/')
        try:
            profile = request.user.profile
            if not profile.is_profile_complete:
                messages.warning(request, _('Veuillez compléter votre profil avant de continuer.'))
                return redirect('profile_complete')
        except Exception:
            messages.warning(request, _('Veuillez créer votre profil avant de continuer.'))
            return redirect('profile_complete')
        return view_func(request, *args, **kwargs)
    return wrapper
