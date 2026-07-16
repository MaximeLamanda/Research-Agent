# Cross-Department Import & Project Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importer les articles pertinents hors département cible avec le bon département extrait (hors stats de run), et filtrer la table projets par multi-sélection département côté serveur.

**Architecture:** Le pipeline remplace le skip `wrong_department` par une branche `cross_department` qui upsert puis émet `project_imported_cross_department` sans incrémenter les compteurs. L'API projets accepte `departments[]` + `country`. Le frontend ajoute un statut live dédié et un `DepartmentCombobox` au-dessus de `ProjectTable`.

**Tech Stack:** Python 3.12, FastAPI, pytest | Next.js 15, React 19, vitest, shadcn Combobox

**Design ref:** `docs/plans/2026-07-05-cross-department-import-design.md`

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `backend/app/agent/pipeline.py` | Branche cross_department + événement |
| `backend/tests/test_cross_department_import.py` | Tests pipeline (nouveau fichier) |
| `backend/tests/test_article_skipped.py` | Supprimer test wrong_department obsolète |
| `backend/app/api/projects.py` | Filtre `departments` multi-valeur |
| `backend/tests/test_projects_api.py` | Tests API filtre (nouveau fichier) |
| `frontend/src/lib/api.ts` | `getProjects({ departments, country })` |
| `frontend/src/lib/run-article-batches.ts` | Statut `cross_department` + handler SSE |
| `frontend/src/lib/run-article-batches.test.ts` | Test statut cross_department |
| `frontend/src/components/run-article-batches.tsx` | Icône + libellé import cross-dept |
| `frontend/src/hooks/use-run-stream.ts` | Handler `project_imported_cross_department` |
| `frontend/src/components/project-list.tsx` | DepartmentCombobox + reload filtré |
| `frontend/src/components/run-steps-timeline.tsx` | Label timeline nouvel événement |

---

### Task 1: Backend pipeline — cross_department import

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Create: `backend/tests/test_cross_department_import.py`
- Modify: `backend/tests/test_article_skipped.py` (remove `test_emits_article_skipped_for_wrong_department`)

- [ ] **Step 1: Write failing test** in `backend/tests/test_cross_department_import.py`:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.pipeline import run_pipeline
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
from app.models.run import Run


def _keep_all_prefilter():
    prefilter = AsyncMock()
    prefilter.select = AsyncMock(
        side_effect=lambda candidates, step_logger=None: {
            c["url"]: (True, "") for c in candidates
        }
    )
    return prefilter


@pytest.mark.asyncio
async def test_cross_department_imports_without_run_stats(db_session):
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

    fake_search = [{"url": "https://example.com/rhone", "title": "Amazon Lyon", "score": 0.9}]
    fake_fetch = [{"url": "https://example.com/rhone", "title": "Amazon Lyon", "text": "x" * 120}]
    emit_mock = AsyncMock()
    project_mock = SimpleNamespace(id=uuid4(), name="Amazon logistics warehouse")
    upsert_mock = MagicMock(return_value=(project_mock, True))

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock) as upsert_patch,
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

        result = await run_pipeline(db_session, run_id=run.id)

    upsert_patch.assert_called_once()
    extraction_arg = upsert_patch.call_args.args[1]
    assert extraction_arg.department == "69 - Rhône"

    cross_events = [c for c in emit_mock.await_args_list if c.args[1] == "project_imported_cross_department"]
    assert len(cross_events) == 1
    payload = cross_events[0].args[2]
    assert payload["target_department"] == "77 - Seine-et-Marne"
    assert payload["extracted_department"] == "69 - Rhône"
    assert payload["project_id"] == str(project_mock.id)

    project_found = [c for c in emit_mock.await_args_list if c.args[1] == "project_found"]
    assert project_found == []

    db_session.refresh(result)
    assert result.articles_found == 0
    assert result.projects_new == 0
    assert result.projects_updated == 0

    processed = db_session.query(ProcessedUrl).filter(ProcessedUrl.url == "https://example.com/rhone").first()
    assert processed is not None
    assert processed.reason == "cross_department"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_cross_department_import.py -v
```

- [ ] **Step 3: Implement in pipeline.py**

Add to `_STEP_MESSAGES`:
```python
"project_imported_cross_department": "Import cross-dépt. ({extracted_department}) : {name}",
```

Replace wrong_department skip block with cross_department branch:

```python
                    target_department = format_department(department, country)
                    extracted_department = normalize_department(extraction.department, country)
                    cross_department = bool(
                        extracted_department
                        and target_department
                        and extracted_department != target_department
                    )
                    if cross_department:
                        extraction.department = extracted_department
                    else:
                        extraction.department = ensure_department(
                            extraction.department, department, country
                        )
```

After `upsert_project` + `session.commit()` + `known_urls.add(url)`, branch stats/events:

```python
                    if cross_department:
                        mark_url_seen(session, url, "cross_department", run_id)
                        session.commit()
                        await log_and_emit(
                            session,
                            run_id,
                            "project_imported_cross_department",
                            {
                                "url": url,
                                "title": title,
                                "name": project.name,
                                "project_id": str(project.id),
                                "is_new": is_new,
                                "target_department": target_department,
                                "extracted_department": extracted_department,
                            },
                        )
                    else:
                        run.articles_found += 1
                        if is_new:
                            run.projects_new += 1
                        else:
                            run.projects_updated += 1
                        session.commit()
                        await log_and_emit(
                            session,
                            run_id,
                            "project_found",
                            {
                                "project_id": str(project.id),
                                "name": project.name,
                                "is_new": is_new,
                            },
                        )
```

Remove old `wrong_department` `_emit_article_skipped` block entirely.

Delete `test_emits_article_skipped_for_wrong_department` from `test_article_skipped.py`.

- [ ] **Step 4: Run tests**

```bash
cd backend && python3 -m pytest tests/test_cross_department_import.py tests/test_article_skipped.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_cross_department_import.py backend/tests/test_article_skipped.py
git commit -m "feat: import cross-department articles without counting run stats"
```

---

### Task 2: Backend API — filtre multi-départements

**Files:**
- Modify: `backend/app/api/projects.py`
- Create: `backend/tests/test_projects_api.py`

- [ ] **Step 1: Write failing test**

```python
from app.models.project import Project


def test_list_projects_filters_by_multiple_departments(client, db_session):
    db_session.add(Project(name="A", department="77 - Seine-et-Marne", country="FR", match_key="a"))
    db_session.add(Project(name="B", department="69 - Rhône", country="FR", match_key="b"))
    db_session.add(Project(name="C", department="38 - Isère", country="FR", match_key="c"))
    db_session.commit()

    response = client.get("/api/projects", params=[("departments", "77"), ("departments", "69"), ("country", "FR")])
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"A", "B"}
```

Use existing `client` fixture from conftest if available; otherwise create minimal fixture in test file.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement**

```python
from app.data.departments import ensure_department, format_department

@router.get("", response_model=list[ProjectRead])
def list_projects(
    department: str | None = Query(None),
    departments: list[str] | None = Query(None),
    country: str = Query("FR"),
    status: str | None = Query(None),
    sector: str | None = Query(None),
    db: Session = Depends(get_db),
):
    ...
    dept_codes = departments or ([department] if department else [])
    if dept_codes:
        normalized = []
        for code in dept_codes:
            fmt = ensure_department(code, code, country) or format_department(code, country)
            if fmt:
                normalized.append(fmt)
        if normalized:
            query = query.filter(Project.department.in_(normalized))
```

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: filter projects API by multiple departments"
```

---

### Task 3: Frontend live UI — statut cross_department

**Files:**
- Modify: `frontend/src/lib/run-article-batches.ts`
- Modify: `frontend/src/lib/run-article-batches.test.ts`
- Modify: `frontend/src/components/run-article-batches.tsx`
- Modify: `frontend/src/hooks/use-run-stream.ts`
- Modify: `frontend/src/components/run-steps-timeline.tsx`

- [ ] Add `cross_department` to `ArticleLineStatus` and `TERMINAL`
- [ ] Handler `project_imported_cross_department` in reducer: set status `cross_department`, store `importedDepartment` from `extracted_department`
- [ ] `StatusIcon`: blue check for `cross_department`
- [ ] Label: `importé → {code}` (extract dept code from string)
- [ ] `use-run-stream.ts`: handler with message « Import cross-dépt. : {name} »
- [ ] Timeline: label + color for `project_imported_cross_department`
- [ ] Remove `wrong_department` from SKIP_REASON_LABELS (or keep unused — prefer remove)
- [ ] Tests vitest for cross_department event
- [ ] Commit: `feat: show cross-department import status in live run panel`

---

### Task 4: Frontend project list — filtre départements

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/project-list.tsx`

- [ ] **Step 1: Update getProjects**

```typescript
export function getProjects(params?: { departments?: string[]; country?: string }) {
  const search = new URLSearchParams();
  params?.departments?.forEach((d) => search.append("departments", d));
  if (params?.country) search.set("country", params.country);
  const qs = search.toString();
  return request<Project[]>(`/api/projects${qs ? `?${qs}` : ""}`);
}
```

- [ ] **Step 2: ProjectList**

- Load country from `getConfig()` on mount (default FR)
- State `selectedDepartments: string[]`
- `DepartmentCombobox` above table
- `load()` calls `getProjects({ departments: selectedDepartments, country })` when departments non-empty; when empty, load all (no filter param)
- Show count with filter context: « X projet(s) » + hint if filtered
- Empty state when filter returns 0 but not loading

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: multi-department server-side filter on project list"
```

---

## Self-Review

| Requirement | Task |
|-------------|------|
| Import cross-dept with extracted department | 1 |
| No run stats increment | 1 |
| `project_imported_cross_department` event | 1, 3 |
| `ProcessedUrl` reason `cross_department` | 1 |
| API multi-dept server filter | 2, 4 |
| DepartmentCombobox on project table | 4 |
| Live UI distinct from done/ignored | 3 |
