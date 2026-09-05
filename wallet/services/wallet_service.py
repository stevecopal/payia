from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from wallet.models import Wallet, LedgerEntry


class WalletService:
    @staticmethod
    def get_wallet(user):
        wallet, created = Wallet.objects.get_or_create(user=user)
        return wallet

    @staticmethod
    @transaction.atomic
    def credit_wallet(user, amount, entry_type, description='', reference_type='', reference_id=None):
        wallet = Wallet.objects.select_for_update().get(user=user)
        amount = Decimal(str(amount))
        entry_type_str = str(entry_type).lower()
        balance_before = wallet.available_balance
        wallet.available_balance += amount
        wallet.save(update_fields=['available_balance', 'updated_at'])

        if entry_type_str == LedgerEntry.EntryType.DEPOSIT:
            wallet.total_deposited += amount
            wallet.save(update_fields=['total_deposited', 'updated_at'])
        elif entry_type_str in [LedgerEntry.EntryType.AI_REVENUE, LedgerEntry.EntryType.REFERRAL_COMMISSION]:
            wallet.total_earnings += amount
            if entry_type_str == LedgerEntry.EntryType.REFERRAL_COMMISSION:
                wallet.referral_earnings += amount
            wallet.save(update_fields=['total_earnings', 'referral_earnings', 'updated_at'])

        ledger_entry = LedgerEntry.objects.create(
            user=user,
            wallet=wallet,
            entry_type=entry_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )
        return wallet, ledger_entry

    @staticmethod
    @transaction.atomic
    def debit_wallet(user, amount, entry_type, description='', reference_type='', reference_id=None):
        wallet = Wallet.objects.select_for_update().get(user=user)
        amount = Decimal(str(amount))
        entry_type_str = str(entry_type).lower()

        if wallet.available_balance < amount:
            raise ValueError("Solde insuffisant.")

        balance_before = wallet.available_balance
        wallet.available_balance -= amount

        if entry_type_str == LedgerEntry.EntryType.WITHDRAWAL:
            wallet.total_withdrawn += amount

        wallet.save(update_fields=['available_balance', 'total_withdrawn', 'updated_at'])

        ledger_entry = LedgerEntry.objects.create(
            user=user,
            wallet=wallet,
            entry_type=entry_type,
            amount=-amount,
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )
        return wallet, ledger_entry

    @staticmethod
    def sync_totals(user):
        """Recalculate wallet totals from ALL sources of truth:
        ledger entries, Commission model, and AiRevenue model."""
        from referrals.models import Commission
        from ai_services.models import AiRevenue

        wallet = Wallet.objects.select_for_update().get(user=user)
        ledger = LedgerEntry.objects.filter(user=user)

        wallet.total_deposited = ledger.filter(
            entry_type__in=['deposit', 'DEPOSIT']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        wallet.total_withdrawn = abs(ledger.filter(
            entry_type__in=['withdrawal', 'WITHDRAWAL']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'))

        wallet.referral_earnings = Commission.objects.filter(
            user=user, status__in=['approved', 'available']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        ai_earnings = AiRevenue.objects.filter(
            user=user, status='credited'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        wallet.total_earnings = wallet.referral_earnings + ai_earnings

        wallet.save(update_fields=[
            'total_deposited', 'total_withdrawn', 'total_earnings',
            'referral_earnings', 'updated_at',
        ])
        return wallet

    @staticmethod
    @transaction.atomic
    def reserve_amount(user, amount):
        wallet = Wallet.objects.select_for_update().get(user=user)
        amount = Decimal(str(amount))

        if wallet.available_balance < amount:
            raise ValueError("Solde insuffisant pour cette opération.")

        wallet.available_balance -= amount
        wallet.pending_balance += amount
        wallet.save(update_fields=['available_balance', 'pending_balance', 'updated_at'])
        return wallet

    @staticmethod
    @transaction.atomic
    def release_amount(user, amount):
        wallet = Wallet.objects.select_for_update().get(user=user)
        amount = Decimal(str(amount))

        if wallet.pending_balance < amount:
            raise ValueError("Montant à libérer supérieur au solde en attente.")

        wallet.pending_balance -= amount
        wallet.available_balance += amount
        wallet.save(update_fields=['available_balance', 'pending_balance', 'updated_at'])
        return wallet
