# Design — Élargir la récolte Exa + préfiltre LLM batch des URLs

Date : 2026-07-03
Statut : validé

## Problème

Chaque recherche Exa est limitée à `num_results=10` (codé en dur dans
`pipeline.py`). La requête par couple (département × secteur) est statique, et
la recherche sémantique Exa est quasi-déterministe : la même requête renvoie
quasiment le même top 10 à chaque run. Comme le filtre `known_urls` écarte
tout ce qui a déjà été vu, il ne reste au 2e run que 0 ou 1 article nouveau —
d'où l'impression de "toujours les mêmes résultats".

Contraintes utilisateur :
- Pas d'augmentation des coûts (Exa `/contents` et extraction LLM complète).
- Maximum ~10 articles fetchés par recherche, comme aujourd'hui.

## Décision (approche A validée)

1. **`num_results` passe de 10 à 25** — même tarif Exa (palier ≤ 25 résultats),
   2,5× plus de candidats par appel. Les `highlights` (snippets) sont déjà
   demandés dans le payload actuel, donc gratuits.
2. **Préfiltre LLM batch** : après le filtrage existant (`known_urls`, domaines
   bloqués), un **seul appel** à un modèle économique reçoit la liste des
   candidats (titre + snippet + URL + date de publication) et retourne pour
   chaque URL `fetch: true/false` + `reason` courte.
3. **Cap de fetch à 10** : parmi les URLs retenues par le préfiltre, on fetch
   au maximum les 10 meilleures (priorisées par score Exa). Le reste du
   pipeline (fetch → extraction complète → SIREN → upsert → dédup) est
   inchangé.
4. **Pas de mémoire des rejets** : les URLs rejetées par le préfiltre émettent
   un `article_skipped` (raison `prefiltered`) mais ne sont **pas** enregistrées
   en `ProcessedUrl`. Elles restent réévaluables au run suivant (coût minime :
   titre+snippet dans un appel batch). Si les batchs regonflent avec toujours
   les mêmes rejets, on pourra ajouter une mémoire type approche B plus tard.
5. **Fallback robuste** : si le préfiltre échoue (erreur LLM, JSON invalide),
   on fetch les 10 premières URLs par score Exa, comme aujourd'hui. Le run ne
   casse jamais à cause du préfiltre.

### Approches écartées

- **B — rejets définitifs en `ProcessedUrl`** : batchs plus petits au fil du
  temps, mais un faux négatif du préfiltre est définitif.
- **C — préfiltre par règles heuristiques (sans LLM)** : zéro coût mais trop
  de faux positifs/négatifs sur les titres de presse locale.

## Composants

### Nouveau module `backend/app/agent/url_prefilter.py`

- Classe `UrlPrefilter` sur le modèle de `LLMExtractor` : appel Vercel AI
  Gateway (`https://ai-gateway.vercel.sh/v1/chat/completions`), parsing JSON
  robuste via le `parse_json_content` existant.
- Prompt : contexte "installateur solaire C&I", critères alignés sur ceux de
  l'extraction (nouvelle construction / extension / agrandissement de bâtiment
  industriel, logistique ou retail ; rejeter voirie, inaugurations, ouvertures
  de boutiques, rénovations légères, etc.).
- Entrée : liste numérotée de candidats `{url, title, snippet, published_at}`.
- Sortie : JSON `[{"url": ..., "fetch": true|false, "reason": "..."}]`.
- En cas d'URL manquante dans la réponse : considérée comme retenue
  (fail-open, cohérent avec le fallback).

### Config (`backend/app/config.py`)

- Nouveau setting `ai_prefilter_model`, configurable par variable
  d'environnement, défaut : un modèle économique via le gateway
  (ex. `openai/gpt-4o-mini`).

### Pipeline (`backend/app/agent/pipeline.py`)

- Constantes nommées : `EXA_NUM_RESULTS = 25`, `MAX_FETCH_PER_SEARCH = 10`.
  Pas de nouveau champ en base.
- Insertion du préfiltre entre le filtrage `known_urls`/bloqués et le
  `exa.fetch`, avec tri des URLs retenues par score Exa décroissant avant le
  cap à 10.

### Observabilité (run steps + SSE, comme les autres événements)

- `prefilter_start` : nombre de candidats envoyés au préfiltre.
- `prefilter_done` : nombre retenus / rejetés, modèle, durée ms.
- `article_skipped` avec raison `prefiltered` pour chaque URL rejetée.
- Messages français correspondants dans `_STEP_MESSAGES`.

## Tests

- Tests unitaires de `url_prefilter.py` : parsing de la réponse (avec et sans
  fences markdown), URLs manquantes dans la réponse (fail-open), erreur LLM →
  exception propagée pour déclencher le fallback.
- Tests pipeline : cap de 10 fetchs respecté, fallback quand le préfiltre
  échoue, événements `prefilter_*` et `article_skipped(prefiltered)` émis,
  rejets non enregistrés en `ProcessedUrl`.

## Hors périmètre (leviers discutés mais non retenus pour l'instant)

- Fenêtre de dates glissante (chercher depuis le dernier run).
- Rotation de variantes de requêtes par secteur.
- Exclusion dynamique des domaines sur-représentés.
- Endpoint Exa `findSimilar` à partir des articles pertinents.
