from django import forms
from django.utils.translation import gettext_lazy as _
from transactions.models import Deposit, PaymentMethod

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'
DARK_INPUT_SM = 'w-full px-4 py-2 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class DepositForm(forms.Form):
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        label=_('Méthode de paiement'),
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
            'min': '1',
        })
    )
    transaction_id = forms.CharField(
        label=_('ID/Numéro de transaction'),
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT,
            'placeholder': 'Ex: TXN123456789',
        }),
        help_text=_('Fournissez le numéro de transaction de votre paiement.')
    )
    proof = forms.ImageField(
        label=_('Preuve de paiement'),
        required=False,
        widget=forms.FileInput(attrs={
            'class': DARK_INPUT,
            'accept': 'image/*,.pdf',
        }),
        help_text=_('Capture d\'écran ou reçu du paiement (JPG, PNG, WEBP, PDF). Max 5Mo.')
    )


class DepositSearchForm(forms.Form):
    q = forms.CharField(
        label=_('Rechercher'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT_SM,
            'placeholder': 'Rechercher par utilisateur, transaction ID...',
        })
    )
    status = forms.ChoiceField(
        label=_('Statut'),
        required=False,
        choices=[('', _('Tous'))] + Deposit.Status.choices,
        widget=forms.Select(attrs={'class': DARK_INPUT_SM}),
    )
