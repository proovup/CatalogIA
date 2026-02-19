# Architecture Technique — Backend `src/ecoia`

## Vue d'ensemble

`ecoia` est une API REST construite avec **FastAPI** (Python ≥ 3.10). Elle expose un ensemble de services pour :

- Gérer des fournisseurs et leurs documents
- Extraire des produits depuis des fichiers (Excel, PDF, DOCX, CSV, TXT) ou des sites web
- Enrichir les fiches produits via des documents complémentaires
- Classifier les produits par catégorie
- Gérer des formats de sortie personnalisés (YAML)
- Scraper des images et données produits sur le web

La stack d'infrastructure repose sur **PostgreSQL** (persistance), **Redis** (futur cache/queue) et **Docling 2.73.1** (parsing documentaire non-Excel).

---

## Structure des répertoires

```
src/ecoia/
├── main.py                  # Point d'entrée FastAPI + CLI Typer
├── config.py                # Settings (pydantic-settings, .env)
├── api/
│   └── endpoints/           # Routeurs FastAPI par domaine
│       ├── classification.py
│       ├── config.py
│       ├── enrichment.py
│       ├── formats.py
│       ├── processing.py
│       ├── products.py
│       ├── scraping.py
│       ├── supplier.py
│       └── upload.py
├── services/                # Logique métier
│   ├── classification_service.py
│   ├── config_validator.py
│   ├── document_processing_service.py
│   ├── enrichment_service.py
│   ├── format_service.py
│   ├── output_format_service.py
│   ├── processing_service.py
│   ├── product_extractor_service.py
│   ├── product_scraper_service.py
│   ├── product_service.py
│   ├── source_preprocessor_service.py
│   ├── supplier_service.py
│   ├── upload_service.py
│   └── ...
├── parsers/                 # Parsers de fichiers
│   ├── __init__.py          # ParserFactory
│   ├── base.py
│   ├── docling_tabular.py   # PDF/DOCX/MD/TXT/CSV via Docling
│   ├── excel.py
│   ├── pdf.py
│   ├── text.py
│   └── word.py
├── schemas/                 # Modèles Pydantic (validation I/O)
│   ├── classification.py
│   ├── document.py
│   ├── format.py
│   ├── output_format.py
│   ├── processing.py
│   └── supplier.py
├── db/
│   ├── database.py          # Engine SQLAlchemy + SessionLocal
│   └── models.py            # Modèles ORM
└── cli/
    └── suppliers.py         # Sous-commandes CLI fournisseurs
```

---

## Configuration (`config.py`)

Toutes les variables sont lues depuis le fichier `.env` via `pydantic-settings`.

| Variable | Défaut | Description |
|---|---|---|
| `APP_NAME` | `EcoIA Generator` | Nom de l'application |
| `VERSION` | `0.1.0` | Version |
| `DEBUG` | `True` | Mode debug |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ecoia` | URL PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | URL Redis |
| `UPLOAD_DIR` | `src/uploads/` | Dossier de stockage des fichiers uploadés |
| `LLM_PROVIDER` | `mistral` | Fournisseur LLM actif (`openai`, `mistral`, `anthropic`, `bedrock`) |
| `LLM_MODEL` | `mistral-large-latest` | Modèle LLM par défaut |
| `MISTRAL_API_KEY` | — | Clé API Mistral |
| `OPENAI_API_KEY` | — | Clé API OpenAI |
| `ANTHROPIC_API_KEY` | — | Clé API Anthropic |
| `AWS_REGION` | `us-east-1` | Région AWS Bedrock |
| `AWS_ACCESS_KEY_ID` | — | Clé AWS |
| `AWS_SECRET_ACCESS_KEY` | — | Secret AWS |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.6` | Seuil de confiance classification |

---

## Point d'entrée (`main.py`)

### API FastAPI

L'application FastAPI est instanciée avec CORS configuré pour `localhost:5173` et `localhost:3000` (dev front).

Les routeurs sont montés sous le préfixe `/api/v1` :

| Préfixe | Module | Domaine |
|---|---|---|
| `/api/v1/documents` | `upload` | Upload de fichiers |
| `/api/v1/suppliers` | `supplier` | Gestion fournisseurs |
| `/api/v1/products` | `products` | Produits, extraction, classification |
| `/api/v1/formats` | `formats` | Formats de sortie |
| `/api/v1/scraping` | `scraping` | Scraping web & galerie images |
| `/api/v1/enrichment` | `enrichment` | Enrichissement de fiches |
| `/api/v1/config` | `config` | Configuration runtime |

Endpoints système :
- `GET /` → statut de l'application
- `GET /health` → health check

### CLI Typer

Le CLI est accessible via la commande `ecoia` (définie dans `pyproject.toml`).

| Commande | Description |
|---|---|
| `ecoia version` | Affiche la version |
| `ecoia serve [--host] [--port] [--reload]` | Démarre le serveur API |
| `ecoia upload <file> [--supplier] [--batch]` | Upload un fichier en base |
| `ecoia process <file> --config <yaml>` | Parse un document et génère le prompt |

---

## Parsers (`parsers/`)

### `ParserFactory`

Sélectionne automatiquement le parser selon l'extension du fichier :

| Extension | Parser |
|---|---|
| `.xlsx`, `.xls` | `ExcelParser` |
| `.pdf` | `PDFParser` → `DoclingTabularParser` (chemin principal) |
| `.docx` | `WordParser` → `DoclingTabularParser` (chemin principal) |
| `.txt`, `.csv` | `TextParser` → `DoclingTabularParser` (chemin principal) |
| `.md`, `.markdown` | `DoclingTabularParser` |

### `DoclingTabularParser`

Chemin principal pour tous les formats non-Excel. Utilise **Docling 2.73.1** pour convertir le document et en extraire les tableaux.

**Flux de traitement :**
1. `DocumentConverter().convert(file_path)` → document Docling
2. Extraction des tableaux natifs (`doc.tables`) via `export_to_dataframe()`
3. Si aucun tableau natif → fallback sur export Markdown + parsing des blocs `|...|`
4. Chaque tableau devient une "feuille" pseudo-Excel nommée `table_1`, `table_2`, …
5. Si aucun tableau exploitable → `ValueError` explicite (pas de fallback silencieux)

**Règle de robustesse :** le fallback vers l'extraction legacy n'est activé qu'en cas de défaillance technique de Docling (import impossible, crash), pas en cas d'absence de tableau.

### `ExcelParser`

Chemin dédié Excel, non modifié. Lit les feuilles via `openpyxl`/`pandas`.

---

## Services (`services/`)

### `ProductExtractorService`

Service central de l'extraction produits. Orchestre :

1. **Préprocessing** (`SourcePreprocessorService`) : lecture du fichier, détection des feuilles, sélection de la feuille maître (master)
2. **Mapping de champs** : application du `field_mapping_override` si fourni
3. **Appel LLM** : génération de fiches produits via le provider configuré
4. **Persistance** : création des `Product` en base depuis la feuille maître uniquement
5. **Enrichissement inter-feuilles** : les feuilles secondaires servent à compléter les produits créés

Paramètres clés de `ExtractRequest` :

| Paramètre | Type | Description |
|---|---|---|
| `document_id` | `str` | UUID du document à traiter |
| `format_name` | `str` | Nom du format de sortie (`default` ou UUID) |
| `analysis` | `dict` | Résultat de l'analyse préalable des feuilles |
| `field_mapping_override` | `dict` | Surcharge du mapping de colonnes |
| `max_products` | `int` | Limite du nombre de produits extraits |
| `source_mode` | `str` | `document` ou `presented_catalog` |
| `presented_mode` | `str` | `docling_ocr` ou `vision_model` |
| `provider` | `str` | Surcharge du provider LLM |
| `model_name` | `str` | Surcharge du modèle LLM |

### `SourcePreprocessorService`

Prépare les données brutes du document pour l'extraction :
- Lecture des feuilles/tableaux
- Détection automatique de la feuille principale (master)
- Génération des échantillons de colonnes pour l'analyse

### `EnrichmentService`

Enrichit des produits existants à partir d'un document complémentaire (notice, fiche technique, catalogue secondaire). Gère le matching produit-document par référence ou nom, avec un score de confiance (`match_confidence`).

Types d'enrichissement supportés : `notice`, `catalogue`, `fiche_technique`, `other`.

### `ClassificationService`

Classifie un produit dans une arborescence de catégories via LLM. Utilise un seuil de confiance configurable (`CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.6`).

### `ProductScraperService`

Scrape des données et images produits depuis le web (via `beautifulsoup4` + `ddgs`). Stocke les résultats dans `ProductScrapeResult`. Fournit un proxy d'image pour contourner les restrictions CORS.

### `SupplierService`

CRUD complet sur les fournisseurs. Supporte la suppression douce (soft delete) si des documents sont associés.

### `FormatService`

CRUD sur les formats de sortie stockés en base. Les formats sont définis en YAML et peuvent être uploadés directement.

### `UploadService`

Gère l'upload et le stockage physique des fichiers dans `UPLOAD_DIR`. Crée l'entrée `Document` en base avec le statut `uploaded`.

---

## Modèles de données (ORM)

| Modèle | Table | Description |
|---|---|---|
| `Supplier` | `suppliers` | Fournisseur avec config de mapping |
| `Document` | `documents` | Fichier uploadé, lié à un fournisseur |
| `Product` | `products` | Fiche produit extraite |
| `EnrichmentDocument` | `enrichment_documents` | Document d'enrichissement lié à un produit |
| `ProductScrapeResult` | `product_scrape_results` | Résultat de scraping web |

---

## Flux d'extraction produits (séquence complète)

```
Client (front_inferno)
  │
  ├─ POST /api/v1/documents/upload          → Document créé (status: uploaded)
  │
  ├─ POST /api/v1/products/analyze          → Analyse des feuilles (LLM)
  │    └─ Retourne: { sheets, suggested_master, columns_preview }
  │
  ├─ POST /api/v1/products/extract          → Job d'extraction créé (job_id)
  │    └─ Paramètres: document_id, format_name, analysis, field_mapping_override, max_products
  │
  └─ GET  /api/v1/products/extract/{job_id}/progress  (SSE)
       └─ Événements: { progress, message, done, status, products_count }
```

Le job d'extraction tourne dans un thread séparé. La progression est streamée via **Server-Sent Events (SSE)**.

---

## Flux d'enrichissement (séquence)

```
Client
  │
  ├─ POST /api/v1/enrichment/upload         → EnrichmentDocument créé
  │
  ├─ POST /api/v1/enrichment/process        → Job d'enrichissement créé (job_id)
  │    └─ Paramètres: document_id, product_ids[], enrichment_type, provider
  │
  └─ GET  /api/v1/enrichment/{job_id}/progress  (SSE)
       └─ Événements: { progress, message, done, status }
```

---

## Dépendances principales

| Package | Version | Usage |
|---|---|---|
| `fastapi` | ≥ 0.115 | Framework API |
| `uvicorn` | ≥ 0.30 | Serveur ASGI |
| `sqlalchemy` | ≥ 2.0 | ORM |
| `alembic` | ≥ 1.13 | Migrations DB |
| `pydantic` | ≥ 2.10 | Validation schémas |
| `docling` | 2.73.1 | Parsing documentaire |
| `langchain` | ≥ 1.2.6 | Orchestration LLM |
| `langchain-mistralai` | ≥ 1.1.1 | Provider Mistral |
| `langchain-openai` | ≥ 0.1.0 | Provider OpenAI |
| `langchain-anthropic` | ≥ 0.1.0 | Provider Anthropic |
| `langchain-aws` | ≥ 1.2.1 | Provider AWS Bedrock |
| `pandas` | ≥ 2.2.1 | Manipulation tabulaire |
| `openpyxl` | ≥ 3.1.2 | Lecture Excel |
| `beautifulsoup4` | ≥ 4.12 | Scraping HTML |
| `typer` | ≥ 0.12 | CLI |
