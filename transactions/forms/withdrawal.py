import re
from decimal import Decimal
from django import forms
from django.utils.translation import gettext_lazy as _
from transactions.models import Withdrawal, PaymentMethod
from core.models import Setting

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
            'placeholder': '6XXXXXXXX',
            'readonly': True,
        })
    )
    withdrawal_account_name = forms.CharField(
        label=_('Nom du titulaire'),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT,
            'placeholder': 'Nom du titulaire du compte',
            'readonly': True,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.min_withdrawal = Decimal(Setting.objects.get(key='minimum_withdrawal').value)
        except Setting.DoesNotExist:
            self.min_withdrawal = Decimal('3500')
        self.fields['amount'].widget.attrs['min'] = str(self.min_withdrawal)
        self.fields['amount'].help_text = _('Montant minimum de retrait: {amount} XAF').format(amount=self.min_withdrawal)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount
        if amount < self.min_withdrawal:
            raise forms.ValidationError(
                _('Le montant minimum de retrait est {amount} XAF.').format(amount=self.min_withdrawal)
            )
        return amount

    def clean_withdrawal_number(self):
        phone = self.cleaned_data.get('withdrawal_number', '').strip()
        phone = phone.replace('+237', '').replace(' ', '')
        if not re.match(r'^6\d{8}$', phone):
            raise forms.ValidationError(
                _('Le numéro doit commencer par 6 et contenir exactement 9 chiffres (ex: 6XXXXXXXX).')
            )
        return phone


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
