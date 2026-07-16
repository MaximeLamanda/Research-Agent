# UK & Ireland — Extension pays de recherche

**Date :** 2026-07-15  
**Statut :** Validé (brainstorming)

## Contexte

Le système supporte FR et DE via un modèle extensible : régions dans `departments.py`, requêtes Exa par pays, prompts LLM, ancres villes (`search_anchors/`), presse locale (`local_press_domains/`), résolution département, dédup groupée par pays.

## Objectif

Ajouter **United Kingdom (GB)** et **Ireland (IE)** avec **parité FR/DE** : même pipeline, même UI, mêmes données (ancres + presse locale complètes). Corriger la dédup pour filtrer explicitement par `project.country`.

## Modèle géographique

| Code ISO | Label UI | Granularité | Nb zones |
|----------|----------|-------------|----------|
| `GB` | United Kingdom | Régions NUTS1 | 12 |
| `IE` | Ireland | Provinces | 4 |

### Régions UK (codes NUTS1 — 3 lettres, évite collisions DE)

| Code | Région |
|------|--------|
| `UKC` | North East |
| `UKD` | North West |
| `UKE` | Yorkshire and The Humber |
| `UKF` | East Midlands |
| `UKG` | West Midlands |
| `UKH` | East of England |
| `UKI` | London |
| `UKJ` | South East |
| `UKK` | South West |
| `UKL` | Wales |
| `UKM` | Scotland |
| `UKN` | Northern Ireland |

Format : `"UKI - London"`, `"UKD - North West"`, etc.

### Provinces Irlande (codes 2 lettres — distincts des Länder DE)

| Code | Province |
|------|----------|
| `LE` | Leinster |
| `MU` | Munster |
| `CN` | Connacht |
| `UL` | Ulster |

Format : `"LE - Leinster"`, etc.

### Détection pays depuis le département

```
code numérique (01-95, 2A/2B)     → FR
code dans DE_LANDER               → DE
code préfixe UK + 3e caractère    → GB
code dans IE_PROVINCES            → IE
sinon                             → null (plus de fallback aveugle FR/DE)
```

Regex format étendue : `^([A-Z]{2,3}|\d{2}[AB]?)\s*[-—]\s*(.+)$`

## Pipeline de recherche

- **Requêtes Exa** (`queries.py`) : `SECTOR_QUERIES_GB` et `SECTOR_QUERIES_IE` en anglais, même structure que FR/DE.
- **Prompts LLM** (`llm_extractor.py`) : règles department GB (NUTS1) et IE (provinces), interdiction d'inventer la région du run.
- **Exa user_location** (`locale_filter.py`) : `GB` et `IE`.
- **Filtre locale** : heuristique étrangère étendue pour GB/IE (pas seulement FR).
- **Ancres villes** : `search_anchors/gb.json` (12 régions × 5 villes), `search_anchors/ie.json` (4 provinces × 5 villes).
- **Phrase villes** : joiner anglais `" and "` pour GB/IE dans `search_anchors_loader.py` ; suffixe `" around {cities}"`.
- **Presse locale** : `local_press_domains/gb.json` et `ie.json` avec domaines régionaux réels.
- **Résolution département** : `is_foreign_location` et marqueurs pays rendus **country-aware** (London n'est plus « étranger » pour un run GB).
- **Company resolver** : inchangé — FR uniquement (comme DE).

## Dédup

### Problème actuel

`run_dedup_pass` charge les projets par préfixe `department LIKE '{code}%'` **sans filtrer `project.country`**. Risque de collision (ex. futur `NW`).

### Correction

Ajouter `Project.country == country` (avec `func.coalesce(Project.country, country) == country` pour legacy null).

`infer_country_from_department` étendu pour GB/IE ; fallback `or "FR"` remplacé par inférence explicite dans `dedup_service`.

## Frontend

- `countries.ts` : GB + IE
- `uk-regions.ts`, `ireland-provinces.ts` : listes régions
- `regions.ts` : registre étendu
- Labels UI : « Regions » (GB), « Provinces » (IE), adaptés dans settings et project detail

## Hors périmètre

- Companies House / CRO (enrichissement entreprise UK/IE)
- Refactor registre unifié des régions

## Risques

- Collisions codes IE (`LE`, `MU`) si inférence sans contexte pays — mitigé par filtre `project.country` en dédup et `country` explicite dans config/run
- Qualité presse locale : domaines à valider en production
