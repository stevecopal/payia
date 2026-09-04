# PAYIA - Plateforme IA et Finance

Plateforme web moderne combinant intelligence artificielle et finance.

## Installation

### Prérequis

- Python 3.12+
- Node.js (pour Tailwind CSS)
- PostgreSQL (production) ou SQLite (développement)

### Installation

```bash
# Cloner le projet
git clone <repo-url>
cd payia

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs

# Installer Tailwind CSS
npm install

# Compiler le CSS
npm run build:css

# Appliquer les migrations
python manage.py migrate

# Créer un super utilisateur
python manage.py createsuperuser

# Lancer le serveur
python manage.py runserver
```

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SECRET_KEY` | Clé secrète Django | ( développement ) |
| `DEBUG` | Mode debug | `True` |
| `ALLOWED_HOSTS` | Hosts autorisés | `localhost,127.0.0.1` |
| `DATABASE_URL` | URL base de données | SQLite |
| `SMS_PROVIDER` | Fournisseur SMS | `console` |

## Structure

```
payia/
├── core/           # Auth, profil, rôles, permissions, audit
├── wallet/         # Portefeuille, journal financier
├── transactions/   # Dépôts, retraits
├── ai_services/    # Offres IA, locations, revenus
├── referrals/      # Parrainage 5 niveaux, commissions
├── notifications/  # Notifications, messages
├── support/        # Tickets de support
├── analytics/      # Statistiques, événements
├── dashboard/      # Tableau de bord utilisateur
└── templates/      # Templates Django
```

## Commandes utiles

```bash
# Lancer les tests
python manage.py test

# Compiler le CSS
npm run build:css

# Watch le CSS
npm run watch:css

# Collecter les fichiers statiques
python manage.py collectstatic

# Créer un super utilisateur
python manage.py createsuperuser
```

## Administration

- Django Admin: `/django-admin/`
- Dashboard Admin PAYIA: `/admin-panel/`

## Technologies

- Django 4.2
- PostgreSQL
- Tailwind CSS
- JavaScript vanilla
- Python
