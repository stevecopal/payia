from decimal import Decimal
from django.test import TestCase
from core.models import User, UserProfile
from wallet.models import Wallet, LedgerEntry
from wallet.services.wallet_service import WalletService


class WalletServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number='+2250700000005',
        )
        UserProfile.objects.get_or_create(user=self.user)
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user)

    def test_get_wallet(self):
        wallet = WalletService.get_wallet(self.user)
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.available_balance, Decimal('0'))

    def test_get_wallet_creates_if_missing(self):
        Wallet.objects.filter(user=self.user).delete()
        wallet = WalletService.get_wallet(self.user)
        self.assertIsNotNone(wallet)
        self.assertEqual(wallet.available_balance, Decimal('0'))

    def test_credit_wallet(self):
        wallet, entry = WalletService.credit_wallet(
            user=self.user,
            amount=Decimal('1000'),
            entry_type='deposit',
            description='Test deposit',
        )
        self.assertEqual(wallet.available_balance, Decimal('1000'))
        self.assertEqual(entry.amount, Decimal('1000'))
        self.assertEqual(entry.balance_before, Decimal('0'))
        self.assertEqual(entry.balance_after, Decimal('1000'))

    def test_credit_updates_total_deposited(self):
        WalletService.credit_wallet(self.user, Decimal('1000'), 'deposit', 'Test')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_deposited, Decimal('1000'))

    def test_credit_ai_revenue_updates_earnings(self):
        WalletService.credit_wallet(self.user, Decimal('500'), 'ai_revenue', 'Test')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_earnings, Decimal('500'))

    def test_credit_referral_commission_updates_earnings(self):
        WalletService.credit_wallet(self.user, Decimal('200'), 'referral_commission', 'Test')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_earnings, Decimal('200'))
        self.assertEqual(self.wallet.referral_earnings, Decimal('200'))

    def test_debit_wallet(self):
        WalletService.credit_wallet(self.user, Decimal('5000'), 'deposit', 'Initial')
        wallet, entry = WalletService.debit_wallet(
            user=self.user,
            amount=Decimal('2000'),
            entry_type='withdrawal',
            description='Test withdrawal',
        )
        self.assertEqual(wallet.available_balance, Decimal('3000'))
        self.assertEqual(entry.amount, Decimal('-2000'))

    def test_debit_updates_total_withdrawn(self):
        WalletService.credit_wallet(self.user, Decimal('5000'), 'deposit', 'Initial')
        WalletService.debit_wallet(self.user, Decimal('2000'), 'withdrawal', 'Test')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_withdrawn, Decimal('2000'))

    def test_debit_insufficient_balance(self):
        with self.assertRaises(ValueError):
            WalletService.debit_wallet(
                self.user, Decimal('1000'), 'withdrawal', 'Test',
            )

    def test_reserve_amount(self):
        WalletService.credit_wallet(self.user, Decimal('5000'), 'deposit', 'Initial')
        wallet = WalletService.reserve_amount(self.user, Decimal('2000'))
        self.assertEqual(wallet.available_balance, Decimal('3000'))
        self.assertEqual(wallet.pending_balance, Decimal('2000'))

    def test_reserve_insufficient_balance(self):
        with self.assertRaises(ValueError):
            WalletService.reserve_amount(self.user, Decimal('2000'))

    def test_release_amount(self):
        WalletService.credit_wallet(self.user, Decimal('5000'), 'deposit', 'Initial')
        WalletService.reserve_amount(self.user, Decimal('2000'))
        wallet = WalletService.release_amount(self.user, Decimal('2000'))
        self.assertEqual(wallet.available_balance, Decimal('5000'))
        self.assertEqual(wallet.pending_balance, Decimal('0'))

    def test_release_exceeds_pending(self):
        with self.assertRaises(ValueError):
            WalletService.release_amount(self.user, Decimal('1000'))


class LedgerEntryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number='+2250700000006',
        )
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user)

    def test_ledger_entries_created(self):
        WalletService.credit_wallet(self.user, Decimal('1000'), 'deposit', 'Test')
        WalletService.debit_wallet(self.user, Decimal('500'), 'withdrawal', 'Test')
        entries = LedgerEntry.objects.filter(user=self.user)
        self.assertEqual(entries.count(), 2)

    def test_ledger_balance_tracking(self):
        WalletService.credit_wallet(self.user, Decimal('1000'), 'deposit', 'Test')
        WalletService.credit_wallet(self.user, Decimal('500'), 'ai_revenue', 'Test')
        entry = LedgerEntry.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertEqual(entry.balance_after, Decimal('1500'))

    def test_ledger_entry_types(self):
        WalletService.credit_wallet(self.user, Decimal('1000'), 'deposit', 'Test')
        WalletService.debit_wallet(self.user, Decimal('500'), 'withdrawal', 'Test')
        types = LedgerEntry.objects.filter(user=self.user).values_list(
            'entry_type', flat=True,
        )
        self.assertIn('deposit', types)
        self.assertIn('withdrawal', types)

    def test_ledger_reference_tracking(self):
        WalletService.credit_wallet(
            self.user, Decimal('1000'), 'deposit', 'Test',
            reference_type='Deposit', reference_id=42,
        )
        entry = LedgerEntry.objects.filter(user=self.user).first()
        self.assertEqual(entry.reference_type, 'Deposit')
        self.assertEqual(entry.reference_id, 42)

    def test_ledger_wallet_link(self):
        WalletService.credit_wallet(self.user, Decimal('1000'), 'deposit', 'Test')
        entry = LedgerEntry.objects.filter(user=self.user).first()
        self.assertEqual(entry.wallet, self.wallet)

    def test_wallet_model_credit(self):
        self.wallet.credit(Decimal('500'), description='Direct credit')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('500'))

    def test_wallet_model_debit(self):
        self.wallet.credit(Decimal('1000'), description='Funding')
        self.wallet.debit(Decimal('300'), description='Direct debit')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('700'))

    def test_wallet_model_debit_insufficient(self):
        with self.assertRaises(ValueError):
            self.wallet.debit(Decimal('1000'), description='Overdraft')

    def test_wallet_model_reserve_release(self):
        self.wallet.credit(Decimal('1000'), description='Funding')
        self.wallet.reserve(Decimal('400'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('600'))
        self.assertEqual(self.wallet.pending_balance, Decimal('400'))
        self.wallet.release(Decimal('400'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('1000'))
        self.assertEqual(self.wallet.pending_balance, Decimal('0'))

    def test_wallet_model_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            self.wallet.credit(Decimal('-100'), description='Negative')
        with self.assertRaises(ValueError):
            self.wallet.debit(Decimal('-100'), description='Negative')
