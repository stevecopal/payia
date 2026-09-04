from django import forms
from django.utils.translation import gettext_lazy as _
from support.models import SupportTicket, SupportMessage

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class SupportTicketForm(forms.Form):
    subject = forms.CharField(
        label=_('Sujet'),
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': DARK_INPUT,
            'placeholder': 'Sujet de votre demande',
        })
    )
    category = forms.ChoiceField(
        label=_('Catégorie'),
        choices=SupportTicket.CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': DARK_INPUT}),
    )
    priority = forms.ChoiceField(
        label=_('Priorité'),
        choices=SupportTicket.PRIORITY_CHOICES,
        initial='MEDIUM',
        widget=forms.Select(attrs={'class': DARK_INPUT}),
    )
    message = forms.CharField(
        label=_('Message'),
        widget=forms.Textarea(attrs={
            'class': DARK_INPUT,
            'rows': 5,
            'placeholder': 'Décrivez votre problème...',
        })
    )
    attachment = forms.FileField(
        label=_('Pièce jointe'),
        required=False,
        widget=forms.FileInput(attrs={
            'class': DARK_INPUT,
        })
    )


class SupportReplyForm(forms.Form):
    message = forms.CharField(
        label=_('Réponse'),
        widget=forms.Textarea(attrs={
            'class': DARK_INPUT,
            'rows': 4,
            'placeholder': 'Votre réponse...',
        })
    )
    attachment = forms.FileField(
        label=_('Pièce jointe'),
        required=False,
        widget=forms.FileInput(attrs={
            'class': DARK_INPUT,
        })
    )
    is_internal_note = forms.BooleanField(
        label=_('Note interne (admin)'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-600 bg-gray-900 text-green-600 focus:ring-green-500'}),
    )


class AdminReplyForm(SupportReplyForm):
    pass
