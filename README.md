# M-Motors

Plateforme de gestion de concession automobile — catalogue véhicules, dossiers clients (achat/location) et espace d'administration.

**Stack :** FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · Jinja2 · Python 3.13

---

## Sommaire

- [Prérequis](#prérequis)
- [Installation locale](#installation-locale)
- [Variables d'environnement](#variables-denvironnement)
- [Base de données](#base-de-données)
- [Créer un compte admin](#créer-un-compte-admin)
- [Lancer l'application](#lancer-lapplication)
- [Tests](#tests)
- [Déploiement web](#déploiement-web)

---

## Prérequis

| Outil | Version minimale |
|---|---|
| Python | 3.13 |
| PostgreSQL | 14+ |
| pip | 23+ |

---

## Installation locale

### 1. Cloner le dépôt

```bash
git clone https://github.com/MaxL34/m-motors.git
cd m-motors
```

### 2. Créer et activer l'environnement virtuel

```bash
python3.13 -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Éditez `.env` selon votre configuration locale (voir [Variables d'environnement](#variables-denvironnement)).

### 5. Créer la base de données PostgreSQL

```bash
psql -U postgres -c "CREATE DATABASE mmotors;"
```

### 6. Appliquer les migrations

```bash
alembic upgrade head
```

### 7. Créer le compte administrateur

```bash
python scripts/create_admin.py
```

Identifiants par défaut : `admin@m-motors.fr` / `changeme123` — **à modifier immédiatement**.

### 8. Lancer le serveur de développement

```bash
uvicorn app.main:app --reload
```

L'application est accessible sur [http://localhost:8000](http://localhost:8000).

---

## Variables d'environnement

Toutes les variables sont chargées depuis le fichier `.env` à la racine du projet.

| Variable                      | Requis | Description |
|-------------------------------|--------|-------------|
| `DATABASE_URL`                | Oui    | URL de connexion PostgreSQL. Ex : `postgresql://user:pass@localhost:5432/mmotors` |
| `SECRET_KEY`                  | Oui    | Clé de signature JWT (minimum 32 caractères). Ex : `une-cle-aleatoire-longue` |
| `ALGORITHM`                   | Non    | Algorithme JWT — défaut : `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Non    | Durée de validité du token JWT en minutes — défaut : `30` |
| `MAX_FILE_SIZE_MB`            | Non    | Taille maximale des fichiers uploadés en Mo — défaut : `5` |
| `UPLOAD_DIR`                  | Non    | Répertoire de stockage des documents — défaut : `app/static/uploads` |
| `SENTRY_DSN`                  | Non    | DSN Sentry pour le monitoring d'erreurs (laisser vide pour désactiver) |
| `ENVIRONMENT`                 | Non    | `development` ou `production` — défaut : `development` |

> **Sécurité :** Ne commitez jamais le fichier `.env`. Il est exclu par `.gitignore`.

Pour générer une `SECRET_KEY` robuste :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Base de données

Le projet utilise **Alembic** pour gérer les migrations de schéma.

```bash
# Appliquer toutes les migrations
alembic upgrade head

# Créer une nouvelle migration après modification d'un modèle
alembic revision --autogenerate -m "description de la migration"

# Revenir à la migration précédente
alembic downgrade -1

# Voir l'état actuel
alembic current
```

---

## Créer un compte admin

```bash
python scripts/create_admin.py
```

Le script crée un utilisateur `admin@m-motors.fr` avec le mot de passe `changeme123` si aucun compte avec cet email n'existe déjà. Changez le mot de passe après la première connexion.

---

## Lancer l'application

**Développement** (rechargement automatique) :

```bash
uvicorn app.main:app --reload
```

**Production** (plusieurs workers) :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Tests

Le projet utilise **pytest** avec couverture de code.

```bash
# Lancer tous les tests
pytest

# Avec rapport de couverture HTML
pytest --cov=app --cov-report=html

# Rapport disponible dans
open htmlcov/index.html
```

> Les tests utilisent une base SQLite en mémoire (`test.db`) — aucune configuration supplémentaire n'est requise.

---

## Déploiement web

### Prérequis communs

- Un serveur PostgreSQL accessible depuis le serveur applicatif
- Les variables d'environnement configurées en production (`ENVIRONMENT=production`, `SENTRY_DSN`, etc.)
- Le répertoire `UPLOAD_DIR` accessible en écriture et persistant entre les redémarrages

---

### Option A — VPS (Ubuntu / Debian)

#### 1. Installer les dépendances système

```bash
sudo apt update && sudo apt install -y python3.13 python3.13-venv python3-pip postgresql nginx
```

#### 2. Déployer l'application

```bash
git clone https://github.com/<votre-org>/m-motors.git /var/www/m-motors
cd /var/www/m-motors
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditez .env
alembic upgrade head
python scripts/create_admin.py
```

#### 3. Configurer systemd

Créez `/etc/systemd/system/mmotors.service` :

```ini
[Unit]
Description=M-Motors FastAPI
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/m-motors
EnvironmentFile=/var/www/m-motors/.env
ExecStart=/var/www/m-motors/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mmotors
sudo systemctl start mmotors
```

#### 4. Configurer Nginx comme reverse proxy

```nginx
server {
    listen 80;
    server_name votre-domaine.fr;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/m-motors/app/static;
        expires 7d;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

#### 5. Activer HTTPS avec Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d votre-domaine.fr
```

---

### Option B — Heroku / Railway / Render

Le projet inclut un `Procfile` prêt à l'emploi :

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

#### Déploiement

```bash
# Heroku
heroku create m-motors
heroku addons:create heroku-postgresql:essential-0
heroku config:set SECRET_KEY=... ENVIRONMENT=production SENTRY_DSN=...
git push heroku main
heroku run alembic upgrade head
heroku run python scripts/create_admin.py

# Railway / Render
# Importez le dépôt GitHub depuis l'interface web,
# ajoutez les variables d'environnement dans les settings,
# puis déclenchez le déploiement.
```

> **Uploads :** Les plateformes PaaS ont un système de fichiers éphémère. Pour la persistance des documents uploadés, utilisez un stockage objet externe (S3, Cloudflare R2, OVH Object Storage) et adaptez `UPLOAD_DIR` en conséquence.

---

### Checklist avant mise en production

- [ ] `SECRET_KEY` aléatoire et longue (≥ 32 caractères)
- [ ] `DATABASE_URL` pointe vers la base de production
- [ ] `ENVIRONMENT=production`
- [ ] `SENTRY_DSN` configuré pour le monitoring d'erreurs
- [ ] Répertoire `UPLOAD_DIR` persistant et accessible en écriture
- [ ] HTTPS activé (Certbot ou certificat fourni par la plateforme)
- [ ] Mot de passe admin changé après la première connexion
- [ ] SMS OTP : remplacer le stub de développement dans `app/services/otp_service.py` par un vrai fournisseur (Twilio, OVH SMS...)
