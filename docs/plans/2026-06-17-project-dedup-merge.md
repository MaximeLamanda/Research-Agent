# Déduplication & merge de projets — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fusionner automatiquement les projets doublons via une `match_key` enrichie (pendant le run) et une passe fuzzy/LLM (fin de run), avec historique traçable et UI.

**Architecture:** Approche 1 — une seule clé `match_key` normalisée (tokens nom + ville, sans entreprise). Module `dedup_agent.py` pour fuzzy + LLM post-run. Table `project_merges` pour l'audit. Projets absorbés marqués `merged_into_id`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest, rapidfuzz (fuzzy), httpx (LLM) | Next.js 15, shadcn/ui | PostgreSQL 16

**Design doc:** `docs/plans/2026-06-17-project-dedup-merge-design.md`

---

### Task 1: Enrichir `make_match_key`

**Files:**
- Modify: `backend/app/agent/deduplication.py`
- Modify: `backend/tests/test_deduplication.py`

**Step 1: Write failing tests for new match_key**

```python
# backend/tests/test_deduplication.py

def test_make_match_key_ignores_company_and_prefixes():
    key_a = make_match_key("Méga-entrepôt Amazon Colombier-Saugnieu", "Colombier-Saugnieu", "Amazon")
    key_b = make_match_key("Entrepôt Amazon Colombier-Saugnieu", "Colombier-Saugnieu", "Amazon France")
    assert key_a == key_b
    assert "amazon" in key_a
    assert "colombier" in key_a

def test_make_match_key_different_projects():
    key_a = make_match_key("Entrepôt frigorifique Alderan", "Satolas-et-Bonce", "Alderan")
    key_b = make_match_key("Entrepôt frigorifique Activimmo", "Satolas-et-Bonce", "Activimmo")
    assert key_a != key_b
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_deduplication.py::test_make_match_key_ignores_company_and_prefixes -v`
Expected: FAIL

**Step 3: Implement normalization**

```python
# backend/app/agent/deduplication.py

import unicodedata
import re

PREFIXES = [
    "mega-entrepot", "entrepot frigorifique", "entrepot", "plateforme logistique",
]
STOPWORDS = {"pour", "avec", "dans", "chez", "site", "projet", "nouveau", "nouvelle"}

def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()

def _extract_name_tokens(name: str) -> list[str]:
    normalized = _normalize_text(name)
    for prefix in PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip(" -/")
    tokens = re.findall(r"[a-z0-9]{4,}", normalized)
    return sorted({t for t in tokens if t not in STOPWORDS})

def make_match_key(name: str, city: str | None, company: str | None = None) -> str:
    tokens = _extract_name_tokens(name or "unknown")
    token_part = "|".join(tokens) if tokens else "unknown"
    city_part = slugify(city or "unknown")
    return f"{token_part}|{city_part}"
```

Note: `company` gardé en paramètre pour compatibilité appels existants, ignoré dans la clé.

**Step 4: Update existing test**

```python
def test_make_match_key():
    key = make_match_key("Entrepôt XYZ", "Lyon", "LogiFrance")
    assert key == "entrepot|lyon"  # "entrepot" reste si seul token après strip
```

Ajuster l'assertion selon le comportement réel des tokens (affiner si « xyz » seul).

**Step 5: Run all dedup tests**

Run: `cd backend && pytest tests/test_deduplication.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/agent/deduplication.py backend/tests/test_deduplication.py
git commit -m "feat: enrich match_key with normalized name tokens and city"
```

---

### Task 2: Modèle `ProjectMerge` + colonnes DB

**Files:**
- Create: `backend/app/models/project_merge.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/run.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py` (`_migrate_schema`)
- Modify: `backend/tests/conftest.py`

**Step 1: Write failing model test**

```python
# backend/tests/test_models.py

def test_project_merge_model(db_session):
    from app.models.project_merge import ProjectMerge
    # create two projects + merge record, assert fields
```

**Step 2: Run test — expect FAIL**

Run: `cd backend && pytest tests/test_models.py -v`

**Step 3: Add models**

```python
# backend/app/models/project_merge.py
class ProjectMerge(Base):
    __tablename__ = "project_merges"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=True)
    kept_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"))
    absorbed_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"))
    method: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# backend/app/models/project.py — add:
merged_into_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=True)
```

```python
# backend/app/models/run.py — add:
projects_merged: Mapped[int] = mapped_column(Integer, default=0)
```

**Step 4: Add migration in `_migrate_schema`**

```python
# backend/app/main.py
if inspector.has_table("projects") and "merged_into_id" not in project_columns:
    connection.execute(text("ALTER TABLE projects ADD COLUMN merged_into_id UUID REFERENCES projects(id)"))
if inspector.has_table("runs") and "projects_merged" not in run_columns:
    connection.execute(text("ALTER TABLE runs ADD COLUMN projects_merged INTEGER NOT NULL DEFAULT 0"))
# project_merges created via create_all if not exists
```

**Step 5: Import `ProjectMerge` in conftest et `models/__init__.py`**

**Step 6: Run tests — expect PASS**

**Step 7: Commit**

```bash
git commit -m "feat: add project_merges table and merged_into_id column"
```

---

### Task 3: Fonction `merge_projects`

**Files:**
- Modify: `backend/app/agent/deduplication.py`
- Test: `backend/tests/test_deduplication.py`

**Step 1: Write failing merge test**

```python
def test_merge_projects_moves_sources_and_marks_absorbed(db_session):
    # Create project A and B with sources each
    # Call merge_projects(A, B, ...)
    # Assert B.merged_into_id == A.id
    # Assert all sources now on A
    # Assert ProjectMerge row created
```

**Step 2: Run — expect FAIL**

**Step 3: Implement `merge_projects`**

```python
def merge_projects(
    session: Session,
    kept: Project,
    absorbed: Project,
    *,
    run_id: uuid.UUID | None,
    method: str,
    score: float | None = None,
) -> ProjectMerge:
    snapshot = {
        "kept": {"name": kept.name, "company": kept.company, "city": kept.city},
        "absorbed": {"name": absorbed.name, "company": absorbed.company, "city": absorbed.city},
    }
    for source in absorbed.sources:
        source.project_id = kept.id
    kept.name = kept.name if len(kept.name) >= len(absorbed.name) else absorbed.name
    kept.company = _fill_field(kept.company, absorbed.company)
    # ... autres champs comme upsert existant
    absorbed.merged_into_id = kept.id
    merge = ProjectMerge(
        run_id=run_id,
        kept_project_id=kept.id,
        absorbed_project_id=absorbed.id,
        method=method,
        score=score,
        snapshot=snapshot,
    )
    session.add(merge)
    session.flush()
    return merge
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

---

### Task 4: Module `dedup_agent.py` (fuzzy + LLM)

**Files:**
- Create: `backend/app/agent/dedup_agent.py`
- Create: `backend/tests/test_dedup_agent.py`
- Modify: `backend/pyproject.toml` (add `rapidfuzz`)

**Step 1: Add dependency**

```bash
cd backend && uv add rapidfuzz  # or pip install rapidfuzz
```

**Step 2: Write failing tests**

```python
def test_fuzzy_score_same_project():
    assert name_similarity("Entrepôt Amazon Colombier", "Méga-entrepôt Amazon Colombier") >= 0.9

def test_find_candidates_same_department(db_session):
    # two projects same dept, high fuzzy → returned as pair

@pytest.mark.asyncio
async def test_llm_merge_decision_mocked(httpx_mock):
    # mock LLM returns same_project: true
```

**Step 3: Implement**

```python
# backend/app/agent/dedup_agent.py

FUZZY_AUTO_MERGE = 0.9
FUZZY_CANDIDATE_MIN = 0.6

def name_similarity(a: str, b: str) -> float:
    tokens_a = " ".join(_extract_name_tokens(a))
    tokens_b = " ".join(_extract_name_tokens(b))
    return fuzz.token_sort_ratio(tokens_a, tokens_b) / 100

def find_candidate_pairs(projects: list[Project]) -> list[tuple[Project, Project, float]]:
    pairs = []
    for i, p1 in enumerate(projects):
        for p2 in projects[i + 1:]:
            if p1.city and p2.city and slugify(p1.city) != slugify(p2.city):
                score = name_similarity(p1.name, p2.name)
                if score < FUZZY_CANDIDATE_MIN:
                    continue
            else:
                score = name_similarity(p1.name, p2.name)
                if score < FUZZY_CANDIDATE_MIN:
                    continue
            pairs.append((p1, p2, score))
    return pairs

async def ask_llm_same_project(llm: LLMExtractor, p1: Project, p2: Project) -> bool:
    # prompt JSON {same_project, reason}
    ...

async def run_dedup_pass(session: Session, run: Run, departments: list[str]) -> int:
    merged = 0
    for dept in departments:
        projects = session.query(Project).filter(
            Project.department == dept,
            Project.merged_into_id.is_(None),
        ).all()
        for p1, p2, score in find_candidate_pairs(projects):
            if score >= FUZZY_AUTO_MERGE:
                merge_projects(session, p1, p2, run_id=run.id, method="fuzzy", score=score)
                merged += 1
            elif score >= FUZZY_CANDIDATE_MIN:
                if await ask_llm_same_project(llm, p1, p2):
                    merge_projects(session, p1, p2, run_id=run.id, method="llm", score=score)
                    merged += 1
        session.commit()
    return merged
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

---

### Task 5: Intégrer dans le pipeline

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Modify: `backend/app/schemas/__init__.py` (`RunRead.projects_merged`)
- Modify: `backend/app/api/runs.py`
- Modify: `backend/app/api/projects.py` (filter `merged_into_id IS NULL`)

**Step 1: Write failing integration test**

```python
# backend/tests/test_dedup_agent.py or test_pipeline.py
@pytest.mark.asyncio
async def test_pipeline_runs_dedup_at_end(db_session, httpx_mock):
    # mock exa + llm, two similar projects → projects_merged > 0
```

**Step 2: Modify pipeline**

```python
# backend/app/agent/pipeline.py — before run_completed:

from app.agent.dedup_agent import run_dedup_pass

await emit_event(run_id, "deduplicating", {"message": "Consolidation des doublons…"})
merged_count = await run_dedup_pass(session, run, config.departments)
run.projects_merged = merged_count
session.commit()

await emit_event(run_id, "run_completed", {
    "articles_found": run.articles_found,
    "projects_new": run.projects_new,
    "projects_updated": run.projects_updated,
    "projects_merged": run.projects_merged,
})
```

**Step 3: Filter active projects in API**

```python
# backend/app/api/projects.py
query = db.query(Project).filter(Project.merged_into_id.is_(None))
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

---

### Task 6: Script migration `rematch_projects.py`

**Files:**
- Create: `backend/scripts/rematch_projects.py`

**Step 1: Implement script**

```python
"""Recalcule match_key et fusionne les collisions existantes."""
# 1. Load active projects
# 2. Group by new match_key
# 3. For groups > 1: keep oldest, merge others (method=match_key, run_id=None)
# 4. Print summary
# 5. Optionally call run_dedup_pass for fuzzy leftovers
```

**Step 2: Run manually**

Run: `cd backend && python scripts/rematch_projects.py`
Expected: log des merges effectués (Amazon, etc.)

**Step 3: Commit**

---

### Task 7: API historique des merges

**Files:**
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/api/projects.py`
- Create: `backend/tests/test_merge_api.py`

**Step 1: Add schemas**

```python
class ProjectMergeRead(BaseModel):
    id: str
    run_id: str | None
    kept_project_id: str
    absorbed_project_id: str
    method: str
    score: float | None
    snapshot: dict
    created_at: datetime | None
```

**Step 2: Add endpoints**

```python
@router.get("/{project_id}/merges", response_model=list[ProjectMergeRead])
def list_project_merges(project_id: uuid.UUID, db: Session = Depends(get_db)):
    # merges where kept_project_id == project_id OR absorbed_project_id == project_id

# backend/app/api/runs.py
@router.get("/{run_id}/merges", response_model=list[ProjectMergeRead])
def list_run_merges(run_id: uuid.UUID, db: Session = Depends(get_db)):
    ...
```

**Step 3: Write + run API tests**

**Step 4: Commit**

---

### Task 8: Frontend — historique merges + SSE

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/use-run-stream.ts`
- Modify: `frontend/src/components/project-table.tsx`
- Create: `frontend/src/components/merge-history-dialog.tsx`

**Step 1: Add API types + fetchers**

```typescript
export interface ProjectMerge {
  id: string;
  run_id: string | null;
  method: string;
  score: number | null;
  snapshot: { kept?: {...}; absorbed?: {...} };
  created_at: string | null;
}

export function getProjectMerges(projectId: string) {
  return request<ProjectMerge[]>(`/api/projects/${projectId}/merges`);
}
```

**Step 2: SSE handler `project_merged` + `deduplicating`**

```typescript
deduplicating: () => setState((s) => ({ ...s, message: "Consolidation des doublons…" })),
project_merged: (data) => setState((s) => ({
  ...s,
  message: `Fusion : ${data.absorbed_name} → ${data.kept_name}`,
})),
```

**Step 3: Merge history dialog on project row**

- Icône/bouton « Historique fusions » si `getProjectMerges` retourne des entrées
- Liste : nom absorbé, date, méthode (badge), run_id tronqué

**Step 4: Stats fin de run — afficher `projects_merged`**

**Step 5: Commit**

```bash
git commit -m "feat: merge history UI and SSE events for deduplication"
```

---

## Vérification finale

```bash
cd backend && pytest -v
cd frontend && npm run build
# Lancer un run manuel, vérifier :
# - Amazon Colombier-Saugnieu = 1 seule ligne
# - SSE affiche "Consolidation des doublons"
# - Historique merges visible sur le projet
```
