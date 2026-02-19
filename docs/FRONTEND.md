# Architecture Frontend — `front_inferno`

## Vue d'ensemble

Le frontend est une **Single Page Application (SPA)** construite avec **Inferno.js** (v9), un framework React-compatible ultra-performant. Il communique exclusivement avec le backend `ecoia` via l'API REST `/api/v1`.

Le build est géré par **Vite 6** avec le plugin Babel `babel-plugin-inferno`. Le style utilise **TailwindCSS v4**.

---

## Stack technique

| Technologie | Version | Rôle |
|---|---|---|
| Inferno.js | ^9.0.11 | Framework UI (React-compatible) |
| inferno-router | ^9.0.11 | Routing SPA (BrowserRouter) |
| TailwindCSS | ^4.0.0 | Styles utilitaires |
| Vite | ^6.0.0 | Bundler / dev server |
| babel-plugin-inferno | ^6.8.5 | Transpilation JSX → Inferno |

---

## Structure des répertoires

```
front_inferno/
├── index.html               # Point d'entrée HTML
├── vite.config.js           # Config Vite + proxy API
├── package.json
└── src/
    ├── index.jsx            # App root, Sidebar, routing
    ├── index.css            # Variables CSS globales, animations
    ├── api.js               # Couche d'accès API (toutes les fonctions fetch)
    ├── constants.js         # Constantes partagées (statuts, types, etc.)
    ├── components/          # Composants réutilisables
    │   ├── Badge.jsx
    │   ├── Card.jsx
    │   ├── DropZone.jsx
    │   ├── DynamicField.jsx
    │   ├── EmptyState.jsx
    │   ├── Field.jsx
    │   ├── Icons.jsx
    │   ├── Modal.jsx
    │   ├── PageHeader.jsx
    │   ├── Skeleton.jsx
    │   └── Toast.jsx
    └── pages/               # Pages de l'application
        ├── Dashboard.jsx
        ├── Suppliers.jsx
        ├── SupplierDetail.jsx
        ├── Products.jsx
        ├── ProductDetail.jsx
        ├── Enrichment.jsx
        ├── Formats.jsx
        ├── Settings.jsx
        └── Upload.jsx
```

---

## Routing (`index.jsx`)

L'application utilise `BrowserRouter` d'`inferno-router`. La `Sidebar` est fixe et le contenu principal est rendu dans `<main>`.

| Route | Composant | Description |
|---|---|---|
| `/` | `Dashboard` | Tableau de bord global |
| `/suppliers` | `Suppliers` | Liste des fournisseurs |
| `/suppliers/:id` | `SupplierDetail` | Détail fournisseur + upload + extraction |
| `/products` | `Products` | Liste des produits avec filtres |
| `/products/:id` | `ProductDetail` | Fiche produit complète |
| `/enrichment` | `Enrichment` | Enrichissement de produits |
| `/formats` | `Formats` | Gestion des formats de sortie |
| `/settings` | `Settings` | Configuration de l'application |

### Sidebar

La `Sidebar` est un composant de classe Inferno avec état local (`collapsed: bool`). Elle se réduit à `72px` (icônes seules) ou s'affiche en `256px` (icônes + labels). Les tooltips apparaissent au survol en mode réduit.

---

## Couche API (`api.js`)

Toutes les communications avec le backend passent par l'objet `api` exporté depuis `api.js`. La base URL est `/api/v1` (proxifiée par Vite en dev).

### Gestion des erreurs

La fonction `request()` parse automatiquement les erreurs FastAPI (format `{ detail: ... }`) et les normalise en message lisible, y compris les erreurs de validation Pydantic (tableau de `{ loc, msg }`).

### Méthodes disponibles

#### Documents
| Méthode | Endpoint | Description |
|---|---|---|
| `listDocuments()` | `GET /products/documents` | Liste tous les documents |
| `uploadDocument(file, supplierId)` | `POST /documents/upload` | Upload un fichier |

#### Produits
| Méthode | Endpoint | Description |
|---|---|---|
| `listProducts(params)` | `GET /products/` | Liste avec filtres (status, supplier_id, search, skip, limit) |
| `getProductStats()` | `GET /products/stats` | Statistiques globales |
| `getProduct(id)` | `GET /products/{id}` | Détail d'un produit |
| `updateProduct(id, data)` | `PUT /products/{id}` | Mise à jour |
| `deleteProduct(id)` | `DELETE /products/{id}` | Suppression |

#### Extraction
| Méthode | Endpoint | Description |
|---|---|---|
| `analyzeDocument(documentId, provider)` | `POST /products/analyze` | Analyse des feuilles avant extraction |
| `extractProducts(documentId, formatName, analysis, options)` | `POST /products/extract` | Lance un job d'extraction |
| `streamExtractionProgress(jobId, onEvent, onDone, onError)` | `GET /products/extract/{jobId}/progress` | SSE de progression |
| `extractWebsiteProducts(payload)` | `POST /products/extract/website` | Extraction depuis un site web |

#### Classification & Régénération
| Méthode | Endpoint | Description |
|---|---|---|
| `classifyProduct(productId, provider, modelName)` | `POST /products/{id}/classify` | Classification LLM |
| `regenerateProduct(productId, formatName, provider, modelName)` | `POST /products/{id}/regenerate` | Régénération complète |
| `regenerateField(productId, data)` | `POST /products/{id}/regenerate-field` | Régénération d'un champ |

#### Fournisseurs
| Méthode | Endpoint | Description |
|---|---|---|
| `listSuppliers(params)` | `GET /suppliers/` | Liste avec pagination |
| `createSupplier(data)` | `POST /suppliers/` | Création |
| `getSupplier(id)` | `GET /suppliers/{id}` | Détail |
| `updateSupplier(id, data)` | `PUT /suppliers/{id}` | Mise à jour |
| `deleteSupplier(id)` | `DELETE /suppliers/{id}` | Suppression |
| `getSupplierDocuments(id)` | `GET /suppliers/{id}/documents` | Documents du fournisseur |

#### Scraping
| Méthode | Endpoint | Description |
|---|---|---|
| `scrapeProduct(productId, data)` | `POST /scraping/{id}/scrape` | Lance un scraping |
| `getScrapeResults(productId)` | `GET /scraping/{id}/scrape-results` | Résultats de scraping |
| `getProductGallery(productId)` | `GET /scraping/{id}/gallery` | Galerie d'images |
| `downloadGalleryImages(productId, imageUrls)` | `POST /scraping/{id}/gallery/download` | Téléchargement ZIP |
| `proxyImageUrl(url)` | `GET /scraping/proxy-image?url=...` | URL proxy pour images |

#### Enrichissement
| Méthode | Endpoint | Description |
|---|---|---|
| `uploadEnrichmentDocument(file, enrichmentType)` | `POST /enrichment/upload` | Upload document d'enrichissement |
| `processEnrichment(documentId, productIds, enrichmentType, options)` | `POST /enrichment/process` | Lance un job d'enrichissement |
| `streamEnrichmentProgress(jobId, onEvent, onDone, onError)` | `GET /enrichment/{jobId}/progress` | SSE de progression |
| `listEnrichmentDocuments(productId)` | `GET /enrichment/documents` | Liste documents d'enrichissement |
| `getProductEnrichments(productId)` | `GET /enrichment/product/{id}` | Enrichissements d'un produit |

#### Configuration
| Méthode | Endpoint | Description |
|---|---|---|
| `getConfig()` | `GET /config/` | Configuration runtime du backend |

---

## Pages

### `Dashboard.jsx`

Tableau de bord avec :
- Statistiques globales (nombre de produits, fournisseurs, documents)
- Graphiques de répartition par statut
- Activité récente

### `Suppliers.jsx`

Liste paginée des fournisseurs avec :
- Recherche par nom
- Création rapide via modal
- Indicateur de statut actif/inactif

### `SupplierDetail.jsx`

Page centrale du workflow d'extraction. Contient :
- Informations du fournisseur (édition inline)
- Liste des documents uploadés
- **Zone d'upload** (drag & drop via `DropZone`)
- **Workflow d'extraction** :
  1. Sélection du document
  2. Analyse des feuilles (appel LLM)
  3. Configuration du mapping (`field_mapping_override`)
  4. Sélection du format de sortie
  5. Lancement de l'extraction avec barre de progression SSE
- Historique des extractions

### `Products.jsx`

Liste des produits avec :
- Filtres : statut, fournisseur, catégorie, marque, plage de dates, recherche textuelle
- Tri configurable
- Pagination
- Affichage de la date de création

### `ProductDetail.jsx`

Fiche produit complète avec :
- Données extraites (nom, description, référence, catégorie, marque)
- Champs personnalisés du format de sortie (`DynamicField`)
- Régénération par champ ou complète
- Classification LLM
- Galerie d'images (scraping)
- Historique des enrichissements
- Édition manuelle

### `Enrichment.jsx`

Workflow d'enrichissement :
1. Upload d'un document complémentaire (notice, fiche technique, catalogue)
2. Sélection des produits à enrichir
3. Choix du type d'enrichissement
4. Progression SSE
5. Résultats avec score de confiance du matching

### `Formats.jsx`

Gestion des formats de sortie YAML :
- Liste des formats en base
- Création via éditeur YAML inline
- Upload d'un fichier `.yaml`
- Édition et suppression

### `Settings.jsx`

Configuration de l'application :
- Affichage de la configuration runtime du backend (`GET /config/`)
- Informations sur le provider LLM actif et le modèle

---

## Composants réutilisables (`components/`)

| Composant | Description |
|---|---|
| `Badge` | Badge coloré (statut, type) |
| `Card` | Conteneur avec ombre et bordure |
| `DropZone` | Zone de drag & drop pour upload de fichiers |
| `DynamicField` | Champ de formulaire dynamique (texte, select, textarea, etc.) |
| `EmptyState` | État vide avec icône et message |
| `Field` | Champ de formulaire simple avec label |
| `Icons` | Bibliothèque d'icônes SVG inline (Lucide-style) |
| `Modal` | Modale avec overlay et gestion du focus |
| `PageHeader` | En-tête de page avec titre, sous-titre et actions |
| `Skeleton` | Placeholder de chargement animé |
| `Toast` | Notification temporaire (succès, erreur, info) |

---

## Proxy Vite (dev)

En développement, Vite proxifie les requêtes `/api/v1/*` vers `http://localhost:8000` pour éviter les problèmes CORS. La configuration est dans `vite.config.js`.

---

## Server-Sent Events (SSE)

Deux flux SSE sont utilisés pour les opérations longues :

### Extraction (`streamExtractionProgress`)
```js
const es = api.streamExtractionProgress(
  jobId,
  (data) => { /* mise à jour progression: data.progress, data.message */ },
  (data) => { /* extraction terminée: data.products_count */ },
  (error) => { /* erreur */ }
);
// Pour annuler: es.close()
```

### Enrichissement (`streamEnrichmentProgress`)
Même pattern que l'extraction.

**Format des événements SSE :**
```json
{
  "progress": 45,
  "message": "Traitement feuille 2/3...",
  "done": false,
  "status": "running"
}
```

Événement final :
```json
{
  "done": true,
  "status": "completed",
  "products_count": 142
}
```
