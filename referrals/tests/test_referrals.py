from decimal import Decimal
from django.test import TestCase
from core.models import User, Setting, UserProfile
from wallet.models import Wallet
from referrals.models import Referral, Commission
from referrals.services.referral_service import ReferralService


class ReferralServiceTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(phone_number='+2250700000009', username='user1')
        self.user2 = User.objects.create(phone_number='+2250700000010', username='user2')

    def test_register_referral(self):
        referral, error = ReferralService.register_referral(
            self.user2, self.user1.referral_code,
        )
        self.assertIsNotNone(referral)
        self.assertIsNone(error)
        self.assertEqual(referral.referral_level, 1)

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

    def test_get_referral_stats(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
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

    def test_commission_calculation(self):
        Setting.objects.create(
            key='level_1_percentage', value='10', setting_type='DECIMAL',
        )

        ReferralService.register_referral(self.user2, self.user1.referral_code)

        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='ai_rental',
            source_id=1,
            amount=Decimal('10000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].amount, Decimal('1000.00'))
        self.assertEqual(commissions[0].referral_level, 1)

    def test_commission_no_referrer_no_commission(self):
        Setting.objects.create(
            key='level_1_percentage', value='10', setting_type='DECIMAL',
        )
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='ai_rental',
            source_id=1,
            amount=Decimal('10000'),
        )
        self.assertEqual(len(commissions), 0)

    def test_commission_default_percentage(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='ai_rental',
            source_id=1,
            amount=Decimal('10000'),
        )
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0].percentage, Decimal('10'))

    def test_multi_level_commission(self):
        Setting.objects.create(
            key='level_1_percentage', value='10', setting_type='DECIMAL',
        )
        Setting.objects.create(
            key='level_2_percentage', value='5', setting_type='DECIMAL',
        )

        user3 = User.objects.create(phone_number='+2250700000030')
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        ReferralService.register_referral(user3, self.user2.referral_code)

        commissions = ReferralService.calculate_commission(
            source_user=user3,
            source_type='ai_rental',
            source_id=1,
            amount=Decimal('10000'),
        )
        self.assertEqual(len(commissions), 2)
        amounts = {c.referral_level: c.amount for c in commissions}
        self.assertEqual(amounts[1], Decimal('1000.00'))
        self.assertEqual(amounts[2], Decimal('500.00'))

    def test_get_user_referrals(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        referrals = ReferralService.get_user_referrals(self.user1)
        self.assertEqual(referrals.count(), 1)

    def test_get_user_referrals_by_level(self):
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        referrals = ReferralService.get_user_referrals(self.user1, level=1)
        self.assertEqual(referrals.count(), 1)
        referrals = ReferralService.get_user_referrals(self.user1, level=2)
        self.assertEqual(referrals.count(), 0)

    def test_get_referral_link(self):
        link = ReferralService.get_referral_link(self.user1)
        self.assertIn(self.user1.referral_code, link)

    def test_commission_status_pending(self):
        Setting.objects.create(
            key='level_1_percentage', value='10', setting_type='DECIMAL',
        )
        ReferralService.register_referral(self.user2, self.user1.referral_code)
        commissions = ReferralService.calculate_commission(
            source_user=self.user2,
            source_type='deposit',
            source_id=1,
            amount=Decimal('5000'),
        )
        self.assertEqual(commissions[0].status, 'pending')

    def test_approve_commission(self):
        Setting.objects.create(
            key='level_1_percentage', value='10', setting_type='DECIMAL',
        )
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
