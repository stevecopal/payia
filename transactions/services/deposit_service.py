import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from transactions.models import Deposit, PaymentMethod
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification


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
            raise ValueError("Le montant doit être supérieur à 0.")

        payment_method = PaymentMethod.objects.filter(
            id=payment_method_id, is_active=True
        ).first()
        if not payment_method:
            raise ValueError("Méthode de paiement invalide ou inactive.")

        if payment_method.min_amount and amount < payment_method.min_amount:
            raise ValueError(f"Le montant minimum est {payment_method.min_amount}.")
        if payment_method.max_amount and amount > payment_method.max_amount:
            raise ValueError(f"Le montant maximum est {payment_method.max_amount}.")

        if transaction_id:
            existing = Deposit.objects.filter(
                transaction_id=transaction_id
            ).exclude(status=Deposit.Status.REJECTED).exists()
            if existing:
                raise ValueError("Ce numéro de transaction a déjà été utilisé.")

        normalized_phone = DepositService.validate_phone(phone_number) if phone_number else ''
        if phone_number and not normalized_phone:
            raise ValueError("Numéro de téléphone invalide. Format attendu: 6XXXXXXXX.")

        ussd_code = payment_method.generate_ussd_code(amount)
        reception_number = payment_method.phone_number

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

        Notification.objects.create(
            user=user,
            notification_type='DEPOSIT_SUBMITTED',
            title='Dépôt soumis',
            message=f'Votre demande de dépôt de {amount} XAF a été envoyée et est en attente de validation.',
        )

        return deposit

    @staticmethod
    def approve_deposit(deposit, admin_user):
        deposit.refresh_from_db()
        if deposit.status != Deposit.Status.PENDING_REVIEW:
            return deposit

        with transaction.atomic():
            deposit.approve(admin_user)

            WalletService.credit_wallet(
                user=deposit.user,
                amount=deposit.amount,
                entry_type='DEPOSIT',
                description=f'Dépôt approuvé via {deposit.payment_method.name}',
                reference_type='Deposit',
                reference_id=deposit.pk,
            )

            deposit.complete()

            Notification.objects.create(
                user=deposit.user,
                notification_type='DEPOSIT_APPROVED',
                title='Dépôt approuvé',
                message=f'Votre dépôt de {deposit.amount} XAF a été approuvé. Votre compte a été crédité.',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='deposit.approved',
                target_type='Deposit',
                target_id=str(deposit.pk),
                description=f'Dépôt de {deposit.amount} XAF approuvé pour {deposit.user.phone_number}',
            )

        return deposit

    @staticmethod
    def reject_deposit(deposit, admin_user, reason):
        if deposit.status != Deposit.Status.PENDING_REVIEW:
            raise ValueError("Ce dépôt ne peut plus être refusé.")

        if not reason:
            raise ValueError("Une raison de rejet est obligatoire.")

        deposit.reject(admin_user, reason)

        message = f'Votre demande de dépôt de {deposit.amount} XAF a été rejetée.'
        if reason:
            message += f' Raison: {reason}'

        Notification.objects.create(
            user=deposit.user,
            notification_type='DEPOSIT_REJECTED',
            title='Dépôt refusé',
            message=message,
        )

        AuditLog.objects.create(
            actor=admin_user,
            action='deposit.rejected',
            target_type='Deposit',
            target_id=str(deposit.pk),
            description=f'Dépôt de {deposit.amount} XAF refusé pour {deposit.user.phone_number}. Raison: {reason}',
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
