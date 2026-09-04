import hashlib
import secrets
import logging
from datetime import timedelta

from django.contrib.auth import login, logout
from django.db import transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.translation import gettext_lazy as _

from core.models import User, OTP, AuditLog

logger = logging.getLogger('core')


class AuthService:
    OTP_EXPIRY_MINUTES = 5
    OTP_MAX_ATTEMPTS = 5
    OTP_RETRY_DELAY_SECONDS = 60
    OTP_LENGTH = 6
    PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 1
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 900

    @staticmethod
    def _get_client_ip(request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    @staticmethod
    def register_user(username, phone_number, password, referral_code=None):
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                phone_number=phone_number,
                password=password,
            )
            if referral_code:
                try:
                    from referrals.services.referral_service import ReferralService
                    referral, error = ReferralService.register_referral(user, referral_code)
                    if referral:
                        user.referred_by = referral.referrer
                        user.save(update_fields=['referred_by'])
                except Exception:
                    pass
            AuditLog.log(
                actor=user,
                action='auth.register',
                target_type='User',
                target_id=str(user.pk),
                description=f'Compte créé: {username}',
            )
        return user

    @staticmethod
    def authenticate_user(request, username, password):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None, _('Identifiants incorrects.')

        if not user.check_password(password):
            return None, _('Identifiants incorrects.')

        if not user.is_active or user.account_status in ('SUSPENDED', 'BLOCKED'):
            return None, _('Votre compte a été désactivé. Contactez le support.')

        if user.is_suspended:
            return None, _('Votre compte a été suspendu. Contactez le support.')

        ip = AuthService._get_client_ip(request)
        user.last_login_ip = ip
        user.save(update_fields=['last_login_ip'])

        login(request, user)

        AuditLog.log(
            actor=user,
            action='auth.login',
            target_type='User',
            target_id=str(user.pk),
            description='Connexion réussie',
            ip_address=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        return user, None

    @staticmethod
    def logout_user(request):
        user = request.user if request.user.is_authenticated else None
        if user:
            AuditLog.log(
                actor=user,
                action='auth.logout',
                target_type='User',
                target_id=str(user.pk),
                description='Déconnexion',
                ip_address=AuthService._get_client_ip(request),
            )
        logout(request)

    @staticmethod
    def change_password(request, user, current_password, new_password):
        if not user.check_password(current_password):
            return False, _('Le mot de passe actuel est incorrect.')

        user.set_password(new_password)
        user.save(update_fields=['password'])

        AuditLog.log(
            actor=user,
            action='auth.password_change',
            target_type='User',
            target_id=str(user.pk),
            description='Mot de passe modifié',
            ip_address=AuthService._get_client_ip(request),
        )
        return True, _('Mot de passe modifié avec succès.')

    @staticmethod
    def generate_password_reset_token(user):
        token = secrets.token_urlsafe(48)
        hashed = hashlib.sha256(token.encode()).hexdigest()
        request_obj = OTP.objects.create(
            user=user,
            code=hashed,
            purpose='PASSWORD_RESET',
            expires_at=timezone.now() + timedelta(
                hours=AuthService.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
            ),
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return uid, token

    @staticmethod
    def validate_password_reset_token(uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

        hashed = hashlib.sha256(token.encode()).hexdigest()
        otp = OTP.objects.filter(
            user=user,
            code=hashed,
            purpose='PASSWORD_RESET',
            is_used=False,
        ).order_by('-created_at').first()

        if not otp:
            return None
        if otp.is_expired():
            return None

        return user

    @staticmethod
    def reset_password(uidb64, token, new_password):
        user = AuthService.validate_password_reset_token(uidb64, token)
        if not user:
            return False, _('Lien de réinitialisation invalide ou expiré.')

        hashed = hashlib.sha256(token.encode()).hexdigest()
        OTP.objects.filter(
            user=user,
            code=hashed,
            purpose='PASSWORD_RESET',
        ).update(is_used=True)

        user.set_password(new_password)
        user.save(update_fields=['password'])

        AuditLog.log(
            actor=user,
            action='auth.password_reset',
            target_type='User',
            target_id=str(user.pk),
            description='Mot de passe réinitialisé',
        )
        return True, _('Mot de passe réinitialisé avec succès.')

    @staticmethod
    def generate_otp(user, purpose='LOGIN', ip_address=None):
        now = timezone.now()
        recent_otp = OTP.objects.filter(
            user=user,
            purpose=purpose,
            created_at__gte=now - timedelta(
                seconds=AuthService.OTP_RETRY_DELAY_SECONDS
            ),
        ).exists()
        if recent_otp:
            return None, _('Veuillez patienter avant de demander un nouveau code.')

        OTP.objects.filter(
            user=user, purpose=purpose, is_used=False
        ).update(is_used=True)

        code = ''.join(
            [str(secrets.randbelow(10)) for _ in range(AuthService.OTP_LENGTH)]
        )

        otp = OTP.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=now + timedelta(minutes=AuthService.OTP_EXPIRY_MINUTES),
            ip_address=ip_address,
        )
        return otp, code

    @staticmethod
    def verify_otp(user, code, purpose='LOGIN'):
        otp = OTP.objects.filter(
            user=user, purpose=purpose, is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return False, _('Aucun code actif trouvé.')

        if otp.is_expired():
            return False, _('Le code a expiré. Veuillez en demander un nouveau.')

        if otp.attempts >= otp.max_attempts:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            return False, _('Nombre maximum de tentatives atteint.')

        if otp.code != code:
            otp.increment_attempts()
            remaining = otp.max_attempts - otp.attempts
            return False, _('Code incorrect. %(remaining)s tentative(s) restante(s).') % {
                'remaining': remaining,
            }

        otp.mark_used()
        return True, _('Code vérifié.')

    @staticmethod
    def create_user_with_phone(phone_number):
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
        )
        if created:
            AuditLog.log(
                actor=user,
                action='auth.register',
                target_type='User',
                target_id=str(user.pk),
                description=f'Compte créé par téléphone: {phone_number}',
            )
        return user, created
