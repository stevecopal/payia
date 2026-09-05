from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import User, UserProfile
from wallet.models import Wallet, LedgerEntry
from wallet.services.wallet_service import WalletService
from ai_services.models import (
    AiModel, AiCategory, AiOffer, AiRental, AiRevenue,
)
from ai_services.services.ai_service import AiService, FREQUENCY_INTERVALS


_user_counter = 0

def _create_user(phone):
    global _user_counter
    _user_counter += 1
    user = User.objects.create_user(
        username=f'user_{_user_counter}',
        phone_number=phone,
    )
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return user, wallet


def _fund_wallet(wallet, amount):
    wallet.available_balance = amount
    wallet.save(update_fields=['available_balance', 'updated_at'])


def _make_offer(slug='daily-machine', frequency='daily', duration=30, revenue=Decimal('1000')):
    model, _ = AiModel.objects.get_or_create(name='GPT-4 Bot', slug='gpt4-bot', defaults={'version': '1.0'})
    category, _ = AiCategory.objects.get_or_create(name='Trading', slug='trading')
    return AiOffer.objects.create(
        name=f'{frequency.title()} Machine',
        slug=slug,
        ai_model=model,
        category=category,
        description=f'{frequency} earning machine',
        price=Decimal('1000'),
        duration_days=duration,
        revenue_frequency=frequency,
        revenue_type='fixed',
        revenue_value=revenue,
        is_active=True,
    )


class AiServiceRentTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000100')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()

    def test_rent_offer_success(self):
        rental = AiService.rent_offer(self.user, self.offer.pk)
        self.assertIsNotNone(rental)
        self.assertEqual(rental.status, AiRental.Status.ACTIVE)
        self.assertEqual(rental.amount_paid, Decimal('1000'))
        self.assertEqual(rental.earning_amount, Decimal('1000'))
        self.assertIsNotNone(rental.next_payment_at)
        self.assertEqual(rental.payment_count, 0)
        self.assertEqual(rental.total_revenue_earned, Decimal('0'))

    def test_rent_offer_debits_wallet(self):
        AiService.rent_offer(self.user, self.offer.pk)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('9000'))

    def test_rent_offer_next_payment_calculation(self):
        rental = AiService.rent_offer(self.user, self.offer.pk)
        expected_next = rental.start_date + timedelta(days=1)
        self.assertEqual(rental.next_payment_at, expected_next)

    def test_rent_offer_insufficient_balance(self):
        _fund_wallet(self.wallet, Decimal('500'))
        with self.assertRaises(ValueError) as ctx:
            AiService.rent_offer(self.user, self.offer.pk)
        self.assertIn('Solde insuffisant', str(ctx.exception))

    def test_rent_offer_duplicate_active(self):
        AiService.rent_offer(self.user, self.offer.pk)
        with self.assertRaises(ValueError) as ctx:
            AiService.rent_offer(self.user, self.offer.pk)
        self.assertIn('louer', str(ctx.exception).lower())

    def test_rent_offer_creates_ledger_entry(self):
        AiService.rent_offer(self.user, self.offer.pk)
        entry = LedgerEntry.objects.filter(
            user=self.user, entry_type='AI_PURCHASE'
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, Decimal('-1000'))

    def test_rent_offer_increments_total_rentals(self):
        old_count = self.offer.total_rentals
        AiService.rent_offer(self.user, self.offer.pk)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.total_rentals, old_count + 1)


class AiServicePaymentTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000200')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()
        self.rental = AiService.rent_offer(self.user, self.offer.pk)

    def test_process_payment_first_cycle(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        revenue = AiService.process_payment(self.rental.pk)

        self.assertIsNotNone(revenue)
        self.assertEqual(revenue.status, 'CREDITED')
        self.assertEqual(revenue.amount, Decimal('1000'))

    def test_process_payment_credits_wallet(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])
        self.wallet.refresh_from_db()
        old_balance = self.wallet.available_balance

        AiService.process_payment(self.rental.pk)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, old_balance + Decimal('1000'))

    def test_process_payment_creates_ledger(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        entry = LedgerEntry.objects.filter(
            user=self.user, entry_type='AI_REVENUE'
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, Decimal('1000'))

    def test_process_payment_updates_rental(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.payment_count, 1)
        self.assertEqual(self.rental.total_revenue_earned, Decimal('1000'))
        self.assertIsNotNone(self.rental.last_payment_at)
        self.assertIsNotNone(self.rental.next_payment_at)

    def test_process_payment_calculates_next_payment(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])
        old_next = self.rental.next_payment_at

        AiService.process_payment(self.rental.pk)

        self.rental.refresh_from_db()
        expected_next = old_next + timedelta(days=1)
        self.assertEqual(self.rental.next_payment_at, expected_next)

    def test_process_payment_not_due(self):
        self.rental.next_payment_at = timezone.now() + timedelta(hours=1)
        self.rental.save(update_fields=['next_payment_at'])

        result = AiService.process_payment(self.rental.pk)
        self.assertIsNone(result)

    def test_process_payment_not_active(self):
        self.rental.status = 'EXPIRED'
        self.rental.save(update_fields=['status'])

        result = AiService.process_payment(self.rental.pk)
        self.assertIsNone(result)

    def test_process_payment_expired_rental(self):
        self.rental.end_date = timezone.now() - timedelta(hours=1)
        self.rental.save(update_fields=['end_date'])
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        result = AiService.process_payment(self.rental.pk)
        self.assertIsNone(result)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, AiRental.Status.EXPIRED)

    def test_process_payment_idempotency(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        result = AiService.process_payment(self.rental.pk)
        self.assertIsNone(result)

    def test_process_payment_payment_reference_unique(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        ref = AiRevenue.generate_payment_reference(self.rental.pk, 1)
        exists = AiRevenue.objects.filter(payment_reference=ref).exists()
        self.assertTrue(exists)

    def test_process_payment_multiple_cycles(self):
        for i in range(3):
            self.rental.refresh_from_db()
            self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
            self.rental.save(update_fields=['next_payment_at'])
            AiService.process_payment(self.rental.pk)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.payment_count, 3)
        self.assertEqual(self.rental.total_revenue_earned, Decimal('3000'))

    def test_process_payment_expiration_after_last_cycle(self):
        self.rental.end_date = self.rental.start_date + timedelta(hours=1)
        self.rental.next_payment_at = self.rental.start_date
        self.rental.save(update_fields=['end_date', 'next_payment_at'])

        revenue = AiService.process_payment(self.rental.pk)
        self.assertIsNotNone(revenue)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, AiRental.Status.EXPIRED)
        self.assertIsNone(self.rental.next_payment_at)

    def test_process_payment_creates_revenue_record(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        revenue = AiRevenue.objects.filter(rental=self.rental).first()
        self.assertIsNotNone(revenue)
        self.assertEqual(revenue.status, 'CREDITED')
        self.assertIsNotNone(revenue.payment_reference)
        self.assertIsNotNone(revenue.ledger_entry)


class AiServiceProcessDuePaymentsTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000300')
        _fund_wallet(self.wallet, Decimal('50000'))
        self.offer = _make_offer()
        self.rental = AiService.rent_offer(self.user, self.offer.pk)

    def test_process_due_payments_finds_due(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        processed, errors = AiService.process_due_payments()
        self.assertEqual(processed, 1)
        self.assertEqual(errors, 0)

    def test_process_due_payments_skips_not_due(self):
        self.rental.next_payment_at = timezone.now() + timedelta(hours=1)
        self.rental.save(update_fields=['next_payment_at'])

        processed, errors = AiService.process_due_payments()
        self.assertEqual(processed, 0)

    def test_process_due_payments_multiple_rentals(self):
        user2, wallet2 = _create_user('+2250700000301')
        _fund_wallet(wallet2, Decimal('50000'))
        rental2 = AiService.rent_offer(user2, self.offer.pk)

        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])
        rental2.next_payment_at = timezone.now() - timedelta(minutes=1)
        rental2.save(update_fields=['next_payment_at'])

        processed, errors = AiService.process_due_payments()
        self.assertEqual(processed, 2)

    def test_process_due_payments_handles_worker_delay(self):
        self.rental.next_payment_at = timezone.now() - timedelta(hours=2)
        self.rental.save(update_fields=['next_payment_at'])

        processed, errors = AiService.process_due_payments()
        self.assertEqual(processed, 1)

        self.rental.refresh_from_db()
        expected_next = self.rental.last_payment_at + timedelta(days=1)
        self.assertEqual(self.rental.next_payment_at, expected_next)

    def test_process_due_payments_idempotent(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        processed1, _ = AiService.process_due_payments()
        processed2, _ = AiService.process_due_payments()

        self.assertEqual(processed1, 1)
        self.assertEqual(processed2, 0)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.payment_count, 1)


class AiServiceExpireRentalsTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000400')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()

    def test_expire_rentals(self):
        rental = AiService.rent_offer(self.user, self.offer.pk)
        rental.end_date = timezone.now() - timedelta(hours=1)
        rental.save(update_fields=['end_date'])

        count = AiService.expire_rentals()
        self.assertEqual(count, 1)

        rental.refresh_from_db()
        self.assertEqual(rental.status, AiRental.Status.EXPIRED)
        self.assertIsNone(rental.next_payment_at)

    def test_expire_rentals_skips_active(self):
        rental = AiService.rent_offer(self.user, self.offer.pk)
        count = AiService.expire_rentals()
        self.assertEqual(count, 0)
        rental.refresh_from_db()
        self.assertEqual(rental.status, AiRental.Status.ACTIVE)

    def test_expire_rentals_no_payment_after_expiry(self):
        rental = AiService.rent_offer(self.user, self.offer.pk)
        rental.end_date = timezone.now() - timedelta(hours=1)
        rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        rental.save(update_fields=['end_date', 'next_payment_at'])

        AiService.expire_rentals()
        result = AiService.process_payment(rental.pk)
        self.assertIsNone(result)


class AiServiceFrequencyTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000500')
        _fund_wallet(self.wallet, Decimal('50000'))

    def test_daily_frequency(self):
        offer = _make_offer(slug='daily-freq', frequency='daily')
        rental = AiService.rent_offer(self.user, offer.pk)
        expected = rental.start_date + timedelta(days=1)
        self.assertEqual(rental.next_payment_at, expected)

    def test_weekly_frequency(self):
        offer = _make_offer(slug='weekly-freq', frequency='weekly')
        rental = AiService.rent_offer(self.user, offer.pk)
        expected = rental.start_date + timedelta(weeks=1)
        self.assertEqual(rental.next_payment_at, expected)

    def test_monthly_frequency(self):
        offer = _make_offer(slug='monthly-freq', frequency='monthly')
        rental = AiService.rent_offer(self.user, offer.pk)
        expected = rental.start_date + timedelta(days=30)
        self.assertEqual(rental.next_payment_at, expected)

    def test_daily_payment_cycle(self):
        offer = _make_offer(slug='daily-cycle', frequency='daily')
        rental = AiService.rent_offer(self.user, offer.pk)
        rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(rental.pk)
        rental.refresh_from_db()
        self.assertIsNotNone(rental.next_payment_at)

        day2_next = rental.last_payment_at + timedelta(days=1)
        self.assertEqual(rental.next_payment_at, day2_next)


class AiServiceConcurrencyTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000600')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()
        self.rental = AiService.rent_offer(self.user, self.offer.pk)
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

    def test_double_process_payment_prevented(self):
        AiService.process_payment(self.rental.pk)
        result = AiService.process_payment(self.rental.pk)
        self.assertIsNone(result)

        self.rental.refresh_from_db()
        self.assertEqual(self.rental.payment_count, 1)

        credits = LedgerEntry.objects.filter(
            user=self.user, entry_type='AI_REVENUE'
        )
        self.assertEqual(credits.count(), 1)

    def test_idempotent_reference(self):
        AiService.process_payment(self.rental.pk)
        ref = AiRevenue.generate_payment_reference(self.rental.pk, 1)
        count = AiRevenue.objects.filter(payment_reference=ref).count()
        self.assertEqual(count, 1)


class AiServiceNotificationTestCase(TestCase):
    def setUp(self):
        from notifications.models import Notification
        self.user, self.wallet = _create_user('+2250700000700')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()

    def test_rent_creates_notification(self):
        from notifications.models import Notification
        AiService.rent_offer(self.user, self.offer.pk)
        notif = Notification.objects.filter(
            user=self.user, notification_type='AI_ACTIVATED'
        ).first()
        self.assertIsNotNone(notif)

    def test_payment_creates_notification(self):
        from notifications.models import Notification
        rental = AiService.rent_offer(self.user, self.offer.pk)
        rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(rental.pk)
        notif = Notification.objects.filter(
            user=self.user, notification_type='AI_ACTIVATED',
            message__contains='généré'
        ).first()
        self.assertIsNotNone(notif)

    def test_expiration_creates_notification(self):
        from notifications.models import Notification
        rental = AiService.rent_offer(self.user, self.offer.pk)
        rental.end_date = timezone.now() - timedelta(hours=1)
        rental.save(update_fields=['end_date'])

        AiService.expire_rentals()
        notif = Notification.objects.filter(
            user=self.user, notification_type='AI_EXPIRED'
        ).first()
        self.assertIsNotNone(notif)


class AiServiceLedgerTestCase(TestCase):
    def setUp(self):
        self.user, self.wallet = _create_user('+2250700000800')
        _fund_wallet(self.wallet, Decimal('10000'))
        self.offer = _make_offer()
        self.rental = AiService.rent_offer(self.user, self.offer.pk)

    def test_ledger_entry_for_purchase(self):
        entry = LedgerEntry.objects.filter(
            user=self.user, entry_type='AI_PURCHASE'
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, Decimal('-1000'))
        self.assertEqual(entry.balance_before, Decimal('10000'))
        self.assertEqual(entry.balance_after, Decimal('9000'))

    def test_ledger_entry_for_revenue(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        entry = LedgerEntry.objects.filter(
            user=self.user, entry_type='AI_REVENUE'
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, Decimal('1000'))
        self.assertEqual(entry.balance_before, Decimal('9000'))
        self.assertEqual(entry.balance_after, Decimal('10000'))

    def test_revenue_linked_to_ledger(self):
        self.rental.next_payment_at = timezone.now() - timedelta(minutes=1)
        self.rental.save(update_fields=['next_payment_at'])

        AiService.process_payment(self.rental.pk)

        revenue = AiRevenue.objects.filter(rental=self.rental).first()
        self.assertIsNotNone(revenue.ledger_entry)
        self.assertEqual(revenue.ledger_entry.entry_type, 'AI_REVENUE')


class AiRevenueModelTestCase(TestCase):
    def test_generate_payment_reference(self):
        ref = AiRevenue.generate_payment_reference(42, 3)
        self.assertEqual(ref, 'RENTAL-42-CYCLE-3')

    def test_payment_reference_unique_constraint(self):
        user, wallet = _create_user('+2250700000900')
        _fund_wallet(wallet, Decimal('10000'))
        offer = _make_offer(slug='unique-ref-test')
        rental = AiRental.objects.create(
            user=user, offer=offer,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            amount_paid=Decimal('1000'),
            earning_amount=Decimal('1000'),
        )
        AiRevenue.objects.create(
            user=user, rental=rental, offer=offer,
            amount=Decimal('1000'),
            payment_reference='UNIQUE-REF-001',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(Exception):
            AiRevenue.objects.create(
                user=user, rental=rental, offer=offer,
                amount=Decimal('1000'),
                payment_reference='UNIQUE-REF-001',
                period_start=timezone.now(),
                period_end=timezone.now() + timedelta(days=1),
            )


class AiRentalModelTestCase(TestCase):
    def test_is_expired(self):
        user, wallet = _create_user('+2250700001000')
        offer = _make_offer(slug='expire-test')
        rental = AiRental.objects.create(
            user=user, offer=offer,
            start_date=timezone.now() - timedelta(days=31),
            end_date=timezone.now() - timedelta(days=1),
            amount_paid=Decimal('1000'),
            earning_amount=Decimal('1000'),
        )
        self.assertTrue(rental.is_expired())

    def test_extend(self):
        user, wallet = _create_user('+2250700001100')
        offer = _make_offer(slug='extend-test')
        rental = AiRental.objects.create(
            user=user, offer=offer,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            amount_paid=Decimal('1000'),
            earning_amount=Decimal('1000'),
        )
        old_end = rental.end_date
        rental.extend(10)
        rental.refresh_from_db()
        self.assertEqual(rental.end_date, old_end + timedelta(days=10))

    def test_deactivate(self):
        user, wallet = _create_user('+2250700001200')
        offer = _make_offer(slug='deactivate-test')
        rental = AiRental.objects.create(
            user=user, offer=offer,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            amount_paid=Decimal('1000'),
            earning_amount=Decimal('1000'),
        )
        rental.deactivate()
        rental.refresh_from_db()
        self.assertEqual(rental.status, AiRental.Status.CANCELLED)
