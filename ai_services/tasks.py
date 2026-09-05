import logging

from celery import shared_task

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
