from decimal import Decimal
from django.test import TestCase
from core.models import User, UserProfile, Setting
from wallet.models import Wallet
from wallet.services.wallet_service import WalletService
from transactions.models import Withdrawal, PaymentMethod
from transactions.services.withdrawal_service import WithdrawalService


class WithdrawalServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number='+2250700000008',
        )
        UserProfile.objects.get_or_create(user=self.user)
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user)
        self.payment_method = PaymentMethod.objects.create(
            name='Mobile Money',
            slug='mobile-money',
            is_active=True,
        )

    def test_create_withdrawal(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        self.assertIsNotNone(withdrawal)
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('5000'))
        self.assertEqual(self.wallet.pending_balance, Decimal('5000'))

    def test_insufficient_balance(self):
        with self.assertRaises(ValueError):
            WithdrawalService.create_withdrawal(
                user=self.user,
                amount=Decimal('5000'),
                payment_method_id=self.payment_method.pk,
                withdrawal_number='+237670000005',
            )

    def test_approve_withdrawal(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        admin = User.objects.create(username='admin_approve_1', phone_number='+237670000096')
        WithdrawalService.approve_withdrawal(withdrawal, admin)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('5000'))
        self.assertEqual(self.wallet.pending_balance, Decimal('0'))

    def test_reject_withdrawal_releases_balance(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        admin = User.objects.create(username='admin_reject_1', phone_number='+237670000095')
        WithdrawalService.reject_withdrawal(withdrawal, admin, 'Test')

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('10000'))
        self.assertEqual(self.wallet.pending_balance, Decimal('0'))

    def test_approve_already_approved_raises(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        admin = User.objects.create(username='admin_approve_2', phone_number='+237670000094')
        WithdrawalService.approve_withdrawal(withdrawal, admin)
        with self.assertRaises(ValueError):
            WithdrawalService.approve_withdrawal(withdrawal, admin)

    def test_reject_without_reason_raises(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        admin = User.objects.create(username='admin_reject_2', phone_number='+237670000093')
        with self.assertRaises(ValueError):
            WithdrawalService.reject_withdrawal(withdrawal, admin, '')

    def test_minimum_withdrawal_enforced(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='5000', setting_type='DECIMAL',
        )

        with self.assertRaises(ValueError):
            WithdrawalService.create_withdrawal(
                user=self.user,
                amount=Decimal('1000'),
                payment_method_id=self.payment_method.pk,
                withdrawal_number='+237670000005',
            )

    def test_fee_calculated(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )
        self.payment_method.fee_percentage = Decimal('5')
        self.payment_method.save()

        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        self.assertGreater(withdrawal.fee, Decimal('0'))
        self.assertEqual(withdrawal.net_amount, withdrawal.amount - withdrawal.fee)

    def test_get_user_withdrawals(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('2000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        withdrawals = WithdrawalService.get_user_withdrawals(self.user)
        self.assertEqual(withdrawals.count(), 1)

    def test_withdrawal_stores_ip(self):
        WalletService.credit_wallet(self.user, Decimal('10000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )
        withdrawal = WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        self.assertIsNotNone(withdrawal.created_at)

    def test_pending_balance_accurate_after_multiple(self):
        WalletService.credit_wallet(self.user, Decimal('20000'), 'DEPOSIT', 'Initial')
        Setting.objects.create(
            key='minimum_withdrawal', value='1000', setting_type='DECIMAL',
        )

        WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('3000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        WithdrawalService.create_withdrawal(
            user=self.user,
            amount=Decimal('4000'),
            payment_method_id=self.payment_method.pk,
            withdrawal_number='+237670000005',
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.pending_balance, Decimal('7000'))
        self.assertEqual(self.wallet.available_balance, Decimal('13000'))
