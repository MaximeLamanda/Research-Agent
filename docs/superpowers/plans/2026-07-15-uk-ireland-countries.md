# UK & Ireland Countries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add United Kingdom (GB) and Ireland (IE) as full-parity research countries, extending the existing FR/DE system with regions, search anchors, local press, Exa queries, LLM prompts, and country-scoped deduplication.

**Architecture:** Extend each existing country extension point (`departments.py`, `queries.py`, `llm_extractor.py`, `locale_filter.py`, `department_resolution.py`, `search_anchors/`, `local_press_domains/`, frontend `countries.ts`/`regions.ts`) following the FR/DE pattern. UK uses 3-letter NUTS1 codes (`UKI`, `UKD`…) to avoid collisions with DE 2-letter Länder. Fix dedup by filtering `project.country` in `run_dedup_pass`.

**Tech Stack:** Python 3.12, FastAPI, pytest, SQLAlchemy | Next.js 15, TypeScript, vitest

## Global Constraints

- Country codes: `GB` (not `UK`), `IE` — ISO 3166-1 alpha-2
- UK region codes: `UKC`, `UKD`, `UKE`, `UKF`, `UKG`, `UKH`, `UKI`, `UKJ`, `UKK`, `UKL`, `UKM`, `UKN` (3 letters)
- IE province codes: `LE`, `MU`, `CN`, `UL` (2 letters, distinct from DE Länder)
- Department format: `"CODE - Name"` (e.g. `"UKI - London"`, `"LE - Leinster"`)
- `infer_country_from_department` returns `null` for unknown codes (no blind fallback to FR/DE)
- Company resolver stays FR-only (same as DE)
- Extraction output language stays English (existing `_LANGUAGE_RULES`)
- Sector enums unchanged: `industriel|logistique|retail`, `conception|travaux|livraison`
- Follow existing test patterns; TDD for each task
- Commit after each task with conventional message

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/data/departments.py` | Modify | GB/IE region registries, code detection, regex |
| `backend/app/agent/dedup_agent.py` | Modify | Filter projects by country |
| `backend/app/agent/dedup_service.py` | Modify | Safer country inference fallback |
| `backend/app/agent/queries.py` | Modify | GB/IE sector queries |
| `backend/app/agent/llm_extractor.py` | Modify | GB/IE department prompts |
| `backend/app/agent/locale_filter.py` | Modify | Exa user_location + foreign heuristics |
| `backend/app/agent/department_resolution.py` | Modify | Country-aware foreign detection |
| `backend/app/data/search_anchors/gb.json` | Create | 12 UK regions × 5 cities |
| `backend/app/data/search_anchors/ie.json` | Create | 4 IE provinces × 5 cities |
| `backend/app/data/search_anchors_loader.py` | Modify | English city phrase joiner |
| `backend/app/data/local_press_domains/gb.json` | Create | Regional UK press domains |
| `backend/app/data/local_press_domains/ie.json` | Create | Provincial IE press domains |
| `frontend/src/data/countries.ts` | Modify | Add GB, IE |
| `frontend/src/data/uk-regions.ts` | Create | UK NUTS1 list |
| `frontend/src/data/ireland-provinces.ts` | Create | IE provinces list |
| `frontend/src/data/regions.ts` | Modify | Register GB, IE |
| `frontend/src/components/settings-accordion.tsx` | Modify | Region label for GB/IE |
| `frontend/src/components/project-detail-drawer.tsx` | Modify | Region label for GB/IE |
| `backend/tests/test_departments.py` | Modify | GB/IE tests |
| `backend/tests/test_dedup_country_filter.py` | Create | Dedup isolation tests |
| `backend/tests/test_queries.py` | Modify | GB/IE query tests |
| `backend/tests/test_locale_filter.py` | Modify | GB/IE locale tests |
| `backend/tests/test_department_resolution.py` | Modify | GB/IE foreign detection |
| `backend/tests/test_search_anchors_loader.py` | Create | GB/IE anchor loader |
| `backend/tests/test_local_press_loader.py` | Modify | GB/IE press domains |
| `backend/tests/test_search_anchors_api.py` | Modify | GB/IE API tests |
| `backend/tests/test_config_api.py` | Modify | GB config test |

---

### Task 1: Backend region registry (GB + IE)

**Files:**
- Modify: `backend/app/data/departments.py`
- Test: `backend/tests/test_departments.py`

**Interfaces:**
- Produces: `GB_REGIONS: dict[str, str]`, `IE_PROVINCES: dict[str, str]` in `REGIONS_BY_COUNTRY`
- Produces: `format_department("UKI", "GB")` → `"UKI - London"`
- Produces: `infer_country_from_department("UKI - London")` → `"GB"`
- Produces: `infer_country_from_department("LE - Leinster")` → `"IE"`
- Produces: `infer_country_from_department("XX - Unknown")` → `None`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_departments.py`:

```python
def test_format_department_gb():
    assert format_department("UKI", "GB") == "UKI - London"
    assert format_department("UKD", "GB") == "UKD - North West"


def test_format_department_ie():
    assert format_department("LE", "IE") == "LE - Leinster"
    assert format_department("MU", "IE") == "MU - Munster"


def test_normalize_department_gb_formatted():
    assert normalize_department("UKI - London", "GB") == "UKI - London"
    assert normalize_department("UKD - North West", "GB") == "UKD - North West"


def test_normalize_department_ie_formatted():
    assert normalize_department("LE - Leinster", "IE") == "LE - Leinster"


def test_infer_country_from_department_gb_ie():
    assert infer_country_from_department("UKI - London") == "GB"
    assert infer_country_from_department("UKM - Scotland") == "GB"
    assert infer_country_from_department("LE - Leinster") == "IE"
    assert infer_country_from_department("MU - Munster") == "IE"


def test_infer_country_from_department_unknown_returns_none():
    assert infer_country_from_department("ZZ - Nowhere") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_departments.py::test_format_department_gb -v`
Expected: FAIL

- [ ] **Step 3: Implement region registry**

In `backend/app/data/departments.py`, add after `DE_LANDER`:

```python
GB_REGIONS: dict[str, str] = {
    "UKC": "North East",
    "UKD": "North West",
    "UKE": "Yorkshire and The Humber",
    "UKF": "East Midlands",
    "UKG": "West Midlands",
    "UKH": "East of England",
    "UKI": "London",
    "UKJ": "South East",
    "UKK": "South West",
    "UKL": "Wales",
    "UKM": "Scotland",
    "UKN": "Northern Ireland",
}

IE_PROVINCES: dict[str, str] = {
    "LE": "Leinster",
    "MU": "Munster",
    "CN": "Connacht",
    "UL": "Ulster",
}
```

Update `REGIONS_BY_COUNTRY`:

```python
REGIONS_BY_COUNTRY: dict[str, dict[str, str]] = {
    "FR": FR_DEPARTMENTS,
    "DE": DE_LANDER,
    "GB": GB_REGIONS,
    "IE": IE_PROVINCES,
}
```

Update `_FORMATTED_RE`:

```python
_FORMATTED_RE = re.compile(r"^([A-Z]{2,3}|\d{2}[AB]?)\s*[-—]\s*(.+)$", re.IGNORECASE)
```

Add `_GB_CODE_RE` and `_IE_CODE_RE`:

```python
_GB_CODE_RE = re.compile(r"^UK[A-Z]$")
_IE_CODES = frozenset(IE_PROVINCES)
```

Update `_detect_country_from_code`:

```python
def _detect_country_from_code(code: str) -> str | None:
    if _FR_CODE_RE.match(code):
        return "FR"
    if _GB_CODE_RE.match(code):
        return "GB"
    if code in _IE_CODES:
        return "IE"
    if _DE_CODE_RE.match(code) and code in DE_LANDER:
        return "DE"
    return None
```

Update `infer_country_from_department` return type to `str | None`; return `None` when undetectable.

Update `normalize_department` fallback loop:

```python
for fallback_country in ("FR", "DE", "GB", "IE"):
```

Update `regions_for_country` default: return empty dict `{}` instead of `FR_DEPARTMENTS` when unknown (or keep FR_DEPARTMENTS for backward compat — use `REGIONS_BY_COUNTRY.get(country, {})`).

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_departments.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/departments.py backend/tests/test_departments.py
git commit -m "feat(regions): add GB NUTS1 and IE province registries"
```

---

### Task 2: Dedup country filter

**Files:**
- Modify: `backend/app/agent/dedup_agent.py:499-509`
- Modify: `backend/app/agent/dedup_service.py:30,50`
- Create: `backend/tests/test_dedup_country_filter.py`

**Interfaces:**
- Consumes: `infer_country_from_department` from Task 1
- Produces: `run_dedup_pass` only compares projects where `project.country == country`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dedup_country_filter.py`:

```python
import pytest
from app.agent.dedup_agent import run_dedup_pass
from app.models.project import Project
from app.models.run import Run


@pytest.mark.asyncio
async def test_dedup_pass_ignores_other_country_same_prefix(db_session):
    """DE NW and a hypothetical GB UKD must not be compared when deduping DE."""
    run = Run(status="completed", mode="full")
    de_project = Project(
        name="Amazon Düsseldorf",
        city="Düsseldorf",
        department="NW - Nordrhein-Westfalen",
        country="DE",
        match_key="amazon|dusseldorf",
    )
    gb_project = Project(
        name="Amazon Manchester",
        city="Manchester",
        department="UKD - North West",
        country="GB",
        match_key="amazon|manchester",
    )
    db_session.add_all([run, de_project, gb_project])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["NW"], country="DE")

    assert events == []
    assert de_project.merged_into_id is None
    assert gb_project.merged_into_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_dedup_country_filter.py -v`
Expected: FAIL (or pass incorrectly if UKD doesn't match NW prefix — adjust test)

Note: The test uses `["NW"]` for DE — GB project has `UKD` prefix so won't match `NW%`. Add a stronger collision test:

```python
@pytest.mark.asyncio
async def test_dedup_pass_filters_by_country_not_department_prefix(db_session):
    run = Run(status="completed", mode="full")
    ie_project = Project(
        name="Dublin Warehouse",
        city="Dublin",
        department="LE - Leinster",
        country="IE",
        match_key="wh|dublin",
    )
    mislabeled = Project(
        name="Dublin Copy",
        city="Dublin",
        department="LE - Leinster",
        country="FR",
        match_key="wh|dublin2",
    )
    db_session.add_all([run, ie_project, mislabeled])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["LE"], country="IE")

    assert len(events) <= 1
    if events:
        assert mislabeled.merged_into_id is not None or ie_project.merged_into_id is not None
```

- [ ] **Step 3: Add country filter in dedup_agent**

In `run_dedup_pass`, update project query:

```python
from sqlalchemy import func

# inside the while loop, replace project query:
projects = [
    project
    for project in session.query(Project)
    .filter(
        Project.merged_into_id.is_(None),
        Project.department.isnot(None),
        func.coalesce(Project.country, country) == country,
        Project.department.like(department_prefix),
    )
    .all()
    if _department_matches(project.department, department_label, country=country)
]
```

In `dedup_service.py`, replace fallback:

```python
project_country = (country or infer_country_from_department(department) or "FR").upper()
```

with:

```python
inferred = infer_country_from_department(department)
project_country = (country or inferred or "FR").upper()
```

(Keep `"FR"` as last resort only when country column is null AND inference fails — existing projects.)

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_dedup_country_filter.py tests/test_dedup_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/dedup_agent.py backend/app/agent/dedup_service.py backend/tests/test_dedup_country_filter.py
git commit -m "fix(dedup): scope candidate pairs by project country"
```

---

### Task 3: Exa queries and LLM prompts

**Files:**
- Modify: `backend/app/agent/queries.py`
- Modify: `backend/app/agent/llm_extractor.py`
- Modify: `backend/tests/test_queries.py`
- Modify: `backend/tests/test_departments.py` (prompt tests if present)

**Interfaces:**
- Produces: `SECTOR_QUERIES_BY_COUNTRY["GB"]`, `SECTOR_QUERIES_BY_COUNTRY["IE"]`
- Produces: `system_prompt_for_country("GB")` mentions NUTS1 region format

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_queries.py`:

```python
from app.agent.queries import SECTOR_QUERIES_BY_COUNTRY


def test_sector_queries_gb_english():
    q = SECTOR_QUERIES_BY_COUNTRY["GB"]["logistique"]
    assert "United Kingdom" in q
    assert "{dept_label}" in q
    assert "logistics" in q.lower() or "warehouse" in q.lower()


def test_sector_queries_ie_english():
    q = SECTOR_QUERIES_BY_COUNTRY["IE"]["industriel"]
    assert "Ireland" in q
    assert "{dept_name}" in q
```

Add prompt test to `backend/tests/test_departments.py` (or create `test_llm_extractor.py` if missing):

```python
def test_system_prompt_for_country_gb():
    prompt = system_prompt_for_country("GB")
    assert "UKI - London" in prompt
    assert "United Kingdom" in prompt or "NUTS1" in prompt or "region" in prompt.lower()


def test_system_prompt_for_country_ie():
    prompt = system_prompt_for_country("IE")
    assert "LE - Leinster" in prompt
    assert "Ireland" in prompt
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && python3 -m pytest tests/test_queries.py::test_sector_queries_gb_english tests/test_departments.py::test_system_prompt_for_country_gb -v`
Expected: FAIL

- [ ] **Step 3: Implement queries and prompts**

In `queries.py`:

```python
SECTOR_QUERIES_GB = {
    "logistique": (
        "article announces investment logistics warehouse distribution centre "
        "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
        "new project extension 2026 2027"
    ),
    "industriel": (
        "article announces investment new factory industrial site "
        "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
        "project launch extension 2026 2027"
    ),
    "retail": (
        "article announces investment new retail park shopping centre "
        "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
        "project extension 2026 2027"
    ),
}

SECTOR_QUERIES_IE = {
    "logistique": (
        "article announces investment logistics warehouse distribution centre "
        "{dept_name} province {dept_code} ({dept_label}) Ireland "
        "new project extension 2026 2027"
    ),
    "industriel": (
        "article announces investment new factory industrial site "
        "{dept_name} province {dept_code} ({dept_label}) Ireland "
        "project launch extension 2026 2027"
    ),
    "retail": (
        "article announces investment new retail park shopping centre "
        "{dept_name} province {dept_code} ({dept_label}) Ireland "
        "project extension 2026 2027"
    ),
}

SECTOR_QUERIES_BY_COUNTRY = {
    "FR": SECTOR_QUERIES_FR,
    "DE": SECTOR_QUERIES_DE,
    "GB": SECTOR_QUERIES_GB,
    "IE": SECTOR_QUERIES_IE,
}
```

In `llm_extractor.py`:

```python
_DEPARTMENT_RULES_GB = """For department, infer the NUTS1 region from the precise site location (city, address, geographic context). Do not guess: use null if the region is not identifiable in the article.
NEVER use the region from the search context or a default region: if the site is abroad or outside the United Kingdom, set department to null and is_relevant=false.
Always use format "code - name" with the 3-letter NUTS1 code (e.g. "UKI - London", "UKD - North West")."""

_DEPARTMENT_RULES_IE = """For department, infer the province from the precise site location (city, address, geographic context). Do not guess: use null if the province is not identifiable in the article.
NEVER use the province from the search context or a default: if the site is abroad or outside Ireland, set department to null and is_relevant=false.
Always use format "code - name" with the 2-letter province code (e.g. "LE - Leinster", "MU - Munster")."""

_DEPARTMENT_FORMATS = {
    "FR": 'format OBLIGATOIRE si connu : "XX - Nom", ex. "69 - Rhône", "38 - Isère" ; jamais le nom seul ni le code seul',
    "DE": 'format OBLIGATOIRE si connu : "XX - Nom", ex. "BY - Bayern", "NW - Nordrhein-Westfalen" ; jamais le nom seul ni le code seul',
    "GB": 'MANDATORY format if known: "XXX - Name", e.g. "UKI - London", "UKD - North West"; never name or code alone',
    "IE": 'MANDATORY format if known: "XX - Name", e.g. "LE - Leinster", "MU - Munster"; never name or code alone',
}

_DEPARTMENT_RULES_BY_COUNTRY = {
    "FR": _DEPARTMENT_RULES_FR,
    "DE": _DEPARTMENT_RULES_DE,
    "GB": _DEPARTMENT_RULES_GB,
    "IE": _DEPARTMENT_RULES_IE,
}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_queries.py tests/test_departments.py -k "gb or ie or prompt" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/queries.py backend/app/agent/llm_extractor.py backend/tests/test_queries.py backend/tests/test_departments.py
git commit -m "feat(search): add GB and IE Exa queries and LLM department prompts"
```

---

### Task 4: Locale filter and department resolution (country-aware)

**Files:**
- Modify: `backend/app/agent/locale_filter.py`
- Modify: `backend/app/agent/department_resolution.py`
- Modify: `backend/tests/test_locale_filter.py`
- Modify: `backend/tests/test_department_resolution.py`

**Interfaces:**
- Produces: `exa_user_location_for_country("GB")` → `"GB"`
- Produces: `is_foreign_location(..., country="GB")` returns `False` for "London warehouse"
- Produces: `is_foreign_location(..., country="GB")` returns `True` for "Lyon France"

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_locale_filter.py`:

```python
def test_exa_user_location_gb_ie():
    assert exa_user_location_for_country("GB") == "GB"
    assert exa_user_location_for_country("IE") == "IE"
```

Add to `backend/tests/test_department_resolution.py`:

```python
def test_is_foreign_location_gb_allows_london():
    assert is_foreign_location("London", "1 High Street", "", country="GB") is False


def test_is_foreign_location_gb_rejects_france():
    assert is_foreign_location("Lyon", "France", "projet à Lyon France", country="GB") is True


def test_is_foreign_location_ie_allows_dublin():
    assert is_foreign_location("Dublin", None, "", country="IE") is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && python3 -m pytest tests/test_locale_filter.py::test_exa_user_location_gb_ie tests/test_department_resolution.py::test_is_foreign_location_gb_allows_london -v`
Expected: FAIL

- [ ] **Step 3: Implement country-aware locale and foreign detection**

In `locale_filter.py`:

```python
_EXA_USER_LOCATION = {
    "FR": "FR",
    "DE": "DE",
    "GB": "GB",
    "IE": "IE",
}
```

Extend `is_likely_foreign_candidate` to handle GB/IE (English sources are expected; reject CJK/spam for all countries, add FR-specific heuristics only for FR).

In `department_resolution.py`, add country parameter to `is_foreign_location`:

```python
_COUNTRY_MARKERS: dict[str, re.Pattern] = {
    "FR": re.compile(r"\b(france|français|francais)\b", re.IGNORECASE),
    "DE": re.compile(r"\b(germany|deutschland)\b", re.IGNORECASE),
    "GB": re.compile(r"\b(united\s+kingdom|\buk\b|england|scotland|wales)\b", re.IGNORECASE),
    "IE": re.compile(r"\b(ireland|éire|eire)\b", re.IGNORECASE),
}

_FOREIGN_BY_TARGET: dict[str, re.Pattern] = {
    "FR": re.compile(r"\b(germany|deutschland|united\s+kingdom|\buk\b|ireland|sweden|china|korea)\b", re.IGNORECASE),
    "DE": re.compile(r"\b(france|united\s+kingdom|\buk\b|ireland|sweden|china|korea)\b", re.IGNORECASE),
    "GB": re.compile(r"\b(france|germany|deutschland|ireland|sweden|china|korea)\b", re.IGNORECASE),
    "IE": re.compile(r"\b(france|germany|deutschland|united\s+kingdom|\buk\b|sweden|china|korea)\b", re.IGNORECASE),
}


def is_foreign_location(
    city: str | None,
    address: str | None,
    article_text: str,
    *,
    country: str = "FR",
) -> bool:
    blob = " ".join(filter(None, [city, address, article_text[:500] if article_text else ""]))
    if not blob.strip():
        return False
    normalized = country.upper()
    home = _COUNTRY_MARKERS.get(normalized)
    if home and home.search(blob):
        return False
    foreign = _FOREIGN_BY_TARGET.get(normalized, _FOREIGN_MARKERS)
    return bool(foreign.search(blob))
```

Update `resolve_extraction_department` to pass `country` to `is_foreign_location`.

Remove `london` from the old `_FOREIGN_MARKERS` blanket list (or stop using it directly).

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_locale_filter.py tests/test_department_resolution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/locale_filter.py backend/app/agent/department_resolution.py backend/tests/test_locale_filter.py backend/tests/test_department_resolution.py
git commit -m "feat(locale): add GB/IE Exa location and country-aware foreign detection"
```

---

### Task 5: Search anchors (GB + IE)

**Files:**
- Create: `backend/app/data/search_anchors/gb.json`
- Create: `backend/app/data/search_anchors/ie.json`
- Modify: `backend/app/data/search_anchors_loader.py`
- Create: `backend/tests/test_search_anchors_loader.py`
- Modify: `backend/tests/test_search_anchors_api.py`

**Interfaces:**
- Produces: `cities_for_region("UKI", "GB")[0] == "London"`
- Produces: `anchor_segment_for_cities(["London", "Reading"], "GB")` contains `"around"`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_search_anchors_loader.py`:

```python
from app.data.search_anchors_loader import (
    anchor_segment_for_cities,
    cities_for_region,
    anchors_for_country,
)


def test_gb_london_cities():
    cities = cities_for_region("UKI", "GB")
    assert cities[0] == "London"
    assert len(cities) == 5


def test_ie_leinster_cities():
    cities = cities_for_region("LE", "IE")
    assert "Dublin" in cities
    assert len(cities) == 5


def test_gb_anchor_segment_english():
    segment = anchor_segment_for_cities(["Manchester", "Liverpool"], "GB")
    assert "around" in segment
    assert "and" in segment


def test_all_gb_regions_have_anchors():
    anchors = anchors_for_country("GB")
    assert len(anchors) == 12


def test_all_ie_provinces_have_anchors():
    anchors = anchors_for_country("IE")
    assert len(anchors) == 4
```

Add to `backend/tests/test_search_anchors_api.py`:

```python
def test_search_anchors_gb_london():
    response = client.get("/api/search-anchors", params={"country": "GB", "codes": ["UKI"]})
    assert response.status_code == 200
    assert response.json()["UKI"]["cities"][0] == "London"


def test_search_anchors_ie_leinster():
    response = client.get("/api/search-anchors", params={"country": "IE", "codes": ["LE"]})
    assert response.status_code == 200
    assert "Dublin" in response.json()["LE"]["cities"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && python3 -m pytest tests/test_search_anchors_loader.py -v`
Expected: FAIL

- [ ] **Step 3: Create anchor data files**

Create `backend/app/data/search_anchors/gb.json`:

```json
{
  "UKC": {"cities": ["Newcastle upon Tyne", "Sunderland", "Middlesbrough", "Durham", "Gateshead"]},
  "UKD": {"cities": ["Manchester", "Liverpool", "Preston", "Chester", "Lancaster"]},
  "UKE": {"cities": ["Leeds", "Sheffield", "Bradford", "Hull", "York"]},
  "UKF": {"cities": ["Nottingham", "Leicester", "Derby", "Lincoln", "Northampton"]},
  "UKG": {"cities": ["Birmingham", "Coventry", "Wolverhampton", "Stoke-on-Trent", "Worcester"]},
  "UKH": {"cities": ["Norwich", "Cambridge", "Ipswich", "Peterborough", "Colchester"]},
  "UKI": {"cities": ["London", "Croydon", "Bromley", "Ealing", "Watford"]},
  "UKJ": {"cities": ["Brighton", "Southampton", "Portsmouth", "Oxford", "Reading"]},
  "UKK": {"cities": ["Bristol", "Plymouth", "Exeter", "Bournemouth", "Swindon"]},
  "UKL": {"cities": ["Cardiff", "Swansea", "Newport", "Wrexham", "Barry"]},
  "UKM": {"cities": ["Glasgow", "Edinburgh", "Aberdeen", "Dundee", "Inverness"]},
  "UKN": {"cities": ["Belfast", "Derry", "Lisburn", "Newry", "Armagh"]}
}
```

Create `backend/app/data/search_anchors/ie.json`:

```json
{
  "LE": {"cities": ["Dublin", "Kilkenny", "Wexford", "Dundalk", "Drogheda"]},
  "MU": {"cities": ["Cork", "Limerick", "Waterford", "Tralee", "Ennis"]},
  "CN": {"cities": ["Galway", "Sligo", "Castlebar", "Athlone", "Ballina"]},
  "UL": {"cities": ["Letterkenny", "Monaghan", "Cavan", "Donegal", "Buncrana"]}
}
```

Update `search_anchors_loader.py` `_phrase_cities` and `anchor_segment_for_cities`:

```python
def _joiner_for_country(country: str) -> str:
    if country == "DE":
        return " und "
    if country in ("GB", "IE"):
        return " and "
    return " et "


def anchor_segment_for_cities(cities: list[str], country: str = "FR") -> str:
    phrase = _phrase_cities(cities, country.upper())
    if not phrase:
        return ""
    normalized = country.upper()
    if normalized == "DE":
        return f" in {phrase}"
    if normalized in ("GB", "IE"):
        return f" around {phrase}"
    return f" autour de {phrase}"
```

Update `_phrase_cities` to use `_joiner_for_country`.

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_search_anchors_loader.py tests/test_search_anchors_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/search_anchors/gb.json backend/app/data/search_anchors/ie.json backend/app/data/search_anchors_loader.py backend/tests/test_search_anchors_loader.py backend/tests/test_search_anchors_api.py
git commit -m "feat(anchors): add GB and IE search anchor cities"
```

---

### Task 6: Local press domains (GB + IE)

**Files:**
- Create: `backend/app/data/local_press_domains/gb.json`
- Create: `backend/app/data/local_press_domains/ie.json`
- Modify: `backend/tests/test_local_press_loader.py`

**Interfaces:**
- Produces: `local_press_domains_for_department("UKI", "GB")` returns non-empty list
- Produces: `local_press_domains_for_department("LE", "IE")` returns non-empty list

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_local_press_loader.py`:

```python
def test_gb_london_press_domains():
    domains = local_press_domains_for_department("UKI", "GB")
    assert "standard.co.uk" in domains
    assert len(domains) >= 3


def test_ie_leinster_press_domains():
    domains = local_press_domains_for_department("LE", "IE")
    assert "irishtimes.com" in domains
    assert len(domains) >= 3


def test_all_gb_regions_have_press_domains():
    from app.data.departments import GB_REGIONS
    for code in GB_REGIONS:
        assert len(local_press_domains_for_department(code, "GB")) >= 2


def test_all_ie_provinces_have_press_domains():
    from app.data.departments import IE_PROVINCES
    for code in IE_PROVINCES:
        assert len(local_press_domains_for_department(code, "IE")) >= 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && python3 -m pytest tests/test_local_press_loader.py::test_gb_london_press_domains -v`
Expected: FAIL

- [ ] **Step 3: Create press domain files**

Create `backend/app/data/local_press_domains/gb.json`:

```json
{
  "UKC": ["chroniclelive.co.uk", "gazettelive.co.uk", "northernecho.co.uk"],
  "UKD": ["manchestereveningnews.co.uk", "liverpoolecho.co.uk", "lep.co.uk"],
  "UKE": ["yorkshirepost.co.uk", "thestar.co.uk", "examinerlive.co.uk"],
  "UKF": ["nottinghampost.com", "leicestermercury.co.uk", "derbytelegraph.co.uk"],
  "UKG": ["birminghammail.co.uk", "coventrytelegraph.net", "expressandstar.com"],
  "UKH": ["edp24.co.uk", "cambridge-news.co.uk", "ipswichstar.co.uk"],
  "UKI": ["standard.co.uk", "cityam.com", "building.co.uk", "constructionenquirer.com"],
  "UKJ": ["theargus.co.uk", "dailyecho.co.uk", "oxfordmail.co.uk"],
  "UKK": ["bristolpost.co.uk", "plymouthherald.co.uk", "bournemouthecho.co.uk"],
  "UKL": ["walesonline.co.uk", "southwalesargus.co.uk", "countytimes.co.uk"],
  "UKM": ["heraldscotland.com", "dailyrecord.co.uk", "pressandjournal.co.uk"],
  "UKN": ["belfasttelegraph.co.uk", "irishnews.com", "derryjournal.com"]
}
```

Create `backend/app/data/local_press_domains/ie.json`:

```json
{
  "LE": ["irishtimes.com", "independent.ie", "thejournal.ie"],
  "MU": ["irishexaminer.com", "limerickleader.ie", "waterford-news.ie"],
  "CN": ["connachttribune.ie", "galwaybeo.ie", "sligotoday.ie"],
  "UL": ["donegallive.ie", "derryjournal.com", "anglocelt.ie"]
}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_local_press_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/local_press_domains/gb.json backend/app/data/local_press_domains/ie.json backend/tests/test_local_press_loader.py
git commit -m "feat(press): add GB and IE local press domain maps"
```

---

### Task 7: Frontend countries and regions UI

**Files:**
- Modify: `frontend/src/data/countries.ts`
- Create: `frontend/src/data/uk-regions.ts`
- Create: `frontend/src/data/ireland-provinces.ts`
- Modify: `frontend/src/data/regions.ts`
- Modify: `frontend/src/components/settings-accordion.tsx`
- Modify: `frontend/src/components/project-detail-drawer.tsx`

**Interfaces:**
- Produces: `COUNTRIES` includes GB and IE
- Produces: `getRegionsForCountry("GB")` returns 12 regions
- Produces: `getRegionsForCountry("IE")` returns 4 provinces

- [ ] **Step 1: Create region data files**

Create `frontend/src/data/uk-regions.ts`:

```typescript
export interface UkRegion {
  code: string;
  name: string;
}

export const UK_REGIONS: UkRegion[] = [
  { code: "UKC", name: "North East" },
  { code: "UKD", name: "North West" },
  { code: "UKE", name: "Yorkshire and The Humber" },
  { code: "UKF", name: "East Midlands" },
  { code: "UKG", name: "West Midlands" },
  { code: "UKH", name: "East of England" },
  { code: "UKI", name: "London" },
  { code: "UKJ", name: "South East" },
  { code: "UKK", name: "South West" },
  { code: "UKL", name: "Wales" },
  { code: "UKM", name: "Scotland" },
  { code: "UKN", name: "Northern Ireland" },
];
```

Create `frontend/src/data/ireland-provinces.ts`:

```typescript
export interface IrelandProvince {
  code: string;
  name: string;
}

export const IRELAND_PROVINCES: IrelandProvince[] = [
  { code: "LE", name: "Leinster" },
  { code: "MU", name: "Munster" },
  { code: "CN", name: "Connacht" },
  { code: "UL", name: "Ulster" },
];
```

- [ ] **Step 2: Update countries and regions registry**

In `frontend/src/data/countries.ts`:

```typescript
export const COUNTRIES: Country[] = [
  { code: "FR", label: "France" },
  { code: "DE", label: "Germany" },
  { code: "GB", label: "United Kingdom" },
  { code: "IE", label: "Ireland" },
];
```

In `frontend/src/data/regions.ts`, import and register:

```typescript
import { UK_REGIONS } from "@/data/uk-regions";
import { IRELAND_PROVINCES } from "@/data/ireland-provinces";

const REGIONS_BY_COUNTRY: Record<string, Region[]> = {
  FR: FRENCH_DEPARTMENTS,
  DE: GERMAN_LANDER,
  GB: UK_REGIONS,
  IE: IRELAND_PROVINCES,
};
```

Update `getRegionLabel` regex to support 3-letter codes:

```typescript
const formatted = code.match(/^([A-Z]{2,3}|\d{2}[AB]?)\s*[-—]\s*(.+)$/i);
```

Update `getRegionsForCountry` default to `[]` instead of `FRENCH_DEPARTMENTS` when unknown.

- [ ] **Step 3: Update UI labels**

In `settings-accordion.tsx`, replace hardcoded DE label:

```typescript
const regionLabel =
  country === "DE" ? "Länder" : country === "GB" ? "Regions" : country === "IE" ? "Provinces" : "Régions";
```

In `project-detail-drawer.tsx`, same pattern for department row label.

- [ ] **Step 4: Verify frontend**

Run: `cd frontend && npm test -- --run 2>/dev/null || npx vitest run 2>/dev/null || echo "Run vitest if configured"`
Run: `cd frontend && npm run build`
Expected: build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/countries.ts frontend/src/data/uk-regions.ts frontend/src/data/ireland-provinces.ts frontend/src/data/regions.ts frontend/src/components/settings-accordion.tsx frontend/src/components/project-detail-drawer.tsx
git commit -m "feat(ui): add GB and IE countries with region selectors"
```

---

### Task 8: Config API and full test suite

**Files:**
- Modify: `backend/tests/test_config_api.py`

- [ ] **Step 1: Write config test**

Add to `backend/tests/test_config_api.py`:

```python
def test_update_config_gb_regions(client):
    response = client.put(
        "/api/config",
        json={"country": "GB", "departments": ["UKI", "UKD"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["country"] == "GB"
    assert data["departments"] == ["UKI", "UKD"]
```

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && python3 -m pytest -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_config_api.py
git commit -m "test: verify GB config API and complete UK/IE country support"
```

---

## Self-Review Checklist

| Spec requirement | Task |
|------------------|------|
| GB 12 NUTS1 regions | Task 1, 5, 7 |
| IE 4 provinces | Task 1, 5, 7 |
| Exa queries EN | Task 3 |
| LLM prompts GB/IE | Task 3 |
| Search anchors complete | Task 5 |
| Local press complete | Task 6 |
| Dedup country filter | Task 2 |
| infer_country GB/IE | Task 1, 2 |
| Foreign detection country-aware | Task 4 |
| Frontend country selector | Task 7 |
| exa_user_location GB/IE | Task 4 |
