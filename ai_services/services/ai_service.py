from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from ai_services.models import AiOffer, AiRental, AiRevenue
from wallet.services.wallet_service import WalletService
from core.models import AuditLog
from notifications.models import Notification


class AiService:
    @staticmethod
    def rent_offer(user, offer_id):
        offer = AiOffer.objects.get(id=offer_id, is_active=True)

        if not offer.can_rent(user):
            raise ValueError("Vous ne pouvez pas louer cette offre.")

        wallet = WalletService.get_wallet(user)
        if wallet.available_balance < offer.price:
            raise ValueError("Solde insuffisant pour louer cette offre.")

        existing_active = AiRental.objects.filter(
            user=user, offer=offer, status='ACTIVE', end_date__gt=timezone.now()
        ).exists()
        if existing_active:
            raise ValueError("Vous avez déjà une location active pour cette offre.")

        with transaction.atomic():
            WalletService.debit_wallet(
                user=user,
                amount=offer.price,
                entry_type='AI_PURCHASE',
                description=f'Location IA: {offer.name} ({offer.duration_days} jours)',
                reference_type='AiOffer',
                reference_id=offer.pk,
            )

            now = timezone.now()
            rental = AiRental.objects.create(
                user=user,
                offer=offer,
                start_date=now,
                end_date=now + timedelta(days=offer.duration_days),
                amount_paid=offer.price,
                status='ACTIVE',
            )

            offer.total_rentals += 1
            offer.save(update_fields=['total_rentals', 'updated_at'])

            Notification.objects.create(
                user=user,
                notification_type='AI_ACTIVATED',
                title='Offre IA activée',
                message=f'Votre offre "{offer.name}" est maintenant active jusqu\'au {rental.end_date.strftime("%d/%m/%Y")}.',
            )

            AuditLog.objects.create(
                actor=user,
                action='ai.rented',
                target_type='AiRental',
                target_id=str(rental.pk),
                description=f'Offre {offer.name} louée pour {offer.price}',
            )

        return rental

    @staticmethod
    def get_user_rentals(user):
        return AiRental.objects.filter(user=user).select_related('offer', 'offer__ai_model').order_by('-created_at')

    @staticmethod
    def get_active_rentals(user):
        return AiRental.objects.filter(
            user=user, status='ACTIVE', end_date__gt=timezone.now()
        ).select_related('offer', 'offer__ai_model')

    @staticmethod
    def expire_rentals():
        expired = AiRental.objects.filter(
            status='ACTIVE', end_date__lte=timezone.now()
        )
        for rental in expired:
            rental.status = 'EXPIRED'
            rental.save(update_fields=['status', 'updated_at'])
            Notification.objects.create(
                user=rental.user,
                notification_type='AI_EXPIRED',
                title='Offre IA expirée',
                message=f'Votre offre "{rental.offer.name}" a expiré.',
            )
        return expired.count()

    @staticmethod
    def credit_revenue(rental, amount):
        with transaction.atomic():
            revenue = AiRevenue.objects.create(
                user=rental.user,
                rental=rental,
                offer=rental.offer,
                amount=amount,
                period_start=timezone.now().date(),
                period_end=timezone.now().date(),
                status='pending',
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
