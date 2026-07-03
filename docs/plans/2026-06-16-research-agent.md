
# Research Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local autonomous weekly research agent that searches construction articles via Exa, extracts structured project data via LLM, and aggregates results in PostgreSQL — with a Next.js/shadcn frontend.

**Architecture:** Monorepo with docker-compose (PostgreSQL + FastAPI + Next.js). Python agent pipeline handles Exa search/fetch, LLM extraction via Vercel AI Gateway, deduplication, and SSE progress. Frontend shows project list, settings accordion, and ColorOrb during runs.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, APScheduler, httpx, Pydantic | Next.js 15, shadcn/ui, motion/react | PostgreSQL 16 | Exa.ai | Vercel AI Gateway

---

### Task 1: Scaffold monorepo & docker-compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

**Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: research
      POSTGRES_PASSWORD: research
      POSTGRES_DB: research_agent
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  pgdata:
```

**Step 2: Create .env.example**

```bash
DATABASE_URL=postgresql://research:research@localhost:5432/research_agent
EXA_API_KEY=
AI_GATEWAY_API_KEY=
AI_MODEL=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Step 3: Create .gitignore** (Python, Node, .env, pgdata)

**Step 4: Init git repo**

```bash
git init
git add .
git commit -m "chore: scaffold monorepo with docker-compose"
```

---

### Task 2: Backend project setup

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Test: `backend/tests/test_health.py`

**Step 1: Write failing health test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test — expect FAIL**

```bash
cd backend && pip install -e ".[dev]" && pytest tests/test_health.py -v
```

**Step 3: Implement minimal FastAPI app**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://research:research@db:5432/research_agent"
    exa_api_key: str = ""
    ai_gateway_api_key: str = ""
    ai_model: str = "openai/gpt-4o"

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Research Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add FastAPI backend scaffold with health endpoint"
```

---

### Task 3: Database models & migrations

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/models/config.py`
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/source.py`
- Create: `backend/app/models/run.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/versions/001_initial.py`
- Test: `backend/tests/test_models.py`

**Step 1: Write failing test for Config model**

```python
def test_config_defaults(db_session):
    from app.models.config import Config
    config = Config(departments=["69", "38"])
    db_session.add(config)
    db_session.commit()
    assert config.sectors == ["industriel", "logistique", "retail"]
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement SQLAlchemy models**

Key fields per design doc:
- `Config`: departments (ARRAY), cron_day, cron_hour, sectors (ARRAY)
- `Project`: all fields + people (JSONB) + match_key (unique)
- `Source`: url (unique), project_id FK, run_id FK
- `Run`: status enum, stats counters

**Step 4: Create Alembic migration `001_initial.py`**

**Step 5: Run test — expect PASS**

**Step 6: Commit**

```bash
git commit -m "feat: add database models and initial migration"
```

---

### Task 4: Config API

**Files:**
- Create: `backend/app/api/config.py`
- Create: `backend/app/schemas/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_config_api.py`

**Step 1: Write failing test**

```python
def test_get_and_update_config(client, db_session):
    response = client.get("/api/config")
    assert response.status_code == 200
    response = client.put("/api/config", json={"departments": ["69", "01"]})
    assert response.status_code == 200
    assert response.json()["departments"] == ["69", "01"]
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement GET/PUT `/api/config`**

Auto-create default config row on first GET if none exists.

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add config API for department settings"
```

---

### Task 5: Exa client

**Files:**
- Create: `backend/app/agent/exa_client.py`
- Test: `backend/tests/test_exa_client.py`

**Step 1: Write failing test with mocked httpx**

```python
@pytest.mark.asyncio
async def test_search_returns_urls(mocker):
    mocker.patch("httpx.AsyncClient.post", return_value=mock_exa_response)
    from app.agent.exa_client import ExaClient
    client = ExaClient(api_key="test")
    results = await client.search("article entrepôt logistique département 69")
    assert len(results) > 0
    assert "url" in results[0]
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement ExaClient**

```python
class ExaClient:
    BASE_URL = "https://api.exa.ai"

    async def search(self, query: str, num_results: int = 10) -> list[dict]: ...
    async def fetch(self, urls: list[str], max_characters: int = 8000) -> list[dict]: ...
```

Use `httpx.AsyncClient`, headers `x-api-key`.

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add Exa search and fetch client"
```

---

### Task 6: LLM extractor

**Files:**
- Create: `backend/app/agent/schemas.py`
- Create: `backend/app/agent/llm_extractor.py`
- Test: `backend/tests/test_llm_extractor.py`

**Step 1: Define Pydantic extraction schema**

```python
class PersonSchema(BaseModel):
    name: str
    role: str | None = None
    company: str | None = None

class ProjectExtraction(BaseModel):
    name: str
    company: str | None = None
    surface_m2: float | None = None
    delivery_date: date | None = None
    city: str | None = None
    address: str | None = None
    department: str | None = None
    status: Literal["conception", "travaux", "livraison"] | None = None
    sector: Literal["industriel", "logistique", "retail"] | None = None
    people: list[PersonSchema] = []
```

**Step 2: Write failing test with mocked AI Gateway response**

**Step 3: Implement LLMExtractor**

POST to `https://ai-gateway.vercel.sh/v1/chat/completions` with:
- System prompt: context installateur solaire C&I, extract JSON
- `response_format: { type: "json_object" }`
- Parse and validate with `ProjectExtraction`

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add LLM structured extraction via Vercel AI Gateway"
```

---

### Task 7: Deduplication & upsert logic

**Files:**
- Create: `backend/app/agent/deduplication.py`
- Test: `backend/tests/test_deduplication.py`

**Step 1: Write failing tests**

```python
def test_make_match_key():
    assert make_match_key("Entrepôt XYZ", "Lyon", "LogiFrance") == "entrepot-xyz|lyon|logifrance"

def test_upsert_creates_new_project(db_session):
    ...

def test_upsert_updates_existing_and_merges_people(db_session):
    ...

def test_skip_duplicate_url(db_session):
    ...
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

- `make_match_key(name, city, company)` → slugify + lowercase
- `upsert_project(session, extraction, source_meta, run_id)` → create/update project, append source, merge people by name

Status priority: conception < travaux < livraison (keep most advanced).

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add project deduplication and upsert logic"
```

---

### Task 8: Agent pipeline

**Files:**
- Create: `backend/app/agent/pipeline.py`
- Create: `backend/app/agent/queries.py`
- Test: `backend/tests/test_pipeline.py`

**Step 1: Write failing integration test with all mocks**

```python
@pytest.mark.asyncio
async def test_pipeline_completes_run(db_session, mocker):
    mocker.patch("app.agent.exa_client.ExaClient.search", ...)
    mocker.patch("app.agent.exa_client.ExaClient.fetch", ...)
    mocker.patch("app.agent.llm_extractor.LLMExtractor.extract", ...)
    run = await run_pipeline(db_session)
    assert run.status == "completed"
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement `run_pipeline`**

```python
SECTOR_QUERIES = {
    "logistique": "article chantier construction entrepôt logistique département {dept} France 2025 2026",
    "industriel": "article nouveau bâtiment industriel département {dept} France projet construction",
    "retail": "article construction centre commercial retail département {dept} France",
}
```

Flow: load config → create run → loop dept × sector → search → filter known URLs → fetch → extract → upsert → complete run.

Emit events via callback for SSE (Task 9).

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add weekly research agent pipeline"
```

---

### Task 9: Runs API + SSE

**Files:**
- Create: `backend/app/api/runs.py`
- Create: `backend/app/schemas/run.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_runs_api.py`

**Step 1: Write failing tests**

```python
def test_trigger_run(client, mocker):
    mocker.patch("app.agent.pipeline.run_pipeline", ...)
    response = client.post("/api/runs")
    assert response.status_code == 202

def test_trigger_run_conflict_when_in_progress(client, db_session):
    # create in_progress run
    response = client.post("/api/runs")
    assert response.status_code == 409

def test_list_runs(client):
    response = client.get("/api/runs")
    assert response.status_code == 200
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement endpoints**

- `POST /api/runs` — trigger pipeline (background task), return run id
- `GET /api/runs` — list runs
- `GET /api/runs/{id}` — run detail
- `GET /api/runs/{id}/stream` — SSE stream (events: run_started, searching, extracting, project_found, run_completed, run_failed)

Use `asyncio.Queue` or in-memory event bus keyed by run_id.

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add runs API with SSE progress stream"
```

---

### Task 10: APScheduler cron

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_scheduler.py`

**Step 1: Write failing test**

```python
def test_scheduler_registers_weekly_job():
    from app.scheduler import create_scheduler
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    assert any(j.id == "weekly_research" for j in jobs)
```

**Step 2: Implement scheduler**

Read `cron_day` and `cron_hour` from config. Default: Monday 6h. Trigger `run_pipeline` on schedule.

Start scheduler in FastAPI `lifespan` context.

**Step 3: Run test — expect PASS**

**Step 4: Commit**

```bash
git commit -m "feat: add APScheduler weekly cron trigger"
```

---

### Task 11: Projects API

**Files:**
- Create: `backend/app/api/projects.py`
- Create: `backend/app/schemas/project.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_projects_api.py`

**Step 1: Write failing test**

```python
def test_list_projects_with_sources(client, db_session):
    # seed project + 2 sources
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert len(response.json()[0]["sources"]) == 2
```

**Step 2: Implement `GET /api/projects`**

Return projects ordered by `last_updated_at DESC`, nested sources array.

Optional query params: `department`, `status`, `sector`.

**Step 3: Run test — expect PASS**

**Step 4: Commit**

```bash
git commit -m "feat: add projects list API with nested sources"
```

---

### Task 12: Frontend scaffold (Next.js + shadcn)

**Files:**
- Create: `frontend/` via `npx create-next-app@latest`
- Init shadcn: `npx shadcn@latest init`

**Step 1: Scaffold Next.js app in `frontend/`**

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir
npx shadcn@latest init -d
npx shadcn@latest add accordion button card badge
```

**Step 2: Add ColorOrb component**

Extract `ColorOrb` from ai-input registry (motion/react dependency):

```bash
npm install motion class-variance-authority
```

Create `frontend/src/components/ui/color-orb.tsx` with the gradient orb animation only (no MorphPanel).

**Step 3: Verify dev server starts**

```bash
npm run dev
```

**Step 4: Commit**

```bash
git commit -m "feat: scaffold Next.js frontend with shadcn and ColorOrb"
```

---

### Task 13: Settings accordion

**Files:**
- Create: `frontend/src/components/settings-accordion.tsx`
- Create: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`

**Step 1: Implement API client**

```typescript
export async function getConfig(): Promise<Config> { ... }
export async function updateConfig(data: Partial<Config>): Promise<Config> { ... }
export async function triggerRun(): Promise<{ id: string }> { ... }
```

**Step 2: Build SettingsAccordion**

- Multi-select or checkbox list of French departments (codes 01–95, 2A, 2B)
- Save button → PUT `/api/config`
- "Lancer maintenant" button → POST `/api/runs`

Use shadcn Accordion + Button.

**Step 3: Manual test** — save departments, trigger run

**Step 4: Commit**

```bash
git commit -m "feat: add settings accordion with department config and manual trigger"
```

---

### Task 14: Project list & agent status

**Files:**
- Create: `frontend/src/components/project-list.tsx`
- Create: `frontend/src/components/project-card.tsx`
- Create: `frontend/src/components/agent-status.tsx`
- Create: `frontend/src/hooks/use-run-stream.ts`
- Modify: `frontend/src/app/page.tsx`

**Step 1: Implement SSE hook**

```typescript
export function useRunStream(runId: string | null) {
  // EventSource on GET /api/runs/{id}/stream
  // Return { status, message, stats }
}
```

**Step 2: Build AgentStatus**

Show ColorOrb (192px) when run is active. Display current step below orb.

**Step 3: Build ProjectCard**

Display: name, city (department), sector badge, status badge, surface, delivery date, company, people lines, collapsible sources list.

**Step 4: Build ProjectList**

Fetch `GET /api/projects`, render cards. Refresh on `run_completed` SSE event.

**Step 5: Wire page layout**

```
[AgentStatus + ColorOrb]
[SettingsAccordion]
[ProjectList]
```

**Step 6: Commit**

```bash
git commit -m "feat: add project list, agent status with ColorOrb, and SSE hook"
```

---

### Task 15: End-to-end local verification

**Files:**
- Modify: `README.md`

**Step 1: Start full stack**

```bash
cp .env.example .env
# Fill EXA_API_KEY, AI_GATEWAY_API_KEY, AI_MODEL
docker-compose up --build
```

**Step 2: Configure departments in UI**

Select 1–2 departments (e.g. 69, 38), save.

**Step 3: Trigger manual run**

Click "Lancer maintenant", verify ColorOrb animates, SSE events flow, projects appear in list.

**Step 4: Verify DB**

```bash
docker-compose exec db psql -U research -d research_agent -c "SELECT name, city, status FROM projects;"
```

**Step 5: Update README with setup instructions**

**Step 6: Commit**

```bash
git commit -m "docs: add README with local setup and verification steps"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-16-research-agent.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session (separate)** — Open a new session with executing-plans for batch execution with checkpoints

Which approach?
