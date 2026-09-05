import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q

from referrals.models import Referral, Commission, ReferralAllocation
from core.models import User, Setting, AuditLog
from wallet.models import LedgerEntry
from notifications.models import Notification

logger = logging.getLogger('referrals')

MAX_LEVELS = 5

DEFAULT_PERCENTAGES = {
    1: Decimal('10'),
    2: Decimal('5'),
    3: Decimal('3'),
    4: Decimal('2'),
    5: Decimal('1'),
}

DEFAULT_MAX_TOTAL_COMMISSION = Decimal('90')


class ReferralService:
    """Centralized referral commission calculation service.

    Financial rule:
        A referral commission is an ALLOCATION from the source deposit,
        NOT a creation of new funds.

        deposit.amount = SUM(all commissions) + productive_amount

    This service ensures:
        1. Commissions are calculated from the source deposit amount
        2. Total commissions never exceed the safety ceiling
        3. Commissions are only credited to eligible referrers
        4. Operations are atomic and idempotent
        5. Full audit trail is maintained
    """

    @staticmethod
    def get_referral_code(user):
        return user.referral_code

    @staticmethod
    def get_referral_link(user, request=None):
        code = user.referral_code
        if request:
            return f"{request.scheme}://{request.get_host()}/referrals/{code}/"
        return f"/referrals/{code}/"

    @staticmethod
    def register_referral(new_user, referral_code):
        if new_user.referral_code == referral_code:
            return None, "Vous ne pouvez pas vous parrainer vous-même."

        try:
            referrer = User.objects.get(referral_code=referral_code, is_active=True)
        except User.DoesNotExist:
            return None, "Code de parrainage invalide."

        if Referral.objects.filter(referred_user=new_user).exists():
            return None, "Vous avez déjà un parrain."

        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=new_user,
            referral_level=1,
        )

        Notification.objects.create(
            user=referrer,
            notification_type='NEW_REFERRAL',
            title='Nouveau filleul',
            message='Un nouvel utilisateur s\'est inscrit avec votre code de parrainage.',
        )

        AuditLog.objects.create(
            actor=new_user,
            action='referral.created',
            target_type='Referral',
            target_id=str(referral.pk),
            description=f'Nouveau parrainage par {referrer.phone_number}',
        )

        return referral, None

    @staticmethod
    def get_user_referrals(user, level=None):
        qs = Referral.objects.filter(referrer=user, is_active=True).select_related('referred_user')
        if level:
            qs = qs.filter(referral_level=level)
        return qs

    @staticmethod
    def get_referral_stats(user):
        stats = {f'level_{i}': 0 for i in range(1, 6)}

        def count_at_level(referrer, level):
            if level > 5:
                return
            direct = Referral.objects.filter(
                referrer=referrer, is_active=True
            ).select_related('referred_user')
            for ref in direct:
                stats[f'level_{level}'] += 1
                count_at_level(ref.referred_user, level + 1)

        count_at_level(user, 1)
        stats['total'] = sum(stats.values())
        return stats

    @staticmethod
    def get_commission_stats(user):
        """Get commission statistics broken down by level."""
        stats = {}
        for level in range(1, MAX_LEVELS + 1):
            total = Commission.objects.filter(
                user=user,
                referral_level=level,
                status__in=['approved', 'available']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            stats[f'level_{level}'] = total

        stats['total'] = Commission.objects.filter(
            user=user,
            status__in=['approved', 'available']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return stats

    @staticmethod
    def get_level_percentages():
        """Load referral commission percentages from settings."""
        percentages = {}
        for level in range(1, MAX_LEVELS + 1):
            try:
                val = Setting.objects.get(key=f'level_{level}_percentage').get_value()
                percentages[level] = Decimal(str(val))
            except Setting.DoesNotExist:
                percentages[level] = DEFAULT_PERCENTAGES.get(level, Decimal('0'))
        return percentages

    @staticmethod
    def get_max_total_commission_percentage():
        """Load the maximum allowed total commission percentage."""
        try:
            return Decimal(str(Setting.get_setting('max_total_commission_percentage', DEFAULT_MAX_TOTAL_COMMISSION)))
        except Exception:
            return DEFAULT_MAX_TOTAL_COMMISSION

    @staticmethod
    def validate_rate_configuration(percentages=None):
        """Validate that total commission rates don't exceed the safety ceiling.

        Returns:
            (is_valid, total_percentage, max_allowed, error_message)
        """
        if percentages is None:
            percentages = ReferralService.get_level_percentages()

        total = sum(percentages.values())
        max_allowed = ReferralService.get_max_total_commission_percentage()

        if total > max_allowed:
            return (
                False,
                total,
                max_allowed,
                f"Le total des commissions ({total}%) dépasse la limite autorisée ({max_allowed}%). "
                f"Veuillez ajuster les pourcentages."
            )
        return (True, total, max_allowed, None)

    @staticmethod
    def _is_referrer_eligible(user):
        """Check if a user is eligible to receive referral commissions."""
        if not user.is_active:
            return False
        if hasattr(user, 'is_suspended') and user.is_suspended:
            return False
        if hasattr(user, 'account_status') and user.account_status in ('blocked', 'suspended', 'inactive'):
            return False
        return True

    @staticmethod
    def _walk_referral_chain(source_user):
        """Walk up the referral chain from a source user.

        Returns:
            List of (level, referrer_user) tuples, up to MAX_LEVELS.
        """
        chain = []
        current_user = source_user
        level = 1

        while level <= MAX_LEVELS:
            try:
                referral = Referral.objects.get(
                    referred_user=current_user,
                    is_active=True,
                )
                chain.append((level, referral.referrer))
                current_user = referral.referrer
                level += 1
            except Referral.DoesNotExist:
                break

        return chain

    @staticmethod
    def calculate_and_allocate_commissions(deposit):
        """Calculate and allocate referral commissions for a deposit.

        This is the CORE financial method. It:
        1. Walks the referral chain
        2. Reads configured percentages
        3. Validates total doesn't exceed safety ceiling
        4. Creates Commission records (idempotent per deposit+level)
        5. Creates ReferralAllocation records
        6. Credits eligible referrers' wallets
        7. Updates deposit.referral_commission_total and productive_amount

        Financial invariant preserved:
            deposit.amount = SUM(commissions) + productive_amount

        Args:
            deposit: The Deposit object (must be APPROVED or COMPLETED)

        Returns:
            dict with calculation results:
            {
                'allocations': [ReferralAllocation, ...],
                'total_commission': Decimal,
                'productive_amount': Decimal,
                'levels_processed': int,
            }
        """
        from wallet.services.wallet_service import WalletService

        with transaction.atomic():
            percentages = ReferralService.get_level_percentages()
            chain = ReferralService._walk_referral_chain(deposit.user)
            base_amount = deposit.amount

            allocations = []
            total_commission = Decimal('0')

            for level, referrer in chain:
                pct = percentages.get(level, Decimal('0'))
                if pct <= 0:
                    continue

                commission_amount = (base_amount * pct / Decimal('100')).quantize(Decimal('0.01'))
                if commission_amount <= 0:
                    continue

                reference = ReferralAllocation.generate_reference(deposit.pk, level)

                existing = ReferralAllocation.objects.filter(
                    reference=reference,
                ).first()
                if existing:
                    logger.info(
                        f'Allocation {reference} already exists (idempotency), skipping.'
                    )
                    allocations.append(existing)
                    if existing.status == ReferralAllocation.Status.APPROVED:
                        total_commission += existing.amount
                    continue

                is_eligible = ReferralService._is_referrer_eligible(referrer)

                allocation = ReferralAllocation.objects.create(
                    deposit=deposit,
                    beneficiary=referrer,
                    source_user=deposit.user,
                    referral_level=level,
                    base_amount=base_amount,
                    percentage=pct,
                    amount=commission_amount,
                    status=ReferralAllocation.Status.PENDING,
                    reference=reference,
                )

                commission = Commission.objects.create(
                    user=referrer,
                    source_user=deposit.user,
                    referral_level=level,
                    source_transaction_type='DEPOSIT_COMPLETED',
                    source_transaction_id=deposit.pk,
                    percentage=pct,
                    amount=commission_amount,
                    status=Commission.Status.PENDING if is_eligible else Commission.Status.CANCELLED,
                )
                allocation.commission = commission
                allocation.save(update_fields=['commission'])

                if is_eligible:
                    wallet, ledger_entry = WalletService.credit_wallet(
                        user=referrer,
                        amount=commission_amount,
                        entry_type=LedgerEntry.EntryType.REFERRAL_COMMISSION,
                        description=(
                            f'Commission parrainage niv.{level} - '
                            f'Dépôt de {deposit.user.phone_number} ({base_amount} XAF)'
                        ),
                        reference_type='Commission',
                        reference_id=commission.pk,
                    )
                    commission.approve()
                    commission.ledger_entry = ledger_entry
                    commission.save(update_fields=['status', 'ledger_entry', 'updated_at'])

                    allocation.approve()
                    allocation.ledger_entry = ledger_entry
                    allocation.save(update_fields=['status', 'ledger_entry', 'updated_at'])

                    total_commission += commission_amount

                    AuditLog.objects.create(
                        actor=referrer,
                        action='referral.commission.credited',
                        target_type='ReferralAllocation',
                        target_id=str(allocation.pk),
                        description=(
                            f'Commission L{level}: {commission_amount} XAF '
                            f'dépôt {deposit.pk} de {deposit.user.phone_number}'
                        ),
                    )
                else:
                    allocation.cancel()
                    allocation.save(update_fields=['status'])

                allocations.append(allocation)

            productive_amount = base_amount - total_commission
            if productive_amount < 0:
                productive_amount = Decimal('0')

            deposit.referral_commission_total = total_commission
            deposit.productive_amount = productive_amount
            deposit.save(update_fields=[
                'referral_commission_total',
                'productive_amount',
                'updated_at',
            ])

            logger.info(
                f'Deposit {deposit.pk}: base={base_amount}, '
                f'commission={total_commission}, productive={productive_amount}, '
                f'levels={len(allocations)}'
            )

            return {
                'allocations': allocations,
                'total_commission': total_commission,
                'productive_amount': productive_amount,
                'levels_processed': len(allocations),
            }

    @staticmethod
    def reverse_commission_allocation(allocation, reason=''):
        """Reverse a previously approved commission allocation.

        This creates a reversal record in the ledger rather than
        deleting the original entry, preserving the audit trail.
        """
        from wallet.services.wallet_service import WalletService

        with transaction.atomic():
            if allocation.status != ReferralAllocation.Status.APPROVED:
                raise ValueError("Seules les allocations approuvées peuvent être annulées.")

            wallet, ledger_entry = WalletService.debit_wallet(
                user=allocation.beneficiary,
                amount=allocation.amount,
                entry_type='ADJUSTMENT',
                description=(
                    f'Annulation commission L{allocation.referral_level} - '
                    f'Dépôt {allocation.deposit.pk}: {reason}'
                ),
                reference_type='ReferralAllocation',
                reference_id=allocation.pk,
            )

            allocation.reverse()
            allocation.ledger_entry = ledger_entry
            allocation.save(update_fields=['status', 'ledger_entry', 'updated_at'])

            if allocation.commission:
                allocation.commission.revoke()
                allocation.commission.ledger_entry = ledger_entry
                allocation.commission.save(update_fields=['status', 'ledger_entry', 'updated_at'])

            allocation.deposit.referral_commission_total -= allocation.amount
            allocation.deposit.productive_amount += allocation.amount
            allocation.deposit.save(update_fields=[
                'referral_commission_total',
                'productive_amount',
                'updated_at',
            ])

            AuditLog.objects.create(
                actor=allocation.beneficiary,
                action='referral.commission.reversed',
                target_type='ReferralAllocation',
                target_id=str(allocation.pk),
                description=(
                    f'Annulation commission L{allocation.referral_level}: '
                    f'{allocation.amount} XAF. Raison: {reason}'
                ),
            )

            return allocation

    @staticmethod
    def calculate_commission(source_user, source_type, source_id, amount):
        """Legacy method for backward compatibility.

        Prefer calculate_and_allocate_commissions() for new code.
        """
        percentages = ReferralService.get_level_percentages()
        commissions = []
        level = 1
        current_user = source_user

        while level <= MAX_LEVELS:
            try:
                referral = Referral.objects.get(
                    referred_user=current_user, is_active=True
                )
            except Referral.DoesNotExist:
                break

            referrer = referral.referrer
            if level in percentages and percentages[level] > 0:
                pct = percentages[level]
                commission_amount = (amount * pct / Decimal('100')).quantize(Decimal('0.01'))
                if commission_amount > 0:
                    commission = Commission.objects.create(
                        user=referrer,
                        source_user=source_user,
                        referral_level=level,
                        source_transaction_type=source_type,
                        source_transaction_id=source_id,
                        percentage=pct,
                        amount=commission_amount,
                        status=Commission.Status.PENDING,
                    )
                    commissions.append(commission)

            current_user = referrer
            level += 1

        return commissions

    @staticmethod
    def approve_commission(commission):
        """Legacy method for backward compatibility."""
        from wallet.services.wallet_service import WalletService
        with transaction.atomic():
            commission.approve()
            wallet, ledger_entry = WalletService.credit_wallet(
                user=commission.user,
                amount=commission.amount,
                entry_type=LedgerEntry.EntryType.REFERRAL_COMMISSION,
                description=f'Commission niveau {commission.referral_level}',
                reference_type='Commission',
                reference_id=commission.pk,
            )
            commission.ledger_entry = ledger_entry
            commission.save(update_fields=['ledger_entry'])
        return commission
