# Déduplication & merge de projets — Design

**Date :** 2026-06-17  
**Statut :** Validé

## Objectif

Fusionner automatiquement les projets doublons (même chantier physique, noms/entreprises différents selon les articles) tout en conservant un historique des merges lié aux runs.

## Décisions validées

| Décision | Choix |
|----------|-------|
| Résultat | Fusion automatique → une seule fiche active |
| Timing | Pendant le run (clé enrichie) + consolidation fuzzy/LLM en fin de run |
| Détection | Hybride : règles + fuzzy + LLM sur cas ambigus (score 0.6–0.9) |
| Traçabilité | Journal en base + stats run + UI dédiée |
| Architecture | **Approche 1** — une seule `match_key` enrichie, affinage itératif |

## Modèle de données

### `match_key` enrichie

Remplace `slugify(nom)|ville|entreprise` par :

```
match_key = tokens_normalisés(nom) | ville_normalisée
```

**Normalisation du nom :**
1. Minuscules, suppression accents
2. Retrait des préfixes génériques : `méga-entrepôt`, `entrepôt`, `entrepôt frigorifique`, `plateforme logistique`…
3. Extraction des tokens significatifs (mots > 3 car., hors stopwords)
4. Tri alphabétique + jointure : `amazon|colombier|saugnieu`

**L'entreprise est retirée de la clé** (source principale de faux négatifs).

### Évolution `projects`

```python
merged_into_id: UUID | None  # null = actif, sinon absorbé
```

- API/UI : uniquement `merged_into_id IS NULL`
- Projet absorbé conservé en base (sources déplacées vers le survivant)

### Nouvelle table `project_merges`

| Champ | Description |
|-------|-------------|
| `run_id` | Run ayant déclenché le merge (nullable pour migration) |
| `kept_project_id` | Projet survivant |
| `absorbed_project_id` | Projet absorbé |
| `method` | `match_key` \| `fuzzy` \| `llm` |
| `score` | Similarité fuzzy (null si match exact) |
| `snapshot` | JSON noms/entreprises/villes avant merge |
| `created_at` | Timestamp |

### Évolution `runs`

```python
projects_merged: int = 0
```

## Logique de détection et merge

### Phase 1 — Pendant le run

Dans `upsert_project` : nouvelle `make_match_key`, comportement upsert inchangé.

### Phase 2 — Fin de run (`dedup_agent.py`)

1. Paires candidates : projets actifs du département, même ville OU score fuzzy nom ≥ 0.6
2. Score ≥ 0.9 → merge auto (`method: fuzzy`)
3. Score 0.6–0.9 → arbitrage LLM (`method: llm`)
4. Score < 0.6 → ignorer

**`merge_projects` :**
1. Déplacer `sources` vers le survivant
2. Fusionner champs (logique existante `_fill_field`, `merge_people`, `_pick_status`)
3. Nom affiché = le plus long
4. `absorbed.merged_into_id = kept.id`
5. Log `project_merges` + `run.projects_merged++` + SSE `project_merged`

### Migration existante

Script `scripts/rematch_projects.py` : recalcul `match_key`, merge des collisions, puis passe fuzzy/LLM.

### Seuils (constantes)

```python
FUZZY_AUTO_MERGE = 0.9
FUZZY_CANDIDATE_MIN = 0.6
```

## API & UI

### API

- `GET /api/projects` — filtre `merged_into_id IS NULL` (défaut)
- `GET /api/projects/{id}/merges` — historique des merges pour un projet
- `GET /api/runs/{id}/merges` — merges déclenchés par un run
- `RunRead.projects_merged` exposé

### SSE

Nouvel événement `project_merged` : `{kept_id, absorbed_name, method}`

### Frontend

- Badge « fusionné » dans la table si le projet a un historique de merges entrants
- Panneau/drawer historique : noms absorbés, date, run, méthode
- Filtre optionnel « fusionnés ce run » dans les stats de fin de run
- Handler SSE `project_merged` dans `use-run-stream.ts`

## Hors scope V1

- Undo de merge
- Affinage manuel des règles de normalisation via UI
- Déduplication inter-départements
