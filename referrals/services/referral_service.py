from decimal import Decimal
from django.db import transaction
from referrals.models import Referral, Commission
from core.models import User, Setting, AuditLog
from notifications.models import Notification


class ReferralService:
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

        ReferralService._build_chain(referrer, new_user)

        Notification.objects.create(
            user=referrer,
            notification_type='NEW_REFERRAL',
            title='Nouveau filleul',
            message=f'Un nouvel utilisateur s\'est inscrit avec votre code de parrainage.',
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
    def _build_chain(referrer, new_user):
        pass

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
    def calculate_commission(source_user, source_type, source_id, amount):
        percentages = {}
        for i in range(1, 6):
            try:
                percentages[i] = Decimal(Setting.objects.get(key=f'level_{i}_percentage').value)
            except Setting.DoesNotExist:
                defaults = {1: 10, 2: 5, 3: 3, 4: 2, 5: 1}
                percentages[i] = Decimal(str(defaults.get(i, 0)))

        commissions = []
        level = 1
        current_user = source_user

        while level <= 5:
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
        from wallet.services.wallet_service import WalletService
        with transaction.atomic():
            commission.approve()
            wallet, ledger_entry = WalletService.credit_wallet(
                user=commission.user,
                amount=commission.amount,
                entry_type='REFERRAL_COMMISSION',
                description=f'Commission niveau {commission.referral_level}',
                reference_type='Commission',
                reference_id=commission.pk,
            )
            commission.ledger_entry = ledger_entry
            commission.save(update_fields=['ledger_entry'])
        return commission
