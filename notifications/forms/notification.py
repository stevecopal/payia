from django import forms
from django.utils.translation import gettext_lazy as _

DARK_INPUT_SM = 'w-full px-4 py-2 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class NotificationFilterForm(forms.Form):
    filter_type = forms.ChoiceField(
        label=_('Filtrer'),
        required=False,
        choices=[
            ('', 'Toutes'),
            ('unread', 'Non lues'),
            ('deposit', 'Dépôts'),
            ('withdrawal', 'Retraits'),
            ('ai', 'Intelligence artificielle'),
            ('referral', 'Parrainage'),
            ('system', 'Système'),
        ],
        widget=forms.Select(attrs={'class': DARK_INPUT_SM}),
    )
