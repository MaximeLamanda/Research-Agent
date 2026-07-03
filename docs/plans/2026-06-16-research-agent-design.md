# Research Agent — Design

**Date :** 2026-06-16  
**Statut :** Validé

## Objectif

Agent de recherche autonome pour un installateur solaire C&I. Chaque semaine, il parcourt des articles de construction (industriel, logistique, retail) par département configuré, extrait des fiches projet structurées et les agrège dans une liste croissante — sans intervention humaine après configuration initiale.

## Stack

| Couche | Technologie |
|--------|-------------|
| Frontend | Next.js, shadcn/ui, ColorOrb (animation gradient) |
| Backend | Python, FastAPI, APScheduler |
| Base de données | PostgreSQL (Docker) |
| Recherche | Exa.ai |
| Extraction | LLM via Vercel AI Gateway (modèle configurable) |
| Hébergement | Local (docker-compose) |

## Architecture

Monorepo local : `docker-compose` lance PostgreSQL, FastAPI (port 8000) et Next.js (port 3000).

```
Next.js ──REST + SSE──▶ FastAPI ──▶ PostgreSQL
                            │
                     Exa.ai + Vercel AI Gateway
```

- **Déclenchement :** cron hebdomadaire (lundi 6h par défaut) + bouton manuel en dev
- **ColorOrb :** visible pendant un `run` en cours, alimenté par SSE

## Modèle de données

### `config`
Configuration globale (une ligne) : `departments[]`, `cron_day`, `cron_hour`, `sectors[]`.

### `projects`
Fiche projet consolidée :
- `name`, `company`, `surface_m2`, `delivery_date`
- `city`, `address`, `department`
- `status` : `conception` | `travaux` | `livraison`
- `sector` : `industriel` | `logistique` | `retail`
- `people` : JSONB `[{name, role, company}]` — responsables projet cités dans les articles
- `match_key` : clé de déduplication unique

### `sources`
Historique des articles par projet : `url` (unique), `title`, `published_at`, `raw_excerpt`, `extracted_data`, `run_id`.

### `runs`
Journal d'exécution : `status`, stats (`articles_found`, `projects_new`, `projects_updated`), `error_message`.

### Agrégation (option C)

- `match_key = slugify(nom) + "|" + ville + "|" + entreprise`
- Projet existant → mise à jour champs vides, fusion `people` (dédup par nom)
- Nouveau → création fiche
- URL déjà connue → ignorée
- Chaque article importé → entrée `sources` liée au projet

## Pipeline agent

1. Créer `run` (`in_progress`)
2. Pour chaque département × secteur (industriel, logistique, retail) :
   - Requête Exa en langage naturel
   - Filtrer URLs déjà en base
   - Fetch contenu complet (Exa)
   - Extraction structurée LLM (Pydantic)
   - Déduplication + upsert projet + source
3. Finaliser `run` (`completed`) avec stats

### Requêtes Exa (exemples)

```
"article chantier construction entrepôt logistique département {XX} France 2025 2026"
"article nouveau bâtiment industriel département {XX} France projet construction"
"article construction centre commercial retail département {XX} France"
```

### SSE (`GET /runs/{id}/stream`)

Événements : `run_started`, `searching`, `extracting`, `project_found`, `run_completed`, `run_failed`.

### Gestion d'erreurs

- Erreur Exa par département → skip, continue
- Article vide → skip
- JSON LLM invalide → 1 retry puis skip
- Erreur DB → `run_failed`
- Run concurrent → refus 409

## Interface (section non détaillée)

- Liste des projets agrégés (fiche + sources en dessous)
- Accordéon paramètres : sélection des départements, bouton « Lancer maintenant »
- ColorOrb animé pendant les runs actifs
