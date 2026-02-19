# CatalogIA Generator (Open Source)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**CatalogIA** est une plateforme open source pour extraire des produits depuis des catalogues fournisseurs et générer des fiches produits avec l'IA.

## 🎯 Objectifs du projet

CatalogIA poursuit plusieurs objectifs complémentaires :

### 📊 Solution adaptée aux entreprises
- **Ingestion multi-formats** : Excel, CSV, PDF, DOCX, Markdown, TXT
- **Extraction structurée** des produits avec intelligence artificielle
- **Enrichissement automatique** des fiches produits
- **Validation et export** vers différents formats

### 🧪 Laboratoire d'expérimentation IA
- **Test d'outils IA** : évaluation et comparaison des solutions du marché
- **Benchmarking de modèles** : tests comparatifs des différents LLM (OpenAI, Anthropic, Mistral, etc.)
- **Exploration de workflows** : prototypage de chaînes de traitement complexes
- **Veille technologique** : intégration des dernières avancées en NLP et computer vision

### 🔬 Plateforme de R&D
- **Génération IA avancée** : expérimentation avec différents types de modèles
- **Architecture modulaire** : facilité d'intégration de nouveaux composants
- **Open source collaboratif** : partage des connaissances et des apprentissages

## 🛠 Stack technologique

### Backend
- **FastAPI** : Framework API moderne avec validation automatique
- **SQLAlchemy** + **Alembic** : ORM et migrations de base de données
- **PostgreSQL** : Base de données principale
- **Redis** : Cache et file d'attente (pour les traitements asynchrones)

### Intelligence Artificielle
- **LangChain** : Orchestration des chaînes de traitement IA
- **Multiple providers** : OpenAI, Anthropic, Mistral, AWS Bedrock
- **Docling 2.73.1** : Parsing documentaire avancé (PDF/DOCX/MD/TXT/CSV)

### Frontend
- **Inferno.js** + **Vite** : Interface utilisateur moderne et réactive
- **TailwindCSS** : Styling utilitaire
- **Server-Sent Events** : Progression en temps réel des traitements

### Outils et CLI
- **Typer** : Interface en ligne de commande élégante
- **pytest** : Tests unitaires et d'intégration
- **black/flake8** : Qualité de code

## 📦 Solutions et packages open source présentés

CatalogIA intègre et présente plusieurs solutions open source remarquables :

### 🤖 LangChain Ecosystem
- **LangChain** (≥ 1.2.6) : Framework d'orchestration IA
- **LangChain Community** : Connecteurs communautaires
- **LangSmith** : Monitoring et debugging des chaînes IA

### 📄 Traitement documentaire
- **Docling** (2.73.1) : Extraction de tableaux depuis documents complexes
- **PyPDF2** & **pdfplumber** : Manipulation PDF
- **python-docx** : Traitement Word
- **openpyxl** : Manipulation Excel

### 🔍 Vectorisation et recherche
- **ChromaDB** : Base de données vectorielle
- **FAISS** : Indexation vectorielle haute performance
- **sentence-transformers** : Embeddings sémantiques

### 🌐 Scraping et web
- **BeautifulSoup4** : Parsing HTML
- **ddgs** (DuckDuckGo Search) : Recherche web
- **httpx** : Client HTTP asynchrone

### 🎨 Interface utilisateur
- **Inferno.js** : Framework JavaScript moderne
- **Vite** : Build tool ultra-rapide
- **TailwindCSS** : Framework CSS utilitaire

## 🚀 Démarrage rapide

### 1) Prérequis

- Python 3.10+
- `uv` (recommandé) ou pip
- Node.js 18+ (pour `front_inferno`)
- PostgreSQL (ou Docker Compose)

### 2) Installation backend

```bash
uv sync
```

Alternative pip:

```bash
pip install -e ".[dev,test]"
```

### 3) Base de données

```bash
uv run alembic upgrade head
```

### 4) Lancer l'API

```bash
uv run ecoia serve --reload
```

L'API démarre sur `http://localhost:8000`.

Documentation interactive Swagger : `http://localhost:8000/docs`

### 5) Lancer le frontend Inferno

```bash
cd front_inferno
npm install
npm run dev
```

Interface: `http://localhost:5173`

## ⚙️ Configuration

### Variables d'environnement

Copier `.env.staging.example` vers `.env` puis adapter:

```env
# Base de données
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecoia

# Redis
REDIS_URL=redis://localhost:6379/0

# Provider LLM (choisir et configurer)
LLM_PROVIDER=mistral
LLM_MODEL=mistral-large-latest
MISTRAL_API_KEY=sk-...

# Alternative: OpenAI
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o
# OPENAI_API_KEY=sk-...

# Alternative: Anthropic
# LLM_PROVIDER=anthropic
# LLM_MODEL=claude-3-5-sonnet-20241022
# ANTHROPIC_API_KEY=sk-ant-...
```

⚠️ **Important** : Ne jamais commiter les clés API dans le repository.

## 🧪 Tests et qualité

```bash
# Tests complets
uv run pytest tests/

# Qualité de code
uv run flake8 src tests
uv run black --check src tests

# Type checking
uv run mypy src/
```

## 📚 Documentation complète

La documentation détaillée est disponible dans le dossier [`docs/`](docs/) :

| Document | Contenu |
|---|---|
| [**SETUP.md**](docs/SETUP.md) | Installation complète et configuration |
| [**TECHNICAL.md**](docs/TECHNICAL.md) | Architecture backend détaillée |
| [**FRONTEND.md**](docs/FRONTEND.md) | Architecture frontend Inferno |
| [**API.md**](docs/API.md) | Référence complète des endpoints REST |
| [**USER_GUIDE.md**](docs/USER_GUIDE.md) | Guide utilisateur de l'interface |

### Architecture en un coup d'œil

```
┌─────────────────────────────────────────────────────────┐
│                    front_inferno                        │
│         Inferno.js + TailwindCSS (port 5173)           │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP REST + SSE
                         │ /api/v1/*
┌────────────────────────▼────────────────────────────────┐
│                   src/ecoia                             │
│              FastAPI (port 8000)                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Parsers  │  │ Services │  │   LLM    │             │
│  │ (Docling │  │ Extract  │  │ Mistral  │             │
│  │  Excel)  │  │ Enrich   │  │ OpenAI   │             │
│  └──────────┘  │ Scraping │  │ Anthropic│             │
│                └──────────┘  └──────────┘             │
└──────────┬──────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
┌───▼───┐   ┌────▼───┐
│  PG   │   │ Redis  │
│  :5432│   │  :6379 │
└───────┘   └────────┘
```

## 🤝 Contribution

Nous encourageons les contributions sous toutes leurs formes :

1. **Fork** le repository
2. **Créer une branche** feature/fix avec un nom clair
3. **Ajouter des tests** et vérifier la qualité de code
4. **Ouvrir une PR** avec une description claire des changements

### Zones d'expérimentation prioritaires
- **Nouveaux parsers** pour formats de documents exotiques
- **Providers LLM** additionnels
- **Workflows d'enrichissement** innovants
- **Métriques d'évaluation** des performances IA

## 📄 Licence

Ce projet est distribué sous **GNU Affero General Public License v3.0**.

- Fichier licence: [LICENSE](LICENSE)
- Texte officiel: https://www.gnu.org/licenses/agpl-3.0

En cas d'usage réseau d'une version modifiée, l'AGPLv3 impose la mise à disposition du code source correspondant.

## 🔗 Liens utiles

- **Repository** : https://github.com/proovup/poc-generator-open-source
- **Issues** : https://github.com/proovup/poc-generator-open-source/issues
- **Documentation** : https://proovup-generator.readthedocs.io

---

**CatalogIA** : *Laboratoire IA pour l'extraction et l'enrichissement de catalogues produits*
