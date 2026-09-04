import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.validators import normalize_phone_number, validate_cameroun_phone_number

User = get_user_model()

INPUT_CLASSES = 'w-full px-4 py-3 bg-gray-900 border border-gray-700 text-white rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition-all placeholder:text-gray-500'


class RegisterForm(forms.Form):
    username = forms.CharField(
        label=_('Nom d\'utilisateur'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'ex: jean123',
            'autocomplete': 'username',
        }),
    )
    phone_number = forms.CharField(
        label=_('Numéro de téléphone'),
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES + ' rounded-l-none',
            'placeholder': '6XXXXXXXX',
            'type': 'tel',
            'inputmode': 'numeric',
            'autocomplete': 'tel',
        }),
    )
    password = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )
    password_confirm = forms.CharField(
        label=_('Confirmer le mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError(_('Le nom d\'utilisateur est obligatoire.'))
        if len(username) < 3:
            raise ValidationError(
                _('Le nom d\'utilisateur doit contenir au moins 3 caractères.')
            )
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                _('Le nom d\'utilisateur ne peut contenir que des lettres, '
                  'chiffres et underscores.')
            )
        if User.objects.filter(username=username).exists():
            raise ValidationError(_('Ce nom d\'utilisateur est déjà pris.'))
        return username

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        try:
            normalized = normalize_phone_number(phone)
        except Exception:
            raise ValidationError(_('Numéro de téléphone invalide.'))
        try:
            validate_cameroun_phone_number(normalized)
        except ValidationError:
            raise
        if User.objects.filter(phone_number=normalized).exists():
            raise ValidationError(
                _('Un compte existe déjà avec ce numéro de téléphone.')
            )
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', _('Les mots de passe ne correspondent pas.'))
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned_data


class LoginForm(forms.Form):
    username = forms.CharField(
        label=_('Nom d\'utilisateur'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Nom d\'utilisateur',
            'autocomplete': 'username',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        }),
    )


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label=_('Mot de passe actuel'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        }),
    )
    new_password = forms.CharField(
        label=_('Nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )
    new_password_confirm = forms.CharField(
        label=_('Confirmer le nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        password = self.cleaned_data.get('current_password')
        if not self.user.check_password(password):
            raise ValidationError(_('Le mot de passe actuel est incorrect.'))
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        new_password_confirm = cleaned_data.get('new_password_confirm')
        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error(
                'new_password_confirm',
                _('Les mots de passe ne correspondent pas.'),
            )
        if new_password:
            try:
                validate_password(new_password, self.user)
            except ValidationError as e:
                self.add_error('new_password', e)
        return cleaned_data


class PasswordResetRequestForm(forms.Form):
    username = forms.CharField(
        label=_('Nom d\'utilisateur'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Nom d\'utilisateur',
            'autocomplete': 'username',
        }),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not User.objects.filter(username=username).exists():
            raise ValidationError(_('Aucun compte trouvé avec ce nom d\'utilisateur.'))
        return username


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(
        label=_('Nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )
    new_password_confirm = forms.CharField(
        label=_('Confirmer le nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        new_password_confirm = cleaned_data.get('new_password_confirm')
        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error(
                'new_password_confirm',
                _('Les mots de passe ne correspondent pas.'),
            )
        if new_password:
            try:
                validate_password(new_password)
            except ValidationError as e:
                self.add_error('new_password', e)
        return cleaned_data


class OTPForm(forms.Form):
    code = forms.CharField(
        label=_('Code de vérification'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES + ' text-center text-2xl tracking-[0.5em]',
            'placeholder': '000000',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        })
    )
