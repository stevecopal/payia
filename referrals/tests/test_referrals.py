from decimal import Decimal
from django.test import TestCase
from django.db import transaction
from django.db import IntegrityError

from core.models import User, Setting, UserProfile
from wallet.models import Wallet, LedgerEntry
from wallet.services.wallet_service import WalletService
from transactions.models import Deposit, PaymentMethod
from transactions.services.deposit_service import DepositService
from referrals.models import Referral, Commission, ReferralAllocation
from referrals.services.referral_service import ReferralService


class ReferralRegistrationTestCase(TestCase):
    """Tests 1-3: Basic referral registration."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')

    def test_no_referrer(self):
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(len(commissions), 0)

    def test_single_level_referrer(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].amount, Decimal('500.00'))
        self.assertEqual(commissions[0].referral_level, 1)

    def test_self_referral_blocked(self):
        referral, error = ReferralService.register_referral(
            self.user1, self.user1.referral_code,
        )
        self.assertIsNone(referral)
        self.assertIsNotNone(error)

    def test_duplicate_referral_blocked(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        referral2, error2 = ReferralService.register_referral(
            self.user2, self.user1.referral_code,
        )
        self.assertIsNone(referral2)

    def test_invalid_code(self):
        referral, error = ReferralService.register_referral(
            self.user2, 'INVALIDCODE',
        )
        self.assertIsNone(referral)
        self.assertIsNotNone(error)


class ReferralStatsTestCase(TestCase):
    """Tests for referral statistics."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')

    def test_get_referral_stats(self):
        user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        ReferralService.register_referral(user2, self.user1.referral_code)
        stats = ReferralService.get_referral_stats(self.user1)
        self.assertEqual(stats['level_1'], 1)
        self.assertEqual(stats['total'], 1)

    def test_five_level_chain(self):
        users = [self.user1]
        for i in range(5):
            user = User.objects.create(
                phone_number=f'+22507000000{20+i}',
                username=f'five_level_user_{i}',
            )
            ReferralService.register_referral(user, users[-1].referral_code)
            users.append(user)

        stats = ReferralService.get_referral_stats(self.user1)
        self.assertEqual(stats['level_1'], 1)
        self.assertEqual(stats['level_2'], 1)
        self.assertEqual(stats['level_3'], 1)
        self.assertEqual(stats['level_4'], 1)
        self.assertEqual(stats['level_5'], 1)
        self.assertEqual(stats['total'], 5)


class CommissionCalculationTestCase(TestCase):
    """Tests 10-16: Commission calculation at each level."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='level_2_percentage', value='5', setting_type='DECIMAL')
        Setting.objects.create(key='level_3_percentage', value='3', setting_type='DECIMAL')
        Setting.objects.create(key='level_4_percentage', value='2', setting_type='DECIMAL')
        Setting.objects.create(key='level_5_percentage', value='1', setting_type='DECIMAL')

    def test_level_1_commission(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].amount, Decimal('500.00'))
        self.assertEqual(commissions[0].referral_level, 1)

    def test_level_2_commission(self):
        user3 = User.objects.create(phone_number='+2250700000030', username='user3')
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        ReferralService.register_referral(user3, self.user2.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=user3,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        amounts = {c.referral_level: c.amount for c in commissions}
        self.assertEqual(amounts[1], Decimal('500.00'))
        self.assertEqual(amounts[2], Decimal('250.00'))

    def test_three_levels(self):
        user3 = User.objects.create(phone_number='+2250700000030', username='user3')
        user4 = User.objects.create(phone_number='+2250700000040', username='user4')
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        ReferralService.register_referral(user3, self.user2.referral_code)
        ReferralService.register_referral(user4, user3.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=user4,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        amounts = {c.referral_level: c.amount for c in commissions}
        self.assertEqual(amounts[1], Decimal('500.00'))
        self.assertEqual(amounts[2], Decimal('250.00'))
        self.assertEqual(amounts[3], Decimal('150.00'))

    def test_five_levels_total(self):
        users = [self.user1]
        for i in range(5):
            user = User.objects.create(
                phone_number=f'+22507000000{50+i}',
                username=f'five_user_{i}',
            )
            ReferralService.register_referral(user, users[-1].referral_code)
            users.append(user)

        source = users[-1]
        commissions = ReferralService.calculate_commission(
            source_user=source,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        amounts = {c.referral_level: c.amount for c in commissions}
        self.assertEqual(amounts[1], Decimal('500.00'))
        self.assertEqual(amounts[2], Decimal('250.00'))
        self.assertEqual(amounts[3], Decimal('150.00'))
        self.assertEqual(amounts[4], Decimal('100.00'))
        self.assertEqual(amounts[5], Decimal('50.00'))
        total = sum(amounts.values())
        self.assertEqual(total, Decimal('1050.00'))

    def test_commission_default_percentage(self):
        Setting.objects.all().delete()
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('10000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].percentage, Decimal('10'))

    def test_commission_status_pending(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(commissions[0].status, 'pending')

    def test_approve_commission(self):
        Wallet.objects.get_or_create(user=self.user1)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        ReferralService.approve_commission(commissions[0])
        commissions[0].refresh_from_db()
        self.assertEqual(commissions[0].status, 'approved')


class CommissionTotalCalculationTestCase(TestCase):
    """Tests 15-16: Commission total and productive amount calculation."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')

    def test_commission_total(self):
        user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        ReferralService.register_referral(user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        total = sum(c.amount for c in commissions)
        self.assertEqual(total, Decimal('500.00'))

    def test_productive_amount_calculation(self):
        amount = Decimal('5000')
        commission = Decimal('500')
        productive = amount - commission
        self.assertEqual(productive, Decimal('4500'))


class DepositIntegrationTestCase(TestCase):
    """Tests 17-19: Deposit status handling (PENDING/APPROVED/REJECTED)."""

    def setUp(self):
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        self.user1 = User.objects.create(phone_number='+2250700000009', username='referrer')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='depositor')
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_pending_deposit_no_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX001',
        )
        self.assertEqual(deposit.status, 'pending_review')
        self.assertFalse(Commission.objects.filter(source_user=self.user2).exists())

    def test_approved_deposit_creates_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX002',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        self.assertEqual(deposit.status, 'completed')
        self.assertEqual(deposit.referral_commission_total, Decimal('500.00'))
        self.assertEqual(deposit.productive_amount, Decimal('4500.00'))

        commissions = Commission.objects.filter(source_user=self.user2)
        self.assertEqual(commissions.count(), 1)
        self.assertEqual(commissions.first().amount, Decimal('500.00'))

    def test_rejected_deposit_no_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX003',
        )
        DepositService.reject_deposit(deposit, self.admin, 'Test rejection')
        self.assertEqual(deposit.status, 'rejected')
        self.assertFalse(Commission.objects.filter(source_user=self.user2).exists())


class IdempotencyTestCase(TestCase):
    """Tests 20-21: Double processing prevention."""

    def setUp(self):
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        self.user1 = User.objects.create(phone_number='+2250700000009', username='referrer')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='depositor')
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_double_allocation_prevented(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX004',
        )
        DepositService.approve_deposit(deposit, self.admin)

        wallet1 = Wallet.objects.get(user=self.user1)
        balance_after_first = wallet1.available_balance

        DepositService.approve_deposit(deposit, self.admin)

        wallet2 = Wallet.objects.get(user=self.user1)
        self.assertEqual(wallet2.available_balance, balance_after_first)

        allocations = ReferralAllocation.objects.filter(deposit=deposit)
        self.assertEqual(allocations.count(), 1)

    def test_commission_not_duplicated(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX005',
        )
        DepositService.approve_deposit(deposit, self.admin)

        commissions = Commission.objects.filter(source_user=self.user2)
        self.assertEqual(commissions.count(), 1)


class FinancialConservationTestCase(TestCase):
    """Tests 33-34: Financial conservation principle."""

    def setUp(self):
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        self.user_a = User.objects.create(phone_number='+2250700000009', username='user_a')
        self.user_b = User.objects.create(phone_number='+2250700000010', username='user_b')
        Wallet.objects.get_or_create(user=self.user_a)
        Wallet.objects.get_or_create(user=self.user_b)
        ReferralService.register_referral(self.user_b, self.user_a.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_single_level_conservation(self):
        deposit = Deposit.objects.create(
            user=self.user_b,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX006',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        self.assertEqual(deposit.amount, Decimal('5000'))
        self.assertEqual(deposit.referral_commission_total, Decimal('500'))
        self.assertEqual(deposit.productive_amount, Decimal('4500'))

        conservation_check = deposit.referral_commission_total + deposit.productive_amount
        self.assertEqual(conservation_check, deposit.amount)

    def test_five_level_conservation(self):
        users = [self.user_a, self.user_b]
        for i in range(4):
            user = User.objects.create(
                phone_number=f'+22507000000{30+i}',
                username=f'conservation_user_{i}',
            )
            Wallet.objects.get_or_create(user=user)
            ReferralService.register_referral(user, users[-1].referral_code)
            users.append(user)

        Setting.objects.create(key='level_2_percentage', value='5', setting_type='DECIMAL')
        Setting.objects.create(key='level_3_percentage', value='3', setting_type='DECIMAL')
        Setting.objects.create(key='level_4_percentage', value='2', setting_type='DECIMAL')
        Setting.objects.create(key='level_5_percentage', value='1', setting_type='DECIMAL')

        source = users[-1]
        deposit = Deposit.objects.create(
            user=source,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX007',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        self.assertEqual(deposit.referral_commission_total, Decimal('1050.00'))
        self.assertEqual(deposit.productive_amount, Decimal('3950.00'))

        conservation_check = deposit.referral_commission_total + deposit.productive_amount
        self.assertEqual(conservation_check, deposit.amount)

        allocations = ReferralAllocation.objects.filter(deposit=deposit)
        self.assertEqual(allocations.count(), 5)

        alloc_total = sum(a.amount for a in allocations)
        self.assertEqual(alloc_total, Decimal('1050.00'))


class SafetyCeilingTestCase(TestCase):
    """Tests 8-9: Safety ceiling validation."""

    def test_valid_configuration(self):
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='level_2_percentage', value='5', setting_type='DECIMAL')
        Setting.objects.create(key='level_3_percentage', value='3', setting_type='DECIMAL')
        Setting.objects.create(key='level_4_percentage', value='2', setting_type='DECIMAL')
        Setting.objects.create(key='level_5_percentage', value='1', setting_type='DECIMAL')
        Setting.objects.create(key='max_total_commission_percentage', value='90', setting_type='DECIMAL')

        is_valid, total, max_allowed, error = ReferralService.validate_rate_configuration()
        self.assertTrue(is_valid)
        self.assertEqual(total, Decimal('21'))
        self.assertEqual(max_allowed, Decimal('90'))

    def test_invalid_configuration(self):
        Setting.objects.create(key='level_1_percentage', value='60', setting_type='DECIMAL')
        Setting.objects.create(key='level_2_percentage', value='30', setting_type='DECIMAL')
        Setting.objects.create(key='level_3_percentage', value='20', setting_type='DECIMAL')
        Setting.objects.create(key='level_4_percentage', value='0', setting_type='DECIMAL')
        Setting.objects.create(key='level_5_percentage', value='0', setting_type='DECIMAL')
        Setting.objects.create(key='max_total_commission_percentage', value='90', setting_type='DECIMAL')

        is_valid, total, max_allowed, error = ReferralService.validate_rate_configuration()
        self.assertFalse(is_valid)
        self.assertEqual(total, Decimal('110'))
        self.assertIsNotNone(error)


class MissingLevelsTestCase(TestCase):
    """Tests 28: When some levels don't exist."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='level_2_percentage', value='5', setting_type='DECIMAL')

    def test_only_existing_levels_get_commission(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].referral_level, 1)
        self.assertEqual(commissions[0].amount, Decimal('500.00'))


class InactiveReferrerTestCase(TestCase):
    """Test 27: Inactive/suspended referrer handling."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_suspended_referrer_gets_cancelled_commission(self):
        self.user1.is_suspended = True
        self.user1.is_active = False
        self.user1.save()

        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX008',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        commission = Commission.objects.get(source_user=self.user2)
        self.assertEqual(commission.status, Commission.Status.CANCELLED)

        allocation = ReferralAllocation.objects.get(deposit=deposit)
        self.assertEqual(allocation.status, ReferralAllocation.Status.CANCELLED)


class EligibleReferrerTestCase(TestCase):
    """Test: Eligible referrer gets credited."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_active_referrer_gets_approved_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX009',
        )
        DepositService.approve_deposit(deposit, self.admin)

        commission = Commission.objects.get(source_user=self.user2)
        self.assertEqual(commission.status, Commission.Status.APPROVED)

        wallet = Wallet.objects.get(user=self.user1)
        self.assertGreater(wallet.available_balance, Decimal('0'))


class ReversalTestCase(TestCase):
    """Test 23: Commission reversal."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_reversal_restores_balance(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX010',
        )
        DepositService.approve_deposit(deposit, self.admin)

        wallet_before = Wallet.objects.get(user=self.user1)
        balance_before = wallet_before.available_balance

        allocation = ReferralAllocation.objects.get(deposit=deposit, status='approved')
        ReferralService.reverse_commission_allocation(allocation, 'Test reversal')

        wallet_after = Wallet.objects.get(user=self.user1)
        self.assertEqual(wallet_after.available_balance, balance_before - Decimal('500'))

        deposit.refresh_from_db()
        self.assertEqual(deposit.referral_commission_total, Decimal('0'))
        self.assertEqual(deposit.productive_amount, Decimal('5000'))

    def test_cannot_reverse_non_approved(self):
        user3 = User.objects.create(phone_number='+2250700000030', username='user3')
        user4 = User.objects.create(phone_number='+2250700000040', username='user4')
        Wallet.objects.get_or_create(user=user3)
        Wallet.objects.get_or_create(user=user4)
        ReferralService.register_referral(user3, self.user1.referral_code)
        ReferralService.register_referral(user4, user3.referral_code)

        Setting.objects.create(key='level_2_percentage', value='5', setting_type='DECIMAL')

        user3.is_suspended = True
        user3.is_active = False
        user3.save()

        deposit = Deposit.objects.create(
            user=user4,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX011',
        )
        DepositService.approve_deposit(deposit, self.admin)

        allocation = ReferralAllocation.objects.filter(
            deposit=deposit, status='cancelled'
        ).first()
        self.assertIsNotNone(allocation)
        with self.assertRaises(ValueError):
            ReferralService.reverse_commission_allocation(allocation, 'Should fail')


class WalletCreditTestCase(TestCase):
    """Tests: Wallet correctly credited for commissions."""

    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo',
            slug='mtn-momo',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )

    def test_wallet_balance_increases_by_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX012',
        )
        DepositService.approve_deposit(deposit, self.admin)

        wallet = Wallet.objects.get(user=self.user1)
        self.assertEqual(wallet.available_balance, Decimal('500.00'))
        self.assertEqual(wallet.referral_earnings, Decimal('500.00'))
        self.assertEqual(wallet.total_earnings, Decimal('500.00'))

    def test_ledger_entry_created(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX013',
        )
        DepositService.approve_deposit(deposit, self.admin)

        entries = LedgerEntry.objects.filter(
            user=self.user1,
            entry_type='referral_commission',
        )
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().amount, Decimal('500.00'))


class AllocationReferenceTestCase(TestCase):
    """Tests: Allocation references are unique and correct."""

    def test_reference_format(self):
        ref = ReferralAllocation.generate_reference(123, 2)
        self.assertEqual(ref, 'DEP-123-LVL-2')

    def test_unique_constraint_per_deposit_level(self):
        user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        Wallet.objects.get_or_create(user=user1)
        Wallet.objects.get_or_create(user=user2)
        ReferralService.register_referral(user2, user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        pm = PaymentMethod.objects.create(
            name='MTN MoMo', slug='mtn-momo', phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#', is_active=True,
        )
        deposit = Deposit.objects.create(
            user=user2, amount=Decimal('5000'), payment_method=pm, transaction_id='TX014',
        )
        DepositService.approve_deposit(deposit, admin)

        allocs = ReferralAllocation.objects.filter(deposit=deposit)
        self.assertEqual(allocs.count(), 1)


class DashboardStatsTestCase(TestCase):
    """Tests: Commission stats by level."""

    def test_commission_stats(self):
        user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        stats = ReferralService.get_commission_stats(user1)
        self.assertEqual(stats['total'], Decimal('0'))
        for level in range(1, 6):
            self.assertEqual(stats[f'level_{level}'], Decimal('0'))


class ProductiveAmountOnDepositTestCase(TestCase):
    """Tests: Productive amount correctly stored on deposit."""

    def setUp(self):
        self.admin = User.objects.create(
            phone_number='+2250700000099', username='admin', is_staff=True
        )
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')
        Wallet.objects.get_or_create(user=self.user1)
        Wallet.objects.get_or_create(user=self.user2)
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        Setting.objects.create(key='level_1_percentage', value='10', setting_type='DECIMAL')
        Setting.objects.create(key='minimum_deposit', value='500', setting_type='INTEGER')
        self.payment_method = PaymentMethod.objects.create(
            name='MTN MoMo', slug='mtn-momo', phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#', is_active=True,
        )

    def test_productive_amount_equals_amount_minus_commission(self):
        deposit = Deposit.objects.create(
            user=self.user2,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX015',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        self.assertEqual(deposit.productive_amount, deposit.amount - deposit.referral_commission_total)

    def test_no_referrer_full_productive_amount(self):
        user3 = User.objects.create(phone_number='+2250700000030', username='user3')
        Wallet.objects.get_or_create(user=user3)
        deposit = Deposit.objects.create(
            user=user3,
            amount=Decimal('5000'),
            payment_method=self.payment_method,
            transaction_id='TX016',
        )
        DepositService.approve_deposit(deposit, self.admin)
        deposit.refresh_from_db()

        self.assertEqual(deposit.referral_commission_total, Decimal('0'))
        self.assertEqual(deposit.productive_amount, Decimal('5000'))
