from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from wallet.models import Wallet
from transactions.models import Deposit, Withdrawal
from referrals.models import Commission
from ai_services.models import AiRental


class Command(BaseCommand):
    help = 'Recalculate wallet totals from actual deposit/withdrawal/commission data'

    def handle(self, *args, **options):
        wallets = Wallet.objects.select_related('user').all()
        count = 0

        for wallet in wallets:
            user = wallet.user

            dep_sum = Deposit.objects.filter(
                user=user, status='completed'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            wit_sum = Withdrawal.objects.filter(
                user=user, status='completed'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            comm_sum = Commission.objects.filter(
                user=user, status='approved'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            ai_earn = AiRental.objects.filter(
                user=user
            ).aggregate(t=Sum('total_revenue_earned'))['t'] or Decimal('0')

            total_earnings = ai_earn + comm_sum

            wallet.total_deposited = dep_sum
            wallet.total_withdrawn = wit_sum
            wallet.referral_earnings = comm_sum
            wallet.total_earnings = total_earnings
            wallet.save(update_fields=[
                'total_deposited', 'total_withdrawn',
                'referral_earnings', 'total_earnings', 'updated_at',
            ])
            count += 1

            self.stdout.write(
                f'  {user.username}: '
                f'dep={dep_sum} wit={wit_sum} '
                f'earn={total_earnings} ref={comm_sum}'
            )

        self.stdout.write(self.style.SUCCESS(f'\n✓ {count} wallets recalculés.'))
