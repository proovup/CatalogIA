# Référence API REST — `ecoia`

Base URL : `http://localhost:8000/api/v1`

Toutes les réponses sont en JSON. Les erreurs retournent `{ "detail": "..." }`.

---

## Système

### `GET /`
Statut de l'application.

**Réponse 200**
```json
{ "name": "EcoIA Generator", "version": "0.1.0", "status": "running" }
```

### `GET /health`
Health check.

**Réponse 200**
```json
{ "status": "ok" }
```

---

## Documents — `/documents`

### `POST /documents/upload`
Upload un fichier et crée un `Document` en base.

**Body** : `multipart/form-data`
| Champ | Type | Requis | Description |
|---|---|---|---|
| `file` | `File` | ✅ | Fichier à uploader (xlsx, pdf, docx, csv, txt) |
| `supplier_id` | `string (UUID)` | ❌ | Associer à un fournisseur |

**Réponse 200**
```json
{
  "id": "uuid",
  "filename": "catalogue.xlsx",
  "file_type": "xlsx",
  "file_size": 204800,
  "status": "uploaded",
  "supplier_id": "uuid",
  "created_at": "2025-01-15T10:30:00"
}
```

---

## Fournisseurs — `/suppliers`

### `GET /suppliers/`
Liste les fournisseurs avec pagination.

**Query params**
| Param | Type | Défaut | Description |
|---|---|---|---|
| `skip` | `int` | `0` | Offset |
| `limit` | `int` | `100` | Taille de page (max 1000) |
| `active_only` | `bool` | `false` | Filtrer les actifs uniquement |

**Réponse 200**
```json
{
  "suppliers": [ { "id": "uuid", "name": "...", "is_active": "active", ... } ],
  "total": 42,
  "page": 1,
  "size": 100
}
```

### `POST /suppliers/`
Crée un fournisseur.

**Body JSON**
```json
{
  "name": "Fournisseur ABC",
  "description": "Description optionnelle",
  "is_active": "active",
  "config": {
    "file_config": {
      "file_type": "xlsx",
      "encoding": "utf-8",
      "has_header": true,
      "sheet_name": "Produits"
    },
    "column_mappings": [
      { "source": "Référence", "target": "reference", "required": true },
      { "source": "Désignation", "target": "name", "required": true },
      { "source": "Prix HT", "target": "price", "required": false }
    ],
    "date_format": "%Y-%m-%d",
    "skip_rows": 0,
    "max_errors": 100
  }
}
```

**Réponse 201** : objet `SupplierResponse`

### `GET /suppliers/{supplier_id}`
Détail d'un fournisseur.

**Réponse 200** : objet `SupplierResponse`

### `PUT /suppliers/{supplier_id}`
Met à jour un fournisseur (champs partiels acceptés).

### `DELETE /suppliers/{supplier_id}`
Supprime un fournisseur (soft delete si des documents sont associés).

**Réponse 204**

### `GET /suppliers/{supplier_id}/documents`
Liste les documents d'un fournisseur.

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "filename": "catalogue.xlsx",
    "file_type": "xlsx",
    "file_size": 204800,
    "status": "uploaded",
    "created_at": "2025-01-15T10:30:00"
  }
]
```

### `POST /suppliers/test-config`
Teste une configuration fournisseur sur un fichier exemple.

**Body JSON**
```json
{
  "config": { ... },
  "sample_file_path": "/path/to/sample.xlsx"
}
```

**Réponse 200**
```json
{
  "success": true,
  "errors": [],
  "warnings": ["Colonne 'Prix TTC' non mappée"],
  "sample_data": [ { "reference": "REF001", "name": "Produit A" } ],
  "mapped_columns": ["reference", "name"]
}
```

---

## Produits — `/products`

### `GET /products/`
Liste les produits avec filtres.

**Query params**
| Param | Type | Description |
|---|---|---|
| `status_filter` | `string` | Filtre par statut (`extracted`, `classified`, `enriched`, …) |
| `supplier_id` | `string (UUID)` | Filtre par fournisseur |
| `search` | `string` | Recherche textuelle (nom, référence) |
| `skip` | `int` | Offset |
| `limit` | `int` | Taille de page |

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "supplier_id": "uuid",
    "supplier_name": "Fournisseur ABC",
    "name": "Produit A",
    "description": "...",
    "price": 29.99,
    "category": "Électronique",
    "reference": "REF001",
    "brand": "Marque X",
    "status": "extracted",
    "raw_data": { ... },
    "processed_data": { ... },
    "created_at": "2025-01-15T10:30:00",
    "document_filename": "catalogue.xlsx"
  }
]
```

### `GET /products/stats`
Statistiques globales des produits.

**Réponse 200**
```json
{
  "total": 1250,
  "by_status": { "extracted": 800, "classified": 300, "enriched": 150 },
  "by_supplier": { "uuid": 400, ... }
}
```

### `GET /products/documents`
Liste tous les documents ayant des produits associés.

### `GET /products/{product_id}`
Détail d'un produit.

### `PUT /products/{product_id}`
Met à jour un produit.

**Body JSON**
```json
{
  "name": "Nouveau nom",
  "description": "...",
  "price": 35.00,
  "category": "...",
  "reference": "...",
  "brand": "...",
  "status": "..."
}
```

### `DELETE /products/{product_id}`
Supprime un produit.

**Réponse 204**

---

## Extraction — `/products/analyze` & `/products/extract`

### `POST /products/analyze`
Analyse les feuilles d'un document avant extraction. Retourne une suggestion de feuille maître et un aperçu des colonnes.

**Body JSON**
```json
{
  "document_id": "uuid",
  "provider": "mistral",
  "model_name": null
}
```

**Réponse 200**
```json
{
  "sheets": {
    "Produits": {
      "columns": ["Référence", "Désignation", "Prix HT"],
      "samples": [ ["REF001", "Produit A", "29.99"] ],
      "total_rows": 450
    }
  },
  "suggested_master": "Produits",
  "analysis": { ... }
}
```

### `POST /products/extract`
Lance un job d'extraction asynchrone.

**Body JSON**
```json
{
  "document_id": "uuid",
  "format_name": "default",
  "analysis": { ... },
  "field_mapping_override": {
    "Référence": "reference",
    "Désignation": "name"
  },
  "max_products": 100,
  "source_mode": "document",
  "presented_mode": "docling_ocr",
  "provider": "mistral",
  "model_name": null
}
```

| Paramètre | Valeurs | Description |
|---|---|---|
| `source_mode` | `document`, `presented_catalog` | Mode de source |
| `presented_mode` | `docling_ocr`, `vision_model` | Mode de présentation (si `presented_catalog`) |

**Réponse 200**
```json
{ "job_id": "uuid", "status": "started" }
```

### `GET /products/extract/{job_id}/progress`
**SSE** — Flux de progression d'un job d'extraction.

**Événements (text/event-stream)**
```
data: {"progress": 25, "message": "Analyse feuille 1/3...", "done": false, "status": "running"}
data: {"progress": 100, "done": true, "status": "completed", "products_count": 142}
data: {"done": true, "status": "error", "error": "Message d'erreur"}
```

### `POST /products/extract/website`
Lance une extraction depuis un site web.

**Body JSON**
```json
{
  "supplier_id": "uuid",
  "format_name": "default",
  "website": {
    "start_url": "https://example.com/catalogue",
    "crawl_mode": "manual",
    "urls": ["https://example.com/produit-1", "https://example.com/produit-2"],
    "max_pages": 30,
    "max_depth": 2
  },
  "max_products": 50,
  "provider": "mistral"
}
```

| `crawl_mode` | Description |
|---|---|
| `manual` | URLs fournies explicitement |
| `semi_auto` | Crawl depuis `start_url` avec suggestions |
| `auto` | Crawl automatique jusqu'à `max_pages` |

---

## Classification — `/products/{id}/classify`

### `POST /products/{product_id}/classify`
Classifie un produit dans une arborescence de catégories via LLM.

**Body JSON**
```json
{
  "provider": "mistral",
  "model_name": null
}
```

**Réponse 200**
```json
{
  "product_id": "uuid",
  "category": "Électronique > Audio > Casques",
  "confidence": 0.87,
  "alternatives": [ ... ]
}
```

---

## Régénération — `/products/{id}/regenerate`

### `POST /products/{product_id}/regenerate`
Régénère la fiche complète d'un produit.

**Body JSON**
```json
{
  "format_name": "default",
  "provider": "mistral",
  "model_name": null
}
```

### `POST /products/{product_id}/regenerate-field`
Régénère un champ spécifique d'un produit.

**Body JSON**
```json
{
  "field_name": "description",
  "context": "Contexte supplémentaire optionnel",
  "provider": "mistral",
  "model_name": null
}
```

---

## Formats — `/formats`

### `GET /formats/`
Liste tous les formats de sortie.

**Réponse 200**
```json
{
  "formats": [
    {
      "id": "uuid",
      "name": "Format e-commerce",
      "description": "...",
      "yaml_content": { ... },
      "created_at": "2025-01-15T10:30:00"
    }
  ],
  "total": 5
}
```

### `POST /formats/`
Crée un format via JSON.

**Body JSON**
```json
{
  "name": "Mon format",
  "description": "...",
  "yaml_content": {
    "fields": [
      { "name": "titre_seo", "type": "text", "prompt": "Génère un titre SEO..." },
      { "name": "bullet_points", "type": "list", "prompt": "Liste 5 avantages..." }
    ]
  }
}
```

### `POST /formats/upload`
Upload un fichier YAML pour créer un format.

**Body** : `multipart/form-data`
| Champ | Type | Description |
|---|---|---|
| `file` | `File` | Fichier `.yaml` |

### `GET /formats/{format_id}`
Détail d'un format.

### `PUT /formats/{format_id}`
Met à jour un format.

### `DELETE /formats/{format_id}`
Supprime un format.

**Réponse 204**

---

## Scraping — `/scraping`

### `POST /scraping/{product_id}/scrape`
Lance un scraping web pour un produit.

**Body JSON**
```json
{
  "urls": ["https://example.com/produit"],
  "search_query": "Produit A REF001",
  "sites": ["amazon.fr", "cdiscount.com"],
  "max_results": 5
}
```

> `urls` et `search_query` sont mutuellement exclusifs. Si `search_query` est fourni, une recherche DuckDuckGo est effectuée.

**Réponse 200** : liste de `ScrapeResultOut`
```json
[
  {
    "id": "uuid",
    "product_id": "uuid",
    "source_url": "https://...",
    "source_site": "amazon.fr",
    "title": "Produit A",
    "description": "...",
    "characteristics": { "poids": "500g", "couleur": "noir" },
    "images": ["https://..."],
    "scraped_at": "2025-01-15T10:30:00"
  }
]
```

### `GET /scraping/{product_id}/scrape-results`
Liste les résultats de scraping d'un produit.

### `GET /scraping/{product_id}/scrape-results/{result_id}`
Détail d'un résultat de scraping.

### `DELETE /scraping/{product_id}/scrape-results/{result_id}`
Supprime un résultat de scraping.

**Réponse 204**

### `GET /scraping/{product_id}/gallery`
Galerie d'images agrégées depuis tous les résultats de scraping.

**Réponse 200**
```json
[
  {
    "url": "https://...",
    "source_url": "https://...",
    "source_site": "amazon.fr",
    "scrape_result_id": "uuid"
  }
]
```

### `POST /scraping/{product_id}/gallery/download`
Télécharge une sélection d'images en ZIP.

**Body JSON**
```json
{ "image_urls": ["https://...", "https://..."] }
```

**Réponse 200** : `application/zip`

### `GET /scraping/proxy-image?url={url}`
Proxy une image externe pour contourner les restrictions CORS.

**Réponse 200** : image binaire avec le bon `Content-Type`

---

## Enrichissement — `/enrichment`

### `POST /enrichment/upload`
Upload un document d'enrichissement.

**Body** : `multipart/form-data`
| Champ | Type | Description |
|---|---|---|
| `file` | `File` | Document (pdf, docx, xlsx, …) |
| `enrichment_type` | `string` | `notice`, `catalogue`, `fiche_technique`, `other` |

**Réponse 200** : objet document uploadé

### `POST /enrichment/process`
Lance un job d'enrichissement asynchrone.

**Body JSON**
```json
{
  "document_id": "uuid",
  "product_ids": ["uuid1", "uuid2"],
  "enrichment_type": "fiche_technique",
  "provider": "mistral",
  "model_name": null
}
```

**Réponse 200**
```json
{ "job_id": "uuid", "status": "started" }
```

### `GET /enrichment/{job_id}/progress`
**SSE** — Flux de progression d'un job d'enrichissement.

Même format que l'extraction.

### `GET /enrichment/documents`
Liste les documents d'enrichissement.

**Query params**
| Param | Type | Description |
|---|---|---|
| `product_id` | `string (UUID)` | Filtrer par produit |

### `GET /enrichment/documents/{id}`
Détail d'un document d'enrichissement.

### `DELETE /enrichment/documents/{id}`
Supprime un document d'enrichissement.

**Réponse 204**

### `GET /enrichment/product/{product_id}`
Liste tous les enrichissements d'un produit.

**Réponse 200** : liste de `EnrichmentDocumentOut`
```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "product_id": "uuid",
    "product_name": "Produit A",
    "document_filename": "notice.pdf",
    "enrichment_type": "notice",
    "extracted_data": { ... },
    "status": "completed",
    "match_confidence": 0.92,
    "match_method": "reference",
    "error_message": null,
    "created_at": "2025-01-15T10:30:00"
  }
]
```

---

## Configuration — `/config`

### `GET /config/`
Retourne la configuration runtime du backend (provider LLM actif, modèle, etc.).

**Réponse 200**
```json
{
  "llm_provider": "mistral",
  "llm_model": "mistral-large-latest",
  "debug": true,
  "version": "0.1.0"
}
```

---

## Codes d'erreur

| Code | Signification |
|---|---|
| `400` | Requête invalide (validation Pydantic, YAML invalide, etc.) |
| `404` | Ressource introuvable |
| `422` | Erreur de validation des paramètres |
| `500` | Erreur interne du serveur |
| `502` | Erreur de proxy (image non accessible) |

**Format d'erreur standard**
```json
{ "detail": "Message d'erreur lisible" }
```

**Format d'erreur de validation Pydantic**
```json
{
  "detail": [
    { "loc": ["body", "name"], "msg": "field required", "type": "value_error.missing" }
  ]
}
```
