import logging
import re
from decimal import Decimal
from django.db import transaction, IntegrityError
from django.utils import timezone
from transactions.models import Deposit, PaymentMethod
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification

logger = logging.getLogger('transactions')


class DepositService:
    @staticmethod
    def normalize_phone(value):
        cleaned = re.sub(r'[\s\-\(\)\.]+', '', str(value).strip())
        if cleaned.startswith('+237'):
            return cleaned
        if cleaned.startswith('237') and not cleaned.startswith('+'):
            return '+' + cleaned
        if cleaned.startswith('6') and len(cleaned) == 9:
            return '+237' + cleaned
        return cleaned

    @staticmethod
    def validate_phone(value):
        normalized = DepositService.normalize_phone(value)
        if not re.match(r'^\+2376\d{8}$', normalized):
            return None
        return normalized

    @staticmethod
    def create_deposit(user, amount, payment_method_id, transaction_id='',
                       phone_number='', proof=None, ip_address=None):
        amount = Decimal(str(amount))

        if amount <= 0:
            raise ValueError("Le montant doit etre superieur a 0.")

        from core.models import Setting
        try:
            min_deposit = Decimal(Setting.objects.get(key='minimum_deposit').value)
        except Setting.DoesNotExist:
            min_deposit = Decimal('2500')

        if amount < min_deposit:
            raise ValueError(f"Le montant minimum de depot est {min_deposit} XAF.")

        payment_method = PaymentMethod.objects.filter(
            id=payment_method_id, is_active=True
        ).first()
        if not payment_method:
            raise ValueError("Methode de paiement invalide ou inactive.")

        if payment_method.min_amount and amount < payment_method.min_amount:
            raise ValueError(f"Le montant minimum est {payment_method.min_amount}.")
        if payment_method.max_amount and amount > payment_method.max_amount:
            raise ValueError(f"Le montant maximum est {payment_method.max_amount}.")

        normalized_phone = DepositService.validate_phone(phone_number) if phone_number else ''
        if phone_number and not normalized_phone:
            raise ValueError("Numero de telephone invalide. Format attendu: 6XXXXXXXX.")

        with transaction.atomic():
            if transaction_id:
                existing = Deposit.objects.select_for_update().filter(
                    transaction_id=transaction_id
                ).exclude(status=Deposit.Status.REJECTED).exists()
                if existing:
                    raise ValueError("Ce numero de transaction a deja ete utilise.")

            ussd_code = payment_method.generate_ussd_code(amount)
            reception_number = payment_method.phone_number

            try:
                deposit = Deposit.objects.create(
                    user=user,
                    amount=amount,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    phone_number=normalized_phone or '',
                    reception_number=reception_number,
                    ussd_code=ussd_code,
                    proof=proof,
                    ip_address=ip_address,
                )
            except IntegrityError:
                raise ValueError("Ce numero de transaction a deja ete utilise.")

            Notification.objects.create(
                user=user,
                notification_type='DEPOSIT_SUBMITTED',
                title='Depot soumis',
                message=f'Votre demande de depot de {amount} XAF a ete envoyee et est en attente de validation.',
            )

        return deposit

    @staticmethod
    def approve_deposit(deposit, admin_user):
        with transaction.atomic():
            deposit = Deposit.objects.select_for_update().get(pk=deposit.pk)
            if deposit.status != Deposit.Status.PENDING_REVIEW:
                return deposit

            deposit.approve(admin_user)

            WalletService.credit_wallet(
                user=deposit.user,
                amount=deposit.amount,
                entry_type='DEPOSIT',
                description=f'Depot approuve via {deposit.payment_method.name}',
                reference_type='Deposit',
                reference_id=deposit.pk,
            )

            deposit.complete()

            Notification.objects.create(
                user=deposit.user,
                notification_type='DEPOSIT_APPROVED',
                title='Depot approuve',
                message=f'Votre depot de {deposit.amount} XAF a ete approuve. Votre compte a ete credite.',
            )

            Notification.objects.create(
                user=admin_user,
                notification_type='DEPOSIT_APPROVED',
                title='Depot approuve',
                message=f'Depot #{deposit.pk} de {deposit.amount} XAF approuve pour {deposit.user.phone_number}.',
                link=f'/admin-panel/deposits/{deposit.pk}/',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='deposit.approved',
                target_type='Deposit',
                target_id=str(deposit.pk),
                description=(
                    f'Depot de {deposit.amount} XAF approuve pour {deposit.user.phone_number}. '
                    f'100% alloue a la machine (pas de commission sur depot).'
                ),
            )

        return deposit

    @staticmethod
    def reject_deposit(deposit, admin_user, reason):
        if not reason:
            raise ValueError("Une raison de rejet est obligatoire.")

        with transaction.atomic():
            deposit = Deposit.objects.select_for_update().get(pk=deposit.pk)
            if deposit.status != Deposit.Status.PENDING_REVIEW:
                raise ValueError("Ce depot ne peut plus etre refuse.")

            deposit.reject(admin_user, reason)

            message = f'Votre demande de depot de {deposit.amount} XAF a ete rejetee.'
            if reason:
                message += f' Raison: {reason}'

            Notification.objects.create(
                user=deposit.user,
                notification_type='DEPOSIT_REJECTED',
                title='Depot refuse',
                message=message,
            )

            Notification.objects.create(
                user=admin_user,
                notification_type='DEPOSIT_REJECTED',
                title='Depot refuse',
                message=f'Depot #{deposit.pk} de {deposit.amount} XAF refuse pour {deposit.user.phone_number}. Raison: {reason}',
                link=f'/admin-panel/deposits/{deposit.pk}/',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='deposit.rejected',
                target_type='Deposit',
                target_id=str(deposit.pk),
                description=f'Depot de {deposit.amount} XAF refuse pour {deposit.user.phone_number}. Raison: {reason}',
            )

        return deposit

    @staticmethod
    def get_user_deposits(user, status=None):
        qs = Deposit.objects.filter(user=user).select_related('payment_method', 'reviewed_by')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')

    @staticmethod
    def get_pending_deposits():
        return Deposit.objects.filter(
            status='pending_review'
        ).select_related('user', 'payment_method', 'reviewed_by').order_by('-created_at')
