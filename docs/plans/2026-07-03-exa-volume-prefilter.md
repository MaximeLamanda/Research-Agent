# Exa 25 résultats + préfiltre LLM batch — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Récupérer 25 résultats par recherche Exa (au lieu de 10) et insérer un préfiltre LLM batch (titre+snippet) qui sélectionne au maximum 10 URLs à fetcher, sans augmenter les coûts.

**Architecture:** Nouveau module `UrlPrefilter` (même patron que `LLMExtractor`, Vercel AI Gateway). Dans `pipeline.py`, entre le filtrage `known_urls`/domaines bloqués et `exa.fetch`, un seul appel LLM batch classe les candidats (`fetch`/`skip`) ; les rejets émettent `article_skipped(prefiltered)` sans être enregistrés en `ProcessedUrl` ; les URLs retenues sont triées par score Exa décroissant et cappées à 10. En cas d'erreur du préfiltre : fallback = comportement actuel (top 10 par ordre Exa).

**Tech Stack:** Python 3.12, FastAPI, httpx, pytest + pytest-asyncio (mocks `unittest.mock`), Vercel AI Gateway (chat completions).

**Design doc:** `docs/plans/2026-07-03-exa-volume-prefilter-design.md`

**Commandes de test:** depuis `backend/`, `python -m pytest tests/<fichier> -v` (les tests existants utilisent la fixture `db_session` de `tests/conftest.py`).

---

### Task 1: Setting `ai_prefilter_model`

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Ajouter le setting**

Dans `backend/app/config.py`, après `ai_model`:

```python
    ai_model: str = "deepseek/deepseek-v4-flash"
    ai_prefilter_model: str = "openai/gpt-4o-mini"
```

**Step 2: Vérifier que rien ne casse**

Run: `cd backend && python -c "from app.config import settings; print(settings.ai_prefilter_model)"`
Expected: `openai/gpt-4o-mini`

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add ai_prefilter_model setting for URL prefilter"
```

---

### Task 2: Module `UrlPrefilter` — parsing et fail-open

**Files:**
- Create: `backend/app/agent/url_prefilter.py`
- Test: `backend/tests/test_url_prefilter.py`

**Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_url_prefilter.py` :

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.agent.url_prefilter import UrlPrefilter, decisions_from_response


def _candidates():
    return [
        {"url": "https://a.com/1", "title": "Nouvelle usine à Lyon", "snippet": "…", "published_at": "2026-06-01"},
        {"url": "https://a.com/2", "title": "Contournement RN88", "snippet": "…", "published_at": None},
        {"url": "https://a.com/3", "title": "Extension entrepôt", "snippet": "…", "published_at": None},
    ]


def test_decisions_from_response_parses_plain_json():
    content = json.dumps([
        {"url": "https://a.com/1", "fetch": True, "reason": "usine neuve"},
        {"url": "https://a.com/2", "fetch": False, "reason": "voirie"},
    ])
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (True, "usine neuve")
    assert decisions["https://a.com/2"] == (False, "voirie")


def test_decisions_from_response_parses_fenced_json():
    content = '```json\n[{"url": "https://a.com/1", "fetch": false, "reason": "hors sujet"}]\n```'
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (False, "hors sujet")


@pytest.mark.asyncio
async def test_select_returns_fetch_flags_and_fail_open_for_missing_urls():
    # L'URL 3 est absente de la réponse LLM → fail-open (retenue).
    llm_content = json.dumps([
        {"url": "https://a.com/1", "fetch": True, "reason": "ok"},
        {"url": "https://a.com/2", "fetch": False, "reason": "voirie"},
    ])
    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": llm_content}}]}
    fake_response.raise_for_status = MagicMock()

    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        client = client_cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=fake_response)
        decisions = await prefilter.select(_candidates())

    assert decisions["https://a.com/1"] == (True, "ok")
    assert decisions["https://a.com/2"] == (False, "voirie")
    assert decisions["https://a.com/3"][0] is True  # fail-open


@pytest.mark.asyncio
async def test_select_propagates_http_errors():
    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        client = client_cls.return_value.__aenter__.return_value
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(httpx.ConnectError):
            await prefilter.select(_candidates())


@pytest.mark.asyncio
async def test_select_with_no_candidates_returns_empty_without_llm_call():
    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        decisions = await prefilter.select([])
    assert decisions == {}
    client_cls.assert_not_called()
```

**Step 2: Vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/test_url_prefilter.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.agent.url_prefilter'`

**Step 3: Implémenter le module**

Créer `backend/app/agent/url_prefilter.py` :

```python
import json
import time
from collections.abc import Awaitable, Callable

import httpx

from app.agent.llm_extractor import parse_json_content
from app.config import settings

StepLogger = Callable[[str, dict | None, int | None], Awaitable[None]]

PREFILTER_SYSTEM_PROMPT = """Tu es un assistant pour un installateur solaire C&I (Commercial & Industrial).
On te fournit une liste de résultats de recherche (titre + extrait + URL + date éventuelle).
Pour CHAQUE entrée, décide s'il vaut la peine de récupérer l'article complet.

fetch=true UNIQUEMENT si le titre/extrait suggère un projet de NOUVELLE construction,
extension, agrandissement ou création de bâtiment industriel, logistique ou retail
(entrepôt, usine, plateforme logistique, centre commercial neuf, bâtiment tertiaire neuf)
offrant un potentiel toiture/ombrières pour le solaire C&I.

fetch=false notamment pour : aménagement routier ou voirie, rénovation légère sans
extension de surface, simple ouverture d'une boutique dans un centre existant,
concertation publique sans chantier neuf, inauguration ou événement sans construction,
politique publique sans bâtiment neuf, site déjà en exploitation sans extension,
fermeture, cession, actualité sans projet de construction.

Dans le doute (titre ambigu mais potentiellement pertinent), mets fetch=true.

Retourne UNIQUEMENT un JSON valide (sans markdown, sans commentaire) :
[{"url": "...", "fetch": true|false, "reason": "raison courte en français"}]
Une entrée par URL fournie, en conservant les URLs EXACTEMENT telles quelles."""


def decisions_from_response(content: str) -> dict[str, tuple[bool, str]]:
    data = parse_json_content(content)
    decisions: dict[str, tuple[bool, str]] = {}
    for item in data:
        url = item.get("url")
        if not url:
            continue
        decisions[url] = (bool(item.get("fetch")), str(item.get("reason") or ""))
    return decisions


def _candidates_payload(candidates: list[dict]) -> str:
    lines = []
    for i, candidate in enumerate(candidates, start=1):
        entry = {
            "url": candidate.get("url"),
            "title": candidate.get("title") or "",
            "snippet": (candidate.get("snippet") or "")[:300],
        }
        if candidate.get("published_at"):
            entry["published_at"] = candidate["published_at"]
        lines.append(f"{i}. {json.dumps(entry, ensure_ascii=False)}")
    return "\n".join(lines)


class UrlPrefilter:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.ai_gateway_api_key
        self.model = model or settings.ai_prefilter_model

    async def select(
        self,
        candidates: list[dict],
        step_logger: StepLogger | None = None,
    ) -> dict[str, tuple[bool, str]]:
        if not candidates:
            return {}
        if step_logger:
            await step_logger(
                "prefilter_start",
                {"candidate_count": len(candidates), "model": self.model},
            )
        started = time.monotonic()
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
                        {"role": "system", "content": PREFILTER_SYSTEM_PROMPT},
                        {"role": "user", "content": _candidates_payload(candidates)},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        decisions = decisions_from_response(content)
        # Fail-open : toute URL absente de la réponse est retenue.
        for candidate in candidates:
            url = candidate.get("url")
            if url and url not in decisions:
                decisions[url] = (True, "absent de la réponse préfiltre")
        if step_logger:
            kept = sum(1 for fetch, _ in decisions.values() if fetch)
            await step_logger(
                "prefilter_done",
                {
                    "model": self.model,
                    "kept_count": kept,
                    "rejected_count": len(decisions) - kept,
                },
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return decisions
```

**Step 4: Vérifier que les tests passent**

Run: `cd backend && python -m pytest tests/test_url_prefilter.py -v`
Expected: 5 PASS

**Step 5: Commit**

```bash
git add backend/app/agent/url_prefilter.py backend/tests/test_url_prefilter.py
git commit -m "feat: add UrlPrefilter LLM batch classifier for search candidates"
```

---

### Task 3: Intégration pipeline — 25 résultats, préfiltre, cap 10, fallback

**Files:**
- Modify: `backend/app/agent/pipeline.py`
- Test: `backend/tests/test_pipeline_prefilter.py`

**Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_pipeline_prefilter.py`. Patron identique à `tests/test_pipeline_test_mode.py` (mocks `app.agent.pipeline.ExaClient`, `LLMExtractor`, `run_dedup_pass`, `emit_event`) avec en plus un mock de `app.agent.pipeline.UrlPrefilter` :

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.schemas import ProjectExtraction
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
from app.models.run import Run


def _make_config():
    return Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )


def _search_results(n: int) -> list[dict]:
    return [
        {"url": f"https://a.com/{i}", "title": f"T{i}", "score": 1.0 - i * 0.01,
         "highlights": [f"snippet {i}"]}
        for i in range(n)
    ]


def _run_patches(config, fake_extraction, decisions):
    prefilter = AsyncMock()
    prefilter.select = AsyncMock(return_value=decisions)
    return prefilter, (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient"),
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=prefilter),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock, return_value=[]),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    )


@pytest.mark.asyncio
async def test_search_requests_25_results_and_caps_fetch_to_10(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(25)
    # Le préfiltre retient 15 URLs (0..14), rejette le reste.
    decisions = {
        f"https://a.com/{i}": (i < 15, "ok" if i < 15 else "hors sujet")
        for i in range(25)
    }
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )

    prefilter, patches = _run_patches(config, fake_extraction, decisions)
    with patches[0], patches[1] as exa_cls, patches[2], patches[3], patches[4], patches[5]:
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=search)
        exa.fetch = AsyncMock(return_value=[])

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    assert exa.search.await_args.kwargs["num_results"] == 25
    fetched_urls = exa.fetch.await_args.args[0]
    assert len(fetched_urls) == 10
    # Priorisées par score Exa décroissant → les 10 premiers indices retenus.
    assert fetched_urls == [f"https://a.com/{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_prefilter_rejects_emit_skip_and_are_not_marked_processed(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(3)
    decisions = {
        "https://a.com/0": (True, "ok"),
        "https://a.com/1": (False, "voirie"),
        "https://a.com/2": (False, "inauguration"),
    }
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )

    prefilter, patches = _run_patches(config, fake_extraction, decisions)
    with patches[0], patches[1] as exa_cls, patches[2], patches[3], patches[4], patches[5]:
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=search)
        exa.fetch = AsyncMock(return_value=[])

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    assert exa.fetch.await_args.args[0] == ["https://a.com/0"]
    # Les rejets du préfiltre ne sont PAS enregistrés en ProcessedUrl.
    processed = {row[0] for row in db_session.query(ProcessedUrl.url).all()}
    assert "https://a.com/1" not in processed
    assert "https://a.com/2" not in processed
    # Un step article_skipped(prefiltered) est loggé pour chaque rejet.
    from app.models.run_step import RunStep

    skips = (
        db_session.query(RunStep)
        .filter(RunStep.run_id == run.id, RunStep.step_type == "article_skipped")
        .all()
    )
    reasons = {(s.data or {}).get("url"): (s.data or {}).get("reason") for s in skips}
    assert reasons.get("https://a.com/1") == "prefiltered"
    assert reasons.get("https://a.com/2") == "prefiltered"


@pytest.mark.asyncio
async def test_prefilter_failure_falls_back_to_top_10(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(15)
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )

    prefilter, patches = _run_patches(config, fake_extraction, {})
    prefilter.select = AsyncMock(side_effect=RuntimeError("llm down"))
    with patches[0], patches[1] as exa_cls, patches[2], patches[3], patches[4], patches[5]:
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=search)
        exa.fetch = AsyncMock(return_value=[])

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    # Fallback : les 10 premières URLs dans l'ordre Exa, run non échoué.
    assert exa.fetch.await_args.args[0] == [f"https://a.com/{i}" for i in range(10)]
    db_session.refresh(run)
    assert run.status == "completed"
```

**Step 2: Vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/test_pipeline_prefilter.py -v`
Expected: FAIL (`AttributeError`/`ImportError` sur `app.agent.pipeline.UrlPrefilter`, puis assertions `num_results == 25`)

**Step 3: Modifier `pipeline.py`**

3a. Imports et constantes (en haut du fichier, après les imports existants) :

```python
from app.agent.url_prefilter import UrlPrefilter

EXA_NUM_RESULTS = 25
MAX_FETCH_PER_SEARCH = 10
```

3b. Messages dans `_STEP_MESSAGES` :

```python
    "prefilter_start": "Préfiltre LLM — {candidate_count} candidat(s)",
    "prefilter_done": "Préfiltre LLM — {kept_count} retenu(s), {rejected_count} rejeté(s) en {duration_ms} ms",
```

3c. Instancier après `llm = LLMExtractor()` :

```python
    prefilter = UrlPrefilter()
```

3d. Dans l'appel `exa.search(...)`, remplacer `num_results=10` par `num_results=EXA_NUM_RESULTS`.

3e. Après le bloc qui calcule `new_urls` et émet les `article_skipped` known/blocked, remplacer le passage direct au fetch par :

```python
                if not new_urls:
                    continue

                candidates = []
                for url in new_urls:
                    result = search_by_url.get(url) or {}
                    highlights = result.get("highlights") or []
                    snippet = highlights[0] if highlights and isinstance(highlights[0], str) else ""
                    candidates.append(
                        {
                            "url": url,
                            "title": result.get("title") or url,
                            "snippet": snippet,
                            "published_at": result.get("publishedDate"),
                            "score": result.get("score"),
                        }
                    )

                try:
                    decisions = await prefilter.select(candidates, step_logger=step_logger)
                except Exception:
                    decisions = None  # fallback : tout garder, ordre Exa

                if decisions is None:
                    kept_urls = new_urls[:MAX_FETCH_PER_SEARCH]
                else:
                    kept, rejected = [], []
                    for candidate in candidates:
                        fetch_flag, _reason = decisions.get(candidate["url"], (True, ""))
                        (kept if fetch_flag else rejected).append(candidate)
                    for candidate in rejected:
                        await _emit_article_skipped(
                            session,
                            run_id,
                            url=candidate["url"],
                            title=candidate["title"],
                            reason="prefiltered",
                        )
                    kept.sort(key=lambda c: c.get("score") or 0.0, reverse=True)
                    kept_urls = [c["url"] for c in kept[:MAX_FETCH_PER_SEARCH]]

                if not kept_urls:
                    continue
```

3f. Remplacer `fetched = await exa.fetch(new_urls)` par `fetched = await exa.fetch(kept_urls)` et `{"url_count": len(new_urls)}` par `{"url_count": len(kept_urls)}`.

**Step 4: Vérifier que tous les tests passent**

Run: `cd backend && python -m pytest tests/test_pipeline_prefilter.py tests/test_pipeline_test_mode.py tests/test_article_skipped.py tests/test_run_steps.py -v`
Expected: PASS partout. Si `test_pipeline_test_mode.py` ou d'autres tests pipeline échouent parce qu'ils ne mockent pas `UrlPrefilter`, ajouter dans leurs `with (...)` :
`patch("app.agent.pipeline.UrlPrefilter") as prefilter_cls` + `prefilter_cls.return_value.select = AsyncMock(return_value={u["url"]: (True, "") for u in fake_search})` (ou laisser le fallback jouer en levant une exception).

**Step 5: Lancer la suite complète**

Run: `cd backend && python -m pytest -q`
Expected: tout PASS

**Step 6: Commit**

```bash
git add backend/app/agent/pipeline.py backend/tests/test_pipeline_prefilter.py backend/tests/test_pipeline_test_mode.py
git commit -m "feat: fetch 25 Exa results, prefilter URLs via batch LLM, cap fetch at 10"
```

---

### Task 4: Vérification finale

**Step 1: Suite complète + lints**

Run: `cd backend && python -m pytest -q`
Expected: tout PASS

**Step 2: Vérifier la doc d'env si présente**

Si `README.md` ou `.env.example` documente `AI_MODEL`, ajouter une ligne pour `AI_PREFILTER_MODEL` (défaut `openai/gpt-4o-mini`). Commit `docs: document AI_PREFILTER_MODEL`.
