from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    PROFILE_STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('EN_ATTENTE', _('En attente')),
        ('VERIFIED', _('Verified')),
    ]

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
        default='XAF',
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
    profile_status = models.CharField(
        max_length=20,
        choices=PROFILE_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_('profile status'),
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
        ordering = ['-created_at']

    def __str__(self):
        return f'Profile of {self.user.phone_number}'

    def update_profile_status(self):
        basic_filled = bool(self.first_name.strip() and self.last_name.strip())
        withdrawal_filled = bool(self.withdrawal_phone_number.strip() and self.withdrawal_account_name.strip())

        if withdrawal_filled:
            self.profile_status = 'VERIFIED'
            self.is_profile_complete = True
        elif basic_filled:
            self.profile_status = 'EN_ATTENTE'
            self.is_profile_complete = True
        else:
            self.profile_status = 'PENDING'
            self.is_profile_complete = False

        self.save(update_fields=['profile_status', 'is_profile_complete', 'updated_at'])
        return self.profile_status
