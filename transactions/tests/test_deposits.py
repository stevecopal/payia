from decimal import Decimal
from django.test import TestCase
from core.models import User, UserProfile
from wallet.models import Wallet
from wallet.services.wallet_service import WalletService
from transactions.models import Deposit, PaymentMethod
from transactions.services.deposit_service import DepositService


class PaymentMethodTestCase(TestCase):
    def test_generate_ussd_code_mtn(self):
        pm = PaymentMethod.objects.create(
            name='MTN Mobile Money',
            slug='mtn-test',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
        )
        code = pm.generate_ussd_code(5000)
        self.assertEqual(code, '*126*14*5555*5000#')

    def test_generate_ussd_code_orange(self):
        pm = PaymentMethod.objects.create(
            name='Orange Money',
            slug='orange-test',
            phone_number='655123456',
            ussd_template='*150*1*{amount}#',
            is_active=True,
        )
        code = pm.generate_ussd_code(10000)
        self.assertEqual(code, '*150*1*10000#')

    def test_generate_ussd_code_empty_template(self):
        pm = PaymentMethod.objects.create(
            name='Cash',
            slug='cash-test',
            is_active=True,
        )
        code = pm.generate_ussd_code(5000)
        self.assertEqual(code, '')

    def test_generate_ussd_code_large_amount(self):
        pm = PaymentMethod.objects.create(
            name='MTN',
            slug='mtn-large',
            ussd_template='*126*{amount}#',
            is_active=True,
        )
        code = pm.generate_ussd_code(500000)
        self.assertEqual(code, '*126*500000#')

    def test_generate_ussd_code_no_placeholder_appends_amount(self):
        pm = PaymentMethod.objects.create(
            name='MTN Simple',
            slug='mtn-simple',
            ussd_template='*126*14#',
            is_active=True,
        )
        code = pm.generate_ussd_code(5000)
        self.assertEqual(code, '*126*14*5000#')

    def test_generate_ussd_code_no_hash_appends_amount(self):
        pm = PaymentMethod.objects.create(
            name='Orange Simple',
            slug='orange-simple',
            ussd_template='*150*1',
            is_active=True,
        )
        code = pm.generate_ussd_code(3000)
        self.assertEqual(code, '*150*1*3000')


class DepositServiceNewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser_new',
            phone_number='+237612345678',
        )
        self.wallet = Wallet.objects.get(user=self.user)
        self.payment_method = PaymentMethod.objects.create(
            name='MTN Mobile Money',
            slug='mtn-deposit-test',
            phone_number='690123456',
            ussd_template='*126*14*5555*{amount}#',
            is_active=True,
            min_amount=Decimal('500'),
            max_amount=Decimal('500000'),
        )

    def _create_admin(self, phone):
        return User.objects.create_user(
            username=f'admin_{phone}',
            phone_number=phone,
            is_staff=True,
        )

    def test_create_deposit_with_phone(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NEW_001',
            phone_number='+237698765432',
            ip_address='127.0.0.1',
        )
        self.assertIsNotNone(deposit)
        self.assertEqual(deposit.status, Deposit.Status.PENDING_REVIEW)
        self.assertEqual(deposit.phone_number, '+237698765432')
        self.assertEqual(deposit.reception_number, '690123456')
        self.assertEqual(deposit.ussd_code, '*126*14*5555*5000#')

    def test_create_deposit_generates_ussd(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('10000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NEW_002',
        )
        self.assertEqual(deposit.ussd_code, '*126*14*5555*10000#')

    def test_wallet_not_credited_on_create(self):
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NEW_003',
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('0'))

    def test_approve_deposits_credits_wallet(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NEW_004',
        )
        admin = self._create_admin('+237699999999')
        DepositService.approve_deposit(deposit, admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('5000'))

    def test_reject_deposit_no_credit(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NEW_005',
        )
        admin = self._create_admin('+237688888888')
        DepositService.reject_deposit(deposit, admin, 'Test rejection')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('0'))

    def test_duplicate_transaction_rejected(self):
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_DUP',
        )
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('5000'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_DUP',
            )

    def test_invalid_phone_number_rejected(self):
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('5000'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_BAD_PHONE',
                phone_number='12345',
            )

    def test_valid_phone_normalized(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NORM',
            phone_number='690123456',
        )
        self.assertEqual(deposit.phone_number, '+237690123456')

    def test_inactive_payment_method_rejected(self):
        self.payment_method.is_active = False
        self.payment_method.save()
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('5000'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_INACTIVE',
            )

    def test_zero_amount_rejected(self):
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('0'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_ZERO',
            )

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('-100'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_NEG',
            )

    def test_min_amount_enforced(self):
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('100'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_MIN',
            )

    def test_max_amount_enforced(self):
        with self.assertRaises(ValueError):
            DepositService.create_deposit(
                user=self.user,
                amount=Decimal('999999'),
                payment_method_id=self.payment_method.pk,
                transaction_id='TXN_MAX',
            )

    def test_notification_created_on_deposit(self):
        from notifications.models import Notification
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NOTIF',
        )
        notif = Notification.objects.filter(
            user=self.user,
            notification_type='DEPOSIT_SUBMITTED'
        ).first()
        self.assertIsNotNone(notif)

    def test_notification_on_approve(self):
        from notifications.models import Notification
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NOTIF_APPROVE',
        )
        admin = self._create_admin("+237677777777")
        DepositService.approve_deposit(deposit, admin)
        notif = Notification.objects.filter(
            user=self.user,
            notification_type='DEPOSIT_APPROVED'
        ).first()
        self.assertIsNotNone(notif)

    def test_notification_on_reject(self):
        from notifications.models import Notification
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_NOTIF_REJECT',
        )
        admin = self._create_admin("+237666666666")
        DepositService.reject_deposit(deposit, admin, 'Invalid proof')
        notif = Notification.objects.filter(
            user=self.user,
            notification_type='DEPOSIT_REJECTED'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('Invalid proof', notif.message)

    def test_approve_idempotent(self):
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_IDEM',
        )
        admin = self._create_admin("+237655555555")
        DepositService.approve_deposit(deposit, admin)
        DepositService.approve_deposit(deposit, admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('5000'))

    def test_get_user_deposits(self):
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('1000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_LIST_1',
        )
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('2000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_LIST_2',
        )
        deposits = DepositService.get_user_deposits(self.user)
        self.assertEqual(deposits.count(), 2)

    def test_get_user_deposits_filtered(self):
        DepositService.create_deposit(
            user=self.user,
            amount=Decimal('1000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_FILT_1',
        )
        admin = self._create_admin("+237644444444")
        deposit2 = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('2000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_FILT_2',
        )
        DepositService.approve_deposit(deposit2, admin)

        pending = DepositService.get_user_deposits(self.user, status='pending_review')
        self.assertEqual(pending.count(), 1)
        completed = DepositService.get_user_deposits(self.user, status='completed')
        self.assertEqual(completed.count(), 1)

    def test_audit_log_on_approve(self):
        from core.models import AuditLog
        deposit = DepositService.create_deposit(
            user=self.user,
            amount=Decimal('5000'),
            payment_method_id=self.payment_method.pk,
            transaction_id='TXN_AUDIT',
        )
        admin = self._create_admin("+237633333333")
        DepositService.approve_deposit(deposit, admin)
        log = AuditLog.objects.filter(
            action='deposit.approved',
            target_type='Deposit',
            target_id=str(deposit.pk),
        ).first()
        self.assertIsNotNone(log)
