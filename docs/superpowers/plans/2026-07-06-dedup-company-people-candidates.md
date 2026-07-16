# Dédup entreprise & contacts (sans SIREN) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer les règles SIREN de déduplication par des signaux fuzzy sur le nom d'entreprise (≥ 85 %, cross-ville) et les contacts partagés (fuzzy nom ≥ 85 %, cross-ville), tout en conservant les règles nom/adresse existantes.

**Architecture:** Extension minimale de `backend/app/agent/dedup_agent.py` : deux helpers (`company_similarity`, `has_people_overlap`), mise à jour de `find_candidate_pairs` et `run_dedup_pass`, suppression de `_same_siren` et des branches associées. Tests TDD dans `backend/tests/test_dedup_agent.py` ; remplacement des 4 tests SIREN obsolètes.

**Tech Stack:** Python 3, rapidfuzz (`fuzz.ratio`, `fuzz.token_sort_ratio`), SQLAlchemy, pytest + pytest-asyncio. Tests : `cd backend && python3 -m pytest ...`

**Spec de référence :** `docs/plans/2026-07-06-dedup-company-people-candidates-design.md`

---

## Fichiers touchés

| Fichier | Action |
|---------|--------|
| `backend/app/agent/dedup_agent.py` | Constantes, helpers, candidature, routage LLM, retrait SIREN |
| `backend/tests/test_dedup_agent.py` | Nouveaux tests + remplacement tests SIREN |

Aucun nouveau fichier. `siren` reste dans `_FINGERPRINT_FIELDS` (invalidation cache si enrichissement).

---

### Task 1: Helpers `company_similarity` et `has_people_overlap`

**Files:**
- Modify: `backend/app/agent/dedup_agent.py` (après les constantes `ADDRESS_CANDIDATE_MIN`, ~ligne 30)
- Test: `backend/tests/test_dedup_agent.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter les imports en tête de `test_dedup_agent.py` :

```python
from app.agent.dedup_agent import (
    FUZZY_AUTO_MERGE,
    COMPANY_SIMILARITY_MIN,
    PEOPLE_NAME_SIMILARITY_MIN,
    _project_payload,
    company_similarity,
    find_candidate_pairs,
    has_people_overlap,
    name_similarity,
    run_dedup_pass,
)
```

Ajouter les tests :

```python
def test_company_similarity_fuzzy_variants():
    score = company_similarity("Carrefour Supply Chain", "Carrefour Supply")
    assert score >= COMPANY_SIMILARITY_MIN


def test_company_similarity_different_companies():
    score = company_similarity("Carrefour Supply", "Amazon France Logistique")
    assert score < COMPANY_SIMILARITY_MIN


def test_has_people_overlap_fuzzy_match():
    people_a = [{"name": "Lorrain Merckaert", "role": "Maire"}]
    people_b = [{"name": "L. Merckaert", "role": None}]
    assert has_people_overlap(people_a, people_b) is True


def test_has_people_overlap_no_match():
    people_a = [{"name": "Alice Martin", "role": "Directrice"}]
    people_b = [{"name": "Bob Dupont", "role": "Maire"}]
    assert has_people_overlap(people_a, people_b) is False


def test_has_people_overlap_empty_lists():
    assert has_people_overlap([], [{"name": "Alice"}]) is False
    assert has_people_overlap([{"name": "Alice"}], []) is False
```

- [ ] **Step 2: Lancer les tests — échec attendu**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py::test_company_similarity_fuzzy_variants tests/test_dedup_agent.py::test_company_similarity_different_companies tests/test_dedup_agent.py::test_has_people_overlap_fuzzy_match tests/test_dedup_agent.py::test_has_people_overlap_no_match tests/test_dedup_agent.py::test_has_people_overlap_empty_lists -v`

Expected: FAIL — `ImportError: cannot import name 'company_similarity'` (ou `COMPANY_SIMILARITY_MIN`)

- [ ] **Step 3: Implémenter les constantes et helpers**

Dans `dedup_agent.py`, après `ADDRESS_CANDIDATE_MIN = 0.55`, ajouter :

```python
COMPANY_SIMILARITY_MIN = 0.85
PEOPLE_NAME_SIMILARITY_MIN = 0.85
```

Après `_normalize_address`, ajouter :

```python
def _normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def company_similarity(company_a: str | None, company_b: str | None) -> float:
    if not company_a or not company_b:
        return 0.0
    return fuzz.ratio(_normalize_label(company_a), _normalize_label(company_b)) / 100


def has_people_overlap(people_a: list, people_b: list) -> bool:
    names_a = [
        _normalize_label(person.get("name", ""))
        for person in people_a
        if person.get("name")
    ]
    names_b = [
        _normalize_label(person.get("name", ""))
        for person in people_b
        if person.get("name")
    ]
    if not names_a or not names_b:
        return False
    for name_a in names_a:
        for name_b in names_b:
            if fuzz.ratio(name_a, name_b) / 100 >= PEOPLE_NAME_SIMILARITY_MIN:
                return True
    return False
```

- [ ] **Step 4: Relancer les tests — succès attendu**

Run: même commande qu'au Step 2.

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/dedup_agent.py backend/tests/test_dedup_agent.py
git commit -m "feat(dedup): add company and people similarity helpers"
```

---

### Task 2: Candidature par entreprise et contact dans `find_candidate_pairs`

**Files:**
- Modify: `backend/app/agent/dedup_agent.py` — fonction `find_candidate_pairs`
- Test: `backend/tests/test_dedup_agent.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Remplacer `test_find_candidate_pairs_same_siren_same_department_without_name_match` par :

```python
def test_find_candidate_pairs_same_company_different_city_without_name_match(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        company="Carrefour Supply Chain",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        company="Carrefour Supply",
        city="Ruy-Montceau",
        department="38 - Isère",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1
```

Remplacer `test_find_candidate_pairs_same_siren_different_department_no_pair` par :

```python
def test_find_candidate_pairs_different_company_no_other_signal(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        company="Carrefour Supply",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        company="Amazon France Logistique",
        city="Lyon",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert pairs == []
```

Ajouter :

```python
def test_find_candidate_pairs_shared_contact_different_city_without_name_match(db_session):
    contact = [{"name": "Lorrain Merckaert", "role": "Maire"}]
    project_a = Project(
        name="Rénovation centre Sourderie",
        city="Montigny-le-Bretonneux",
        department="78 - Yvelines",
        people=contact,
        match_key="a|b",
    )
    project_b = Project(
        name="Extension parc activités",
        city="Trappes",
        department="78 - Yvelines",
        people=[{"name": "L. Merckaert", "role": "Élu"}],
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1
```

- [ ] **Step 2: Lancer les tests — échec attendu**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py::test_find_candidate_pairs_same_company_different_city_without_name_match tests/test_dedup_agent.py::test_find_candidate_pairs_different_company_no_other_signal tests/test_dedup_agent.py::test_find_candidate_pairs_shared_contact_different_city_without_name_match -v`

Expected: FAIL — `assert 0 == 1` ou `assert 1 == 0`

- [ ] **Step 3: Mettre à jour `find_candidate_pairs`**

Remplacer le corps de la boucle (à partir du calcul `name_score`) par :

```python
            name_score = name_similarity(project_a.name, project_b.name)
            brand_overlap = has_brand_overlap(project_a.name, project_b.name)
            address_score = address_similarity(project_a.address, project_b.address)
            address_overlap = has_address_overlap(project_a.address, project_b.address)
            company_score = company_similarity(project_a.company, project_b.company)
            people_overlap = has_people_overlap(
                project_a.people or [], project_b.people or []
            )

            name_match = name_score >= FUZZY_CANDIDATE_MIN or brand_overlap
            address_match = (
                address_score >= ADDRESS_CANDIDATE_MIN
                or address_overlap
                or address_score >= ADDRESS_AUTO_MERGE
            )
            company_match = company_score >= COMPANY_SIMILARITY_MIN
            people_match = people_overlap

            if not name_match and not address_match and not company_match and not people_match:
                continue

            same_city = _same_city(project_a.city, project_b.city)

            # Candidature par nom : même commune, sauf preuve par l'adresse.
            if name_match and not address_match and not same_city:
                continue

            pair_score = _pair_match_score(
                name_score,
                address_score,
                brand_overlap=brand_overlap,
                address_overlap=address_overlap,
            )
            pairs.append((project_a, project_b, pair_score))
```

- [ ] **Step 4: Relancer les tests — succès attendu**

Run: même commande qu'au Step 2.

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/dedup_agent.py backend/tests/test_dedup_agent.py
git commit -m "feat(dedup): candidate pairs by company and shared contacts"
```

---

### Task 3: Retirer SIREN et brancher LLM sur entreprise/contact

**Files:**
- Modify: `backend/app/agent/dedup_agent.py` — `_should_auto_merge_company_city`, `_auto_merge_reason`, `run_dedup_pass` ; supprimer `_same_siren`, `_same_department`, `_same_company` si plus utilisés
- Test: `backend/tests/test_dedup_agent.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Supprimer `test_run_dedup_pass_auto_merges_same_siren_same_city` et `test_run_dedup_pass_same_siren_different_city_goes_to_llm`.

Ajouter :

```python
@pytest.mark.asyncio
async def test_run_dedup_pass_same_company_different_city_goes_to_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Plateforme logistique Carrefour Supply",
        company="Carrefour Supply Chain",
        city="Vénissieux",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Nouveau hub e-commerce",
        company="Carrefour Supply",
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


@pytest.mark.asyncio
async def test_run_dedup_pass_shared_contact_goes_to_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Rénovation centre Sourderie",
        city="Montigny-le-Bretonneux",
        department="78 - Yvelines",
        people=[{"name": "Lorrain Merckaert", "role": "Maire"}],
        match_key="a|b",
    )
    absorbed = Project(
        name="Extension parc activités",
        city="Trappes",
        department="78 - Yvelines",
        people=[{"name": "L. Merckaert", "role": "Élu"}],
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(True, "Même opération citée par le maire"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["78"])

    assert len(events) == 1
    assert events[0]["method"] == "llm"
    llm_mock.assert_awaited_once()
```

- [ ] **Step 2: Lancer les tests — échec attendu**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py::test_run_dedup_pass_same_company_different_city_goes_to_llm tests/test_dedup_agent.py::test_run_dedup_pass_shared_contact_goes_to_llm -v`

Expected: FAIL — `llm_mock.assert_awaited_once()` échoue (LLM non appelé)

- [ ] **Step 3: Mettre à jour `_should_auto_merge_company_city`**

Remplacer l'appel `_same_company(...)` par fuzzy :

```python
def _should_auto_merge_company_city(
    kept: Project,
    absorbed: Project,
    *,
    name_score: float,
) -> bool:
    return (
        company_similarity(kept.company, absorbed.company) >= COMPANY_SIMILARITY_MIN
        and _same_city(kept.city, absorbed.city)
        and has_brand_overlap(kept.name, absorbed.name)
        and name_score >= COMPANY_CITY_AUTO_MERGE
    )
```

- [ ] **Step 4: Mettre à jour `_auto_merge_reason`**

Supprimer le bloc SIREN en tête de fonction. La fonction commence par :

```python
def _auto_merge_reason(
    kept: Project,
    absorbed: Project,
    *,
    score: float,
    name_score: float,
    address_score: float,
) -> str:
    if address_score >= ADDRESS_AUTO_MERGE:
        return f"Adresses très similaires (score adresse {address_score:.0%})"
    if _should_auto_merge_company_city(kept, absorbed, name_score=name_score):
        return "Même promoteur, même commune et noms proches"
    return f"Similarité des noms ≥ {FUZZY_AUTO_MERGE:.0%} (score {score:.0%})"
```

- [ ] **Step 5: Mettre à jour `run_dedup_pass`**

Dans la boucle sur les paires, remplacer le bloc fusion auto / LLM par :

```python
                name_score = name_similarity(kept.name, absorbed.name)
                address_score = address_similarity(kept.address, absorbed.address)
                address_overlap = has_address_overlap(kept.address, absorbed.address)
                company_score = company_similarity(kept.company, absorbed.company)
                people_overlap = has_people_overlap(
                    kept.people or [], absorbed.people or []
                )

                should_merge = (
                    score >= FUZZY_AUTO_MERGE
                    or address_score >= ADDRESS_AUTO_MERGE
                    or _should_auto_merge_company_city(
                        kept, absorbed, name_score=name_score
                    )
                )
                method = "fuzzy"
                merge_reason = ""
                if should_merge:
                    merge_reason = _auto_merge_reason(
                        kept,
                        absorbed,
                        score=score,
                        name_score=name_score,
                        address_score=address_score,
                    )
                if not should_merge and (
                    name_score >= FUZZY_CANDIDATE_MIN
                    or has_brand_overlap(kept.name, absorbed.name)
                    or address_score >= ADDRESS_CANDIDATE_MIN
                    or address_overlap
                    or company_score >= COMPANY_SIMILARITY_MIN
                    or people_overlap
                ):
```

- [ ] **Step 6: Supprimer le code mort SIREN**

Supprimer les fonctions `_same_siren`, `_same_department`, `_same_company` si plus référencées.

Vérifier qu'aucune référence `siren` ne reste dans la logique de candidature/fusion (garder `siren` dans `_FINGERPRINT_FIELDS`).

- [ ] **Step 7: Relancer les tests — succès attendu**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/test_dedup_agent.py -v`

Expected: tous les tests de `test_dedup_agent.py` passent

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent/dedup_agent.py backend/tests/test_dedup_agent.py
git commit -m "feat(dedup): replace SIREN rules with company and contact LLM triggers"
```

---

### Task 4: Suite complète et régression

**Files:**
- Test: `backend/tests/test_dedup_agent.py`, `backend/tests/test_amazon_colombier_dedup.py`, `backend/tests/test_user_reported_dedup.py`, `backend/tests/test_valvert_dedup.py`

- [ ] **Step 1: Lancer toute la suite backend**

Run: `cd /Users/maximelamanda/Research-Agent/backend && python3 -m pytest tests/ -q`

Expected: 0 failed

Si un test échoue parce qu'il dépendait du SIREN, adapter le scénario (même entreprise fuzzy ou contact partagé) sans réintroduire de règle SIREN.

- [ ] **Step 2: Commit final si corrections**

```bash
git add -A
git commit -m "test(dedup): fix regressions after company/contact candidate rules"
```

---

## Self-review (checklist interne)

| Exigence spec | Task |
|---------------|------|
| Retrait SIREN candidature | Task 2 Step 3, Task 3 Step 6 |
| Retrait fusion auto SIREN | Task 3 Step 4–5 |
| Retrait LLM trigger SIREN | Task 3 Step 5 |
| Entreprise fuzzy ≥ 85 % cross-ville | Task 1, 2, 3 |
| Contact fuzzy ≥ 85 % cross-ville | Task 1, 2, 3 |
| Auto-merge promoteur+ville sur fuzzy | Task 3 Step 3 |
| Filtre ville sur nom conservé | Task 2 Step 3 |

Aucun placeholder TBD restant.
