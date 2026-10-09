"""Taches planifiees liees aux depots en ligne (Tara Money).

Tara Money ne rejoue jamais automatiquement un webhook en echec : la
reconciliation ci-dessous reinterroge periodiquement le prestataire afin
qu'aucun paiement confirme ne reste sans credit.
"""

import logging

from celery import shared_task

logger = logging.getLogger('transactions')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reconcile_online_payments(self):
    from transactions.services.online_deposit_service import OnlineDepositService
    try:
        stats = OnlineDepositService.reconcile()
        if stats.get('credited') or stats.get('failed'):
            logger.info('Reconciliation Tara: %s', stats)
        return stats
    except Exception as exc:
        logger.error('reconcile_online_payments failed: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_online_payment_attempts(self):
    from transactions.services.online_deposit_service import OnlineDepositService
    try:
        expired = OnlineDepositService.expire_attempts()
        return {'expired': expired}
    except Exception as exc:
        logger.error('expire_online_payment_attempts failed: %s', exc)
        raise self.retry(exc=exc)
