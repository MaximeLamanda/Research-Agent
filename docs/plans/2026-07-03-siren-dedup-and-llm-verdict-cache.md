# SIREN Dedup Rule + LLM Verdict Cache — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Utiliser le SIREN comme signal fort de déduplication et mettre en cache les verdicts LLM de comparaison de paires pour éviter les appels répétés et les verdicts contradictoires.

**Architecture:** (1) `find_candidate_pairs` et `run_dedup_pass` (backend/app/agent/dedup_agent.py) apprennent une règle SIREN : même SIREN + même commune → fusion auto (method="siren") ; même SIREN + même département → paire candidate soumise au LLM même sans similarité de nom/adresse. (2) Nouveau modèle `DedupDecision` (table `dedup_decisions`) qui persiste chaque verdict LLM avec une empreinte (fingerprint) des deux fiches ; tant que les fiches n'ont pas changé, le verdict est réutilisé sans rappeler le LLM.

**Tech Stack:** Python 3, SQLAlchemy 2 (Mapped/mapped_column), pytest + pytest-asyncio, SQLite en tests (`Base.metadata.create_all`, pas d'Alembic — la prod utilise aussi `create_all` au démarrage, voir `backend/app/main.py:147`).

**Contraintes d'environnement :** le workspace n'est PAS un dépôt git — ignorer toutes les étapes "commit". Lancer les tests avec `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest ...`. Ne pas utiliser le paramètre working_directory du shell (bug constaté) : toujours préfixer par `cd`.

**Baseline tests :** 146 passed, 2 failed (préexistants) : `tests/test_valvert_dedup.py::test_run_dedup_pass_merges_valvert_variants_via_llm` et `tests/test_amazon_colombier_dedup.py::test_run_dedup_pass_calls_llm_for_amazon_when_same_department_without_company` — leurs mocks renvoient `True` au lieu du tuple `(True, "")` attendu depuis que `ask_llm_same_project` renvoie `(bool, str)`.

---

### Task 1: Réparer les 2 tests préexistants cassés (mocks obsolètes)

**Files:**
- Modify: `backend/tests/test_valvert_dedup.py`
- Modify: `backend/tests/test_amazon_colombier_dedup.py`

**Step 1: Reproduire l'échec**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_valvert_dedup.py tests/test_amazon_colombier_dedup.py -q`
Expected: 2 FAILED avec `TypeError: cannot unpack non-iterable bool object` à `app/agent/dedup_agent.py:405`.

**Step 2: Corriger les mocks**

Dans les deux fichiers, trouver les `AsyncMock(return_value=True)` (ou équivalent) patchant `app.agent.dedup_agent.ask_llm_same_project` et remplacer par `AsyncMock(return_value=(True, ""))`. Ne rien changer d'autre.

**Step 3: Vérifier**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/ -q`
Expected: 148 passed, 0 failed.

---

### Task 2: Règle SIREN dans la déduplication

**Files:**
- Modify: `backend/app/agent/dedup_agent.py`
- Test: `backend/tests/test_dedup_agent.py` (ajouter des tests, ne pas casser les existants)

**Contexte :** `run_dedup_pass` compare les projets actifs d'un département. Aujourd'hui les candidats viennent uniquement de la similarité nom/adresse (`find_candidate_pairs`), et la fusion auto de `run_dedup_pass` ignore `Project.siren` (String nullable, identifiant légal unique d'entreprise, déjà renseigné par le pipeline via `CompanyResolver`). Deux fiches avec le même SIREN sont très probablement le même promoteur ; même SIREN + même commune est un signal quasi certain de même chantier.

**Spécification :**

1. Ajouter en haut du fichier un helper :

```python
def _same_siren(siren_a: str | None, siren_b: str | None) -> bool:
    if not siren_a or not siren_b:
        return False
    return siren_a.strip() == siren_b.strip()
```

2. Dans `find_candidate_pairs` : calculer `siren_match = _same_siren(project_a.siren, project_b.siren)`. Une paire avec `siren_match` devient candidate même si `name_match` et `address_match` sont faux, à condition que `_same_department(project_a.department, project_b.department)` soit vrai OU `_same_city(project_a.city, project_b.city)` soit vrai. Le garde-fou existant « name_match sans adresse exige la même commune » ne doit PAS bloquer une paire `siren_match`. Le `pair_score` reste celui de `_pair_match_score` (inchangé).

3. Dans `run_dedup_pass` :
   - Ajouter une condition de fusion auto : `_same_siren(kept.siren, absorbed.siren) and _same_city(kept.city, absorbed.city)` → `should_merge = True`, `method = "siren"`.
   - La bande LLM (le `if not should_merge and (...)`) doit aussi se déclencher si `_same_siren(kept.siren, absorbed.siren)` (même sans similarité nom/adresse).
   - `method` reste `"fuzzy"` pour les autres fusions auto et `"llm"` pour l'arbitrage LLM.

4. Dans `_auto_merge_reason` : ajouter en PREMIÈRE position `if _same_siren(kept.siren, absorbed.siren) and _same_city(kept.city, absorbed.city): return f"Même SIREN ({kept.siren}) et même commune"`.

**Step 1: Écrire les tests qui échouent** (dans `backend/tests/test_dedup_agent.py`)

```python
def test_find_candidate_pairs_same_siren_same_department_without_name_match(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        siren="552100554",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        siren="552100554",
        city="Ruy-Montceau",
        department="38 - Isère",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1


def test_find_candidate_pairs_same_siren_different_department_no_pair(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        siren="552100554",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        siren="552100554",
        city="Lyon",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert pairs == []


@pytest.mark.asyncio
async def test_run_dedup_pass_auto_merges_same_siren_same_city(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Plateforme logistique Carrefour Supply",
        siren="451321335",
        city="Vénissieux",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Nouveau hub e-commerce",
        siren="451321335",
        city="Vénissieux",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    db_session.refresh(absorbed)
    assert len(events) == 1
    assert events[0]["method"] == "siren"
    assert absorbed.merged_into_id == kept.id
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_dedup_pass_same_siren_different_city_goes_to_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Plateforme logistique Carrefour Supply",
        siren="451321335",
        city="Vénissieux",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Nouveau hub e-commerce",
        siren="451321335",
        city="Corbas",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, "Deux sites distincts"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert events == []
    llm_mock.assert_awaited_once()
```

**Step 2: Vérifier qu'ils échouent**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py -q`
Expected: les 4 nouveaux tests FAILED (pas de paire candidate / pas de fusion), les anciens passent.

**Step 3: Implémenter la spécification ci-dessus dans `dedup_agent.py`**

**Step 4: Vérifier**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/ -q`
Expected: tout passe (152 passed).

---

### Task 3: Modèle `DedupDecision` (cache des verdicts LLM)

**Files:**
- Create: `backend/app/models/dedup_decision.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/conftest.py` (ajouter l'import noqa)
- Test: `backend/tests/test_models.py` (ajouter un test)

**Spécification :**

Nouveau modèle calqué sur le style de `ProjectMerge` (`backend/app/models/project_merge.py`) :

```python
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class DedupDecision(Base):
    """Verdict LLM persistant pour une paire de projets (évite de re-poser la même question)."""

    __tablename__ = "dedup_decisions"
    __table_args__ = (
        UniqueConstraint("project_a_id", "project_b_id", name="uq_dedup_decisions_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Paire canonique : project_a_id < project_b_id (ordre str(uuid)).
    project_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=False)
    project_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=False)
    same_project: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
    # Empreinte des champs pertinents des deux fiches au moment du verdict ;
    # si l'une des fiches change, l'empreinte diverge et le verdict est re-demandé.
    pair_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run | None"] = relationship("Run")
```

- `app/models/__init__.py` : ajouter l'import et l'entrée `__all__` (ordre alphabétique existant : après `Config`).
- `tests/conftest.py` ligne 13 : ajouter `DedupDecision` à l'import noqa pour que `create_all` crée la table en tests.
- Vérifier que la table est créée en prod : `backend/app/main.py` importe `app.models.run` avant `create_all` ; contrôler que la chaîne d'imports enregistre bien `DedupDecision` (si ce n'est pas le cas, ajouter un import explicite `from app.models import dedup_decision  # noqa: F401` à côté de l'import Run existant dans `main.py`).

**Step 1: Test qui échoue** (dans `tests/test_models.py`, suivre le style des tests existants du fichier)

```python
def test_dedup_decision_roundtrip(db_session):
    from app.models import DedupDecision, Project, Run

    run = Run(status="in_progress")
    project_a = Project(name="A", match_key="a|x")
    project_b = Project(name="B", match_key="b|x")
    db_session.add_all([run, project_a, project_b])
    db_session.flush()

    decision = DedupDecision(
        project_a_id=min(project_a.id, project_b.id, key=str),
        project_b_id=max(project_a.id, project_b.id, key=str),
        same_project=False,
        reason="Sites distincts",
        pair_fingerprint="abc123",
        run_id=run.id,
    )
    db_session.add(decision)
    db_session.commit()

    stored = db_session.query(DedupDecision).one()
    assert stored.same_project is False
    assert stored.reason == "Sites distincts"
    assert stored.pair_fingerprint == "abc123"
```

**Step 2: Vérifier l'échec** — `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_models.py -q` → ImportError.

**Step 3: Implémenter** (modèle + __init__ + conftest + vérif main.py).

**Step 4: Vérifier** — `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/ -q` → tout passe.

---

### Task 4: Brancher le cache des verdicts dans `run_dedup_pass`

**Files:**
- Modify: `backend/app/agent/dedup_agent.py`
- Test: `backend/tests/test_dedup_agent.py`

**Contexte :** `run_dedup_pass` re-scanne le département en boucle (`while True`) après chaque fusion, et chaque run repart de zéro : les paires déjà refusées par le LLM sont re-soumises indéfiniment. On veut : avant d'appeler `ask_llm_same_project`, consulter `DedupDecision` ; si un verdict existe pour la paire canonique ET que `pair_fingerprint` correspond à l'état actuel des fiches, réutiliser le verdict sans appel LLM. Après chaque appel LLM réel, persister (ou mettre à jour) le verdict.

**Spécification :**

1. Ajouter dans `dedup_agent.py` :

```python
import hashlib

_FINGERPRINT_FIELDS = (
    "name",
    "company",
    "siren",
    "city",
    "address",
    "department",
    "status",
    "sector",
)


def _project_fingerprint(project: Project) -> str:
    values = [str(getattr(project, field) or "") for field in _FINGERPRINT_FIELDS]
    values.append(str(project.surface_m2 or ""))
    values.append(str(project.delivery_date or ""))
    return "|".join(values)


def _pair_key(project_a: Project, project_b: Project) -> tuple[uuid.UUID, uuid.UUID]:
    if str(project_a.id) <= str(project_b.id):
        return project_a.id, project_b.id
    return project_b.id, project_a.id


def pair_fingerprint(project_a: Project, project_b: Project) -> str:
    first, second = sorted(
        (_project_fingerprint(project_a), _project_fingerprint(project_b))
    )
    return hashlib.sha256(f"{first}||{second}".encode()).hexdigest()


def get_cached_verdict(
    session: Session, project_a: Project, project_b: Project
) -> tuple[bool, str] | None:
    a_id, b_id = _pair_key(project_a, project_b)
    decision = (
        session.query(DedupDecision)
        .filter(
            DedupDecision.project_a_id == a_id,
            DedupDecision.project_b_id == b_id,
        )
        .first()
    )
    if decision is None or decision.pair_fingerprint != pair_fingerprint(project_a, project_b):
        return None
    return decision.same_project, decision.reason or ""


def store_verdict(
    session: Session,
    project_a: Project,
    project_b: Project,
    *,
    same_project: bool,
    reason: str,
    run_id: uuid.UUID | None,
) -> None:
    a_id, b_id = _pair_key(project_a, project_b)
    decision = (
        session.query(DedupDecision)
        .filter(
            DedupDecision.project_a_id == a_id,
            DedupDecision.project_b_id == b_id,
        )
        .first()
    )
    if decision is None:
        decision = DedupDecision(
            project_a_id=a_id,
            project_b_id=b_id,
            same_project=same_project,
            reason=reason or None,
            pair_fingerprint=pair_fingerprint(project_a, project_b),
            run_id=run_id,
        )
        session.add(decision)
    else:
        decision.same_project = same_project
        decision.reason = reason or None
        decision.pair_fingerprint = pair_fingerprint(project_a, project_b)
        decision.run_id = run_id
    session.flush()
```

2. Dans `run_dedup_pass`, remplacer le bloc d'arbitrage LLM par :

```python
if not should_merge and (
    name_score >= FUZZY_CANDIDATE_MIN
    or has_brand_overlap(kept.name, absorbed.name)
    or address_score >= ADDRESS_CANDIDATE_MIN
    or address_overlap
    or _same_siren(kept.siren, absorbed.siren)
):
    cached = get_cached_verdict(session, kept, absorbed)
    if cached is not None:
        should_merge, merge_reason = cached
        method = "llm_cached"
    else:
        should_merge, merge_reason = await ask_llm_same_project(
            llm, kept, absorbed, step_logger=step_logger
        )
        store_verdict(
            session,
            kept,
            absorbed,
            same_project=should_merge,
            reason=merge_reason,
            run_id=run.id,
        )
        method = "llm"
```

Note : les verdicts positifs sont aussi stockés (traçabilité et cohérence si la fusion échoue), mais en pratique une fusion retire la paire de la circulation. Les verdicts négatifs sont le vrai gain : ils suppriment les rappels LLM dans la boucle `while True` et entre les runs.

3. Imports en tête de fichier : `import hashlib`, `from app.models.dedup_decision import DedupDecision` (et vérifier que `uuid` est déjà importé — oui, ligne 5).

**Step 1: Tests qui échouent** (dans `tests/test_dedup_agent.py`)

```python
@pytest.mark.asyncio
async def test_run_dedup_pass_caches_negative_llm_verdict(db_session):
    from app.models import DedupDecision

    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, "Deux opérations distinctes"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events_first = await run_dedup_pass(db_session, run, ["69"])
        events_second = await run_dedup_pass(db_session, run, ["69"])

    assert events_first == []
    assert events_second == []
    llm_mock.assert_awaited_once()  # 2e passe servie par le cache

    decision = db_session.query(DedupDecision).one()
    assert decision.same_project is False
    assert decision.reason == "Deux opérations distinctes"


@pytest.mark.asyncio
async def test_run_dedup_pass_reasks_llm_when_project_changed(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        await run_dedup_pass(db_session, run, ["69"])

        absorbed.address = "ZAC de Chesnes, Satolas-et-Bonce"
        db_session.commit()

        await run_dedup_pass(db_session, run, ["69"])

    assert llm_mock.await_count == 2  # fingerprint changé → nouvelle question


@pytest.mark.asyncio
async def test_run_dedup_pass_cached_positive_verdict_merges_without_llm(db_session):
    from app.agent.dedup_agent import store_verdict

    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    store_verdict(
        db_session, kept, absorbed,
        same_project=True, reason="Même chantier", run_id=run.id,
    )
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    db_session.refresh(absorbed)
    assert len(events) == 1
    assert events[0]["method"] == "llm_cached"
    assert absorbed.merged_into_id == kept.id
    llm_mock.assert_not_awaited()
```

**Step 2: Vérifier l'échec** — `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py -q` → les 3 nouveaux FAILED.

**Step 3: Implémenter la spécification.**

**Step 4: Vérifier** — `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/ -q` → tout passe.

**Attention :** `merge_projects` crée un `ProjectMerge` avec le champ `method` — la valeur `"llm_cached"` doit transiter telle quelle (colonne String libre, pas d'enum). Vérifier qu'aucun code frontend/API ne restreint `method` (grep rapide sur `"fuzzy"` / `"llm"` dans `backend/app/api` ; si un filtre existe, le signaler dans le rapport).
