import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from core.forms.auth import (
    RegisterForm,
    LoginForm,
    PasswordChangeForm,
    PasswordResetRequestForm,
    PasswordResetForm,
    OTPForm,
)
from core.services.auth_service import AuthService
from core.services.sms_service import get_sms_provider
from core.permissions import login_required_custom

logger = logging.getLogger('core')


def register_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or (
            hasattr(request.user, 'role') and request.user.role
            and request.user.role.slug in ('admin', 'super-admin')
        ):
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            referral_code = request.session.pop('referral_code', None)
            user = AuthService.register_user(
                username=form.cleaned_data['username'],
                phone_number=form.cleaned_data['phone_number'],
                password=form.cleaned_data['password'],
                referral_code=referral_code,
            )
            otp, error = AuthService.generate_otp(
                user, 'REGISTER', AuthService._get_client_ip(request)
            )
            if otp:
                sms = get_sms_provider()
                sms.send_otp(user.phone_number, otp.code)
                request.session['otp_user_id'] = user.pk
                request.session['otp_purpose'] = 'REGISTER'
                messages.success(
                    request,
                    _('Compte créé. Un code de vérification a été envoyé.'),
                )
                return redirect('verify_otp')
            else:
                messages.error(request, error)
    else:
        form = RegisterForm()
    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or (
            hasattr(request.user, 'role') and request.user.role
            and request.user.role.slug in ('admin', 'super-admin')
        ):
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user, error = AuthService.authenticate_user(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user:
                messages.success(request, _('Connexion réussie.'))
                if user.is_superuser or (
                    hasattr(user, 'role') and user.role
                    and user.role.slug in ('admin', 'super-admin')
                ):
                    return redirect('admin_dashboard')
                else:
                    return redirect('dashboard')
            else:
                messages.error(request, error)
    else:
        form = LoginForm()
    return render(request, 'auth/login.html', {'form': form})


@login_required_custom
def logout_view(request):
    if request.method == 'POST':
        AuthService.logout_user(request)
        messages.success(request, _('Déconnexion réussie.'))
        return redirect('home')
    return redirect('home')


def verify_otp_view(request):
    user_id = request.session.get('otp_user_id')
    purpose = request.session.get('otp_purpose', 'LOGIN')

    if not user_id:
        messages.error(request, _('Session expirée. Veuillez recommencer.'))
        return redirect('login')

    from core.models import User
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, _('Utilisateur introuvable.'))
        return redirect('login')

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            success, message = AuthService.verify_otp(user, code, purpose)
            if success:
                from django.contrib.auth import login
                login(request, user)
                del request.session['otp_user_id']
                del request.session['otp_purpose']
                messages.success(request, _('Connexion réussie.'))
                if user.is_superuser or (
                    hasattr(user, 'role') and user.role
                    and user.role.slug in ('admin', 'super-admin')
                ):
                    return redirect('admin_dashboard')
                try:
                    profile = user.profile
                    if not profile.is_profile_complete:
                        return redirect('profile_complete')
                except Exception:
                    return redirect('profile_complete')
                return redirect('dashboard')
            else:
                messages.error(request, message)
    else:
        form = OTPForm()
    return render(request, 'auth/verify_otp.html', {'form': form, 'user': user})


@login_required_custom
def password_change_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            success, message = AuthService.change_password(
                request,
                request.user,
                form.cleaned_data['current_password'],
                form.cleaned_data['new_password'],
            )
            if success:
                messages.success(request, message)
                return redirect('security_settings')
            else:
                messages.error(request, message)
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'auth/password_change.html', {'form': form})


def password_reset_request_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or (
            hasattr(request.user, 'role') and request.user.role
            and request.user.role.slug in ('admin', 'super-admin')
        ):
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            from core.models import User
            user = User.objects.get(username=form.cleaned_data['username'])
            uid, token = AuthService.generate_password_reset_token(user)
            messages.success(
                request,
                _('Un lien de réinitialisation a été généré. '
                  'Vérifiez vos messages.'),
            )
            return redirect('password_reset_confirm', uidb64=uid, token=token)
    else:
        form = PasswordResetRequestForm()
    return render(request, 'auth/password_reset_request.html', {'form': form})


def password_reset_confirm_view(request, uidb64, token):
    user = AuthService.validate_password_reset_token(uidb64, token)
    if not user:
        messages.error(
            request,
            _('Lien de réinitialisation invalide ou expiré.'),
        )
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            success, message = AuthService.reset_password(
                uidb64, token, form.cleaned_data['new_password']
            )
            if success:
                messages.success(request, message)
                return redirect('login')
            else:
                messages.error(request, message)
    else:
        form = PasswordResetForm()
    return render(request, 'auth/password_reset_confirm.html', {'form': form})
