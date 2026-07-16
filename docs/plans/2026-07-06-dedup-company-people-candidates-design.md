# Dédup — candidats entreprise & contacts (sans SIREN)

**Date :** 2026-07-06  
**Statut :** Validé (brainstorming)

## Contexte

La déduplication actuelle (`backend/app/agent/dedup_agent.py`) forme des paires candidates via similarité nom/adresse, avec des règles SIREN (candidature, fusion auto, déclenchement LLM). Les paires dont les noms diffèrent fortement mais partagent le même promoteur ou le même contact ne deviennent jamais candidates.

## Objectif

1. **Retirer entièrement le SIREN** comme signal de déduplication (le champ reste sur le modèle pour l'enrichissement entreprise).
2. **Ajouter deux nouveaux signaux de candidature** (en OR avec nom/adresse existants) :
   - **Entreprise** : `company_similarity >= 85 %` (fuzzy), **sans exiger la même ville**
   - **Contact** : au moins un nom en commun avec `fuzz.ratio >= 85 %`, **sans exiger la même ville**
3. Conserver les règles de fusion auto existantes (fuzzy nom ≥ 90 %, adresse ≥ 88 %, promoteur+ville+brand ≥ 65 %), en passant la règle promoteur+ville sur fuzzy entreprise 85 % au lieu du slugify exact.

## Règles de candidature (`find_candidate_pairs`)

Une paire est candidate si **au moins un** signal :

| Signal | Condition | Même ville requise ? |
|--------|-----------|----------------------|
| Nom | score ≥ 45 % ou `brand_overlap` | Oui (sauf adresse) |
| Adresse | score ≥ 55 %, overlap, ou ≥ 88 % | Non |
| Entreprise | `company_similarity >= 0.85` | Non |
| Contact | `has_people_overlap` (fuzzy nom ≥ 85 %) | Non |

Le filtre ville sur le nom reste : `name_match` sans `address_match` exige `same_city`.

## Routage fusion auto / LLM (`run_dedup_pass`)

**Fusion auto (inchangée sauf SIREN) :**
- score nom ≥ 90 %
- adresse ≥ 88 %
- promoteur fuzzy ≥ 85 % + même ville + `brand_overlap` + nom ≥ 65 %

**LLM** si pas fusion auto et au moins un signal ambigu :
- nom ≥ 45 %, `brand_overlap`, adresse ≥ 55 %, `address_overlap`
- **ou** `company_similarity >= 0.85`
- **ou** `has_people_overlap`

## Hors périmètre

- Pas de changement du prompt LLM (déjà riche)
- Pas de fuzzy sur le SIREN en secours
- Pas de refactor en prédicats composables (approche minimale)

## Risques

- Plus d'appels LLM (promoteur multi-sites, contacts publics récurrents)
- Mitigation : cache `DedupDecision` inchangé ; verdict négatif persistant
