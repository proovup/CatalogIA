# Guide Utilisateur — CatalogIA

CatalogIA est une plateforme de génération automatique de fiches produits à partir de catalogues fournisseurs (Excel, PDF, Word, CSV) ou de sites web, enrichies par IA.

---

## Navigation

La barre latérale gauche donne accès aux 6 sections principales :

| Section | Description |
|---|---|
| **Dashboard** | Vue d'ensemble : statistiques, activité récente |
| **Fournisseurs** | Gérer les fournisseurs et lancer les extractions |
| **Produits** | Consulter, filtrer et éditer les fiches produits |
| **Enrichissement** | Enrichir des produits avec des documents complémentaires |
| **Formats Custom** | Définir des formats de sortie personnalisés |
| **Configuration** | Voir la configuration du backend (provider LLM, modèle) |

La sidebar peut être réduite (icônes seules) en cliquant sur **Réduire** en bas.

---

## Workflow principal : de l'import à la fiche produit

### Étape 1 — Créer un fournisseur

1. Aller dans **Fournisseurs** → cliquer **Nouveau fournisseur**
2. Renseigner le nom et une description optionnelle
3. Valider → le fournisseur apparaît dans la liste

> La configuration de mapping (colonnes source → champs cibles) peut être définie maintenant ou ajustée lors de l'extraction.

---

### Étape 2 — Uploader un document

Depuis la page **Détail fournisseur** :

1. Glisser-déposer le fichier dans la zone d'upload (ou cliquer pour parcourir)
2. Formats acceptés : `.xlsx`, `.xls`, `.pdf`, `.docx`, `.csv`, `.txt`
3. Le document apparaît dans la liste avec le statut **uploaded**

> Pour les fichiers Excel, chaque feuille est traitée séparément. Pour les autres formats, Docling détecte automatiquement les tableaux.

---

### Étape 3 — Analyser le document

Avant l'extraction, une analyse préalable identifie la structure du document :

1. Sélectionner le document dans la liste
2. Cliquer **Analyser**
3. L'IA analyse les feuilles/tableaux et suggère :
   - La **feuille maître** (source principale des produits)
   - Les colonnes détectées avec des exemples de valeurs
   - Un mapping de champs suggéré

> Cette étape est optionnelle mais recommandée pour les documents complexes (plusieurs feuilles, colonnes non standard).

---

### Étape 4 — Configurer l'extraction

Avant de lancer l'extraction, vous pouvez ajuster :

- **Format de sortie** : choisir parmi les formats disponibles (ou `default`)
- **Mapping de champs** : corriger ou surcharger le mapping suggéré
  - Exemple : mapper la colonne `"Désignation article"` vers le champ `name`
- **Limite de produits** : restreindre à N produits (utile pour tester)
- **Provider LLM** : surcharger le provider configuré (Mistral, OpenAI, Anthropic…)

---

### Étape 5 — Lancer l'extraction

1. Cliquer **Extraire les produits**
2. Une barre de progression s'affiche en temps réel (flux SSE)
3. Les messages indiquent la feuille en cours de traitement
4. À la fin : nombre de produits créés affiché

> En cas d'erreur (document sans tableau, clé API invalide…), un message explicite est affiché.

---

### Étape 6 — Consulter les produits

Aller dans **Produits** pour voir tous les produits extraits.

**Filtres disponibles :**
- Statut (`extracted`, `classified`, `enriched`, …)
- Fournisseur
- Catégorie
- Marque
- Plage de dates
- Recherche textuelle (nom, référence)

**Tri :** par date, nom, statut.

**Pagination :** navigation par pages.

---

## Fiche produit détaillée

Cliquer sur un produit pour ouvrir sa fiche complète.

### Données disponibles

- **Informations de base** : nom, référence, marque, catégorie, prix
- **Description** : texte généré par l'IA
- **Champs personnalisés** : définis par le format de sortie (ex. titre SEO, bullet points, fiche technique)
- **Données brutes** : données extraites avant traitement IA
- **Galerie d'images** : images récupérées par scraping web

### Actions disponibles

| Action | Description |
|---|---|
| **Éditer** | Modifier manuellement n'importe quel champ |
| **Régénérer un champ** | Relancer l'IA sur un champ spécifique |
| **Régénérer la fiche** | Relancer l'IA sur toute la fiche |
| **Classifier** | Classer le produit dans une catégorie via IA |
| **Scraper** | Rechercher des données et images sur le web |

---

## Enrichissement de produits

L'enrichissement permet de compléter des fiches existantes avec des documents complémentaires (notices, fiches techniques, catalogues secondaires).

### Workflow

1. Aller dans **Enrichissement**
2. Uploader le document complémentaire
3. Sélectionner le type : `notice`, `fiche_technique`, `catalogue`, `autre`
4. Sélectionner les produits à enrichir (recherche par nom ou référence)
5. Cliquer **Enrichir**
6. Suivre la progression en temps réel

### Résultats

Chaque enrichissement affiche :
- **Score de confiance** : probabilité que le document corresponde au produit
- **Méthode de matching** : comment le produit a été identifié (`reference`, `name`, …)
- **Données extraites** : champs enrichis depuis le document

---

## Scraping d'images et de données

Depuis la fiche produit, l'onglet **Galerie** permet de :

1. **Lancer un scraping** :
   - Par URL directe (coller une ou plusieurs URLs)
   - Par recherche automatique (le système cherche le produit sur le web)
   - En ciblant des sites spécifiques (ex. `amazon.fr`, `cdiscount.com`)

2. **Consulter les résultats** :
   - Images trouvées avec leur source
   - Caractéristiques techniques récupérées
   - Description du site source

3. **Télécharger les images** :
   - Sélectionner les images souhaitées
   - Cliquer **Télécharger** → fichier ZIP

---

## Formats de sortie personnalisés

Les formats définissent les champs supplémentaires générés par l'IA pour chaque produit.

### Créer un format

1. Aller dans **Formats Custom**
2. Cliquer **Nouveau format**
3. Définir le format en YAML :

```yaml
name: Format e-commerce
description: Format optimisé pour la vente en ligne
fields:
  - name: titre_seo
    type: text
    prompt: "Génère un titre SEO accrocheur de 60 caractères max"
  - name: bullet_points
    type: list
    prompt: "Liste 5 avantages produits en bullet points"
  - name: fiche_technique
    type: object
    prompt: "Extrait les caractéristiques techniques clés"
```

4. Valider → le format est disponible lors des extractions

### Uploader un format YAML

Cliquer **Importer YAML** et sélectionner un fichier `.yaml` existant.

---

## Dashboard

Le tableau de bord affiche :

- **Nombre total de produits** extraits
- **Répartition par statut** : extracted, classified, enriched
- **Fournisseurs actifs** et leur volume de produits
- **Activité récente** : dernières extractions et enrichissements

---

## Configuration

La page **Configuration** affiche la configuration active du backend :

- Provider LLM actif (Mistral, OpenAI, Anthropic, AWS Bedrock)
- Modèle utilisé
- Version de l'application

> Pour modifier la configuration, éditer le fichier `.env` et redémarrer le serveur.

---

## Conseils pratiques

### Qualité de l'extraction

- **Nommez clairement vos colonnes** dans les fichiers source (ex. `Référence`, `Désignation`, `Prix HT`) pour faciliter le mapping automatique
- **Utilisez l'analyse préalable** pour vérifier que la feuille maître est bien détectée
- **Testez avec `max_products: 10`** avant de lancer une extraction complète sur un gros catalogue

### Formats Excel multi-feuilles

- La feuille maître crée les produits
- Les autres feuilles enrichissent automatiquement les produits créés (par référence croisée)
- Vérifiez que la feuille maître contient bien une colonne de référence unique

### Documents PDF/Word

- Docling détecte les tableaux automatiquement
- Si le document ne contient pas de tableau structuré, l'extraction retournera une erreur explicite
- Pour les catalogues en format texte libre (sans tableau), préférez le mode `presented_catalog`

### Performance

- Les extractions volumineuses (> 500 produits) peuvent prendre plusieurs minutes
- La barre de progression SSE reste active même si vous naviguez dans l'application
- En cas de déconnexion, le job continue côté serveur
