# Persistance des URLs préfiltrées — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mémoriser définitivement les URLs rejetées au préfiltre LLM et distinguer visuellement les articles « en attente » (retenus mais non fetchés) des articles rejetés.

**Architecture:** Ajouter `mark_url_seen` au moment du rejet préfiltre dans `pipeline.py` ; les URLs `not_fetched` restent hors `ProcessedUrl`. Côté frontend, introduire le statut `deferred` pour les articles retenus mais hors cap de 10 fetch.

**Tech Stack:** Python/FastAPI, SQLAlchemy (`ProcessedUrl`), React/TypeScript, Vitest, pytest

---

### Task 1: Persister les URLs prefiltered en backend

**Files:**
- Modify: `backend/app/agent/pipeline.py:467-474`
- Modify: `backend/tests/test_pipeline_prefilter.py:74-125`
- Create: `backend/tests/test_prefiltered_persistence.py`

**Step 1: Write the failing test**

Dans `backend/tests/test_pipeline_prefilter.py`, renommer `test_prefilter_rejects_emit_skip_and_are_not_marked_processed` en `test_prefilter_rejects_are_marked_processed` et inverser les assertions :

```python
processed = {row[0] for row in db_session.query(ProcessedUrl.url).all()}
assert "https://a.com/1" in processed
assert "https://a.com/2" in processed
rows = db_session.query(ProcessedUrl).filter(ProcessedUrl.url.in_(["https://a.com/1", "https://a.com/2"])).all()
assert all(r.reason == "prefiltered" for r in rows)
```

Ajouter dans `backend/tests/test_prefiltered_persistence.py` :

```python
@pytest.mark.asyncio
async def test_prefiltered_url_suppressed_on_next_run(db_session):
    # Run 1 : URL prefiltered → ProcessedUrl
    # Run 2 : même URL dans résultats Exa → filtrée (known), pas dans visible_results
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_pipeline_prefilter.py::test_prefilter_rejects_are_marked_processed tests/test_prefiltered_persistence.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Dans `pipeline.py`, dans la boucle `for candidate in rejected:` avant `_emit_article_skipped` :

```python
mark_url_seen(session, candidate["url"], "prefiltered", run_id)
known_urls.add(candidate["url"])
session.commit()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_pipeline_prefilter.py tests/test_prefiltered_persistence.py -v`
Expected: PASS

---

### Task 2: Statut `deferred` pour les articles non fetchés (frontend)

**Files:**
- Modify: `frontend/src/lib/run-article-batches.ts`
- Modify: `frontend/src/components/run-article-batches.tsx`
- Modify: `frontend/src/lib/run-article-batches.test.ts`

**Step 1: Write the failing test**

Dans `run-article-batches.test.ts` :

```typescript
it("marks unfetched articles as deferred on exa_fetch_done", () => {
  let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
    sector: "industriel",
    department: "69",
    results: [
      { url: "https://a.com/fetched", title: "Fetched", score: 0.9 },
      { url: "https://a.com/waiting", title: "Waiting", score: 0.5 },
    ],
  });
  state = applyRunStreamEvent(state, "exa_fetch_done", {
    articles: [{ url: "https://a.com/fetched", title: "Fetched" }],
  });
  const waiting = state.batches[0].articles.find((a) => a.url === "https://a.com/waiting");
  expect(waiting?.status).toBe("deferred");
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- run-article-batches.test.ts -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- Ajouter `"deferred"` à `ArticleLineStatus`
- `SKIP_REASON_LABELS.not_fetched` → `"en attente"` (ou clé `deferred`)
- `markUnfetchedAsIgnored` → renommer en `markUnfetchedAsDeferred`, status `"deferred"`
- `TERMINAL` inclut `"deferred"`
- `run-article-batches.tsx` : icône `Clock`, pas de `line-through` pour `deferred`, label « en attente »

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- run-article-batches.test.ts -v`
Expected: PASS

---

### Task 3: Vérification finale

**Step 1: Run all related tests**

```bash
cd backend && python3 -m pytest tests/test_pipeline_prefilter.py tests/test_prefiltered_persistence.py tests/test_known_urls.py -v
cd frontend && npm test -- run-article-batches.test.ts -v
```

Expected: all PASS
