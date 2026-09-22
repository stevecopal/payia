from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from transactions.models import PaymentMethod
from ai_services.models import AiModel, AiCategory, AiOffer


class Command(BaseCommand):
    help = 'Initialise la base de données PAYIA avec les méthodes de paiement, catégories IA, modèles IA et offres IA pour l\'administrateur.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Supprime toutes les données initiales avant de recréer',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Suppression des données initiales...'))
            AiOffer.objects.all().delete()
            AiModel.objects.all().delete()
            AiCategory.objects.all().delete()
            PaymentMethod.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Données supprimées.'))

        self.stdout.write(self.style.SUCCESS('🚀 Initialisation de la base de données PAYIA...\n'))

        self.create_payment_methods()
        self.create_ai_categories()
        self.create_ai_models()
        self.create_ai_offers()

        self.stdout.write(self.style.SUCCESS(
            f'✅ Initialisation terminée : '
            f'{PaymentMethod.objects.count()} méthodes, '
            f'{AiCategory.objects.count()} catégories, '
            f'{AiModel.objects.count()} modèles, '
            f'{AiOffer.objects.count()} offres.'
        ))

    def create_payment_methods(self):
        """Crée les 2 méthodes de paiement : MTN Mobile Money et Orange Money."""
        methods = [
            {
                "name": "MTN Mobile Money",
                "slug": "mtn-mobile-money",
                "description": "MTN Mobile Money — Le moyen de paiement le plus rapide et sécurisé. Effectuez vos transactions en quelques secondes via votre compte MTN Mobile Money.",
                "phone_number": "690123456",
                "reception_name": "PAYIA MTN MM",
                "ussd_template": "*126*14*5555*{amount}#",
                "instructions": "Composez *126*14*5555*{amount}# sur votre téléphone MTN pour valider le paiement. Le montant sera déduit directement de votre compte Mobile Money.",
                "requires_proof": True,
                "requires_transaction_id": True,
                "min_amount": Decimal("500"),
                "max_amount": Decimal("500000"),
                "fee_percentage": Decimal("0"),
                "fee_fixed": Decimal("0"),
                "icon": "mtn",
                "display_order": 1,
            },
            {
                "name": "Orange Money",
                "slug": "orange-money",
                "description": "Orange Money — Paiement rapide et fiable via Orange Money. Transférez instantanément depuis votre compte Orange Money vers PAYIA.",
                "phone_number": "655123456",
                "reception_name": "PAYIA ORANGE MM",
                "ussd_template": "*150*1*{amount}#",
                "instructions": "Composez *150*1*{amount}# sur votre téléphone Orange pour effectuer le paiement. La transaction est sécurisée et instantanée.",
                "requires_proof": True,
                "requires_transaction_id": True,
                "min_amount": Decimal("500"),
                "max_amount": Decimal("500000"),
                "fee_percentage": Decimal("0"),
                "fee_fixed": Decimal("0"),
                "icon": "orange",
                "display_order": 2,
            },
        ]
        for data in methods:
            PaymentMethod.objects.get_or_create(slug=data["slug"], defaults=data)
            self.stdout.write(f'  ✅ Méthode de paiement créée : {data["name"]}')
        self.stdout.write(f'  🎯 {len(methods)} méthodes de paiement initialisées.\n')

    def create_ai_categories(self):
        """Crée les catégories IA pour organiser les offres."""
        categories = [
            ("Trading IA", "Algorithmes de trading automatisé et analyse de marché en temps réel pour maximiser vos rendements financiers.", 1),
            ("Analyse de données", "Outils d'analyse avancée et prédiction de tendances pour une prise de décision éclairée.", 2),
            ("Génération de contenu", "Solutions de création de contenu par IA : textes, images et médias de haute qualité.", 3),
            ("Automatisation", "Automatisation intelligente des processus métier pour gagner du temps et réduire les coûts.", 4),
            ("Assistants IA", "Assistants virtuels et chatbots IA pour un support client 24h/24 et une productivité accrue.", 5),
        ]
        for name, desc, order in categories:
            AiCategory.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": desc, "display_order": order}
            )
            self.stdout.write(f'  ✅ Catégorie créée : {name}')
        self.stdout.write(f'  🎯 {len(categories)} catégories IA initialisées.\n')

    def create_ai_models(self):
        """Crée les 10 modèles IA professionnels avec des descriptions détaillées."""
        models_data = [
            {
                "name": "GPT-4o Turbo",
                "slug": "gpt-4o-turbo",
                "description": "Le modèle de langage le plus puissant au monde. GPT-4o Turbo offre des performances exceptionnelles en compréhension et génération de texte, avec une vitesse de traitement ultra-rapide et une précision maximale pour les applications professionnelles, la rédaction technique et l'analyse de documents complexes.",
                "version": "4.0",
                "image": "ai_models/gpt-4o-turbo.png",
                "display_order": 1,
            },
            {
                "name": "Claude 3.5 Sonnet",
                "slug": "claude-3-5-sonnet",
                "description": "L'assistant IA d'Anthropic avec une intelligence remarquable et une safety intégrée. Claude 3.5 Sonnet excelle dans le raisonnement logique, la programmation avancée et l'analyse nuancée de textes, tout en respectant les plus hauts standards de sécurité et d'éthique.",
                "version": "3.5",
                "image": "ai_models/claude-3-5-sonnet.png",
                "display_order": 2,
            },
            {
                "name": "Gemini 1.5 Pro",
                "slug": "gemini-1-5-pro",
                "description": "Le modèle multimodal de Google AI capable de comprendre et traiter simultanément texte, images, audio et vidéo. Gemini 1.5 Pro offre une fenêtre de contexte massive de 1 million de tokens pour des analyses approfondies et des réponses ultra-précises.",
                "version": "1.5",
                "image": "ai_models/gemini-1-5-pro.png",
                "display_order": 3,
            },
            {
                "name": "Stable Diffusion XL",
                "slug": "stable-diffusion-xl",
                "description": "Le générateur d'images par IA le plus avancé. Stable Diffusion XL produit des images photoréalistes et artistiques de qualité professionnelle à partir de descriptions textuelles. Idéal pour la création visuelle, le design graphique et la génération de contenu médiatique.",
                "version": "2.0",
                "image": "ai_models/stable-diffusion-xl.png",
                "display_order": 4,
            },
            {
                "name": "DALL-E 3",
                "slug": "dall-e-3",
                "description": "Le générateur d'images d'OpenAI avec une compréhension linguistique inégalée. DALL-E 3 transforme vos descriptions textuelles en images détaillées et cohérentes avec une fidélité exceptionnelle aux instructions. Parfait pour le marketing, l'illustration et la création de contenu visuel.",
                "version": "3.0",
                "image": "ai_models/dall-e-3.png",
                "display_order": 5,
            },
            {
                "name": "Midjourney v6",
                "slug": "midjourney-v6",
                "description": "La référence en matière de création artistique par IA. Midjourney v6 génère des œuvres d'art, des illustrations et des visuels de qualité galerie avec un style unique et esthétique. Idéal pour les créateurs, les designers et les artistes cherchant l'excellence visuelle.",
                "version": "6.0",
                "image": "ai_models/midjourney-v6.png",
                "display_order": 6,
            },
            {
                "name": "Whisper Large v3",
                "slug": "whisper-large-v3",
                "description": "Le système de reconnaissance vocale le plus précis au monde. Whisper Large v3 transcrit automatiquement la parole en texte avec une précision de 95%+ dans plus de 50 langues. Essentiel pour la transcription médicale, l'accessibilité et l'analyse de réunions.",
                "version": "3.0",
                "image": "ai_models/whisper-large-v3.png",
                "display_order": 7,
            },
            {
                "name": "TradingBot Pro",
                "slug": "tradingbot-pro",
                "description": "Le bot de trading algorithmique le plus sophistiqué. TradingBot Pro analyse les marchés financiers en temps réel avec des stratégies de trading avancées, des indicateurs techniques et des algorithmes de machine learning pour maximiser vos rendements avec une gestion des risques intelligente.",
                "version": "5.0",
                "image": "ai_models/tradingbot-pro.png",
                "display_order": 8,
            },
            {
                "name": "DataSense AI",
                "slug": "datasense-ai",
                "description": "La plateforme d'analyse de données pilotée par IA. DataSense AI transforme vos données brutes en insights actionnables grâce à des algorithmes de machine learning avancés, des visualisations interactives et des prédictions précises pour les entreprises et les chercheurs.",
                "version": "4.0",
                "image": "ai_models/datasense-ai.png",
                "display_order": 9,
            },
            {
                "name": "AutoML Engine",
                "slug": "automl-engine",
                "description": "La plateforme d'auto-apprentissage automatique la plus complète. AutoML Engine permet de créer, déployer et optimiser des modèles de machine learning sans code. Idéal pour les entreprises qui souhaitent exploiter la puissance de l'IA sans expertise technique approfondie.",
                "version": "3.0",
                "image": "ai_models/automl-engine.png",
                "display_order": 10,
            },
        ]
        for data in models_data:
            AiModel.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "version": data["version"],
                    "image": data["image"],
                    "is_active": True,
                    "display_order": data["display_order"],
                }
            )
            self.stdout.write(f'  ✅ Modèle IA créé : {data["name"]} (v{data["version"]})')
        self.stdout.write(f'  🎯 {len(models_data)} modèles IA initialisés.\n')

    def create_ai_offers(self):
        """Crée les offres IA pour chaque modèle avec des prix professionnels."""
        offers_data = [
            # ── GPT-4o Turbo ──
            {
                "name": "GPT-4o Turbo Starter",
                "slug": "gpt-4o-starter",
                "model_slug": "gpt-4o-turbo",
                "category_slug": "assistants-ia",
                "description": "Accès premium à GPT-4o Turbo pour la rédaction, l'analyse et la compréhension de textes. Parfait pour les professionnels et les créateurs de contenu. Réponses rapides et précises dans un environnement sécurisé.",
                "price": Decimal("50000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("3500"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 3 500 XAF/jour pendant 30 jours. Accès complet à tous les modèles GPT-4o Turbo avec priorité de traitement.",
                "is_active": True,
                "is_featured": True,
                "display_order": 1,
            },
            {
                "name": "GPT-4o Turbo Business",
                "slug": "gpt-4o-business",
                "model_slug": "gpt-4o-turbo",
                "category_slug": "assistants-ia",
                "description": "Offre professionnelle GPT-4o Turbo avec API dédiée, intégration avancée et support technique 24/7. Conçu pour les entreprises nécessitant des volumes élevés de traitement textuel.",
                "price": Decimal("150000"),
                "duration_days": 90,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("8000"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 8 000 XAF/jour pendant 90 jours. API dédiée, priorité maximale et support technique inclus.",
                "is_active": True,
                "is_featured": True,
                "display_order": 2,
            },
            # ── Claude 3.5 Sonnet ──
            {
                "name": "Claude 3.5 Starter",
                "slug": "claude-35-starter",
                "model_slug": "claude-3-5-sonnet",
                "category_slug": "assistants-ia",
                "description": "Accès à Claude 3.5 Sonnet pour le raisonnement avancé et la programmation. L'IA la plus sûre du marché avec des capacités exceptionnelles en analyse et codage.",
                "price": Decimal("40000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("2800"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 2 800 XAF/jour pendant 30 jours. Accès complet à Claude 3.5 avec sécurité renforcée.",
                "is_active": True,
                "is_featured": False,
                "display_order": 3,
            },
            {
                "name": "Claude 3.5 Pro",
                "slug": "claude-35-pro",
                "model_slug": "claude-3-5-sonnet",
                "category_slug": "assistants-ia",
                "description": "Offre professionnelle Claude 3.5 Sonnet avec capacités illimitées, traitement parallèle et support dédié. Idéal pour les développeurs et les analystes avancés.",
                "price": Decimal("120000"),
                "duration_days": 60,
                "revenue_frequency": "weekly",
                "revenue_type": "percentage",
                "revenue_value": Decimal("10"),
                "revenue_metric": "% du capital investi",
                "conditions": "10% de rendement hebdomadaire sur votre capital investi pendant 60 jours. Capacités illimitées et support prioritaire.",
                "is_active": True,
                "is_featured": True,
                "display_order": 4,
            },
            # ── Gemini 1.5 Pro ──
            {
                "name": "Gemini Multimodal",
                "slug": "gemini-multimodal",
                "model_slug": "gemini-1-5-pro",
                "category_slug": "analyse-de-donnees",
                "description": "Exploitez la puissance multimodale de Gemini 1.5 Pro pour analyser textes, images et données simultanément. La fenêtre de contexte de 1M tokens permet des analyses massives et profondes.",
                "price": Decimal("60000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("4200"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 4 200 XAF/jour pendant 30 jours. Accès complet à la multimodalité avec analyse vidéo et audio.",
                "is_active": True,
                "is_featured": True,
                "display_order": 5,
            },
            # ── Stable Diffusion XL ──
            {
                "name": "Image Generator Pro",
                "slug": "image-generator-pro",
                "model_slug": "stable-diffusion-xl",
                "category_slug": "generation-de-contenu",
                "description": "Créez des images professionnelles et photoréalistes avec Stable Diffusion XL. Générez des visuels de haute qualité pour le marketing, le design et la création de contenu.",
                "price": Decimal("25000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("1500"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 1 500 XAF/jour pendant 30 jours. Génération d'images illimitée avec résolution maximale.",
                "is_active": True,
                "is_featured": False,
                "display_order": 6,
            },
            # ── DALL-E 3 ──
            {
                "name": "DALL-E Creator",
                "slug": "dall-e-creator",
                "model_slug": "dall-e-3",
                "category_slug": "generation-de-contenu",
                "description": "Transformez vos idées en images détaillées avec DALL-E 3. La compréhension linguistique avancée garantit une fidélité parfaite entre vos descriptions et les résultats générés.",
                "price": Decimal("30000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("2000"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 2 000 XAF/jour pendant 30 jours. Génération d'images ultra-détaillées avec compréhension sémantique avancée.",
                "is_active": True,
                "is_featured": True,
                "display_order": 7,
            },
            # ── Whisper Large v3 ──
            {
                "name": "Transcription Premium",
                "slug": "transcription-premium",
                "model_slug": "whisper-large-v3",
                "category_slug": "automatisation",
                "description": "Transcription vocale professionnelle avec Whisper Large v3. Convertissez automatiquement la parole en texte avec une précision exceptionnelle dans 50+ langues pour vos réunions, interviews et documents audio.",
                "price": Decimal("20000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("1400"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 1 400 XAF/jour pendant 30 jours. Transcription illimitée avec une précision de 95%+ et support multilingue.",
                "is_active": True,
                "is_featured": False,
                "display_order": 8,
            },
            # ── TradingBot Pro ──
            {
                "name": "TradingBot Pro Starter",
                "slug": "tradingbot-starter",
                "model_slug": "tradingbot-pro",
                "category_slug": "trading-ia",
                "description": "Bot de trading algorithmique pour débutants et intermédiaires. TradingBot Pro Starter analyse les marchés en temps réel et exécute des stratégies de trading automatisées avec gestion des risques intégrée.",
                "price": Decimal("35000"),
                "duration_days": 30,
                "revenue_frequency": "daily",
                "revenue_type": "fixed",
                "revenue_value": Decimal("2500"),
                "revenue_metric": "XAF/jour",
                "conditions": "Revenu garanti de 2 500 XAF/jour pendant 30 jours. Stratégies de trading automatisées avec stop-loss et take-profit.",
                "is_active": True,
                "is_featured": True,
                "display_order": 9,
            },
            {
                "name": "TradingBot Pro Elite",
                "slug": "tradingbot-elite",
                "model_slug": "tradingbot-pro",
                "category_slug": "trading-ia",
                "description": "Le bot de trading ultime pour investisseurs avancés. TradingBot Pro Elite offre des algorithmes quantitatifs, une analyse prédictive et une optimisation de portefeuille avec des rendements exceptionnels.",
                "price": Decimal("200000"),
                "duration_days": 90,
                "revenue_frequency": "weekly",
                "revenue_type": "percentage",
                "revenue_value": Decimal("12"),
                "revenue_metric": "% du capital investi",
                "conditions": "12% de rendement hebdomadaire sur votre capital pendant 90 jours. Algorithmes quantitatifs avancés et optimisation de portefeuille.",
                "is_active": True,
                "is_featured": True,
                "display_order": 10,
            },
            # ── DataSense AI ──
            {
                "name": "DataSense Basic",
                "slug": "datasense-basic",
                "model_slug": "datasense-ai",
                "category_slug": "analyse-de-donnees",
                "description": "Analyse de données simplifiée pour les petits projets et les entrepreneurs. DataSense Basic transforme vos données en insights actionnables avec des tableaux de bord intuitifs et des rapports automatiques.",
                "price": Decimal("18000"),
                "duration_days": 30,
                "revenue_frequency": "weekly",
                "revenue_type": "percentage",
                "revenue_value": Decimal("8"),
                "revenue_metric": "% du capital investi",
                "conditions": "8% de rendement hebdomadaire sur votre capital investi pendant 30 jours. Tableaux de bord et rapports automatiques inclus.",
                "is_active": True,
                "is_featured": False,
                "display_order": 11,
            },
            # ── AutoML Engine ──
            {
                "name": "AutoML Starter",
                "slug": "automl-starter",
                "model_slug": "automl-engine",
                "category_slug": "automatisation",
                "description": "La plateforme d'auto-apprentissage pour créer vos propres modèles ML sans code. AutoML Starter permet aux entreprises de tirer parti de l'IA avec des modèles personnalisés et optimisés.",
                "price": Decimal("55000"),
                "duration_days": 45,
                "revenue_frequency": "weekly",
                "revenue_type": "percentage",
                "revenue_value": Decimal("10"),
                "revenue_metric": "% du capital investi",
                "conditions": "10% de rendement hebdomadaire pendant 45 jours. Création et déploiement de modèles ML personnalisés sans code.",
                "is_active": True,
                "is_featured": True,
                "display_order": 12,
            },
        ]
        for data in offers_data:
            model = AiModel.objects.get(slug=data.pop("model_slug"))
            category = AiCategory.objects.get(slug=data.pop("category_slug"))
            AiOffer.objects.get_or_create(slug=data["slug"], defaults={**data, "ai_model": model, "category": category})
            self.stdout.write(f'  ✅ Offre créée : {data["name"]} — {data["price"]:,} XAF/{data["duration_days"]}j')
        self.stdout.write(f'  🎯 {len(offers_data)} offres IA initialisées.\n')
