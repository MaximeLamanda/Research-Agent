# SIREN Enrichment, Run Steps & Test Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrichir les projets avec des données SIREN via `recherche-entreprises.api.gouv.fr` (décision LLM), persister un journal d'étapes consultable en temps réel et après coup, et ajouter un bouton « Test (1 lien) » qui ne traite que la première URL Exa du premier dept×secteur.

**Architecture:** Client HTTP direct vers l'API gouv (pas de MCP), `CompanyResolver` LLM pour choisir le candidat, table `run_steps` alimentée par `log_and_emit()` à chaque étape du pipeline, champ `Run.mode` (`full` | `test_single`). Le mode test limite la boucle à 1 dept × 1 secteur × 1 URL et saute la dédup.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx, pytest, Next.js 15, React 19, SSE

---

## File Map

| File | Responsibility |
|------|----------------|
| `backend/app/models/run_step.py` | Modèle SQLAlchemy `run_steps` |
| `backend/app/models/run.py` | Ajout `mode` sur `Run` |
| `backend/app/models/project.py` | Ajout `siren`, `company_legal_name`, `naf_code` |
| `backend/app/agent/entreprise_client.py` | Appel `recherche-entreprises.api.gouv.fr` |
| `backend/app/agent/company_resolver.py` | LLM choisit le bon candidat SIREN |
| `backend/app/agent/schemas.py` | `CompanyCandidate`, `CompanyResolution` |
| `backend/app/agent/pipeline.py` | `log_and_emit`, mode test, enrichissement SIREN |
| `backend/app/api/runs.py` | `POST` avec body `mode`, `GET /steps` |
| `backend/app/schemas/__init__.py` | `RunStepRead`, `RunCreate`, champs projet/run |
| `backend/app/main.py` | Migrations inline colonnes + table |
| `backend/tests/test_entreprise_client.py` | Tests client API gouv |
| `backend/tests/test_company_resolver.py` | Tests résolution LLM |
| `backend/tests/test_run_steps.py` | Tests persistance étapes |
| `backend/tests/test_pipeline_test_mode.py` | Tests mode test_single |
| `backend/tests/test_runs_api.py` | Tests API mode + steps endpoint |
| `frontend/src/lib/api.ts` | Types + `triggerTestRun` + `getRunSteps` |
| `frontend/src/hooks/use-agent-settings.ts` | `handleTestRun` |
| `frontend/src/hooks/use-run-stream.ts` | Handlers nouveaux événements |
| `frontend/src/components/run-detail-drawer.tsx` | Timeline des étapes |
| `frontend/src/app/page.tsx` | Bouton « Test (1 lien) » |
| `docs/plans/2026-06-25-siren-run-steps-test-design.md` | Design doc validé |

---

### Task 1: Modèle RunStep

**Files:**
- Create: `backend/app/models/run_step.py`
- Modify: `backend/app/models/run.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_run_steps.py`:

```python
import uuid

from app.models.run import Run
from app.models.run_step import RunStep


def test_run_step_model(db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_type="searching",
        message="Recherche articles — industriel (dept. 69)",
        data={"department": "69", "sector": "industriel", "query": "test query"},
    )
    db_session.add(step)
    db_session.commit()

    saved = db_session.query(RunStep).filter(RunStep.run_id == run.id).one()
    assert saved.step_type == "searching"
    assert saved.data["department"] == "69"
    assert saved.message is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_run_steps.py::test_run_step_model -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.run_step'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/models/run_step.py`:

```python
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=False, index=True)
    step_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run"] = relationship("Run", back_populates="steps")
```

Add to `backend/app/models/run.py` after `created_at`:

```python
    mode: Mapped[str] = mapped_column(String, nullable=False, default="full")
```

Add relationship in `Run` class:

```python
    steps: Mapped[list["RunStep"]] = relationship("RunStep", back_populates="run", order_by="RunStep.created_at")
```

Add TYPE_CHECKING import for RunStep in run.py.

Update `backend/app/models/__init__.py`:

```python
from app.models.run_step import RunStep

__all__ = [..., "RunStep"]
```

Update `backend/tests/conftest.py` import line:

```python
from app.models import Config, Project, ProjectMerge, ProjectUpdate, Run, RunStep, Source  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_run_steps.py::test_run_step_model -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/run_step.py backend/app/models/run.py backend/app/models/__init__.py backend/tests/conftest.py backend/tests/test_run_steps.py
git commit -m "feat: add RunStep model and Run.mode field"
```

---

### Task 2: Migrations inline

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add migration for runs.mode and projects SIREN fields and run_steps table**

In `_migrate_schema()` in `backend/app/main.py`, after the existing `runs` block:

```python
    if inspector.has_table("runs"):
        run_columns = {column["name"] for column in inspector.get_columns("runs")}
        with engine.begin() as connection:
            if "projects_merged" not in run_columns:
                connection.execute(
                    text("ALTER TABLE runs ADD COLUMN projects_merged INTEGER NOT NULL DEFAULT 0")
                )
            if "mode" not in run_columns:
                connection.execute(
                    text("ALTER TABLE runs ADD COLUMN mode VARCHAR NOT NULL DEFAULT 'full'")
                )

    if inspector.has_table("projects"):
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        with engine.begin() as connection:
            # ... existing columns ...
            if "siren" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN siren VARCHAR"))
            if "company_legal_name" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN company_legal_name VARCHAR"))
            if "naf_code" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN naf_code VARCHAR"))
```

Note: `Base.metadata.create_all()` already creates `run_steps` for new installs. Existing DBs get the table on next startup via `create_all` after model is registered.

- [ ] **Step 2: Verify app starts**

Run: `cd backend && TESTING=1 python -c "from app.main import app; print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add inline migrations for mode and SIREN columns"
```

---

### Task 3: Champs SIREN sur Project

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_project_siren_fields(db_session):
    from app.models.project import Project

    project = Project(
        name="Entrepôt Test",
        match_key="test|lyon",
        siren="123456789",
        company_legal_name="TEST SAS",
        naf_code="52.10B",
    )
    db_session.add(project)
    db_session.commit()

    saved = db_session.query(Project).one()
    assert saved.siren == "123456789"
    assert saved.company_legal_name == "TEST SAS"
    assert saved.naf_code == "52.10B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py::test_project_siren_fields -v`

Expected: FAIL — `TypeError: 'siren' is an invalid keyword argument`

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/models/project.py` after `company`:

```python
    siren: Mapped[str | None] = mapped_column(String)
    company_legal_name: Mapped[str | None] = mapped_column(String)
    naf_code: Mapped[str | None] = mapped_column(String)
```

Add to `ProjectRead` in `backend/app/schemas/__init__.py`:

```python
    siren: str | None = None
    company_legal_name: str | None = None
    naf_code: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models.py::test_project_siren_fields -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/project.py backend/app/schemas/__init__.py backend/tests/test_models.py
git commit -m "feat: add SIREN fields to Project model"
```

---

### Task 4: EntrepriseClient (API recherche-entreprises)

**Files:**
- Create: `backend/app/agent/entreprise_client.py`
- Test: `backend/tests/test_entreprise_client.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_entreprise_client.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.entreprise_client import EntrepriseClient, extract_dept_code


def test_extract_dept_code():
    assert extract_dept_code("69 - Rhône") == "69"
    assert extract_dept_code("BY - Bayern") is None
    assert extract_dept_code(None) is None


@pytest.mark.asyncio
async def test_search_returns_candidates():
    mock_response = {
        "results": [
            {
                "siren": "552032534",
                "nom_complet": "DANONE",
                "nom_raison_sociale": "DANONE",
                "activite_principale": "10.51C",
                "siege": {
                    "adresse": "17 BOULEVARD HAUSSMANN",
                    "code_postal": "75009",
                    "libelle_commune": "PARIS",
                    "departement": "75",
                },
            }
        ],
        "total_results": 1,
    }

    client = EntrepriseClient()
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_response):
        results = await client.search("Danone", departement="75")

    assert len(results) == 1
    assert results[0].siren == "552032534"
    assert results[0].nom_complet == "DANONE"
    assert results[0].naf_code == "10.51C"
    assert results[0].ville == "PARIS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_entreprise_client.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/agent/entreprise_client.py`:

```python
import httpx
from pydantic import BaseModel

BASE_URL = "https://recherche-entreprises.api.gouv.fr"


class CompanyCandidate(BaseModel):
    siren: str
    nom_complet: str
    nom_raison_sociale: str | None = None
    naf_code: str | None = None
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    departement: str | None = None


def extract_dept_code(department: str | None) -> str | None:
    if not department:
        return None
    code = department.split(" - ")[0].strip()
    return code if code.isdigit() and len(code) <= 3 else None


class EntrepriseClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def _get(self, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.base_url}/search", params=params)
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        query: str,
        *,
        departement: str | None = None,
        code_postal: str | None = None,
        per_page: int = 5,
    ) -> list[CompanyCandidate]:
        params: dict = {"q": query, "per_page": per_page}
        if departement:
            params["departement"] = departement
        if code_postal:
            params["code_postal"] = code_postal

        payload = await self._get(params)
        candidates: list[CompanyCandidate] = []
        for item in payload.get("results", []):
            siege = item.get("siege") or {}
            candidates.append(
                CompanyCandidate(
                    siren=str(item.get("siren", "")),
                    nom_complet=item.get("nom_complet") or item.get("nom_raison_sociale") or "",
                    nom_raison_sociale=item.get("nom_raison_sociale"),
                    naf_code=item.get("activite_principale"),
                    adresse=siege.get("adresse"),
                    code_postal=siege.get("code_postal"),
                    ville=siege.get("libelle_commune"),
                    departement=siege.get("departement"),
                )
            )
        return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_entreprise_client.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/entreprise_client.py backend/tests/test_entreprise_client.py
git commit -m "feat: add EntrepriseClient for recherche-entreprises API"
```

---

### Task 5: CompanyResolver (LLM décision)

**Files:**
- Create: `backend/app/agent/company_resolver.py`
- Modify: `backend/app/agent/schemas.py`
- Test: `backend/tests/test_company_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_company_resolver.py`:

```python
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.company_resolver import CompanyResolver
from app.agent.entreprise_client import CompanyCandidate
from app.agent.schemas import CompanyResolution


@pytest.mark.asyncio
async def test_resolve_picks_candidate():
    candidates = [
        CompanyCandidate(
            siren="552032534",
            nom_complet="DANONE",
            naf_code="10.51C",
            ville="PARIS",
        ),
        CompanyCandidate(
            siren="999999999",
            nom_complet="DANONE LOGISTIQUE",
            naf_code="52.10B",
            ville="LYON",
        ),
    ]

    llm_json = json.dumps(
        {
            "matched": True,
            "siren": "552032534",
            "company_legal_name": "DANONE",
            "naf_code": "10.51C",
            "confidence": "high",
            "reason": "Correspond au nom extrait et au contexte article.",
        }
    )

    resolver = CompanyResolver()
    with patch.object(resolver, "_call_llm", new_callable=AsyncMock, return_value=llm_json):
        result = await resolver.resolve(
            company_name="Danone",
            article_context="Danone investit dans un nouvel entrepôt à Paris.",
            candidates=candidates,
            city="Paris",
        )

    assert isinstance(result, CompanyResolution)
    assert result.matched is True
    assert result.siren == "552032534"
    assert result.company_legal_name == "DANONE"


@pytest.mark.asyncio
async def test_resolve_no_candidates():
    resolver = CompanyResolver()
    result = await resolver.resolve(
        company_name="Inconnue",
        article_context="texte",
        candidates=[],
    )
    assert result.matched is False
    assert result.siren is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_company_resolver.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/agent/schemas.py`:

```python
class CompanyResolution(BaseModel):
    matched: bool = False
    siren: str | None = None
    company_legal_name: str | None = None
    naf_code: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    reason: str | None = None
```

Create `backend/app/agent/company_resolver.py`:

```python
import json

import httpx

from app.agent.entreprise_client import CompanyCandidate
from app.agent.llm_extractor import parse_json_content
from app.agent.schemas import CompanyResolution
from app.config import settings

_RESOLVE_PROMPT = """Tu choisis quelle entreprise française correspond le mieux au contexte d'un article de presse.
On te donne le nom extrait de l'article, le contexte, la ville éventuelle, et une liste de candidats issus de recherche-entreprises.api.gouv.fr.

Retourne UNIQUEMENT un JSON valide (sans markdown) avec:
matched (true|false)
siren (string 9 chiffres ou null)
company_legal_name (string ou null)
naf_code (string ou null)
confidence (high|medium|low ou null)
reason (1 phrase en français expliquant le choix ou le rejet)

Règles:
- matched=true seulement si un candidat correspond clairement au promoteur/entreprise du projet décrit.
- En cas de doute entre plusieurs candidats homonymes, préfère celui dont la ville/département correspond au projet.
- Si aucun candidat ne convient, matched=false et siren=null.
"""


class CompanyResolver:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.ai_gateway_api_key
        self.model = model or settings.ai_model

    async def _call_llm(self, user_content: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://ai-gateway.vercel.sh/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _RESOLVE_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def resolve(
        self,
        *,
        company_name: str,
        article_context: str,
        candidates: list[CompanyCandidate],
        city: str | None = None,
    ) -> CompanyResolution:
        if not candidates:
            return CompanyResolution(matched=False, reason="Aucun candidat trouvé dans l'API gouv.")

        payload = {
            "company_name": company_name,
            "city": city,
            "article_excerpt": article_context[:1500],
            "candidates": [c.model_dump() for c in candidates],
        }
        content = await self._call_llm(json.dumps(payload, ensure_ascii=False))
        data = parse_json_content(content)
        return CompanyResolution.model_validate(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_company_resolver.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/company_resolver.py backend/app/agent/schemas.py backend/tests/test_company_resolver.py
git commit -m "feat: add CompanyResolver LLM for SIREN matching"
```

---

### Task 6: log_and_emit + messages d'étape

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Test: `backend/tests/test_run_steps.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_run_steps.py`:

```python
import pytest
from unittest.mock import AsyncMock

from app.agent.pipeline import log_and_emit, step_message
from app.models.run import Run
from app.models.run_step import RunStep


def test_step_message_searching():
    msg = step_message("searching", {"department": "69", "sector": "industriel"})
    assert "69" in msg
    assert "industriel" in msg


@pytest.mark.asyncio
async def test_log_and_emit_persists_step(db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.agent.pipeline.emit_event", AsyncMock())
        await log_and_emit(
            db_session,
            run.id,
            "extracting",
            {"url": "https://example.com", "title": "Test"},
        )

    steps = db_session.query(RunStep).filter(RunStep.run_id == run.id).all()
    assert len(steps) == 1
    assert steps[0].step_type == "extracting"
    assert steps[0].data["url"] == "https://example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_run_steps.py::test_log_and_emit_persists_step -v`

Expected: FAIL — `cannot import name 'log_and_emit'`

- [ ] **Step 3: Write minimal implementation**

Add to top of `backend/app/agent/pipeline.py`:

```python
from app.models.run_step import RunStep

_STEP_MESSAGES = {
    "run_started": "Run démarré",
    "searching": "Recherche articles — {sector} (dept. {department})",
    "extracting": "Analyse article : {title}",
    "company_searching": "Recherche SIREN pour {company}",
    "company_resolved": "SIREN identifié : {siren} ({company_legal_name})",
    "company_skipped": "SIREN non identifié : {reason}",
    "project_found": "Projet {'créé' if is_new else 'mis à jour'} : {name}",
    "deduplicating": "Consolidation des doublons…",
    "project_merged": "Fusion : {absorbed_name} → {kept_name}",
    "run_completed": "Run terminé",
    "run_failed": "Run échoué : {error}",
}


def step_message(event: str, data: dict | None) -> str:
    data = data or {}
    template = _STEP_MESSAGES.get(event, event)
    try:
        return template.format(**data)
    except KeyError:
        return template


async def log_and_emit(
    session: Session,
    run_id: uuid.UUID,
    event: str,
    data: dict | None = None,
):
    message = step_message(event, data)
    session.add(
        RunStep(
            run_id=run_id,
            step_type=event,
            message=message,
            data=data or {},
        )
    )
    session.commit()
    await emit_event(run_id, event, data)
```

Replace all `await emit_event(run_id, ...)` calls in `pipeline.py` with `await log_and_emit(session, run_id, ...)`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_run_steps.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_run_steps.py
git commit -m "feat: persist run steps via log_and_emit"
```

---

### Task 7: Enrichissement SIREN dans le pipeline

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Modify: `backend/app/agent/deduplication.py`
- Test: `backend/tests/test_pipeline_siren.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_siren.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.entreprise_client import CompanyCandidate
from app.agent.schemas import CompanyResolution, ProjectExtraction
from app.agent.pipeline import enrich_company


@pytest.mark.asyncio
async def test_enrich_company_applies_resolution():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Entrepôt Amazon",
        company="Amazon France Logistique",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
    )
    entreprise = MagicMock()
    entreprise.search = AsyncMock(
        return_value=[
            CompanyCandidate(
                siren="123456789",
                nom_complet="AMAZON FRANCE LOGISTIQUE",
                naf_code="52.10B",
                ville="COLombier-Saugnieu",
            )
        ]
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock(
        return_value=CompanyResolution(
            matched=True,
            siren="123456789",
            company_legal_name="AMAZON FRANCE LOGISTIQUE",
            naf_code="52.10B",
            confidence="high",
            reason="ok",
        )
    )

    result = await enrich_company(
        extraction,
        article_text="Amazon construit un entrepôt...",
        country="FR",
        entreprise=entreprise,
        resolver=resolver,
    )

    assert result.siren == "123456789"
    assert result.company_legal_name == "AMAZON FRANCE LOGISTIQUE"
    entreprise.search.assert_awaited_once()
    resolver.resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_company_skips_non_fr():
    extraction = ProjectExtraction(is_relevant=True, name="Halle", company="Firma GmbH")
    result = await enrich_company(extraction, article_text="text", country="DE")
    assert result.matched is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pipeline_siren.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/agent/pipeline.py`:

```python
from app.agent.company_resolver import CompanyResolver
from app.agent.entreprise_client import EntrepriseClient, extract_dept_code
from app.agent.schemas import CompanyResolution

async def enrich_company(
    extraction: ProjectExtraction,
    *,
    article_text: str,
    country: str,
    entreprise: EntrepriseClient | None = None,
    resolver: CompanyResolver | None = None,
) -> CompanyResolution:
    if country != "FR" or not extraction.company:
        return CompanyResolution(matched=False, reason="Pas d'entreprise ou pays non FR")

    entreprise = entreprise or EntrepriseClient()
    resolver = resolver or CompanyResolver()
    dept_code = extract_dept_code(extraction.department)
    candidates = await entreprise.search(
        extraction.company,
        departement=dept_code,
    )
    return await resolver.resolve(
        company_name=extraction.company,
        article_context=article_text,
        candidates=candidates,
        city=extraction.city,
    )
```

In the article processing loop (after successful LLM extract, when `is_relevant` and `extraction.company`), add:

```python
                    company_resolution = CompanyResolution(matched=False)
                    if extraction.is_relevant and extraction.company and country == "FR":
                        await log_and_emit(
                            session, run_id, "company_searching",
                            {"company": extraction.company, "url": url},
                        )
                        company_resolution = await enrich_company(
                            extraction,
                            article_text=text,
                            country=country,
                        )
                        if company_resolution.matched:
                            await log_and_emit(
                                session, run_id, "company_resolved",
                                {
                                    "siren": company_resolution.siren,
                                    "company_legal_name": company_resolution.company_legal_name,
                                },
                            )
                        else:
                            await log_and_emit(
                                session, run_id, "company_skipped",
                                {"reason": company_resolution.reason or "non identifié"},
                            )
```

Update `upsert_project` signature in `deduplication.py`:

```python
def upsert_project(
    session: Session,
    extraction: ProjectExtraction,
    *,
    url: str,
    title: str | None,
    raw_excerpt: str | None,
    run_id: uuid.UUID,
    country: str = "FR",
    company_resolution: CompanyResolution | None = None,
) -> tuple[Project, bool]:
```

Add to `TRACKED_FIELDS` in `deduplication.py`:

```python
TRACKED_FIELDS = (
    ...
    "siren",
    "company_legal_name",
    "naf_code",
)
```

When creating/updating project, apply resolution if matched:

```python
    if company_resolution and company_resolution.matched:
        if is_new or not project.siren:
            project.siren = company_resolution.siren
        project.company_legal_name = _fill_field(
            project.company_legal_name, company_resolution.company_legal_name
        )
        project.naf_code = _fill_field(project.naf_code, company_resolution.naf_code)
```

Pass `company_resolution=company_resolution` from pipeline to `upsert_project`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_pipeline_siren.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/app/agent/deduplication.py backend/tests/test_pipeline_siren.py
git commit -m "feat: enrich projects with SIREN via gouv API and LLM"
```

---

### Task 8: Mode test_single dans le pipeline

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Test: `backend/tests/test_pipeline_test_mode.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_test_mode.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.models.config import Config
from app.models.run import Run


@pytest.mark.asyncio
async def test_test_single_mode_processes_one_url(db_session):
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

    fake_search = [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}]
    fake_fetch = [{"url": "https://a.com/1", "title": "A", "text": "x" * 120}]
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=__import__("app.agent.schemas", fromlist=["ProjectExtraction"]).ProjectExtraction(
            is_relevant=False, name="skip"
        )
    )

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock) as dedup,
        patch("app.agent.pipeline.log_and_emit", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    exa.fetch.assert_awaited_once()
    fetched_urls = exa.fetch.await_args.args[0]
    assert fetched_urls == ["https://a.com/1"]
    dedup.assert_not_awaited()
    db_session.refresh(run)
    assert run.status == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pipeline_test_mode.py -v`

Expected: FAIL (dedup called or multiple URLs fetched)

- [ ] **Step 3: Write minimal implementation**

Change `run_pipeline` signature:

```python
async def run_pipeline(session: Session, run_id: uuid.UUID | None = None) -> Run:
```

At start, read `run.mode`:

```python
    test_single = run.mode == "test_single"
```

Replace department/sector loops:

```python
        departments = config.departments[:1] if test_single else config.departments
        sectors = config.sectors[:1] if test_single else config.sectors

        for department in departments:
            for sector in sectors:
                ...
                new_urls = [...]
                if test_single and new_urls:
                    new_urls = new_urls[:1]

                ...
                for item in fetched:
                    ...
                    # after processing one article in test_single, break out
                    if test_single:
                        break
                if test_single:
                    break
            if test_single:
                break

        if not test_single:
            await log_and_emit(session, run_id, "deduplicating", {"message": "..."})
            merged_events = await run_dedup_pass(...)
            ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pipeline_test_mode.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_pipeline_test_mode.py
git commit -m "feat: add test_single run mode (1 URL, no dedup)"
```

---

### Task 9: API runs — mode + endpoint steps

**Files:**
- Modify: `backend/app/api/runs.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_runs_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_runs_api.py`:

```python
from app.models.run import Run
from app.models.run_step import RunStep


def test_trigger_test_run(client):
    with patch("app.api.runs.run_pipeline", new_callable=AsyncMock):
        response = client.post("/api/runs", json={"mode": "test_single"})
    assert response.status_code == 202
    assert response.json()["mode"] == "test_single"


def test_list_run_steps(client, db_session):
    run = Run(status="completed", mode="full")
    db_session.add(run)
    db_session.flush()
    db_session.add(
        RunStep(
            run_id=run.id,
            step_type="searching",
            message="test",
            data={"department": "69"},
        )
    )
    db_session.commit()

    response = client.get(f"/api/runs/{run.id}/steps")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["step_type"] == "searching"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_runs_api.py::test_trigger_test_run tests/test_runs_api.py::test_list_run_steps -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/schemas/__init__.py`:

```python
from typing import Literal

class RunCreate(BaseModel):
    mode: Literal["full", "test_single"] = "full"


class RunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    step_type: str
    message: str | None = None
    data: dict = Field(default_factory=dict)
    created_at: datetime | None = None
```

Add `mode: str = "full"` to `RunRead`.

In `backend/app/api/runs.py`:

```python
from app.models.run_step import RunStep
from app.schemas import RunCreate, RunStepRead

def _run_to_read(run: Run) -> RunRead:
    return RunRead(..., mode=run.mode)

@router.post("", status_code=202, response_model=RunRead)
def trigger_run(
    background_tasks: BackgroundTasks,
    body: RunCreate | None = None,
    db: Session = Depends(get_db),
):
    mode = (body.mode if body else "full")
    ...
    run = Run(status="pending", mode=mode)
    ...

@router.get("/{run_id}/steps", response_model=list[RunStepRead])
def list_run_steps(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = (
        db.query(RunStep)
        .filter(RunStep.run_id == run_id)
        .order_by(RunStep.created_at.asc())
        .all()
    )
    return [
        RunStepRead(
            id=str(step.id),
            run_id=str(step.run_id),
            step_type=step.step_type,
            message=step.message,
            data=step.data or {},
            created_at=step.created_at,
        )
        for step in steps
    ]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_runs_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/runs.py backend/app/schemas/__init__.py backend/tests/test_runs_api.py
git commit -m "feat: add run mode API and GET /runs/{id}/steps"
```

---

### Task 10: Frontend — API client et types

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add types and functions**

```typescript
export interface RunStep {
  id: string;
  run_id: string;
  step_type: string;
  message: string | null;
  data: Record<string, unknown>;
  created_at: string | null;
}

// Add to Run interface:
  mode: string;

// Add to Project interface:
  siren: string | null;
  company_legal_name: string | null;
  naf_code: string | null;

export function getRunSteps(runId: string) {
  return request<RunStep[]>(`/api/runs/${runId}/steps`);
}

export function triggerRun(mode: "full" | "test_single" = "full") {
  return request<Run>(" /api/runs", { method: "POST", body: JSON.stringify({ mode }) });
}

export function triggerTestRun() {
  return triggerRun("test_single");
}
```

Fix typo: path is `"/api/runs"` not `" /api/runs"`.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build`

Expected: build succeeds (or `npx tsc --noEmit` if faster)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add run steps API client and test run trigger"
```

---

### Task 11: Bouton Test + hook settings

**Files:**
- Modify: `frontend/src/hooks/use-agent-settings.ts`
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Add handleTestRun to hook**

In `use-agent-settings.ts`, import `triggerTestRun` and add:

```typescript
  async function handleTestRun() {
    setLoading(true);
    try {
      if (!saved) {
        await updateConfig({ country, departments: selected, ... });
      }
      const run = await triggerTestRun();
      onRunStarted(run.id);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to start test run.");
    } finally {
      setLoading(false);
    }
  }
```

Export `handleTestRun` in return object.

- [ ] **Step 2: Add button in page.tsx**

Below « Run now », add:

```tsx
            {!active && (
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button ... onClick={settings.handleRun}>Run now</Button>
                <Button
                  variant="outline"
                  size="xl"
                  onClick={settings.handleTestRun}
                  disabled={settings.loading || settings.selected.length === 0 || !!settings.apiError}
                  className="min-w-48"
                >
                  Test (1 lien)
                </Button>
              </div>
            )}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-agent-settings.ts frontend/src/app/page.tsx
git commit -m "feat: add Test (1 lien) button in UI"
```

---

### Task 12: Timeline dans le drawer + handlers SSE

**Files:**
- Modify: `frontend/src/components/run-detail-drawer.tsx`
- Modify: `frontend/src/hooks/use-run-stream.ts`

- [ ] **Step 1: Add SSE handlers for company events**

In `use-run-stream.ts`, add to handlers:

```typescript
      company_searching: (data) =>
        setState((s) => ({
          ...s,
          message: `Recherche SIREN — ${data.company}`,
        })),
      company_resolved: (data) =>
        setState((s) => ({
          ...s,
          message: `SIREN trouvé : ${data.siren}`,
        })),
      company_skipped: (data) =>
        setState((s) => ({
          ...s,
          message: `SIREN non identifié`,
        })),
```

- [ ] **Step 2: Add timeline section to drawer**

In `run-detail-drawer.tsx`:

```typescript
import { getRunSteps, RunStep } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  run_started: "Démarrage",
  searching: "Recherche",
  extracting: "Extraction",
  company_searching: "Recherche SIREN",
  company_resolved: "SIREN identifié",
  company_skipped: "SIREN ignoré",
  project_found: "Projet",
  deduplicating: "Déduplication",
  project_merged: "Fusion",
  run_completed: "Terminé",
  run_failed: "Échec",
};
```

Add state `steps`, fetch in useEffect alongside merges/updates/sources:

```typescript
    Promise.all([..., getRunSteps(run.id)])
```

Add section **before** Updates:

```tsx
          <section className="space-y-3">
            <h3 className="text-sm font-medium">Timeline ({steps.length})</h3>
            {steps.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune étape enregistrée.</p>
            ) : (
              <ol className="relative border-l pl-4 space-y-3">
                {steps.map((step) => (
                  <li key={step.id} className="text-sm">
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(step.created_at)}
                    </span>
                    <p className="font-medium">
                      {STEP_LABELS[step.step_type] ?? step.step_type}
                    </p>
                    {step.message && (
                      <p className="text-xs text-muted-foreground">{step.message}</p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>
```

For runs `in_progress`, poll steps every 3s:

```typescript
  useEffect(() => {
    if (!open || !run || run.status !== "in_progress") return;
    const interval = setInterval(() => {
      getRunSteps(run.id).then(setSteps).catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [open, run]);
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/run-detail-drawer.tsx frontend/src/hooks/use-run-stream.ts
git commit -m "feat: show run step timeline in drawer"
```

---

### Task 13: Afficher SIREN sur les projets (UI)

**Files:**
- Modify: `frontend/src/components/project-detail-drawer.tsx` (or `project-card.tsx`)
- Modify: `frontend/src/lib/project-formatters.ts` if needed

- [ ] **Step 1: Display SIREN fields when present**

In project detail drawer, after company field:

```tsx
            {project.siren && (
              <p className="text-sm">
                <span className="text-muted-foreground">SIREN </span>
                {project.siren}
                {project.company_legal_name ? ` — ${project.company_legal_name}` : ""}
              </p>
            )}
            {project.naf_code && (
              <p className="text-sm">
                <span className="text-muted-foreground">NAF </span>
                {project.naf_code}
              </p>
            )}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/project-detail-drawer.tsx
git commit -m "feat: display SIREN on project detail"
```

---

### Task 14: Design doc + test suite complète

**Files:**
- Create: `docs/plans/2026-06-25-siren-run-steps-test-design.md`

- [ ] **Step 1: Write design doc** summarizing validated decisions from brainstorming.

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && pytest -v`

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add docs/plans/2026-06-25-siren-run-steps-test-design.md
git commit -m "docs: add SIREN enrichment and run steps design"
```

---

## Manual Test Plan

1. Démarrer `docker compose up` ou backend + frontend en local
2. Configurer au moins 1 département et secteur
3. Cliquer **Test (1 lien)** — vérifier dans l'onglet Runs :
   - `mode = test_single`
   - Timeline avec étapes : searching → extracting → (company_searching → company_resolved ou company_skipped) → run_completed
4. Si un projet pertinent est trouvé avec entreprise FR, vérifier SIREN sur la fiche projet
5. Cliquer **Run now** — vérifier que le run complet traite plusieurs URLs et inclut la dédup

---

## Self-Review

| Requirement | Task |
|-------------|------|
| API recherche-entreprises + décision LLM | Tasks 4, 5, 7 |
| Persistance étapes run | Tasks 1, 6, 9 |
| Affichage temps réel + drawer | Tasks 12 |
| Bouton test 1 lien (1er Exa) | Tasks 8, 9, 11 |
| Champs SIREN sur projet | Tasks 3, 7, 13 |
| Design doc | Task 14 |

No placeholders detected. Type names consistent: `CompanyResolution`, `RunStep`, `log_and_emit`, `test_single`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-siren-enrichment-run-steps-test-mode.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
