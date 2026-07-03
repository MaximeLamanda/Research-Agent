# Run Article Batches UI — Design

**Date :** 2026-07-01  
**Statut :** Validé

## Objectif

Pendant un run actif, afficher sous la bulle `ColorOrb` et le texte animé `ShiningText` une liste live des articles trouvés par recherche Exa — un bloc par combinaison secteur + département, avec une ligne par article (jusqu'à 10), un indicateur circulaire à gauche qui se coche au fur et à mesure de l'analyse LLM, et un repli automatique du bloc une fois les 10 articles traités.

## Décisions validées

| Sujet | Choix |
|-------|-------|
| Empilement des blocs | Un bloc par recherche (secteur + département), empilés verticalement |
| Contenu de la liste | Les 10 résultats Exa (`exa_search_done`), triés par score décroissant |
| Articles ignorés | Affichés et cochés immédiatement en grisé (pas d'analyse LLM) |
| Zone d'affichage | Sous `AgentStatus`, au-dessus des settings — uniquement pendant `active === true` |
| Timeline drawer | Inchangée (`RunStepsTimeline` reste pour l'historique détaillé) |

## Layout

```
ColorOrb
ShiningText (analyse en cours)
─────────────────────────────
▼ Industriel · 69 - Rhône      ← bloc ouvert
 ○ Article 1…
 ◉ Article 2…  (scan en cours)
 ✓ Article 3…  (analysé)
 ⊘ Article 4…  (ignoré)
▸ Logistique · 69 - Rhône      ← bloc refermé auto
─────────────────────────────
Settings / boutons
```

## États par ligne

| État | Cercle | Style |
|------|--------|-------|
| `pending` | Vide | Normal |
| `scanning` | Pulse animé | Texte accentué |
| `done` | ✓ vert | Normal |
| `ignored` | ✓ gris | Grisé + label « ignoré » |
| `not_relevant` | ✓ orange | Badge discret optionnel |

Chaque ligne : titre tronqué (lien) + score Exa à droite.

## Comportement du bloc

1. **Ouverture** — à `exa_search_done` : titre `{secteur} · {département}`, 10 articles `pending`.
2. **Progression** — événements SSE mettent à jour les lignes.
3. **Fermeture auto** — quand les 10 lignes sont terminales (`done`, `ignored`, `not_relevant`) → accordéon replié (animation ~200 ms).
4. **Réouverture** — clic sur l'en-tête d'un bloc refermé.

## Flux SSE

### Événements existants réutilisés

- `exa_search_done` → crée le batch + 10 articles `pending`
- `exa_fetch_done` → URLs absentes du fetch → `ignored` (filet de sécurité)
- `extracting` → article → `scanning`
- `llm_extract_done` → article en `scanning` → `done` ou `not_relevant`
- `article_not_relevant` → `not_relevant`

### Nouvel événement

- `article_skipped` — `{ url, title?, reason: "known" | "blocked" | "short_text" | "extraction_failed" }`  
  Émis côté pipeline pour les URLs filtrées avant ou sans analyse LLM complète.

## Architecture

**Approche retenue :** état frontend alimenté par SSE existants + `article_skipped` minimal côté backend.

- `frontend/src/lib/run-article-batches.ts` — reducer pur, testable
- `frontend/src/hooks/use-run-stream.ts` — étendu avec `batches`
- `frontend/src/components/run-article-batches.tsx` — UI accordéon
- `backend/app/agent/pipeline.py` — émission `article_skipped`

## Tests

- Backend : pytest sur émission `article_skipped` (known, blocked, short_text)
- Frontend : vitest sur le reducer pur (`applyRunStreamEvent`)
