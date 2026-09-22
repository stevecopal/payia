import logging
from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ai_services.models import AiOffer, AiRental, AiRevenue
from wallet.models import Wallet
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification

logger = logging.getLogger('ai_services')


FREQUENCY_INTERVALS = {
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
    'monthly': timedelta(days=30),
}


def _compute_next_payment_at(current_next, frequency):
    interval = FREQUENCY_INTERVALS.get(frequency, timedelta(days=1))
    return current_next + interval


class AiService:
    @staticmethod
    def rent_offer(user, offer_id):
        with transaction.atomic():
            offer = AiOffer.objects.select_for_update().get(id=offer_id, is_active=True)

            if not offer.can_rent(user):
                raise ValueError("Vous ne pouvez pas louer cette offre.")

            wallet = Wallet.objects.select_for_update().get(user=user)
            if wallet.available_balance < offer.price:
                raise ValueError("Solde insuffisant pour louer cette offre.")

            existing_active = AiRental.objects.filter(
                user=user, offer=offer, status=AiRental.Status.ACTIVE, end_date__gt=timezone.now()
            ).exists()
            if existing_active:
                raise ValueError("Vous avez deja une location active pour cette offre.")

            earning_amount = offer.get_expected_revenue()

            WalletService.debit_wallet(
                user=user,
                amount=offer.price,
                entry_type='AI_PURCHASE',
                description=f'Location IA: {offer.name} ({offer.duration_days} jours)',
                reference_type='AiOffer',
                reference_id=offer.pk,
            )

            now = timezone.now()
            interval = FREQUENCY_INTERVALS.get(offer.revenue_frequency, timedelta(days=1))
            next_payment_at = now + interval

            rental = AiRental.objects.create(
                user=user,
                offer=offer,
                start_date=now,
                end_date=now + timedelta(days=offer.duration_days),
                amount_paid=offer.price,
                productive_amount=offer.price,
                earning_amount=earning_amount,
                next_payment_at=next_payment_at,
                status=AiRental.Status.ACTIVE,
                payment_count=0,
            )

            offer.total_rentals += 1
            offer.save(update_fields=['total_rentals', 'updated_at'])

            Notification.objects.create(
                user=user,
                notification_type='AI_ACTIVATED',
                title='Offre IA activee',
                message=f'Votre offre "{offer.name}" est maintenant active jusqu\'au {rental.end_date.strftime("%d/%m/%Y")}.',
            )

            AuditLog.objects.create(
                actor=user,
                action='ai.rented',
                target_type='AiRental',
                target_id=str(rental.pk),
                description=f'Offre {offer.name} louee pour {offer.price} (revenu brut: {earning_amount}/periode)',
            )

        return rental

    @staticmethod
    def get_user_rentals(user):
        return AiRental.objects.filter(user=user).select_related('offer', 'offer__ai_model').order_by('-created_at')

    @staticmethod
    def get_active_rentals(user):
        return AiRental.objects.filter(
            user=user, status=AiRental.Status.ACTIVE, end_date__gt=timezone.now()
        ).select_related('offer', 'offer__ai_model')

    @staticmethod
    @transaction.atomic
    def process_payment(rental_id):
        from referrals.services.referral_service import ReferralService

        rental = AiRental.objects.select_for_update().get(id=rental_id)

        now = timezone.now()

        if rental.status != AiRental.Status.ACTIVE:
            logger.info(f'Rental {rental_id} not active (status={rental.status}), skipping.')
            return None

        if rental.end_date <= now:
            rental.status = AiRental.Status.EXPIRED
            rental.next_payment_at = None
            rental.save(update_fields=['status', 'next_payment_at', 'updated_at'])
            Notification.objects.create(
                user=rental.user,
                notification_type='AI_EXPIRED',
                title='Offre IA expiree',
                message=f'Votre offre "{rental.offer.name}" a expire.',
            )
            logger.info(f'Rental {rental_id} expired.')
            return None

        if rental.next_payment_at is None:
            logger.warning(f'Rental {rental_id} has no next_payment_at, skipping.')
            return None

        if rental.next_payment_at > now:
            logger.info(f'Rental {rental_id} payment not yet due (next={rental.next_payment_at}).')
            return None

        payment_count = rental.payment_count + 1
        payment_reference = AiRevenue.generate_payment_reference(rental.pk, payment_count)

        existing = AiRevenue.objects.filter(payment_reference=payment_reference).exists()
        if existing:
            logger.warning(f'Payment {payment_reference} already exists, skipping (idempotency).')
            return None

        period_start = rental.next_payment_at
        interval = FREQUENCY_INTERVALS.get(
            rental.offer.revenue_frequency, timedelta(days=1)
        )
        period_end = period_start + interval

        gross_revenue = rental.earning_amount

        revenue = AiRevenue.objects.create(
            user=rental.user,
            rental=rental,
            offer=rental.offer,
            amount=gross_revenue,
            payment_reference=payment_reference,
            period_start=period_start,
            period_end=period_end,
            status=AiRevenue.Status.PENDING,
        )

        commission_result = ReferralService.calculate_revenue_commission(rental, gross_revenue)
        net_amount = commission_result['net_amount']

        for c in commission_result['commissions']:
            c.ai_revenue = revenue
            c.save(update_fields=['ai_revenue'])

        wallet, ledger_entry = WalletService.credit_wallet(
            user=rental.user,
            amount=net_amount,
            entry_type='AI_REVENUE',
            description=f'Revenu IA net: {rental.offer.name} (Cycle {payment_count})',
            reference_type='AiRevenue',
            reference_id=revenue.pk,
        )

        revenue.ledger_entry = ledger_entry
        revenue.status = 'CREDITED'
        revenue.credited_at = timezone.now()
        revenue.save(update_fields=['ledger_entry', 'status', 'credited_at'])

        next_payment_at = _compute_next_payment_at(rental.next_payment_at, rental.offer.revenue_frequency)

        if next_payment_at >= rental.end_date:
            next_payment_at = None

        rental.payment_count = payment_count
        rental.last_payment_at = rental.next_payment_at
        rental.total_revenue_earned += net_amount
        rental.next_payment_at = next_payment_at

        if next_payment_at is None:
            rental.status = AiRental.Status.EXPIRED
            rental.save(update_fields=[
                'payment_count', 'last_payment_at', 'total_revenue_earned',
                'next_payment_at', 'status', 'updated_at',
            ])
            Notification.objects.create(
                user=rental.user,
                notification_type='AI_EXPIRED',
                title='Location terminee',
                message=f'Votre location "{rental.offer.name}" est terminee. Total gagne: {rental.total_revenue_earned} XAF.',
            )
        else:
            rental.save(update_fields=[
                'payment_count', 'last_payment_at', 'total_revenue_earned',
                'next_payment_at', 'updated_at',
            ])

        Notification.objects.create(
            user=rental.user,
            notification_type='AI_ACTIVATED',
            title='Paiement recu',
            message=f'Votre machine "{rental.offer.name}" a genere {gross_revenue} XAF. Apres commissions parrainage ({commission_result["total_commission"]} XAF), vous recevez {net_amount} XAF.',
        )

        AuditLog.objects.create(
            actor=rental.user,
            action='ai.payment.credited',
            target_type='AiRental',
            target_id=str(rental.pk),
            description=f'Revenu brut {gross_revenue} XAF, commission {commission_result["total_commission"]} XAF, net {net_amount} XAF (cycle {payment_count})',
        )

        logger.info(
            f'Payment {payment_reference} processed: gross={gross_revenue}, '
            f'commission={commission_result["total_commission"]}, net={net_amount} '
            f'for rental {rental_id}, next_payment_at={next_payment_at}'
        )

        return revenue

    @staticmethod
    @transaction.atomic
    def process_due_payments():
        now = timezone.now()
        due_rentals = AiRental.objects.filter(
            status=AiRental.Status.ACTIVE,
            next_payment_at__isnull=False,
            next_payment_at__lte=now,
            end_date__gt=now,
        ).select_for_update()

        processed = 0
        errors = 0
        for rental in due_rentals:
            try:
                result = AiService.process_payment(rental.pk)
                if result:
                    processed += 1
            except Exception as e:
                errors += 1
                logger.error(f'Error processing payment for rental {rental.pk}: {e}')

        return processed, errors

    @staticmethod
    @transaction.atomic
    def expire_rentals():
        now = timezone.now()
        expired = AiRental.objects.filter(
            status=AiRental.Status.ACTIVE, end_date__lte=now
        ).select_for_update()

        count = 0
        for rental in expired:
            rental.status = AiRental.Status.EXPIRED
            rental.next_payment_at = None
            rental.save(update_fields=['status', 'next_payment_at', 'updated_at'])
            Notification.objects.create(
                user=rental.user,
                notification_type='AI_EXPIRED',
                title='Offre IA expiree',
                message=f'Votre offre "{rental.offer.name}" a expire.',
            )
            count += 1
        return count

    @staticmethod
    def credit_revenue(rental, amount):
        with transaction.atomic():
            revenue = AiRevenue.objects.create(
                user=rental.user,
                rental=rental,
                offer=rental.offer,
                amount=amount,
                payment_reference=AiRevenue.generate_payment_reference(
                    rental.pk, rental.payment_count + 1
                ),
                period_start=timezone.now(),
                period_end=timezone.now() + timedelta(days=1),
                status=AiRevenue.Status.PENDING,
            )

            wallet, ledger_entry = WalletService.credit_wallet(
                user=rental.user,
                amount=amount,
                entry_type='AI_REVENUE',
                description=f'Revenu IA: {rental.offer.name}',
                reference_type='AiRevenue',
                reference_id=revenue.pk,
            )

            revenue.ledger_entry = ledger_entry
            revenue.status = 'CREDITED'
            revenue.credited_at = timezone.now()
            revenue.save(update_fields=['ledger_entry', 'status', 'credited_at'])

            rental.total_revenue_earned += amount
            rental.save(update_fields=['total_revenue_earned', 'updated_at'])

        return revenue
