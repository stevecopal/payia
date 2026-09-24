from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from ai_services.services.ai_service import AiService
from core.forms.profile import ProfileForm, WithdrawalInfoForm, ProfilePictureForm
from core.models import AuditLog, UserProfile
from core.permissions import login_required_custom
from referrals.services.referral_service import ReferralService


@login_required_custom
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    wallet = None
    try:
        wallet = request.user.wallet
    except Exception:
        pass

    # Complétion du profil : identité, email, informations de retrait.
    completion_steps = [
        {
            'key': 'identity',
            'done': bool(profile.first_name.strip() and profile.last_name.strip()),
            'target': 'profile_edit',
        },
        {
            'key': 'email',
            'done': bool(profile.email.strip()),
            'target': 'profile_edit',
        },
        {
            'key': 'withdrawal',
            'done': bool(
                profile.withdrawal_phone_number.strip()
                and profile.withdrawal_account_name.strip()
            ),
            'target': 'withdrawal_info',
        },
    ]
    done_steps = sum(1 for step in completion_steps if step['done'])
    completion_percent = round(done_steps * 100 / len(completion_steps))

    referral_stats = ReferralService.get_referral_stats(request.user)

    return render(request, 'profile/profile.html', {
        'profile': profile,
        'wallet': wallet,
        'completion_steps': completion_steps,
        'completion_percent': completion_percent,
        'active_machines_count': AiService.get_active_rentals(request.user).count(),
        'referrals_count': referral_stats['total'],
        'referral_link': ReferralService.get_referral_link(request.user, request),
    })


@login_required_custom
def profile_edit(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            profile.update_profile_status()
            messages.success(request, _('Profil mis à jour.'))
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'profile/edit.html', {'form': form})


@login_required_custom
def profile_complete(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.update_profile_status()
            if profile.profile_status == 'EN_ATTENTE':
                messages.success(request, _('Profil complété. Veuillez ajouter vos informations de retrait.'))
            elif profile.profile_status == 'VERIFIED':
                messages.success(request, _('Profil vérifié avec succès.'))
            else:
                messages.success(request, _('Profil mis à jour.'))
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'profile/complete.html', {'form': form})


@login_required_custom
def withdrawal_info_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if profile.withdrawal_phone_number and profile.withdrawal_account_name:
        if request.method == 'POST':
            messages.warning(request, _('Les informations de retrait ont déjà été enregistrées et ne peuvent pas être modifiées.'))
            return redirect('profile')
        messages.info(request, _('Vos informations de retrait sont déjà enregistrées.'))
        return redirect('profile')

    if request.method == 'POST':
        form = WithdrawalInfoForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.update_profile_status()
            if profile.profile_status == 'VERIFIED':
                messages.success(request, _('Informations de retrait enregistrées. Profil vérifié.'))
            else:
                messages.success(request, _('Informations de retrait mises à jour.'))
            return redirect('profile')
    else:
        form = WithdrawalInfoForm(instance=profile)
    return render(request, 'profile/withdrawal_info.html', {'form': form})
