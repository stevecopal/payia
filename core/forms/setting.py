from django import forms
from django.utils.translation import gettext_lazy as _
from core.models import Setting

DARK_INPUT = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class SettingForm(forms.Form):
    def __init__(self, *args, settings_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if settings_queryset:
            for setting in settings_queryset:
                field_name = f'setting_{setting.key}'
                if setting.setting_type == 'INTEGER':
                    self.fields[field_name] = forms.IntegerField(
                        label=setting.key.replace('_', ' ').title(),
                        initial=int(setting.value),
                        required=False,
                        widget=forms.NumberInput(attrs={'class': DARK_INPUT}),
                    )
                elif setting.setting_type == 'DECIMAL':
                    self.fields[field_name] = forms.DecimalField(
                        label=setting.key.replace('_', ' ').title(),
                        initial=setting.value,
                        required=False,
                        max_digits=12,
                        decimal_places=2,
                        widget=forms.NumberInput(attrs={'class': DARK_INPUT, 'step': '0.01'}),
                    )
                elif setting.setting_type == 'BOOLEAN':
                    self.fields[field_name] = forms.BooleanField(
                        label=setting.key.replace('_', ' ').title(),
                        initial=setting.value.lower() in ('true', '1', 'yes'),
                        required=False,
                        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-600 bg-gray-900 text-green-600 focus:ring-green-500'}),
                    )
                else:
                    self.fields[field_name] = forms.CharField(
                        label=setting.key.replace('_', ' ').title(),
                        initial=setting.value,
                        required=False,
                        widget=forms.TextInput(attrs={'class': DARK_INPUT}),
                    )
