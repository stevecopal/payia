from django import forms
from django.utils.translation import gettext_lazy as _
from ai_services.models import AiOffer

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'
DARK_INPUT_SM = 'w-full px-4 py-2 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class AiOfferFilterForm(forms.Form):
    q = forms.CharField(
        label=_('Rechercher'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT_SM,
            'placeholder': 'Rechercher une offre IA...',
        })
    )
    category = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    model = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    min_price = forms.DecimalField(
        label=_('Prix minimum'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': DARK_INPUT_SM,
            'placeholder': 'Min',
        })
    )
    max_price = forms.DecimalField(
        label=_('Prix maximum'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': DARK_INPUT_SM,
            'placeholder': 'Max',
        })
    )
    sort = forms.ChoiceField(
        label=_('Trier par'),
        required=False,
        choices=[
            ('', 'Populaire'),
            ('price_asc', 'Prix croissant'),
            ('price_desc', 'Prix décroissant'),
            ('newest', 'Plus récent'),
            ('duration', 'Durée'),
        ],
        widget=forms.Select(attrs={'class': DARK_INPUT_SM}),
    )
