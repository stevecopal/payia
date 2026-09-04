import random
from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from core.models import User, UserProfile, Role, Permission, Setting
from wallet.models import Wallet, LedgerEntry
from transactions.models import PaymentMethod, Deposit, Withdrawal
from ai_services.models import AiModel, AiCategory, AiOffer
from referrals.models import Referral, Commission
from notifications.models import Notification, Message
from support.models import SupportTicket, SupportMessage
from analytics.models import AnalyticsEvent


class Command(BaseCommand):
    help = 'Remplit la base de données avec des données de test'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Supprimer toutes les données avant de remplir')

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Suppression des données...'))
            AnalyticsEvent.objects.all().delete()
            SupportMessage.objects.all().delete()
            SupportTicket.objects.all().delete()
            Message.objects.all().delete()
            Notification.objects.all().delete()
            Commission.objects.all().delete()
            Referral.objects.all().delete()
            Withdrawal.objects.all().delete()
            Deposit.objects.all().delete()
            PaymentMethod.objects.all().delete()
            AiOffer.objects.all().delete()
            AiModel.objects.all().delete()
            AiCategory.objects.all().delete()
            LedgerEntry.objects.all().delete()
            Wallet.objects.all().delete()
            UserProfile.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            Role.objects.all().delete()
            Permission.objects.all().delete()
            Setting.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Données supprimées.'))

        self.stdout.write(self.style.SUCCESS('Début du remplissage...'))

        self.create_permissions()
        self.create_roles()
        self.create_settings()
        self.create_payment_methods()
        self.create_ai_categories()
        self.create_ai_models()
        self.create_ai_offers()
        admin = self.create_admin()
        users = self.create_users()
        self.create_deposits(users, admin)
        self.create_withdrawals(users, admin)
        self.create_referrals(users)
        self.create_commissions(users)
        self.create_notifications(users)
        self.create_messages(users, admin)
        self.create_support_tickets(users, admin)
        self.create_analytics_events(users)
        self.recalc_wallets(users)

        self.stdout.write(self.style.SUCCESS('Base de données remplie avec succès !'))

    # ── Recalculate Wallet Totals ──────────────────────────────
    def recalc_wallets(self, users):
        from django.db.models import Sum
        from referrals.models import Commission as CommModel
        from ai_services.models import AiRental

        for wallet in Wallet.objects.select_related('user').all():
            user = wallet.user
            wallet.total_deposited = Deposit.objects.filter(
                user=user, status='completed'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            wallet.total_withdrawn = Withdrawal.objects.filter(
                user=user, status='completed'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            wallet.referral_earnings = CommModel.objects.filter(
                user=user, status='approved'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            ai_earn = AiRental.objects.filter(
                user=user
            ).aggregate(t=Sum('total_revenue_earned'))['t'] or Decimal('0')
            wallet.total_earnings = ai_earn + wallet.referral_earnings
            wallet.save(update_fields=[
                'total_deposited', 'total_withdrawn',
                'referral_earnings', 'total_earnings', 'updated_at',
            ])
        self.stdout.write(f'  ✓ {Wallet.objects.count()} wallets recalculés')

    # ── Permissions ──────────────────────────────────────────────
    def create_permissions(self):
        perms = [
            ('manage_users', 'Gérer les utilisateurs', 'user'),
            ('manage_deposits', 'Gérer les dépôts', 'transaction'),
            ('manage_withdrawals', 'Gérer les retraits', 'transaction'),
            ('manage_ai', 'Gérer les offres IA', 'ai'),
            ('manage_settings', 'Gérer les paramètres', 'system'),
            ('view_statistics', 'Voir les statistiques', 'analytics'),
            ('manage_support', 'Gérer le support', 'support'),
            ('manage_referrals', 'Gérer les parrainages', 'referral'),
            ('send_messages', 'Envoyer des messages', 'communication'),
            ('manage_payments', 'Gérer les méthodes de paiement', 'transaction'),
        ]
        for codename, name, category in perms:
            Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': name, 'category': category}
            )
        self.stdout.write(f'  ✓ {len(perms)} permissions créées')

    # ── Roles ────────────────────────────────────────────────────
    def create_roles(self):
        roles_data = {
            'Utilisateur': {
                'description': 'Utilisateur standard',
                'perms': [],
            },
            'Modérateur': {
                'description': 'Modérateur de la plateforme',
                'perms': ['manage_deposits', 'manage_withdrawals', 'manage_support'],
            },
            'Admin': {
                'description': 'Administrateur de la plateforme',
                'perms': ['manage_users', 'manage_deposits', 'manage_withdrawals', 'manage_ai',
                          'view_statistics', 'manage_support', 'manage_referrals', 'send_messages',
                          'manage_payments'],
            },
        }
        for name, data in roles_data.items():
            role, _ = Role.objects.get_or_create(
                name=name,
                defaults={'description': data['description']}
            )
            if data['perms']:
                perms = Permission.objects.filter(codename__in=data['perms'])
                role.permissions.set(perms)
        self.stdout.write(f'  ✓ {len(roles_data)} rôles créés')

    # ── Settings ─────────────────────────────────────────────────
    def create_settings(self):
        settings_data = [
            ('minimum_withdrawal', '1000', 'INTEGER', 'Montant minimum de retrait'),
            ('minimum_deposit', '500', 'INTEGER', 'Montant minimum de dépôt'),
            ('commission_level_1', '10', 'DECIMAL', 'Commission parrainage niveau 1 (%)'),
            ('commission_level_2', '5', 'DECIMAL', 'Commission parrainage niveau 2 (%)'),
            ('commission_level_3', '3', 'DECIMAL', 'Commission parrainage niveau 3 (%)'),
            ('commission_level_4', '2', 'DECIMAL', 'Commission parrainage niveau 4 (%)'),
            ('commission_level_5', '1', 'DECIMAL', 'Commission parrainage niveau 5 (%)'),
            ('platform_name', 'PAYIA', 'STRING', 'Nom de la plateforme'),
            ('platform_currency', 'XOF', 'STRING', 'Devise par défaut'),
            ('maintenance_mode', 'false', 'BOOLEAN', 'Mode maintenance'),
        ]
        for key, value, stype, desc in settings_data:
            Setting.objects.get_or_create(
                key=key,
                defaults={'value': value, 'setting_type': stype, 'description': desc}
            )
        self.stdout.write(f'  ✓ {len(settings_data)} paramètres créés')

    # ── Payment Methods ──────────────────────────────────────────
    def create_payment_methods(self):
        methods = [
            {
                'name': 'MTN Mobile Money',
                'slug': 'mtn-mobile-money',
                'description': 'Paiement via MTN Mobile Money',
                'phone_number': '690123456',
                'ussd_template': '*126*14*5555*{amount}#',
                'instructions': 'Composez le code USSD affiché pour transférer le montant. Le numéro de réception est configuré par l\'administration.',
                'min_amount': Decimal('500'),
                'max_amount': Decimal('500000'),
                'fee_percentage': Decimal('0'),
                'fee_fixed': Decimal('0'),
                'display_order': 1,
            },
            {
                'name': 'Orange Money',
                'slug': 'orange-money',
                'description': 'Paiement via Orange Money',
                'phone_number': '655123456',
                'ussd_template': '*150*1*{amount}#',
                'instructions': 'Composez le code USSD affiché pour transférer le montant. Le numéro de réception est configuré par l\'administration.',
                'min_amount': Decimal('500'),
                'max_amount': Decimal('500000'),
                'fee_percentage': Decimal('0'),
                'fee_fixed': Decimal('0'),
                'display_order': 2,
            },
            {
                'name': 'Virement bancaire',
                'slug': 'virement-bancaire',
                'description': 'Virement bancaire direct',
                'instructions': 'Effectuez un virement vers le compte bancaire fourni et joignez le reçu.',
                'min_amount': Decimal('10000'),
                'max_amount': Decimal('5000000'),
                'fee_percentage': Decimal('0'),
                'fee_fixed': Decimal('500'),
                'display_order': 3,
            },
        ]
        for data in methods:
            PaymentMethod.objects.get_or_create(
                slug=data['slug'],
                defaults=data
            )
        self.stdout.write(f'  ✓ {len(methods)} méthodes de paiement créées')

    # ── AI Categories ────────────────────────────────────────────
    def create_ai_categories(self):
        categories = [
            ('Trading IA', 'Algorithmes de trading automatisé', 1),
            ('Analyse de données', 'Outils d\'analyse et prédiction', 2),
            ('Génération de contenu', 'Création de contenu par IA', 3),
            ('Automatisation', 'Automatisation de processus', 4),
        ]
        for name, desc, order in categories:
            AiCategory.objects.get_or_create(
                slug=slugify(name),
                defaults={'name': name, 'description': desc, 'display_order': order}
            )
        self.stdout.write(f'  ✓ {len(categories)} catégories IA créées')

    # ── AI Models ────────────────────────────────────────────────
    def create_ai_models(self):
        models_data = [
            ('GPT-4 Turbo', 'gpt-4-turbo', 'Modèle de langage avancé', '4.0'),
            ('Stable Diffusion XL', 'stable-diffusion-xl', 'Génération d\'images', '1.0'),
            ('Trading Bot Pro', 'trading-bot-pro', 'Bot de trading automatisé', '3.2'),
            ('Data Analyzer', 'data-analyzer', 'Analyse de données en temps réel', '2.1'),
        ]
        for name, slug, desc, version in models_data:
            AiModel.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc, 'version': version}
            )
        self.stdout.write(f'  ✓ {len(models_data)} modèles IA créés')

    # ── AI Offers ────────────────────────────────────────────────
    def create_ai_offers(self):
        offers = [
            {
                'name': 'Trading Starter',
                'slug': 'trading-starter',
                'model_slug': 'trading-bot-pro',
                'category_slug': 'trading-ia',
                'description': 'Bot de trading pour débutants. Investissement minimal, revenus stables.',
                'price': Decimal('25000'),
                'duration_days': 30,
                'revenue_frequency': 'daily',
                'revenue_type': 'fixed',
                'revenue_value': Decimal('1200'),
                'conditions': 'Revenu garanti de 1200 XOF/jour pendant 30 jours.',
                'is_featured': True,
                'display_order': 1,
            },
            {
                'name': 'Trading Pro',
                'slug': 'trading-pro',
                'model_slug': 'trading-bot-pro',
                'category_slug': 'trading-ia',
                'description': 'Bot de trading avancé pour investisseurs sérieux. Revenus élevés.',
                'price': Decimal('100000'),
                'duration_days': 60,
                'revenue_frequency': 'daily',
                'revenue_type': 'fixed',
                'revenue_value': Decimal('5500'),
                'conditions': 'Revenu garanti de 5500 XOF/jour pendant 60 jours.',
                'is_featured': True,
                'display_order': 2,
            },
            {
                'name': 'Data Basic',
                'slug': 'data-basic',
                'model_slug': 'data-analyzer',
                'category_slug': 'analyse-de-donnees',
                'description': 'Analyse de données simplifiée pour petits projets.',
                'price': Decimal('15000'),
                'duration_days': 30,
                'revenue_frequency': 'weekly',
                'revenue_type': 'percentage',
                'revenue_value': Decimal('8'),
                'conditions': '8% du montant investi retourne chaque semaine.',
                'display_order': 3,
            },
            {
                'name': 'Content Creator',
                'slug': 'content-creator',
                'model_slug': 'gpt-4-turbo',
                'category_slug': 'generation-de-contenu',
                'description': 'Génération de contenu automatisée avec GPT-4.',
                'price': Decimal('35000'),
                'duration_days': 30,
                'revenue_frequency': 'daily',
                'revenue_type': 'fixed',
                'revenue_value': Decimal('1800'),
                'conditions': 'Revenu de 1800 XOF/jour. Idéal pour créateurs de contenu.',
                'display_order': 4,
            },
            {
                'name': 'Image AI',
                'slug': 'image-ai',
                'model_slug': 'stable-diffusion-xl',
                'category_slug': 'generation-de-contenu',
                'description': 'Génération d\'images par IA. Revenus sur les créations.',
                'price': Decimal('20000'),
                'duration_days': 15,
                'revenue_frequency': 'daily',
                'revenue_type': 'fixed',
                'revenue_value': Decimal('1500'),
                'conditions': 'Revenu de 1500 XOF/jour pendant 15 jours.',
                'display_order': 5,
            },
            {
                'name': 'Auto Premium',
                'slug': 'auto-premium',
                'model_slug': 'data-analyzer',
                'category_slug': 'automatisation',
                'description': 'Automatisation complète de processus métier.',
                'price': Decimal('75000'),
                'duration_days': 45,
                'revenue_frequency': 'weekly',
                'revenue_type': 'percentage',
                'revenue_value': Decimal('12'),
                'conditions': '12% de rendement hebdomadaire pendant 45 jours.',
                'is_featured': True,
                'display_order': 6,
            },
        ]
        for data in offers:
            model = AiModel.objects.get(slug=data.pop('model_slug'))
            category = AiCategory.objects.get(slug=data.pop('category_slug'))
            AiOffer.objects.get_or_create(
                slug=data['slug'],
                defaults={**data, 'ai_model': model, 'category': category}
            )
        self.stdout.write(f'  ✓ {len(offers)} offres IA créées')

    # ── Admin ────────────────────────────────────────────────────
    def create_admin(self):
        admin_role = Role.objects.get(slug='admin')
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'phone_number': '+237690000001',
                'first_name': 'Admin',
                'last_name': 'PAYIA',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
                'account_status': 'ACTIVE',
                'is_phone_verified': True,
                'kyc_status': 'VERIFIED',
                'role': admin_role,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            UserProfile.objects.get_or_create(
                user=admin,
                defaults={
                    'first_name': 'Admin',
                    'last_name': 'PAYIA',
                    'country': 'CM',
                    'preferred_currency': 'XOF',
                }
            )
        self.stdout.write(f'  ✓ Admin créé (admin / admin123)')
        return admin

    # ── Users ────────────────────────────────────────────────────
    def create_users(self):
        user_role = Role.objects.get(slug='utilisateur')
        users_data = [
            ('jean_kamga', '+237691234567', 'Jean', 'Kamga'),
            ('marie_ngono', '+237692345678', 'Marie', 'Ngono'),
            ('pierre_mbida', '+237693456789', 'Pierre', 'Mbida'),
            ('sophie_atangana', '+237694567890', 'Sophie', 'Atangana'),
            ('paul_fotso', '+237695678901', 'Paul', 'Fotso'),
            ('anne_ndjock', '+237696789012', 'Anne', 'Ndjock'),
            ('daniel TLabel', '+237697890123', 'Daniel', 'Tabel'),
            ('grace_mbiada', '+237698901234', 'Grace', 'Mbiada'),
        ]
        users = []
        for username, phone, first, last in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'phone_number': phone,
                    'first_name': first,
                    'last_name': last,
                    'is_active': True,
                    'account_status': 'ACTIVE',
                    'is_phone_verified': True,
                    'kyc_status': 'VERIFIED',
                    'role': user_role,
                }
            )
            if created:
                user.set_password('test1234')
                user.save()
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'first_name': first,
                        'last_name': last,
                        'country': 'CM',
                        'preferred_currency': 'XOF',
                    }
                )
            users.append(user)
        self.stdout.write(f'  ✓ {len(users)} utilisateurs créés (mot de passe: test1234)')

        # Donner du solde à quelques utilisateurs
        for user in users[:4]:
            wallet = Wallet.objects.get(user=user)
            amount = Decimal(str(random.randint(50000, 500000)))
            wallet.credit(amount, description='Dépôt initial de test')
            wallet.refresh_from_db()

        return users

    # ── Deposits ─────────────────────────────────────────────────
    def create_deposits(self, users, admin):
        pm = PaymentMethod.objects.get(slug='mobile-money')
        statuses = ['completed', 'pending_review', 'approved', 'rejected']
        count = 0
        for user in users[:5]:
            for i in range(random.randint(1, 3)):
                amount = Decimal(str(random.choice([5000, 10000, 25000, 50000, 100000])))
                status = random.choice(statuses)
                deposit = Deposit.objects.create(
                    user=user,
                    amount=amount,
                    payment_method=pm,
                    transaction_id=f'TXN{random.randint(100000, 999999)}',
                    status=status,
                    reviewed_by=admin if status != 'pending_review' else None,
                )
                count += 1
        self.stdout.write(f'  ✓ {count} dépôts créés')

    # ── Withdrawals ──────────────────────────────────────────────
    def create_withdrawals(self, users, admin):
        pm = PaymentMethod.objects.get(slug='mobile-money')
        count = 0
        for user in users[:3]:
            for i in range(random.randint(0, 2)):
                amount = Decimal(str(random.choice([5000, 10000, 25000])))
                fee = Decimal('100')
                Withdrawal.objects.create(
                    user=user,
                    amount=amount,
                    fee=fee,
                    net_amount=amount - fee,
                    withdrawal_method=pm,
                    withdrawal_number=user.phone_number,
                    status='completed',
                    reviewed_by=admin,
                )
                count += 1
        self.stdout.write(f'  ✓ {count} retraits créés')

    # ── Referrals ────────────────────────────────────────────────
    def create_referrals(self, users):
        count = 0
        for i, user in enumerate(users[1:5], start=0):
            referrer = users[0] if i == 0 else users[i - 1]
            if referrer != user:
                ref, created = Referral.objects.get_or_create(
                    referrer=referrer,
                    referred_user=user,
                    defaults={'referral_level': 1}
                )
                if created:
                    count += 1
        self.stdout.write(f'  ✓ {count} parrainages créés')

    # ── Commissions ──────────────────────────────────────────────
    def create_commissions(self, users):
        count = 0
        for user in users[:3]:
            Commission.objects.get_or_create(
                user=user,
                source_user=users[0],
                referral_level=1,
                source_transaction_type='deposit',
                source_transaction_id=1,
                defaults={
                    'percentage': Decimal('10'),
                    'amount': Decimal(str(random.randint(500, 5000))),
                    'status': 'approved',
                }
            )
            count += 1
        self.stdout.write(f'  ✓ {count} commissions créées')

    # ── Notifications ────────────────────────────────────────────
    def create_notifications(self, users):
        notif_data = [
            ('DEPOSIT_APPROVED', 'Dépôt approuvé', 'Votre dépôt de 50 000 XOF a été approuvé.'),
            ('AI_ACTIVATED', 'Offre IA activée', 'Votre offre "Trading Starter" est maintenant active.'),
            ('NEW_REFERRAL', 'Nouveau filleul', 'Un nouvel utilisateur s\'est inscrit avec votre code.'),
            ('SYSTEM_MESSAGE', 'Bienvenue', 'Bienvenue sur PAYIA. Commencez à investir dès maintenant.'),
            ('SECURITY_ALERT', 'Nouvelle connexion', 'Une nouvelle connexion a été détectée sur votre compte.'),
        ]
        count = 0
        for user in users[:5]:
            for ntype, title, msg in notif_data[:3]:
                Notification.objects.get_or_create(
                    user=user,
                    notification_type=ntype,
                    title=title,
                    defaults={'message': msg}
                )
                count += 1
        self.stdout.write(f'  ✓ {count} notifications créées')

    # ── Messages ─────────────────────────────────────────────────
    def create_messages(self, users, admin):
        count = 0
        for user in users[:3]:
            Message.objects.get_or_create(
                sender=admin,
                recipient=user,
                subject='Bienvenue sur PAYIA',
                defaults={
                    'body': 'Merci de vous être inscrit sur PAYIA. N\'hésitez pas à nous contacter si vous avez des questions.',
                    'message_type': 'INDIVIDUAL',
                    'is_system_message': True,
                }
            )
            count += 1
        self.stdout.write(f'  ✓ {count} messages créés')

    # ── Support Tickets ──────────────────────────────────────────
    def create_support_tickets(self, users, admin):
        tickets_data = [
            ('DEPOSIT', 'HIGH', 'Dépôt non crédité', 'J\'ai effectué un dépôt de 25 000 XOF mais il n\'a pas encore été crédité.'),
            ('AI', 'MEDIUM', 'Question sur les revenus', 'Comment sont calculés les revenus de mon offre IA ?'),
            ('ACCOUNT', 'LOW', 'Modification de profil', 'Je souhaite modifier mon numéro de téléphone.'),
        ]
        count = 0
        for i, (cat, priority, subject, body) in enumerate(tickets_data):
            user = users[i % len(users)]
            ticket, created = SupportTicket.objects.get_or_create(
                user=user,
                subject=subject,
                defaults={
                    'category': cat,
                    'priority': priority,
                    'status': 'OPEN',
                }
            )
            if created:
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    message=body,
                )
                count += 1
        self.stdout.write(f'  ✓ {count} tickets de support créés')

    # ── Analytics Events ─────────────────────────────────────────
    def create_analytics_events(self, users):
        event_types = ['PAGE_VIEW', 'REGISTRATION', 'LOGIN', 'AI_VIEWED', 'AI_RENTED']
        count = 0
        for user in users[:5]:
            for _ in range(random.randint(2, 5)):
                AnalyticsEvent.objects.create(
                    event_type=random.choice(event_types),
                    user=user,
                    ip_address=f'192.168.1.{random.randint(1, 254)}',
                    user_agent='Mozilla/5.0 (Linux; Android 13)',
                )
                count += 1
        self.stdout.write(f'  ✓ {count} événements analytics créés')
