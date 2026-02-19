# Installation et Configuration

## Prérequis

| Outil | Version minimale |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
| Docker + Docker Compose | (optionnel, recommandé) |

---

## Installation rapide (Docker)

La méthode la plus simple pour démarrer l'infrastructure (PostgreSQL + Redis) :

```bash
docker-compose up -d db redis
```

Cela démarre :
- PostgreSQL sur `localhost:5432` (base `ecoia`, user `postgres`, password `postgres`)
- Redis sur `localhost:6379`

---

## Installation du backend (`src/ecoia`)

### 1. Créer l'environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# ou
.venv\Scripts\activate     # Windows
```

### 2. Installer les dépendances

Avec `uv` (recommandé) :
```bash
pip install uv
uv pip install -e ".[dev]"
```

Avec `pip` classique :
```bash
pip install -e ".[dev]"
```

### 3. Configurer les variables d'environnement

Copier le fichier d'exemple et l'éditer :
```bash
cp .env.staging.example .env
```

Variables obligatoires à renseigner dans `.env` :

```env
# Base de données
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecoia

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM — choisir un provider et renseigner la clé correspondante
LLM_PROVIDER=mistral
LLM_MODEL=mistral-large-latest

MISTRAL_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
```

### 4. Appliquer les migrations de base de données

```bash
alembic upgrade head
```

### 5. Démarrer le serveur API

```bash
ecoia serve --reload
```

Le serveur démarre sur `http://localhost:8000`.

Documentation interactive Swagger : `http://localhost:8000/docs`

---

## Installation du frontend (`front_inferno`)

### 1. Installer les dépendances Node

```bash
cd front_inferno
npm install
```

### 2. Démarrer le serveur de développement

```bash
npm run dev
```

Le frontend démarre sur `http://localhost:5173`.

> Vite proxifie automatiquement les requêtes `/api/v1/*` vers `http://localhost:8000`. Assurez-vous que le backend est démarré.

### 3. Build de production

```bash
npm run build
```

Les fichiers compilés sont dans `front_inferno/dist/`.

---

## Providers LLM

### Mistral (défaut)

```env
LLM_PROVIDER=mistral
LLM_MODEL=mistral-large-latest
MISTRAL_API_KEY=sk-...
```

Modèles disponibles : `mistral-large-latest`, `mistral-small-latest`, `open-mistral-7b`

### OpenAI

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

Modèles disponibles : `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`

### Anthropic

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

### AWS Bedrock

```env
LLM_PROVIDER=bedrock
LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

---

## Migrations de base de données

### Créer une nouvelle migration

```bash
alembic revision --autogenerate -m "description de la migration"
```

### Appliquer les migrations

```bash
alembic upgrade head
```

### Revenir en arrière

```bash
alembic downgrade -1
```

### Voir l'historique

```bash
alembic history
```

---

## CLI `ecoia`

Le CLI est disponible après installation du package.

```bash
# Afficher la version
ecoia version

# Démarrer le serveur
ecoia serve
ecoia serve --host 0.0.0.0 --port 8000 --reload

# Uploader un fichier
ecoia upload catalogue.xlsx --supplier <uuid>

# Traiter un document (mode CLI)
ecoia process catalogue.xlsx --config configs/format_default.yaml
```

---

## Déploiement Docker complet

Pour déployer l'application complète (backend + infrastructure) :

```bash
docker-compose up -d
```

Le `docker-compose.yml` démarre :
- `db` : PostgreSQL 15
- `redis` : Redis 7
- `app` : backend ecoia sur le port 8000

> Le frontend doit être buildé séparément et servi via un reverse proxy (nginx, Caddy…) ou un CDN.

### Variables d'environnement Docker

Passer les variables via le fichier `.env` ou directement dans `docker-compose.yml` :

```yaml
environment:
  - DATABASE_URL=postgresql://postgres:postgres@db:5432/ecoia
  - REDIS_URL=redis://redis:6379/0
  - LLM_PROVIDER=mistral
  - MISTRAL_API_KEY=sk-...
```

---

## Tests

### Lancer tous les tests

```bash
pytest
```

### Avec rapport de couverture

```bash
pytest --cov=src/ecoia --cov-report=html
```

Le rapport HTML est généré dans `htmlcov/`.

### Filtrer les tests

```bash
# Tests unitaires uniquement
pytest -m unit

# Tests d'intégration
pytest -m integration

# Exclure les tests lents
pytest -m "not slow"
```

---

## Linting et formatage

```bash
# Formatage automatique
black src/ tests/

# Tri des imports
isort src/ tests/

# Vérification style
flake8 src/ tests/

# Type checking
mypy src/
```

### Pre-commit hooks

```bash
pre-commit install
pre-commit run --all-files
```

---

## Structure des fichiers de configuration

```
configs/
├── format_default.yaml      # Format de sortie par défaut
└── ...                      # Autres formats YAML
```

### Exemple de format YAML

```yaml
name: default
description: Format de sortie par défaut
fields:
  - name: titre_commercial
    type: text
    prompt: "Génère un titre commercial accrocheur pour ce produit"
  - name: description_longue
    type: text
    prompt: "Rédige une description détaillée de 200 mots"
  - name: caracteristiques
    type: object
    prompt: "Extrait les caractéristiques techniques clés sous forme de paires clé-valeur"
  - name: mots_cles_seo
    type: list
    prompt: "Génère 10 mots-clés SEO pertinents"
```

---

## Résolution de problèmes courants

### `alembic upgrade head` échoue

Vérifier que PostgreSQL est démarré et que `DATABASE_URL` est correct :
```bash
psql postgresql://postgres:postgres@localhost:5432/ecoia -c "SELECT 1"
```

### Docling non disponible

Vérifier que la version exacte est installée :
```bash
pip show docling | grep Version
# Doit afficher: Version: 2.73.1
```

### Erreur CORS en développement

Vérifier que le frontend tourne sur `localhost:5173` ou `localhost:3000` (ports autorisés dans `main.py`).

### Clé API LLM invalide

Tester la configuration via `GET /config/` qui retourne le provider actif. Vérifier la variable d'environnement correspondante dans `.env`.

### Le job d'extraction ne progresse pas

Vérifier les logs du serveur (`ecoia serve --reload`). Les jobs tournent dans des threads séparés — une exception non gérée peut bloquer silencieusement le job.
