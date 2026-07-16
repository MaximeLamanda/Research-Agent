# Persistance des URLs préfiltrées — Design

**Date :** 2026-07-06  
**Statut :** Validé

## Problème

Pour chaque combinaison département × secteur, Exa renvoie 25 résultats. Le préfiltre LLM en rejette une partie ; parmi les retenus, seuls 10 sont fetchés. Aujourd’hui :

- Les URLs **rejetées au préfiltre** (`prefiltered`) ne sont pas mémorisées → elles réapparaissent à chaque run.
- Les URLs **retenues mais hors top 10** (`not_fetched`) ne sont pas mémorisées non plus → comportement voulu, mais confondu visuellement avec les rejets.

## Décisions validées

| Sujet | Choix |
|-------|-------|
| URLs `prefiltered` | Exclusion **définitive** via `ProcessedUrl(reason="prefiltered")` |
| URLs `not_fetched` | **Pas** en `ProcessedUrl` — éligibles au run suivant |
| UI `prefiltered` | Statut `ignored` + label « préfiltré » (inchangé) |
| UI `not_fetched` | Nouveau statut `deferred` + label « en attente » (pas de barré) |

## Flux par URL (25 résultats Exa)

```
Exa search (25)
  ├─ known / blocked / foreign_locale → skip immédiat (déjà géré)
  ├─ prefiltered (LLM fetch=false) → ProcessedUrl + article_skipped
  ├─ kept mais hors top 10 → not_fetched (deferred en UI, pas en base)
  └─ fetched → analyse LLM → ProcessedUrl ou Source
```

## Changements backend

Dans `pipeline.py`, au rejet préfiltre, ajouter (comme `foreign_locale`) :

```python
mark_url_seen(session, url, "prefiltered", run_id)
known_urls.add(url)
session.commit()
```

`load_known_urls` inchangé — inclut déjà toutes les entrées `ProcessedUrl`.

## Changements frontend

- `ArticleLineStatus` : ajouter `deferred`
- `exa_fetch_done` : articles non fetchés → `status: "deferred"` (au lieu de `ignored` + `not_fetched`)
- `TERMINAL` : inclure `deferred` pour permettre le repli du batch
- UI : icône horloge, pas de `line-through`, label « en attente »

## Tests

- Backend : `test_prefilter_rejects_emit_skip_and_are_marked_processed` (renommer / inverser l’assertion)
- Backend : nouveau test — URL prefiltered absente du prochain run
- Frontend : test `deferred` sur `exa_fetch_done`

## Hors scope

- File d’attente explicite pour `not_fetched`
- Over-fetch Exa (50→filtrer→10)
- TTL sur les `prefiltered`
