# Documentation CatalogIA

Bienvenue dans la documentation de **CatalogIA** — plateforme de génération automatique de fiches produits par IA.

## Index

| Document | Contenu |
|---|---|
| [SETUP.md](./SETUP.md) | Installation, configuration, déploiement |
| [TECHNICAL.md](./TECHNICAL.md) | Architecture backend `src/ecoia` |
| [FRONTEND.md](./FRONTEND.md) | Architecture frontend `front_inferno` |
| [API.md](./API.md) | Référence complète des endpoints REST |
| [USER_GUIDE.md](./USER_GUIDE.md) | Guide utilisateur de l'interface CatalogIA |

---

## Architecture en un coup d'œil

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

## Flux principal

```
Fournisseur → Upload document → Analyse feuilles → Extraction LLM → Fiches produits
                                                                          │
                                                          Enrichissement ─┤
                                                          Classification  ─┤
                                                          Scraping images ─┘
```

## Licence

AGPLv3 — voir [LICENSE](../LICENSE)
