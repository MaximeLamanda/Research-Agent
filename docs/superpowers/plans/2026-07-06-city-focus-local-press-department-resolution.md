# City-Focus Presse Locale & Résolution Département Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** En mode `city_focus`, restreindre les recherches Exa à la presse locale du département ciblé, et corriger l'attribution départementale pour que le département suive la ville réelle de l'article (cross-import) au lieu de rester collé au département du run — avec rejet des articles hors pays.

**Architecture:** Un fichier JSON `local_press_domains/{country}.json` alimente un loader ; le pipeline passe `include_domains` à Exa uniquement quand `geographical_granularity == "city_focus"`. Un nouveau module `department_resolution.py` infère le département depuis les villes-ancres (`search_anchors`), détecte les localisations étrangères, et remplace la logique `ensure_department` aveugle du pipeline. Le flux `cross_department` existant est conservé ; les articles étrangers sont ignorés via `article_skipped` / `foreign_location`.

**Tech Stack:** Python 3.12, FastAPI, pytest, SQLAlchemy | Next.js 15, vitest

**Contexte bug (run `c7c7486c…`, 2026-07-06) :** Recherche dept 77 en `city_focus` → Exa renvoie Corée/Suède/Chine ; le LLM hallucine `department: "77 - Seine-et-Marne"` pour Yongin et Södertälje ; `ensure_department` confirme le 77 car `extracted == target`. Aucun `include_domains` n'est utilisé aujourd'hui malgré le sandbox Rhône.

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `backend/app/data/local_press_domains/fr.json` | Domaines presse locale par code département |
| `backend/app/data/local_press_domains/de.json` | Squelette DE (vide ou minimal) |
| `backend/app/data/local_press_loader.py` | `local_press_domains_for_department(code, country)` |
| `backend/app/agent/department_resolution.py` | Inférence ville→dept, détection étranger, résolution |
| `backend/app/agent/pipeline.py` | `include_domains` city_focus + appel résolution dept |
| `backend/app/agent/llm_extractor.py` | Prompt : interdiction d'inventer le dept du run |
| `backend/tests/test_local_press_loader.py` | Tests loader |
| `backend/tests/test_department_resolution.py` | Tests résolution (nouveau) |
| `backend/tests/test_city_focus_search.py` | Test pipeline → `include_domains` (nouveau) |
| `backend/tests/test_cross_department_import.py` | Ajout tests ville-ancre + étranger |
| `frontend/src/lib/run-article-batches.ts` | Libellé `foreign_location` |
| `frontend/src/components/run-steps-timeline.tsx` | (optionnel) déjà couvert par message backend |

---

### Task 1: Données presse locale + loader

**Files:**
- Create: `backend/app/data/local_press_domains/fr.json`
- Create: `backend/app/data/local_press_domains/de.json`
- Create: `backend/app/data/local_press_loader.py`
- Create: `backend/tests/test_local_press_loader.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_local_press_loader.py`:

```python
from app.data.local_press_loader import local_press_domains_for_department


def test_returns_domains_for_seine_et_marne():
    domains = local_press_domains_for_department("77", "FR")
    assert "actu.fr" in domains
    assert "leparisien.fr" in domains
    assert len(domains) >= 3


def test_returns_domains_for_rhone():
    domains = local_press_domains_for_department("69", "FR")
    assert "leprogres.fr" in domains


def test_returns_empty_for_unknown_department():
    assert local_press_domains_for_department("99", "FR") == []


def test_returns_empty_for_unsupported_country():
    assert local_press_domains_for_department("77", "XX") == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_local_press_loader.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.data.local_press_loader`

- [ ] **Step 3: Create data files**

Create `backend/app/data/local_press_domains/fr.json` (sources validées : historique base locale + sandbox Rhône) :

```json
{
  "69": [
    "leprogres.fr",
    "lyoncapitale.fr",
    "lyonmag.com",
    "brefeco.com",
    "lechodutriangle.com"
  ],
  "77": [
    "actu.fr",
    "leparisien.fr",
    "mesinfos.fr",
    "info.fr",
    "lemoniteur.fr"
  ],
  "91": [
    "actu.fr",
    "leparisien.fr",
    "lechorepublicain.fr",
    "mesinfos.fr"
  ],
  "93": [
    "actu.fr",
    "leparisien.fr",
    "leparisien.fr",
    "seine-saint-denis.fr"
  ],
  "94": [
    "actu.fr",
    "leparisien.fr",
    "mesinfos.fr"
  ],
  "78": [
    "actu.fr",
    "lagazette-yvelines.fr",
    "leparisien.fr"
  ]
}
```

**Note :** retirer le doublon `leparisien.fr` dans `93` avant commit. Étendre progressivement aux autres départements configurés ; pour les codes absents, le loader retourne `[]` et le pipeline fera une recherche sans filtre domaine (voir Task 2).

Create `backend/app/data/local_press_domains/de.json` :

```json
{}
```

- [ ] **Step 4: Implement loader**

Create `backend/app/data/local_press_loader.py`:

```python
"""Domaines de presse locale par département / Land pour les recherches Exa city_focus."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.data.departments import _normalize_code

_DATA_DIR = Path(__file__).resolve().parent / "local_press_domains"


@lru_cache
def _load_domains(country: str) -> dict[str, list[str]]:
    path = _DATA_DIR / f"{country.lower()}.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for code, domains in raw.items():
        normalized = _normalize_code(str(code), country.upper())
        if not isinstance(domains, list):
            continue
        cleaned = []
        seen: set[str] = set()
        for domain in domains:
            if not isinstance(domain, str):
                continue
            d = domain.strip().lower()
            if d and d not in seen:
                seen.add(d)
                cleaned.append(d)
        if cleaned:
            result[normalized] = cleaned
    return result


def local_press_domains_for_department(code: str, country: str = "FR") -> list[str]:
    """Domaines presse locale pour un département ; liste vide si non configuré."""
    normalized = _normalize_code(code.strip(), country.upper())
    return list(_load_domains(country.upper()).get(normalized, []))
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python3 -m pytest tests/test_local_press_loader.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/data/local_press_domains/ backend/app/data/local_press_loader.py backend/tests/test_local_press_loader.py
git commit -m "feat: local press domain loader for city_focus Exa searches"
```

---

### Task 2: Pipeline — `include_domains` en mode `city_focus`

**Files:**
- Modify: `backend/app/agent/pipeline.py:325-337`
- Create: `backend/tests/test_city_focus_search.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_city_focus_search.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.models.config import Config
from app.models.run import Run


def _city_focus_config():
    return Config(
        country="FR",
        departments=["77"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
        geographical_granularity="city_focus",
        region_cities={"77": ["Meaux", "Chelles"]},
    )


@pytest.mark.asyncio
async def test_city_focus_passes_local_press_include_domains(db_session):
    config = _city_focus_config()
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single", geographical_granularity="city_focus")
    db_session.add(run)
    db_session.commit()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor"),
        patch("app.agent.pipeline.UrlPrefilter") as prefilter_cls,
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock, return_value=[]),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=[])
        prefilter_cls.return_value.select = AsyncMock(return_value={})

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    kwargs = exa.search.await_args.kwargs
    assert kwargs.get("include_domains") is not None
    assert "actu.fr" in kwargs["include_domains"]
    assert "leparisien.fr" in kwargs["include_domains"]


@pytest.mark.asyncio
async def test_large_granularity_does_not_pass_include_domains(db_session):
    config = _city_focus_config()
    config.geographical_granularity = "large"
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single", geographical_granularity="large")
    db_session.add(run)
    db_session.commit()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor"),
        patch("app.agent.pipeline.UrlPrefilter") as prefilter_cls,
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock, return_value=[]),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=[])
        prefilter_cls.return_value.select = AsyncMock(return_value={})

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    kwargs = exa.search.await_args.kwargs
    assert kwargs.get("include_domains") is None
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_city_focus_search.py -v
```

- [ ] **Step 3: Implement in pipeline**

Add import at top of `backend/app/agent/pipeline.py`:

```python
from app.data.local_press_loader import local_press_domains_for_department
```

Inside the search loop, before `search_results = await exa.search(...)`, compute domains:

```python
                include_domains: list[str] | None = None
                if (config.geographical_granularity or "large") == "city_focus":
                    domains = local_press_domains_for_department(department, country)
                    if domains:
                        include_domains = domains
```

Pass to `exa.search`:

```python
                    search_results = await exa.search(
                        query,
                        num_results=EXA_NUM_RESULTS,
                        search_type=config.exa_search_type,
                        category=config.exa_category or None,
                        start_published_date=(
                            effective_start.isoformat() if effective_start else None
                        ),
                        end_published_date=(
                            effective_end.isoformat() if effective_end else None
                        ),
                        include_domains=include_domains,
                        exclude_domains=exa_exclude_domains(config.exa_category or None),
                    )
```

Enrichir le payload `exa_search_start` / `exa_search_done` avec `"include_domains": include_domains` pour l'observabilité.

- [ ] **Step 4: Run tests**

```bash
cd backend && python3 -m pytest tests/test_city_focus_search.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_city_focus_search.py
git commit -m "feat: restrict Exa search to local press domains in city_focus mode"
```

---

### Task 3: Module `department_resolution`

**Files:**
- Create: `backend/app/agent/department_resolution.py`
- Create: `backend/tests/test_department_resolution.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_department_resolution.py`:

```python
from app.agent.department_resolution import (
    department_from_anchor_city,
    is_foreign_location,
    resolve_extraction_department,
)
from app.agent.schemas import ProjectExtraction


def test_department_from_anchor_city_meaux():
    assert department_from_anchor_city("Meaux", "FR") == "77"


def test_department_from_anchor_city_lyon():
    assert department_from_anchor_city("Lyon", "FR") == "69"


def test_department_from_anchor_city_unknown():
    assert department_from_anchor_city("Yongin", "FR") is None


def test_is_foreign_location_korea():
    assert is_foreign_location(
        "Yongin",
        "727 Jigok-dong, Giheung-gu, Yongin, Gyeonggi, South Korea",
        "",
    )


def test_is_foreign_location_sweden():
    assert is_foreign_location("Södertälje", "Stockholm Syd, Sweden", "")


def test_is_foreign_location_french_city():
    assert not is_foreign_location("Meaux", "Zone industrielle, Meaux", "Seine-et-Marne")


def test_resolve_overrides_hallucinated_target_dept_with_city_anchor():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Amazon warehouse",
        city="Lyon",
        department="77 - Seine-et-Marne",
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "cross_department"
    assert resolved.department == "69 - Rhône"


def test_resolve_keeps_target_when_city_in_target():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Local plant",
        city="Meaux",
        department=None,
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "ok"
    assert resolved.department == "77 - Seine-et-Marne"


def test_resolve_foreign_location():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="LivsMed facility",
        city="Yongin",
        department="77 - Seine-et-Marne",
        address="South Korea",
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "foreign"
    assert resolved is extraction
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_department_resolution.py -v
```

- [ ] **Step 3: Implement**

Create `backend/app/agent/department_resolution.py`:

```python
"""Résolution du département extrait : ville-ancre, détection étranger, cross-dept."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from app.agent.schemas import ProjectExtraction
from app.data.departments import ensure_department, format_department, normalize_department
from app.data.search_anchors_loader import anchors_for_country

ResolutionKind = Literal["ok", "cross_department", "foreign"]

_FOREIGN_MARKERS = re.compile(
    r"\b("
    r"south\s+korea|north\s+korea|\bkorea\b|republic\s+of\s+korea|"
    r"sweden|stockholm|södertälje|sodertalje|"
    r"\bchina\b|chinese|beijing|shanghai|hunan|shandong|"
    r"germany|deutschland|berlin|munich|münchen|"
    r"japan|tokyo|"
    r"united\s+states|\busa\b|"
    r"united\s+kingdom|\buk\b|london|"
    r"gyeonggi|"
    r")\b",
    re.IGNORECASE,
)

_FR_COUNTRY_MARKERS = re.compile(
    r"\b(france|français|francais|île-de-france|ile-de-france)\b",
    re.IGNORECASE,
)


def _normalize_city(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _city_to_department_map(country: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for code, entry in anchors_for_country(country).items():
        for city in entry.get("cities") or []:
            mapping[_normalize_city(city)] = code
    return mapping


def department_from_anchor_city(city: str | None, country: str = "FR") -> str | None:
    if not city or not city.strip():
        return None
    return _city_to_department_map(country).get(_normalize_city(city))


def is_foreign_location(
    city: str | None,
    address: str | None,
    article_text: str,
) -> bool:
    blob = " ".join(filter(None, [city, address, article_text[:500] if article_text else ""]))
    if not blob.strip():
        return False
    if _FR_COUNTRY_MARKERS.search(blob):
        return False
    return bool(_FOREIGN_MARKERS.search(blob))


def resolve_extraction_department(
    extraction: ProjectExtraction,
    *,
    target_department_code: str,
    country: str = "FR",
) -> tuple[ProjectExtraction, ResolutionKind]:
    if is_foreign_location(extraction.city, extraction.address, ""):
        return extraction, "foreign"

    target_department = format_department(target_department_code, country)
    city_dept_code = department_from_anchor_city(extraction.city, country)

    if city_dept_code:
        city_department = format_department(city_dept_code, country)
        if city_department and city_department != target_department:
            extraction.department = city_department
            return extraction, "cross_department"
        if city_department:
            extraction.department = city_department
            return extraction, "ok"

    extracted_department = normalize_department(extraction.department, country)
    if (
        extracted_department
        and target_department
        and extracted_department != target_department
    ):
        extraction.department = extracted_department
        return extraction, "cross_department"

    extraction.department = ensure_department(
        extraction.department, target_department_code, country
    )
    return extraction, "ok"
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python3 -m pytest tests/test_department_resolution.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/department_resolution.py backend/tests/test_department_resolution.py
git commit -m "feat: resolve extraction department from anchor cities and detect foreign locations"
```

---

### Task 4: Pipeline — intégrer résolution + skip étranger

**Files:**
- Modify: `backend/app/agent/pipeline.py:494-520`
- Modify: `backend/tests/test_cross_department_import.py`
- Modify: `backend/tests/test_article_skipped.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_cross_department_import.py`:

```python
@pytest.mark.asyncio
async def test_city_anchor_overrides_hallucinated_run_department(db_session):
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

    fake_search = [{"url": "https://example.com/lyon", "title": "Usine Lyon", "score": 0.9}]
    fake_fetch = [{"url": "https://example.com/lyon", "title": "Usine Lyon", "text": "x" * 120}]
    emit_mock = AsyncMock()
    project_mock = SimpleNamespace(id=uuid4(), name="Usine Lyon")
    upsert_mock = MagicMock(return_value=(project_mock, True))

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
                name="Usine Lyon",
                city="Lyon",
                department="77 - Seine-et-Marne",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    extraction_arg = upsert_mock.call_args.args[1]
    assert extraction_arg.department == "69 - Rhône"
    cross_events = [c for c in emit_mock.await_args_list if c.args[1] == "project_imported_cross_department"]
    assert len(cross_events) == 1
```

Add to `backend/tests/test_article_skipped.py`:

```python
@pytest.mark.asyncio
async def test_emits_article_skipped_for_foreign_location(db_session):
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

    fake_search = [{"url": "https://example.com/kr", "title": "LivsMed", "score": 0.9}]
    fake_fetch = [{"url": "https://example.com/kr", "title": "LivsMed", "text": "x" * 120}]
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
                name="LivsMed Yongin",
                city="Yongin",
                address="South Korea",
                department="77 - Seine-et-Marne",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped" and c.args[2].get("reason") == "foreign_location"
    ]
    assert len(skipped) == 1
    upsert_mock.assert_not_called()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_cross_department_import.py::test_city_anchor_overrides_hallucinated_run_department tests/test_article_skipped.py::test_emits_article_skipped_for_foreign_location -v
```

- [ ] **Step 3: Replace department block in pipeline**

Add import:

```python
from app.agent.department_resolution import resolve_extraction_department
```

Replace lines 494–506 with:

```python
                    resolution, resolution_kind = resolve_extraction_department(
                        extraction,
                        target_department_code=department,
                        country=country,
                    )
                    extraction = resolution
                    target_department = format_department(department, country)
                    extracted_department = normalize_department(extraction.department, country)
                    cross_department = resolution_kind == "cross_department"

                    if resolution_kind == "foreign":
                        mark_url_seen(session, url, "foreign_location", run_id)
                        known_urls.add(url)
                        session.commit()
                        await _emit_article_skipped(
                            session,
                            run_id,
                            url=url,
                            title=title,
                            reason="foreign_location",
                            extra={"city": extraction.city},
                        )
                        continue
```

Le reste du bloc `cross_department` / `project_found` / stats reste inchangé (l.501+).

- [ ] **Step 4: Run full backend tests**

```bash
cd backend && python3 -m pytest tests/test_department_resolution.py tests/test_cross_department_import.py tests/test_article_skipped.py tests/test_city_focus_search.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_cross_department_import.py backend/tests/test_article_skipped.py
git commit -m "feat: resolve department from city anchors and skip foreign articles"
```

---

### Task 5: Durcir le prompt LLM extraction

**Files:**
- Modify: `backend/app/agent/llm_extractor.py:36-37`

- [ ] **Step 1: Add rule to `_DEPARTMENT_RULES_FR`**

Append to `_DEPARTMENT_RULES_FR`:

```python
_DEPARTMENT_RULES_FR = """Pour department, déduis-le de la localisation précise du chantier (ville, adresse, contexte géographique). Ne devine pas : mets null si le département n'est pas identifiable dans l'article.
N'utilise JAMAIS le département de la recherche ou un département par défaut : si le chantier est à l'étranger ou hors de France, mets null pour department et is_relevant=false.
Utilise toujours le format "code - nom" avec le code département à 2 caractères (ex. "69 - Rhône")."""
```

Mirror for `_DEPARTMENT_RULES_DE` with Bundesland wording.

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent/llm_extractor.py
git commit -m "fix: forbid LLM from copying search target department in extraction prompt"
```

---

### Task 6: Frontend — libellé `foreign_location`

**Files:**
- Modify: `frontend/src/lib/run-article-batches.ts`
- Modify: `frontend/src/lib/run-article-batches.test.ts`

- [ ] **Step 1: Add label**

In `SKIP_REASON_LABELS` (or equivalent map), add:

```typescript
  foreign_location: "hors France",
```

- [ ] **Step 2: Add test** (si `SKIP_REASON_LABELS` est exporté et testé) :

```typescript
  it("labels foreign_location skip reason", () => {
    expect(SKIP_REASON_LABELS.foreign_location).toBe("hors France");
  });
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npm test -- run-article-batches.test.ts
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/run-article-batches.ts frontend/src/lib/run-article-batches.test.ts
git commit -m "feat: show foreign_location skip label in live article panel"
```

---

## Self-Review

| Exigence utilisateur | Task |
|---------------------|------|
| `city_focus` → presse locale (Exa `include_domains`) | 1, 2 |
| Département s'adapte quand ville hors dept du run | 3, 4 |
| Ne plus coller au dept du run (hallucination LLM) | 3, 4, 5 |
| Articles étrangers rejetés (Yongin, Suède) | 3, 4 |
| Cross-import existant préservé (Lyon depuis run 77) | 3, 4 |
| Observabilité (`include_domains` dans steps) | 2 |
| UI skip reason | 6 |

**Hors scope (YAGNI) :**
- Géocodage API ville→dept pour villes hors liste ancres (ex. Colombier-Saugnieu) — le LLM reste la source ; le cross-import LLM existant couvre ce cas.
- Préfiltre géographique LLM (coût supplémentaire).
- Peuplement exhaustif des 101 départements en presse locale — commencer par 77/69/91/93/94/78, étendre à la demande.
- Changement de `exa_search_type` deep → auto (amélioration séparée).

**Limite connue :** une ville française absente des ancres ET avec un LLM qui hallucine le dept du run ne sera pas corrigée par la ville-ancre ; le prompt (Task 5) + `include_domains` (Task 2) réduisent fortement ce cas.

## Test plan manuel

1. Config : dept **77**, granularité **city_focus**, villes Meaux/Chelles, preset **this_week**.
2. Lancer une run — vérifier dans les steps `exa_search_done` que `include_domains` contient `actu.fr`, `leparisien.fr`.
3. Les résultats Exa doivent être quasi exclusivement presse locale IDF/77 (plus de sites chinois).
4. Si un article Rhône passe (cross-dept) : statut **import cross-dépt.** avec dept **69**, pas **77**.
5. Articles Corée/Suède : **hors France** en gris, pas de projet tagué 77.
6. Relancer : URLs `foreign_location` ne sont plus fetchées.
