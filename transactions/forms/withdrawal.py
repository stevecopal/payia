from django import forms
from django.utils.translation import gettext_lazy as _
from transactions.models import Withdrawal, PaymentMethod

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'
DARK_INPUT_SM = 'w-full px-4 py-2 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class WithdrawalForm(forms.Form):
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        label=_('Méthode de retrait'),
        widget=forms.Select(attrs={'class': DARK_INPUT}),
        empty_label=_('Choisir une méthode'),
    )
    amount = forms.DecimalField(
        label=_('Montant'),
        min_value=1,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': DARK_INPUT,
            'placeholder': '0.00',
        })
    )
    withdrawal_number = forms.CharField(
        label=_('Numéro de retrait'),
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT,
            'placeholder': '+2376XXXXXXXX',
        })
    )
    withdrawal_account_name = forms.CharField(
        label=_('Nom du titulaire'),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT,
            'placeholder': 'Nom du titulaire du compte',
        })
    )
    note = forms.CharField(
        label=_('Note (optionnel)'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': DARK_INPUT,
            'rows': 3,
            'placeholder': 'Note optionnelle...',
        })
    )


class WithdrawalSearchForm(forms.Form):
    q = forms.CharField(
        label=_('Rechercher'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT_SM,
            'placeholder': 'Rechercher...',
        })
    )
    status = forms.ChoiceField(
        label=_('Statut'),
        required=False,
        choices=[('', _('Tous'))] + Withdrawal.Status.choices,
        widget=forms.Select(attrs={'class': DARK_INPUT_SM}),
    )
