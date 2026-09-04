from django import forms
from django.utils.translation import gettext_lazy as _
from core.models import UserProfile

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': _('Prénom'),
            'last_name': _('Nom'),
            'email': _('Email'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': DARK_INPUT, 'placeholder': 'Votre prénom'}),
            'last_name': forms.TextInput(attrs={'class': DARK_INPUT, 'placeholder': 'Votre nom'}),
            'email': forms.EmailInput(attrs={'class': DARK_INPUT, 'placeholder': 'email@exemple.com'}),
        }


class WithdrawalInfoForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['withdrawal_phone_number', 'withdrawal_account_name']
        labels = {
            'withdrawal_phone_number': _('Numéro de retrait'),
            'withdrawal_account_name': _('Nom du titulaire du compte'),
        }
        widgets = {
            'withdrawal_phone_number': forms.TextInput(attrs={
                'class': DARK_INPUT,
                'placeholder': '+2376XXXXXXXX',
            }),
            'withdrawal_account_name': forms.TextInput(attrs={
                'class': DARK_INPUT,
                'placeholder': 'Nom complet',
            }),
        }


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_picture']
        labels = {
            'profile_picture': _('Photo de profil'),
        }
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': DARK_INPUT,
                'accept': 'image/*',
            }),
        }
