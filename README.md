# Research Agent

Agent de recherche autonome pour installateur solaire C&I (Commercial & Industriel). Chaque semaine, il parcourt la presse de construction (industriel, logistique, retail) département par département, extrait des fiches projet structurées via LLM, identifie l'entreprise porteuse (SIREN) et consolide les doublons — le tout suivi en temps réel depuis une interface web.

## Fonctionnement

Chaque run exécute le pipeline suivant, pour chaque combinaison secteur × département :

1. **Recherche** — requêtes ciblées via [Exa.ai](https://exa.ai) (type de recherche, catégorie et fenêtre de publication configurables), avec filtrage des domaines bloqués et des URLs déjà traitées.
2. **Extraction LLM** — chaque article est analysé (via Vercel AI Gateway) pour en extraire une fiche projet : nom, entreprise, surface, localisation, date de livraison, pitch commercial… Les articles non pertinents sont écartés.
3. **Résolution SIREN** — l'entreprise est recherchée dans l'API Recherche d'Entreprises (data.gouv), puis un LLM tranche entre les candidats pour rattacher le bon SIREN et la raison sociale légale.
4. **Déduplication** — rapprochement fuzzy (nom, adresse, SIREN) puis arbitrage LLM pour fusionner les projets décrivant le même chantier ; les verdicts sont mis en cache.
5. **Restitution** — les événements du run sont diffusés en SSE vers le frontend : orbe animé, statut en direct, blocs d'articles par recherche avec progression de l'analyse, timeline détaillée des étapes.

Les runs se déclenchent manuellement depuis l'interface ou automatiquement via un cron hebdomadaire (jour et heure configurables). Un module GIS optionnel (base BDNB/OSM) permet d'estimer les emprises de bâtiments.

## Stack

| Couche | Technologies |
|--------|--------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL (ou SQLite en local), APScheduler, SSE |
| Agent | Exa.ai (recherche), Vercel AI Gateway (LLM, `deepseek/deepseek-v4-flash` par défaut), API Recherche d'Entreprises, RapidFuzz |
| Frontend | Next.js 15, React 19, Tailwind CSS 4, shadcn/ui, motion |

## Structure du projet

```
backend/
  app/agent/      # Pipeline : Exa, extraction LLM, résolution SIREN, dédup
  app/api/        # Routes FastAPI : runs, projects, config, GIS, search anchors
  app/models/     # Modèles ORM : Run, RunStep, Project, Source, merges…
  app/gis/        # Estimation d'emprises bâtiments (BDNB/OSM)
  tests/          # Suite pytest
frontend/
  src/components/ # UI : liste projets, timeline de run, batches d'articles…
  src/hooks/      # use-run-stream (SSE), use-agent-settings
docs/plans/       # Documents de design et plans d'implémentation
```

## Démarrage local

### Prérequis

- Python ≥ 3.12, Node.js ≥ 20 (ou Docker)
- Une clé [Exa](https://exa.ai) et une clé [Vercel AI Gateway](https://vercel.com/docs/ai-gateway)

### Configuration

```bash
cp .env.example .env
# Renseigner EXA_API_KEY et AI_GATEWAY_API_KEY
# AI_MODEL est optionnel (défaut : deepseek/deepseek-v4-flash)
```

### Option A — Docker (recommandé)

```bash
docker compose up --build
```

Lance PostgreSQL, le backend (port 8000) et le frontend (port 3000).

### Option B — Sans Docker

```bash
# Terminal 1 — backend (SQLite, aucun PostgreSQL requis)
cd backend && pip install -e ".[dev]"
DATABASE_URL="sqlite:///./research.db" uvicorn app.main:app --reload --port 8001

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

> **Note :** si le backend tourne sur le port `8001`, mettez `NEXT_PUBLIC_API_URL=http://localhost:8001` dans `.env`.

- Frontend : http://localhost:3000
- API : http://localhost:8000 (Docker) ou http://localhost:8001 — healthcheck sur `/health`

### Variables d'environnement

| Variable | Description |
|----------|-------------|
| `EXA_API_KEY` | Clé API Exa.ai (recherche d'articles) — **requis** |
| `AI_GATEWAY_API_KEY` | Clé Vercel AI Gateway (extraction LLM) — **requis** |
| `AI_MODEL` | Modèle LLM (défaut : `deepseek/deepseek-v4-flash`) |
| `DATABASE_URL` | PostgreSQL ou SQLite (défaut Docker : PostgreSQL du compose) |
| `NEXT_PUBLIC_API_URL` | URL de l'API vue par le frontend |
| `GIS_DATABASE_URL` | Base BDNB/OSM locale pour le module GIS — optionnel |

## Tests

```bash
# Backend (pytest)
cd backend && pytest

# Frontend (vitest + vérification des types)
cd frontend && npm test && npx tsc --noEmit
```

## Documentation

Les documents de design et plans d'implémentation sont dans [`docs/plans/`](docs/plans/), notamment :

- [Design initial de l'agent](docs/plans/2026-06-16-research-agent-design.md)
- [Déduplication et fusion de projets](docs/plans/2026-06-17-project-dedup-merge-design.md)
- [UI des batches d'articles en run](docs/plans/2026-07-01-run-article-batches-design.md)
- [Dédup SIREN et cache des verdicts LLM](docs/plans/2026-07-03-siren-dedup-and-llm-verdict-cache.md)
