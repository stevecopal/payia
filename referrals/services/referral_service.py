import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from referrals.models import Referral, Commission
from core.models import User, AuditLog
from wallet.models import LedgerEntry
from notifications.models import Notification

logger = logging.getLogger('referrals')

MAX_LEVELS = 2

LEVEL_PERCENTAGES = {
    1: Decimal('10'),
    2: Decimal('5'),
}


class ReferralService:
    """Referral commission service - revenue-based model.

    Financial rule:
        Commissions are ONLY generated when a referred user's machine
        produces revenue. They are NEVER taken from deposits.

        revenue_amount = commission_L1 + commission_L2 + user_net_amount

    Level 1 (direct referrer): 10% of machine revenue
    Level 2 (referrer's referrer): 5% of machine revenue
    Total commission: 15% of machine revenue
    User receives: 85% of machine revenue
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
            return None, "Vous ne pouvez pas vous parrainer vous-meme."

        try:
            referrer = User.objects.get(referral_code=referral_code, is_active=True)
        except User.DoesNotExist:
            return None, "Code de parrainage invalide."

        with transaction.atomic():
            if Referral.objects.filter(referred_user=new_user).exists():
                return None, "Vous avez deja un parrain."

            try:
                referral = Referral.objects.create(
                    referrer=referrer,
                    referred_user=new_user,
                    referral_level=1,
                )
            except Exception:
                return None, "Erreur lors de l'inscription du parrainage."

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
        stats = {'level_1': 0, 'level_2': 0}

        level_1_refs = Referral.objects.filter(
            referrer=user, is_active=True
        ).select_related('referred_user').only('referred_user_id')
        stats['level_1'] = level_1_refs.count()

        for ref in level_1_refs:
            stats['level_2'] += Referral.objects.filter(
                referrer=ref.referred_user, is_active=True
            ).count()

        stats['total'] = stats['level_1'] + stats['level_2']
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
        """Return configured commission percentages per level."""
        return dict(LEVEL_PERCENTAGES)

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
        """Walk up the referral chain from a source user (max 2 levels).

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
    def calculate_revenue_commission(rental, revenue_amount):
        """Calculate and credit referral commissions from machine revenue.

        This is called EVERY TIME a machine generates revenue.
        Commissions are deducted from the revenue, and the user receives the net.

        Args:
            rental: The AiRental instance
            revenue_amount: Gross revenue the machine generated this cycle

        Returns:
            dict with:
                'commissions': [Commission, ...],
                'total_commission': Decimal,
                'net_amount': Decimal (what the user receives),
        """
        from wallet.services.wallet_service import WalletService

        with transaction.atomic():
            percentages = ReferralService.get_level_percentages()
            chain = ReferralService._walk_referral_chain(rental.user)
            base_amount = Decimal(str(revenue_amount))

            commissions = []
            total_commission = Decimal('0')

            for level, referrer in chain:
                pct = percentages.get(level, Decimal('0'))
                if pct <= 0:
                    continue

                commission_amount = (base_amount * pct / Decimal('100')).quantize(Decimal('0.01'))
                if commission_amount <= 0:
                    continue

                is_eligible = ReferralService._is_referrer_eligible(referrer)

                commission = Commission.objects.create(
                    user=referrer,
                    source_user=rental.user,
                    referral_level=level,
                    ai_revenue=None,
                    percentage=pct,
                    gross_revenue=base_amount,
                    amount=commission_amount,
                    status=Commission.Status.APPROVED if is_eligible else Commission.Status.CANCELLED,
                )

                if is_eligible:
                    wallet, ledger_entry = WalletService.credit_wallet(
                        user=referrer,
                        amount=commission_amount,
                        entry_type=LedgerEntry.EntryType.REFERRAL_COMMISSION,
                        description=(
                            f'Commission parrainage niv.{level} - '
                            f'Revenu machine de {rental.user.phone_number} ({base_amount} XAF)'
                        ),
                        reference_type='Commission',
                        reference_id=commission.pk,
                    )
                    commission.ledger_entry = ledger_entry
                    commission.save(update_fields=['ledger_entry', 'updated_at'])

                    total_commission += commission_amount

                    AuditLog.objects.create(
                        actor=referrer,
                        action='referral.commission.credited',
                        target_type='Commission',
                        target_id=str(commission.pk),
                        description=(
                            f'Commission L{level}: {commission_amount} XAF '
                            f'revenu machine {rental.offer.name} de {rental.user.phone_number}'
                        ),
                    )

                    Notification.objects.create(
                        user=referrer,
                        notification_type='COMMISSION_RECEIVED',
                        title='Commission de parrainage reçue',
                        message=f'Vous avez reçu une commission de {commission_amount} XAF (Niveau {level}) provenant du filleul {rental.user.phone_number}.',
                        link='/referrals/',
                    )

                commissions.append(commission)

            net_amount = base_amount - total_commission
            if net_amount < 0:
                net_amount = Decimal('0')

            logger.info(
                f'Revenue commission: rental={rental.pk}, gross={base_amount}, '
                f'commission={total_commission}, net={net_amount}, '
                f'levels={len(commissions)}'
            )

            return {
                'commissions': commissions,
                'total_commission': total_commission,
                'net_amount': net_amount,
            }

    @staticmethod
    def get_revenue_breakdown(revenue_amount):
        """Calculate the revenue breakdown without creating records.

        Used for display purposes (e.g., offer detail page).

        Returns:
            dict with:
                'gross': Decimal,
                'commission_l1': Decimal,
                'commission_l2': Decimal,
                'total_commission': Decimal,
                'net': Decimal,
        """
        base = Decimal(str(revenue_amount))
        pct_l1 = LEVEL_PERCENTAGES.get(1, Decimal('0'))
        pct_l2 = LEVEL_PERCENTAGES.get(2, Decimal('0'))

        commission_l1 = (base * pct_l1 / Decimal('100')).quantize(Decimal('0.01'))
        commission_l2 = (base * pct_l2 / Decimal('100')).quantize(Decimal('0.01'))
        total = commission_l1 + commission_l2
        net = base - total
        if net < 0:
            net = Decimal('0')

        return {
            'gross': base,
            'commission_l1': commission_l1,
            'commission_l2': commission_l2,
            'total_commission': total,
            'net': net,
        }
