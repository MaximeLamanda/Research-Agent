# Run Article Batches UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher sous la bulle ColorOrb, pendant un run, des blocs accordéon par recherche (secteur + département) listant les 10 articles Exa avec progression visuelle (cercle → check) et repli auto à la fin du batch.

**Architecture:** Le backend émet un nouvel événement SSE `article_skipped` pour les URLs filtrées avant analyse LLM. Le frontend maintient l'état des batches via un reducer pur (`run-article-batches.ts`) alimenté par les événements SSE dans `use-run-stream.ts`, rendu par `RunArticleBatches` sur la page principale.

**Tech Stack:** Python 3.12, FastAPI, pytest | Next.js 15, React 19, Tailwind, Radix Accordion, vitest

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `backend/app/agent/pipeline.py` | Émet `article_skipped`, message step |
| `backend/tests/test_article_skipped.py` | Tests pipeline skips |
| `frontend/src/lib/run-article-batches.ts` | Types + reducer pur |
| `frontend/src/lib/run-article-batches.test.ts` | Tests vitest reducer |
| `frontend/src/hooks/use-run-stream.ts` | Handlers SSE + état `batches` |
| `frontend/src/components/run-article-batches.tsx` | UI accordéon live |
| `frontend/src/app/page.tsx` | Intégration sous AgentStatus |
| `frontend/package.json` | Scripts vitest |

---

### Task 1: Backend — événement `article_skipped`

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Create: `backend/tests/test_article_skipped.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_article_skipped.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.pipeline import run_pipeline
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
from app.models.run import Run


@pytest.mark.asyncio
async def test_emits_article_skipped_for_known_url_at_search_time(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    db_session.add(
        ProcessedUrl(url="https://example.com/known", reason="not_relevant")
    )
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [
        {"url": "https://example.com/known", "title": "Known", "score": 0.9},
        {"url": "https://example.com/new", "title": "New", "score": 0.8},
    ]
    fake_fetch = [
        {"url": "https://example.com/new", "title": "New", "text": "x" * 120},
    ]
    emit_mock = AsyncMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(is_relevant=True, name="Test", city="Lyon")
        )

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    assert len(skipped) == 1
    payload = skipped[0].args[2]
    assert payload["url"] == "https://example.com/known"
    assert payload["reason"] == "known"


@pytest.mark.asyncio
async def test_emits_article_skipped_for_short_text(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://example.com/short", "title": "Short", "score": 0.7}]
    fake_fetch = [{"url": "https://example.com/short", "title": "Short", "text": "tiny"}]
    emit_mock = AsyncMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock()

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    assert any(s["reason"] == "short_text" for s in skipped)
    llm_cls.return_value.extract.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_article_skipped.py -v`

Expected: FAIL — no `article_skipped` events emitted

- [ ] **Step 3: Implement `article_skipped` in pipeline**

In `backend/app/agent/pipeline.py`:

1. Add to `_STEP_MESSAGES`:
```python
"article_skipped": "Article ignoré ({reason}) : {title}",
```

2. Add helper after `_exa_fetch_articles_payload`:
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

3. After `exa_search_done` step_logger call and `new_urls` computation, emit skips for filtered URLs:
```python
search_by_url = {r["url"]: r for r in search_results if r.get("url")}
for url, result in search_by_url.items():
    if url in new_urls:
        continue
    if url in known_urls:
        reason = "known"
    elif is_blocked_url(url):
        reason = "blocked"
    else:
        continue
    await _emit_article_skipped(
        session,
        run_id,
        url=url,
        title=result.get("title") or url,
        reason=reason,
    )
```

4. Change `if not new_urls: continue` to still allow batch completion when all skipped (keep `continue` but skips already emitted).

5. In the fetch loop, before `if len(text.strip()) < 100: continue`, replace with:
```python
if len(text.strip()) < 100:
    await _emit_article_skipped(
        session, run_id, url=url, title=title, reason="short_text"
    )
    continue
```

6. In extraction exception handler (both retries failed), before `continue`:
```python
await _emit_article_skipped(
    session, run_id, url=url, title=title, reason="extraction_failed"
)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_article_skipped.py tests/test_pipeline_test_mode.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_article_skipped.py
git commit -m "feat: emit article_skipped SSE events for filtered URLs"
```

---

### Task 2: Frontend — reducer pur + vitest

**Files:**
- Create: `frontend/src/lib/run-article-batches.ts`
- Create: `frontend/src/lib/run-article-batches.test.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add vitest**

In `frontend/package.json`, add devDependencies and script:
```json
"scripts": {
  "test": "vitest run",
  "test:watch": "vitest"
},
"devDependencies": {
  "vitest": "^3.2.4"
}
```

Run: `cd frontend && npm install`

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/run-article-batches.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  applyRunStreamEvent,
  initialBatchesState,
  type ArticleBatch,
} from "./run-article-batches";

describe("applyRunStreamEvent", () => {
  it("creates a batch from exa_search_done with articles sorted by score", () => {
    const state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [
        { url: "https://a.com/low", title: "Low", score: 0.3 },
        { url: "https://a.com/high", title: "High", score: 0.9 },
      ],
    });
    expect(state.batches).toHaveLength(1);
    expect(state.batches[0].articles[0].url).toBe("https://a.com/high");
    expect(state.batches[0].articles[0].status).toBe("pending");
    expect(state.batches[0].collapsed).toBe(false);
  });

  it("marks article as ignored on article_skipped", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/x",
      reason: "known",
    });
    expect(state.batches[0].articles[0].status).toBe("ignored");
  });

  it("auto-collapses batch when all articles are terminal", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/x",
      reason: "known",
    });
    expect(state.batches[0].collapsed).toBe(true);
  });

  it("transitions extracting → done via llm_extract_done on scanning article", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "extracting", {
      url: "https://a.com/x",
      title: "X",
    });
    expect(state.batches[0].articles[0].status).toBe("scanning");
    state = applyRunStreamEvent(state, "llm_extract_done", {
      title: "X",
      is_relevant: true,
    });
    expect(state.batches[0].articles[0].status).toBe("done");
    expect(state.batches[0].collapsed).toBe(true);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test`

Expected: FAIL — module not found

- [ ] **Step 4: Implement reducer**

Create `frontend/src/lib/run-article-batches.ts`:

```typescript
export type ArticleLineStatus =
  | "pending"
  | "scanning"
  | "done"
  | "ignored"
  | "not_relevant";

export interface ArticleLine {
  url: string;
  title: string;
  score?: number;
  status: ArticleLineStatus;
  skipReason?: string;
}

export interface ArticleBatch {
  id: string;
  sector: string;
  department: string;
  collapsed: boolean;
  manuallyExpanded: boolean;
  articles: ArticleLine[];
}

export interface BatchesState {
  batches: ArticleBatch[];
  scanningUrl: string | null;
}

const TERMINAL: ArticleLineStatus[] = ["done", "ignored", "not_relevant"];

const SECTOR_LABELS: Record<string, string> = {
  industriel: "Industriel",
  logistique: "Logistique",
  retail: "Retail",
};

export function sectorLabel(sector: string): string {
  return SECTOR_LABELS[sector] ?? sector;
}

export function initialBatchesState(): BatchesState {
  return { batches: [], scanningUrl: null };
}

function isTerminal(status: ArticleLineStatus): boolean {
  return TERMINAL.includes(status);
}

function maybeCollapseBatch(batch: ArticleBatch): ArticleBatch {
  if (batch.manuallyExpanded) return batch;
  const allDone = batch.articles.length > 0 && batch.articles.every((a) => isTerminal(a.status));
  return allDone ? { ...batch, collapsed: true } : batch;
}

function updateArticleInLatestBatch(
  state: BatchesState,
  url: string,
  updater: (article: ArticleLine) => ArticleLine
): BatchesState {
  const batches = [...state.batches];
  for (let i = batches.length - 1; i >= 0; i--) {
    const idx = batches[i].articles.findIndex((a) => a.url === url);
    if (idx === -1) continue;
    const articles = [...batches[i].articles];
    articles[idx] = updater(articles[idx]);
    batches[i] = maybeCollapseBatch({ ...batches[i], articles });
    return { ...state, batches };
  }
  return state;
}

function markUnfetchedAsIgnored(
  batch: ArticleBatch,
  fetchedUrls: Set<string>
): ArticleBatch {
  const articles = batch.articles.map((a) =>
    !fetchedUrls.has(a.url) && a.status === "pending"
      ? { ...a, status: "ignored" as const, skipReason: "not_fetched" }
      : a
  );
  return maybeCollapseBatch({ ...batch, articles });
}

export function toggleBatchExpanded(state: BatchesState, batchId: string): BatchesState {
  return {
    ...state,
    batches: state.batches.map((b) =>
      b.id === batchId
        ? { ...b, collapsed: !b.collapsed, manuallyExpanded: !b.collapsed }
        : b
    ),
  };
}

export function applyRunStreamEvent(
  state: BatchesState,
  event: string,
  data: Record<string, unknown>
): BatchesState {
  switch (event) {
    case "exa_search_done": {
      const sector = String(data.sector ?? "");
      const department = String(data.department ?? "");
      const raw = Array.isArray(data.results) ? data.results : [];
      const articles: ArticleLine[] = raw
        .filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
        .map((r) => ({
          url: String(r.url ?? ""),
          title: String(r.title ?? r.url ?? ""),
          score: typeof r.score === "number" ? r.score : undefined,
          status: "pending" as const,
        }))
        .filter((a) => a.url.length > 0)
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

      const batch: ArticleBatch = {
        id: `${sector}-${department}-${Date.now()}`,
        sector,
        department,
        collapsed: false,
        manuallyExpanded: false,
        articles,
      };
      return { ...state, batches: [...state.batches, batch], scanningUrl: null };
    }

    case "exa_fetch_done": {
      const raw = Array.isArray(data.articles) ? data.articles : [];
      const fetchedUrls = new Set(
        raw
          .filter((a): a is Record<string, unknown> => typeof a === "object" && a !== null)
          .map((a) => String(a.url ?? ""))
          .filter(Boolean)
      );
      if (state.batches.length === 0) return state;
      const batches = [...state.batches];
      const last = batches.length - 1;
      batches[last] = markUnfetchedAsIgnored(batches[last], fetchedUrls);
      return { ...state, batches };
    }

    case "article_skipped":
      return updateArticleInLatestBatch(state, String(data.url ?? ""), (a) => ({
        ...a,
        status: "ignored",
        skipReason: String(data.reason ?? "skipped"),
      }));

    case "extracting": {
      const url = String(data.url ?? "");
      const next = updateArticleInLatestBatch(state, url, (a) => ({
        ...a,
        status: "scanning",
      }));
      return { ...next, scanningUrl: url };
    }

    case "llm_extract_done": {
      const url = state.scanningUrl;
      if (!url) return state;
      const isRelevant = data.is_relevant === true;
      const next = updateArticleInLatestBatch(state, url, (a) => ({
        ...a,
        status: isRelevant ? "done" : "not_relevant",
      }));
      return { ...next, scanningUrl: null };
    }

    case "article_not_relevant":
      return updateArticleInLatestBatch(state, String(data.url ?? ""), (a) => ({
        ...a,
        status: "not_relevant",
      }));

    case "run_started":
      return initialBatchesState();

    default:
      return state;
  }
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm test`

Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/run-article-batches.ts frontend/src/lib/run-article-batches.test.ts
git commit -m "feat: add run article batches reducer with vitest"
```

---

### Task 3: Étendre `useRunStream` avec les batches

**Files:**
- Modify: `frontend/src/hooks/use-run-stream.ts`

- [ ] **Step 1: Extend state and handlers**

Update `RunStreamState`:
```typescript
import {
  applyRunStreamEvent,
  initialBatchesState,
  toggleBatchExpanded,
  type BatchesState,
} from "@/lib/run-article-batches";

export interface RunStreamState {
  active: boolean;
  message: string;
  stats: { ... } | null;
  batches: BatchesState;
}
```

Initialize with `batches: initialBatchesState()`.

Add helper inside `useEffect`:
```typescript
function applyEvent(event: string, data: Record<string, unknown>) {
  setState((s) => ({
    ...s,
    batches: applyRunStreamEvent(s.batches, event, data),
  }));
}
```

Call `applyEvent` from every existing handler (before or after message update). Add handlers:
```typescript
article_skipped: (data) => {
  applyEvent("article_skipped", data);
},
exa_search_done: (data) => {
  applyEvent("exa_search_done", data);
},
exa_fetch_done: (data) => {
  applyEvent("exa_fetch_done", data);
},
llm_extract_done: (data) => {
  applyEvent("llm_extract_done", data);
},
```

Export toggle function:
```typescript
return {
  ...state,
  toggleBatch: (batchId: string) =>
    setState((s) => ({
      ...s,
      batches: toggleBatchExpanded(s.batches, batchId),
    })),
};
```

On `run_started` reset: `batches: initialBatchesState()`.

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-run-stream.ts
git commit -m "feat: wire article batches state into run stream hook"
```

---

### Task 4: Composant `RunArticleBatches`

**Files:**
- Create: `frontend/src/components/run-article-batches.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  sectorLabel,
  type ArticleBatch,
  type ArticleLine,
  type BatchesState,
} from "@/lib/run-article-batches";
import { Check, Circle, Loader2, Minus } from "lucide-react";

function StatusIcon({ article }: { article: ArticleLine }) {
  switch (article.status) {
    case "scanning":
      return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-violet-500" />;
    case "done":
      return <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />;
    case "ignored":
      return <Minus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
    case "not_relevant":
      return <Check className="h-3.5 w-3.5 shrink-0 text-orange-400" />;
    default:
      return <Circle className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40" />;
  }
}

function ArticleRow({ article }: { article: ArticleLine }) {
  const muted = article.status === "ignored";
  return (
    <li
      className={`flex items-center gap-2 py-1 text-xs ${muted ? "text-muted-foreground" : ""}`}
    >
      <StatusIcon article={article} />
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className={`min-w-0 flex-1 truncate hover:underline ${muted ? "line-through" : "text-foreground"}`}
      >
        {article.title}
      </a>
      {article.score != null && (
        <span className="shrink-0 tabular-nums text-[10px] text-muted-foreground">
          {article.score.toFixed(2)}
        </span>
      )}
      {article.status === "ignored" && (
        <span className="shrink-0 text-[10px] text-muted-foreground">ignoré</span>
      )}
    </li>
  );
}

function BatchBlock({
  batch,
  onToggle,
}: {
  batch: ArticleBatch;
  onToggle: () => void;
}) {
  const doneCount = batch.articles.filter((a) =>
    ["done", "ignored", "not_relevant"].includes(a.status)
  ).length;

  return (
    <Accordion
      type="single"
      collapsible
      value={batch.collapsed ? "" : batch.id}
      onValueChange={() => onToggle()}
    >
      <AccordionItem value={batch.id} className="border rounded-lg px-3">
        <AccordionTrigger className="py-2 text-xs hover:no-underline">
          <span className="font-medium">
            {sectorLabel(batch.sector)} · {batch.department}
          </span>
          <span className="ml-2 text-muted-foreground">
            {doneCount}/{batch.articles.length}
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-2">
          <ul className="space-y-0.5">
            {batch.articles.map((article) => (
              <ArticleRow key={article.url} article={article} />
            ))}
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function RunArticleBatches({
  batches,
  onToggleBatch,
}: {
  batches: BatchesState;
  onToggleBatch: (batchId: string) => void;
}) {
  if (batches.batches.length === 0) return null;

  return (
    <div className="flex w-full max-w-sm flex-col gap-2">
      {batches.batches.map((batch) => (
        <BatchBlock
          key={batch.id}
          batch={batch}
          onToggle={() => onToggleBatch(batch.id)}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: successful build

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/run-article-batches.tsx
git commit -m "feat: add RunArticleBatches live progress component"
```

---

### Task 5: Intégration page principale

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Wire component**

In `page.tsx`:
```tsx
import { RunArticleBatches } from "@/components/run-article-batches";

const { active, message, stats, batches, toggleBatch } = useRunStream(...);

// After AgentStatus when active:
{active && (
  <>
    <AgentStatus active={active} message={message} stats={null} />
    <RunArticleBatches batches={batches} onToggleBatch={toggleBatch} />
  </>
)}
```

Ensure `RunArticleBatches` renders between `AgentStatus` and the title/buttons block.

- [ ] **Step 2: Manual smoke test**

1. Start backend: `cd backend && DATABASE_URL="sqlite:///./research.db" python3 -m uvicorn app.main:app --reload --port 8001`
2. Start frontend: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8001 npm run dev`
3. Launch a test run — verify blocks appear, circles update, blocks collapse

- [ ] **Step 3: Run all tests**

Run: `cd backend && python3 -m pytest -q` and `cd frontend && npm test`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: show live article batches under ColorOrb during runs"
```

---

## Self-Review

| Exigence spec | Task |
|---------------|------|
| Bloc par secteur+département | Task 2 reducer, Task 4 UI |
| 10 articles triés par score | Task 2 `exa_search_done` |
| Cercle → check progression | Task 4 `StatusIcon` |
| Ignorés cochés immédiatement | Task 1 `article_skipped`, Task 2 |
| Repli auto à 10/10 | Task 2 `maybeCollapseBatch` |
| ShiningText au-dessus | Task 5 placement |
| Visible seulement pendant run | Task 5 `active &&` |

**Note:** `/execute-plan` est déprécié — utiliser `superpowers:subagent-driven-development` ou `superpowers:executing-plans`.
