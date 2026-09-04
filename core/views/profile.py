from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from core.forms.profile import ProfileForm, WithdrawalInfoForm, ProfilePictureForm
from core.models import AuditLog, UserProfile
from core.permissions import login_required_custom


@login_required_custom
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    wallet = None
    try:
        wallet = request.user.wallet
    except Exception:
        pass

    return render(request, 'profile/profile.html', {
        'profile': profile,
        'wallet': wallet,
    })


@login_required_custom
def profile_edit(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
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
            profile.is_profile_complete = True
            profile.save()
            messages.success(request, _('Profil complété avec succès.'))
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
            form.save()
            messages.success(request, _('Informations de retrait mises à jour.'))
            return redirect('profile')
    else:
        form = WithdrawalInfoForm(instance=profile)
    return render(request, 'profile/withdrawal_info.html', {'form': form})
