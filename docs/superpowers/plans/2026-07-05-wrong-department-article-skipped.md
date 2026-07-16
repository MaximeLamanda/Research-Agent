# Wrong Department Article Skipped Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Émettre un événement `article_skipped` avec `reason=wrong_department` lorsqu'un article extrait par le LLM appartient à un département différent de celui ciblé par la recherche, au lieu d'un `continue` silencieux — avec persistance de l'URL et affichage UI explicite.

**Architecture:** Le pipeline remplace le `continue` silencieux (l.491–496 de `pipeline.py`) par un appel à `_emit_article_skipped` + `mark_url_seen`, sur le même modèle que `prefiltered` / `short_text`. Le frontend réutilise le handler SSE `article_skipped` existant ; on ajoute un libellé lisible pour `wrong_department` dans le panneau live et la timeline.

**Tech Stack:** Python 3.12, FastAPI, pytest, SQLAlchemy | Next.js 15, React 19, vitest

---

## Contexte du bug

Run `a4b467ed…` (2026-07-05) : 14 articles marqués `is_relevant=true` par le LLM, **0 projet créé**. Cause : filtre département silencieux après extraction. L'UI affichait une coche verte (`done`) car `llm_extract_done` arrive avant le filtre ; l'article n'était ni loggé ni marqué `ProcessedUrl`, donc re-fetché à chaque run.

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `backend/app/agent/pipeline.py` | Remplacer `continue` silencieux par `_emit_article_skipped` + `mark_url_seen` |
| `backend/tests/test_article_skipped.py` | Tests TDD pour `wrong_department` |
| `frontend/src/lib/run-article-batches.ts` | Constante libellés `skipReason` (export) |
| `frontend/src/lib/run-article-batches.test.ts` | Test transition `done` → `ignored` sur `wrong_department` |
| `frontend/src/components/run-article-batches.tsx` | Afficher libellé `skipReason` au lieu de « ignoré » générique |
| `frontend/src/components/run-steps-timeline.tsx` | Label + couleur pour step `article_skipped` |

---

### Task 1: Backend — émettre `article_skipped` avec `reason=wrong_department`

**Files:**
- Modify: `backend/app/agent/pipeline.py:489-496`
- Modify: `backend/tests/test_article_skipped.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_article_skipped.py`:

```python
@pytest.mark.asyncio
async def test_emits_article_skipped_for_wrong_department(db_session):
    config = Config(
        country="FR",
        departments=["77"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [
        {"url": "https://example.com/rhone", "title": "Amazon Lyon", "score": 0.9},
    ]
    fake_fetch = [
        {
            "url": "https://example.com/rhone",
            "title": "Amazon Lyon",
            "text": "x" * 120,
        },
    ]
    emit_mock = AsyncMock()
    upsert_mock = AsyncMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(
                is_relevant=True,
                name="Amazon logistics warehouse",
                department="69 - Rhône",
                city="Colombier-Saugnieu",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    wrong = [s for s in skipped if s.get("reason") == "wrong_department"]
    assert len(wrong) == 1
    assert wrong[0]["url"] == "https://example.com/rhone"
    assert wrong[0]["target_department"] == "77 - Seine-et-Marne"
    assert wrong[0]["extracted_department"] == "69 - Rhône"
    upsert_mock.assert_not_called()

    processed = (
        db_session.query(ProcessedUrl)
        .filter(ProcessedUrl.url == "https://example.com/rhone")
        .first()
    )
    assert processed is not None
    assert processed.reason == "wrong_department"
```

Add a second test preserving existing behavior when department is null (fallback via `ensure_department`):

```python
@pytest.mark.asyncio
async def test_null_extracted_department_falls_back_and_does_not_skip(db_session):
    config = Config(
        country="FR",
        departments=["77"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://example.com/new", "title": "New", "score": 0.8}]
    fake_fetch = [{"url": "https://example.com/new", "title": "New", "text": "x" * 120}]
    emit_mock = AsyncMock()
    upsert_mock = AsyncMock(return_value=(AsyncMock(), True))

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(
                is_relevant=True,
                name="Local project",
                department=None,
                city="Meaux",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    wrong = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped" and c.args[2].get("reason") == "wrong_department"
    ]
    assert wrong == []
    upsert_mock.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python3 -m pytest tests/test_article_skipped.py::test_emits_article_skipped_for_wrong_department -v
```
Expected: FAIL — no `article_skipped` with `wrong_department`, `upsert_project` may be called.

- [ ] **Step 3: Implement in pipeline**

In `backend/app/agent/pipeline.py`, replace lines 491–496:

```python
                    if (
                        extracted_department
                        and target_department
                        and extracted_department != target_department
                    ):
                        continue
```

with:

```python
                    if (
                        extracted_department
                        and target_department
                        and extracted_department != target_department
                    ):
                        mark_url_seen(session, url, "wrong_department", run_id)
                        known_urls.add(url)
                        session.commit()
                        await _emit_article_skipped(
                            session,
                            run_id,
                            url=url,
                            title=title,
                            reason="wrong_department",
                        )
                        await log_and_emit(
                            session,
                            run_id,
                            "article_skipped",
                            {
                                "url": url,
                                "title": title,
                                "reason": "wrong_department",
                                "target_department": target_department,
                                "extracted_department": extracted_department,
                            },
                        )
                        continue
```

**Note:** `_emit_article_skipped` appelle déjà `log_and_emit` avec `article_skipped`. Vérifier son implémentation actuelle :

```python
async def _emit_article_skipped(
    session: Session,
    run_id: uuid.UUID,
    *,
    url: str,
    title: str,
    reason: str,
) -> None:
    await log_and_emit(
        session,
        run_id,
        "article_skipped",
        {"url": url, "title": title, "reason": reason},
    )
```

**Correction — ne pas doubler l'événement.** Étendre `_emit_article_skipped` pour accepter des champs extra optionnels :

```python
async def _emit_article_skipped(
    session: Session,
    run_id: uuid.UUID,
    *,
    url: str,
    title: str,
    reason: str,
    extra: dict | None = None,
) -> None:
    payload = {"url": url, "title": title, "reason": reason}
    if extra:
        payload.update(extra)
    await log_and_emit(session, run_id, "article_skipped", payload)
```

Puis remplacer le bloc silencieux par :

```python
                    if (
                        extracted_department
                        and target_department
                        and extracted_department != target_department
                    ):
                        mark_url_seen(session, url, "wrong_department", run_id)
                        known_urls.add(url)
                        session.commit()
                        await _emit_article_skipped(
                            session,
                            run_id,
                            url=url,
                            title=title,
                            reason="wrong_department",
                            extra={
                                "target_department": target_department,
                                "extracted_department": extracted_department,
                            },
                        )
                        continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd backend && python3 -m pytest tests/test_article_skipped.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_article_skipped.py
git commit -m "fix: emit article_skipped when extracted department mismatches search target"
```

---

### Task 2: Frontend — libellé `wrong_department` dans le panneau live

**Files:**
- Modify: `frontend/src/lib/run-article-batches.ts`
- Modify: `frontend/src/lib/run-article-batches.test.ts`
- Modify: `frontend/src/components/run-article-batches.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/lib/run-article-batches.test.ts`:

```typescript
  it("overrides done status to ignored on wrong_department skip", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "77",
      results: [{ url: "https://a.com/rhone", title: "Amazon Lyon", score: 0.9 }],
    });
    state = applyRunStreamEvent(state, "extracting", {
      url: "https://a.com/rhone",
      title: "Amazon Lyon",
    });
    state = applyRunStreamEvent(state, "llm_extract_done", {
      title: "Amazon Lyon",
      is_relevant: true,
    });
    expect(state.batches[0].articles[0].status).toBe("done");

    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/rhone",
      reason: "wrong_department",
      target_department: "77 - Seine-et-Marne",
      extracted_department: "69 - Rhône",
    });
    expect(state.batches[0].articles[0].status).toBe("ignored");
    expect(state.batches[0].articles[0].skipReason).toBe("wrong_department");
  });
```

- [ ] **Step 2: Run test to verify it passes (reducer already handles article_skipped)**

Run:
```bash
cd frontend && npm test -- run-article-batches.test.ts
```
Expected: PASS (le reducer existant gère déjà `article_skipped` ; ce test documente le scénario `done → ignored`).

- [ ] **Step 3: Add skip reason labels**

In `frontend/src/lib/run-article-batches.ts`, add after imports / before types:

```typescript
export const SKIP_REASON_LABELS: Record<string, string> = {
  known: "connu",
  blocked: "bloqué",
  prefiltered: "préfiltré",
  not_fetched: "non fetché",
  short_text: "texte court",
  extraction_failed: "extraction échouée",
  wrong_department: "hors dépt.",
  skipped: "ignoré",
};
```

- [ ] **Step 4: Use labels in ArticleRow**

In `frontend/src/components/run-article-batches.tsx`:

1. Import `SKIP_REASON_LABELS` from `@/lib/run-article-batches`.
2. Replace the generic `{article.status === "ignored" && (…ignoré…)}` block with:

```tsx
      {article.status === "ignored" && article.skipReason && (
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {SKIP_REASON_LABELS[article.skipReason] ?? article.skipReason}
        </span>
      )}
      {article.status === "ignored" && !article.skipReason && (
        <span className="shrink-0 text-[10px] text-muted-foreground">ignoré</span>
      )}
```

- [ ] **Step 5: Run frontend tests**

Run:
```bash
cd frontend && npm test -- run-article-batches.test.ts
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/run-article-batches.ts frontend/src/lib/run-article-batches.test.ts frontend/src/components/run-article-batches.tsx
git commit -m "feat: show wrong_department skip reason in live article batches"
```

---

### Task 3: Timeline — label pour `article_skipped`

**Files:**
- Modify: `frontend/src/components/run-steps-timeline.tsx`

- [ ] **Step 1: Add step label and color**

In `STEP_LABELS`, add:
```typescript
  article_skipped: "Article ignoré",
```

In `STEP_COLORS`, add:
```typescript
  article_skipped: "bg-gray-400",
```

- [ ] **Step 2: Manual check**

Lancer une run test avec un article hors département. Dans le drawer détail run, vérifier que la timeline affiche « Article ignoré (wrong_department) : … » via le message backend existant `"Article ignoré ({reason}) : {title}"`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/run-steps-timeline.tsx
git commit -m "feat: add article_skipped label in run steps timeline"
```

---

## Self-Review

| Exigence | Task |
|----------|------|
| Émettre `article_skipped` avec `reason=wrong_department` | Task 1 |
| Inclure `target_department` + `extracted_department` dans le payload | Task 1 |
| Marquer URL `ProcessedUrl` pour éviter re-fetch | Task 1 |
| UI live : article passe de vert à ignoré avec libellé | Task 2 |
| Timeline : step visible | Task 3 |
| Comportement inchangé si `department=null` (fallback 77) | Task 1 test 2 |
| Pas de double événement SSE | Task 1 (`_emit_article_skipped` étendu, pas de second `log_and_emit`) |

**Hors scope (YAGNI pour ce plan):**
- Distinction UI « pertinent LLM » vs « projet créé » (statut `project_found`)
- Backfill `ProcessedUrl` depuis steps historiques `article_skipped`
- Durcissement Exa géographique

## Test plan manuel

1. Configurer département **77** uniquement.
2. Lancer une run — observer des articles Amazon Rhône (69) marqués **« hors dépt. »** en gris barré, pas en vert.
3. Stats fin de run : `articles_found=0` mais steps `article_skipped` visibles dans le drawer.
4. Relancer la run : les URLs `wrong_department` ne doivent **plus** être fetchées (filtrées à `known_urls` via `ProcessedUrl`).
