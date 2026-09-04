from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from transactions.models import Withdrawal, PaymentMethod
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification


class WithdrawalService:
    @staticmethod
    def create_withdrawal(user, amount, payment_method_id, withdrawal_number, withdrawal_account_name='', note=''):
        amount = Decimal(str(amount))
        payment_method = PaymentMethod.objects.get(id=payment_method_id, is_active=True)

        from core.models import Setting
        try:
            min_withdrawal = Decimal(Setting.objects.get(key='minimum_withdrawal').value)
        except Setting.DoesNotExist:
            min_withdrawal = Decimal('1000')

        if amount < min_withdrawal:
            raise ValueError(f"Le montant minimum de retrait est {min_withdrawal}.")

        fee = Decimal(str(payment_method.calculate_fee(amount)))
        net_amount = amount - fee

        wallet = WalletService.get_wallet(user)
        if wallet.available_balance < amount:
            raise ValueError("Solde insuffisant.")

        with transaction.atomic():
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
                title='Retrait demandé',
                message=f'Votre retrait de {amount} a été demandé. Montant net: {net_amount}.',
            )

            AuditLog.objects.create(
                actor=user,
                action='withdrawal.created',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {amount} demandé',
            )

        return withdrawal

    @staticmethod
    def approve_withdrawal(withdrawal, admin_user, external_reference=''):
        if withdrawal.status not in [Withdrawal.Status.PENDING, Withdrawal.Status.UNDER_REVIEW]:
            raise ValueError("Ce retrait ne peut plus être approuvé.")

        with transaction.atomic():
            withdrawal.approve(admin_user)

            if external_reference:
                withdrawal.external_reference = external_reference
                withdrawal.save(update_fields=['external_reference'])

            WalletService.release_amount(withdrawal.user, withdrawal.amount)
            WalletService.debit_wallet(
                user=withdrawal.user,
                amount=withdrawal.amount,
                entry_type='WITHDRAWAL',
                description=f'Retrait approuvé via {withdrawal.withdrawal_method.name}',
                reference_type='Withdrawal',
                reference_id=withdrawal.pk,
            )

            Notification.objects.create(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_APPROVED',
                title='Retrait approuvé',
                message=f'Votre retrait de {withdrawal.amount} a été approuvé.',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='withdrawal.approved',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {withdrawal.amount} approuvé pour {withdrawal.user.phone_number}',
            )

        return withdrawal

    @staticmethod
    def reject_withdrawal(withdrawal, admin_user, reason):
        if withdrawal.status not in [Withdrawal.Status.PENDING, Withdrawal.Status.UNDER_REVIEW]:
            raise ValueError("Ce retrait ne peut plus être refusé.")

        if not reason:
            raise ValueError("Une raison de rejet est obligatoire.")

        with transaction.atomic():
            withdrawal.reject(admin_user, reason)

            WalletService.release_amount(withdrawal.user, withdrawal.amount)

            Notification.objects.create(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_REJECTED',
                title='Retrait refusé',
                message=f'Votre retrait de {withdrawal.amount} a été refusé. Raison: {reason}',
            )

            AuditLog.objects.create(
                actor=admin_user,
                action='withdrawal.rejected',
                target_type='Withdrawal',
                target_id=str(withdrawal.pk),
                description=f'Retrait de {withdrawal.amount} refusé. Raison: {reason}',
            )

        return withdrawal

    @staticmethod
    def get_user_withdrawals(user, status=None):
        qs = Withdrawal.objects.filter(user=user).select_related('withdrawal_method', 'reviewed_by')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')
