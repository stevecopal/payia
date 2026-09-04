from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    user = models.OneToOneField(
        'core.User',
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('user'),
    )
    first_name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name=_('first name'),
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name=_('last name'),
    )
    email = models.EmailField(
        blank=True,
        default='',
        verbose_name=_('email'),
    )
    country = models.CharField(
        max_length=2,
        blank=True,
        default='',
        verbose_name=_('country'),
    )
    withdrawal_phone_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name=_('withdrawal phone number'),
    )
    withdrawal_account_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('withdrawal account name'),
    )
    preferred_currency = models.CharField(
        max_length=3,
        default='XOF',
        verbose_name=_('preferred currency'),
    )
    profile_picture = models.ImageField(
        upload_to='profiles/',
        blank=True,
        default='',
        verbose_name=_('profile picture'),
    )
    is_profile_complete = models.BooleanField(
        default=False,
        verbose_name=_('profile complete'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('created at'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('updated at'),
    )

    class Meta:
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')

    def __str__(self):
        return f'Profile of {self.user.phone_number}'

    def complete_profile(self):
        required_fields = [
            self.first_name,
            self.last_name,
            self.withdrawal_phone_number,
            self.withdrawal_account_name,
        ]
        self.is_profile_complete = all(field.strip() for field in required_fields)
        self.save(update_fields=['is_profile_complete', 'updated_at'])
        return self.is_profile_complete
