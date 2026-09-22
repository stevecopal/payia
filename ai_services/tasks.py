import logging

from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('ai_services')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_due_rental_payments(self):
    from ai_services.services.ai_service import AiService
    try:
        processed, errors = AiService.process_due_payments()
        logger.info(f'Payment processing: {processed} processed, {errors} errors.')
        return {'processed': processed, 'errors': errors}
    except Exception as exc:
        logger.error(f'process_due_rental_payments failed: {exc}')
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def expire_rentals_task(self):
    from ai_services.services.ai_service import AiService
    try:
        count = AiService.expire_rentals()
        logger.info(f'Expired {count} rentals.')
        return {'expired': count}
    except Exception as exc:
        logger.error(f'expire_rentals_task failed: {exc}')
        raise self.retry(exc=exc)


@shared_task(bind=True)
def process_single_rental_payment(self, rental_id):
    from ai_services.services.ai_service import AiService
    try:
        result = AiService.process_payment(rental_id)
        if result:
            return {'processed': True, 'revenue_id': result.pk}
        return {'processed': False}
    except Exception as exc:
        logger.error(f'process_single_rental_payment failed for rental {rental_id}: {exc}')
        raise self.retry(exc=exc)


@shared_task(bind=True)
def daily_commission_summary(self):
    """Send daily commission summary notifications to all users with commissions."""
    from django.db.models import Sum
    from datetime import timedelta
    from core.models import User
    from referrals.models import Commission
    from notifications.models import Notification
    from wallet.services.wallet_service import WalletService

    now = timezone.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = start_of_day - timedelta(days=1)
    yesterday_end = start_of_day

    users_with_commissions = Commission.objects.filter(
        created_at__gte=yesterday_start,
        created_at__lt=yesterday_end,
        status__in=['approved', 'available'],
    ).values_list('user_id', flat=True).distinct()

    count = 0
    for user_id in users_with_commissions:
        try:
            user = User.objects.get(pk=user_id)
            total_commissions = Commission.objects.filter(
                user=user,
                created_at__gte=yesterday_start,
                created_at__lt=yesterday_end,
                status__in=['approved', 'available'],
            ).aggregate(total=Sum('amount'))['total'] or 0

            if total_commissions > 0:
                Notification.objects.create(
                    user=user,
                    notification_type='COMMISSION_RECEIVED',
                    title='Résumé des commissions du jour',
                    message=f'Vous avez reçu un total de {total_commissions} XAF en commissions de parrainage hier. Votre solde a été crédité.',
                    link='/referrals/',
                )
                count += 1

                wallet = WalletService.get_wallet(user)
                wallet.refresh_from_db()
        except User.DoesNotExist:
            continue

    logger.info(f'Daily commission summary: {count} users notified.')
    return {'notified_users': count}
