import logging
import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from transactions.models import Withdrawal, PaymentMethod
from wallet.models import Wallet
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification

logger = logging.getLogger('transactions')


class WithdrawalService:
    @staticmethod
    def create_withdrawal(user, amount, payment_method_id, withdrawal_number, withdrawal_account_name='', note=''):
        amount = Decimal(str(amount))
        payment_method = PaymentMethod.objects.get(id=payment_method_id, is_active=True)

        from core.models import Setting
        try:
            min_withdrawal = Decimal(Setting.objects.get(key='minimum_withdrawal').value)
        except Setting.DoesNotExist:
            min_withdrawal = Decimal('3500')

        if amount < min_withdrawal:
            raise ValueError(f"Le montant minimum de retrait est {min_withdrawal}.")

        fee = Decimal(str(payment_method.calculate_fee(amount)))
        net_amount = amount - fee

        withdrawal_number = withdrawal_number.replace('+237', '').replace(' ', '').strip()
        if not re.match(r'^6\d{8}$', withdrawal_number):
            raise ValueError("Le numero de retrait doit commencer par 6 et contenir exactement 9 chiffres.")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=user)

            if wallet.available_balance < amount:
                raise ValueError("Solde insuffisant.")

            WalletService.reserve_amount(user, amount)

            withdrawal = Withdrawal.objects.create(
                user=user,
                amount=amount,
                fee=fee,
                net_amount=net_amount,
                withdrawal_method=payment_method,
                withdrawal_number=withdrawal_number,
                withdrawal_account_name=withdrawal_account_name,
                ip_address=None,
            )

            Notification.objects.create(
                user=user,
                notification_type='WITHDRAWAL_REQUESTED',
                title='Retrait demande',
                message=f'Votre retrait de {amount} a ete demande. Montant net: {net_amount}.',
            )

            AuditLog.objects.create(
                actor=user,
                action='withdrawal.created',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {amount} demande',
            )

        return withdrawal

    @staticmethod
    def approve_withdrawal(withdrawal, admin_user, external_reference=''):
        with transaction.atomic():
            withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal.pk)

            if withdrawal.status not in [Withdrawal.Status.PENDING, Withdrawal.Status.UNDER_REVIEW]:
                raise ValueError("Ce retrait ne peut plus etre approuve.")

            withdrawal.approve(admin_user)

            if external_reference:
                withdrawal.external_reference = external_reference
                withdrawal.save(update_fields=['external_reference'])

            WalletService.release_amount(withdrawal.user, withdrawal.amount)
            WalletService.debit_wallet(
                user=withdrawal.user,
                amount=withdrawal.amount,
                entry_type='WITHDRAWAL',
                description=f'Retrait approuve via {withdrawal.withdrawal_method.name}',
                reference_type='Withdrawal',
                reference_id=withdrawal.pk,
            )

            Notification.objects.create(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_APPROVED',
                title='Retrait approuve',
                message=f'Votre retrait de {withdrawal.amount} a ete approuve.',
            )

            Notification.objects.create(
                user=admin_user,
                notification_type='WITHDRAWAL_APPROVED',
                title='Retrait approuve',
                message=f'Retrait #{withdrawal.pk} de {withdrawal.amount} XAF approuve pour {withdrawal.user.phone_number}.',
                link=f'/admin-panel/withdrawals/{withdrawal.pk}/',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='withdrawal.approved',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {withdrawal.amount} approuve pour {withdrawal.user.phone_number}',
            )

        return withdrawal

    @staticmethod
    def reject_withdrawal(withdrawal, admin_user, reason):
        if not reason:
            raise ValueError("Une raison de rejet est obligatoire.")

        with transaction.atomic():
            withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal.pk)

            if withdrawal.status not in [Withdrawal.Status.PENDING, Withdrawal.Status.UNDER_REVIEW]:
                raise ValueError("Ce retrait ne peut plus etre refuse.")

            withdrawal.reject(admin_user, reason)

            WalletService.release_amount(withdrawal.user, withdrawal.amount)

            Notification.objects.create(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_REJECTED',
                title='Retrait refuse',
                message=f'Votre retrait de {withdrawal.amount} a ete refuse. Raison: {reason}',
            )

            Notification.objects.create(
                user=admin_user,
                notification_type='WITHDRAWAL_REJECTED',
                title='Retrait refuse',
                message=f'Retrait #{withdrawal.pk} de {withdrawal.amount} XAF refuse pour {withdrawal.user.phone_number}. Raison: {reason}',
                link=f'/admin-panel/withdrawals/{withdrawal.pk}/',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='withdrawal.rejected',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {withdrawal.amount} refuse pour {withdrawal.user.phone_number}. Raison: {reason}',
            )

        return withdrawal

    @staticmethod
    def complete_withdrawal(withdrawal, admin_user):
        with transaction.atomic():
            withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal.pk)

            if withdrawal.status not in [Withdrawal.Status.APPROVED, Withdrawal.Status.PROCESSING]:
                raise ValueError("Seuls les retraits approuves peuvent etre marques comme payes.")

            withdrawal.complete(admin_user)

            Notification.objects.create(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_COMPLETED',
                title='Retrait complete',
                message=f'Votre retrait de {withdrawal.net_amount} XAF a ete paye.',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='withdrawal.completed',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {withdrawal.net_amount} marque comme paye pour {withdrawal.user.phone_number}',
            )

        return withdrawal

    @staticmethod
    def get_user_withdrawals(user, status=None):
        qs = Withdrawal.objects.filter(user=user).select_related('withdrawal_method', 'reviewed_by')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')
