import secrets
import string

from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.validators import validate_cameroun_phone_number


class UserManager(BaseUserManager):
    def create_user(self, username, phone_number, password=None, **extra_fields):
        if not username:
            raise ValueError(_('Le nom d\'utilisateur est obligatoire.'))
        if not phone_number:
            raise ValueError(_('Le numéro de téléphone est obligatoire.'))
        user = self.model(username=username, phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Le superutilisateur doit avoir is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Le superutilisateur doit avoir is_superuser=True.'))
        return self.create_user(username, phone_number, password, **extra_fields)


class User(AbstractUser):
    objects = UserManager()

    KYC_STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('VERIFIED', _('Verified')),
        ('REJECTED', _('Rejected')),
        ('REQUIRES_ACTION', _('Requires Action')),
    ]

    ACCOUNT_STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('INACTIVE', _('Inactive')),
        ('SUSPENDED', _('Suspended')),
        ('BLOCKED', _('Blocked')),
    ]

    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_('username'),
    )
    email = None

    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[validate_cameroun_phone_number],
        verbose_name=_('phone number'),
    )
    is_phone_verified = models.BooleanField(
        default=False,
        verbose_name=_('phone verified'),
    )
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='ACTIVE',
        verbose_name=_('account status'),
    )
    role = models.ForeignKey(
        'core.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('role'),
    )
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_('referral code'),
    )
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        verbose_name=_('referred by'),
    )
    is_suspended = models.BooleanField(
        default=False,
        verbose_name=_('is suspended'),
    )
    suspension_reason = models.TextField(
        blank=True,
        default='',
        verbose_name=_('suspension reason'),
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_('KYC status'),
    )
    risk_score = models.IntegerField(
        default=0,
        verbose_name=_('risk score'),
    )
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('last login IP'),
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone_number']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return self.username

    @property
    def full_name(self):
        first = self.first_name or ''
        last = self.last_name or ''
        return f'{first} {last}'.strip()

    @property
    def display_name(self):
        full = self.full_name
        return full if full else self.username

    @property
    def is_account_active(self):
        return (
            self.is_active
            and not self.is_suspended
            and self.account_status == 'ACTIVE'
        )

    @staticmethod
    def generate_referral_code():
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = 'PAY' + ''.join(secrets.choice(alphabet) for _ in range(7))
            if not User.objects.filter(referral_code=code).exists():
                return code

    def suspend(self, reason=''):
        self.is_suspended = True
        self.suspension_reason = reason
        self.is_active = False
        self.account_status = 'SUSPENDED'
        self.save(update_fields=[
            'is_suspended', 'suspension_reason', 'is_active', 'account_status',
        ])

    def unsuspend(self):
        self.is_suspended = False
        self.suspension_reason = ''
        self.is_active = True
        self.account_status = 'ACTIVE'
        self.save(update_fields=[
            'is_suspended', 'suspension_reason', 'is_active', 'account_status',
        ])

    def block(self, reason=''):
        self.is_active = False
        self.account_status = 'BLOCKED'
        self.suspension_reason = reason
        self.save(update_fields=[
            'is_active', 'account_status', 'suspension_reason',
        ])

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
