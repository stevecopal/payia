"""Ajout du moyen de paiement en ligne Tara Money + limite de depot.

Migration **additive uniquement** : elle ne modifie ni ne supprime aucune
donnee existante.
"""

from django.db import migrations


def create_tara_payment_method(apps, schema_editor):
    from decouple import config

    PaymentMethod = apps.get_model('transactions', 'PaymentMethod')
    Setting = apps.get_model('core', 'Setting')

    PaymentMethod.objects.get_or_create(
        slug='tara-money',
        defaults={
            'name': 'Tara Money (en ligne)',
            'description': (
                'Paiement en ligne Mobile Money / carte. '
                'Creditez votre portefeuille automatiquement apres confirmation.'
            ),
            'is_active': True,
            'phone_number': '',
            'reception_name': '',
            'ussd_template': '',
            'instructions': (
                'Vous etes redirige vers la page de paiement securisee Tara Money. '
                'Votre depot est credite automatiquement apres verification du paiement.'
            ),
            'requires_proof': False,
            'requires_transaction_id': False,
            'min_amount': None,
            'max_amount': None,
            'fee_percentage': 0,
            'fee_fixed': 0,
            'icon': 'globe',
            'display_order': 50,
        },
    )

    maximum_deposit = config('TARA_DEPOSIT_MAX', default=5000000, cast=int)
    Setting.objects.get_or_create(
        key='maximum_deposit',
        defaults={
            'value': str(maximum_deposit),
            'setting_type': 'INTEGER',
            'description': 'Montant maximum de depot (XAF)',
        },
    )


def remove_tara_payment_method(apps, schema_editor):
    """Reverse volontairement sans effet : aucune donnee n'est supprimee."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0008_depositattempt'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_tara_payment_method, remove_tara_payment_method),
    ]
