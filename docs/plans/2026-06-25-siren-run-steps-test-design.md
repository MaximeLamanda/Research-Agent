# SIREN Enrichment, Run Steps & Test Mode — Design

**Date:** 2026-06-25

## Objectif

Enrichir les projets C&I avec des données SIREN, tracer chaque étape du pipeline agent, et permettre un test rapide sur un seul lien.

## Décisions validées

### Source SIREN
- **API** : `recherche-entreprises.api.gouv.fr` (gratuite, sans clé)
- **Décision** : le LLM choisit le bon candidat parmi les résultats de recherche
- Pas de MCP — appel HTTP direct (cohérent avec Exa et AI Gateway)

### Journal d'étapes
- Table `run_steps` persistée en base
- Chaque événement SSE est aussi enregistré via `log_and_emit()`
- Affichage : timeline dans le drawer du run + messages temps réel (ColorOrb)
- Polling toutes les 3s pendant un run `in_progress`

### Mode test
- `POST /api/runs` avec `{ "mode": "test_single" }`
- 1er département × 1er secteur configurés
- Première URL Exa uniquement
- Pas de passe de déduplication

### Données projet enrichies
- `siren` (9 chiffres)
- `company_legal_name` (dénomination officielle)
- `naf_code` (code APE)

## Flux

```
Article → LLM extract → recherche-entreprises.api.gouv.fr
       → LLM choisit candidat → upsert projet + SIREN
       → log_and_emit à chaque étape
```

## UI

- Bouton **Test (1 lien)** à côté de **Run now**
- Timeline chronologique dans le drawer Runs
- SIREN affiché dans le détail projet
