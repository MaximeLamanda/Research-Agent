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

Ce préfiltre est volontairement permissif : l'analyse fine (y compris la géographie)
se fait ensuite sur le texte complet. En cas de doute, retiens l'article (fetch=true).

fetch=true si le titre ou l'extrait laisse penser à un projet industriel, logistique,
commercial ou tertiaire potentiellement pertinent pour le solaire en toiture, par exemple :
- nouvelle construction, extension, agrandissement, déménagement ou création de site
- investissement, implantation, usine, entrepôt, plateforme logistique, zone d'activités
- lancement de travaux, permis de construire, livraison d'un nouveau bâtiment
- réindustrialisation ou réhabilitation lourde avec extension de surface

fetch=false UNIQUEMENT si l'article est clairement hors sujet thématique, par exemple :
- voirie, transport, politique ou société sans lien avec un bâtiment ou site
- simple ouverture de boutique sans chantier
- concertation ou débat public sans projet concret annoncé
- fermeture, liquidation ou cession sans projet de remplacement

Ne filtre PAS sur la géographie (ville, département, région, pays) : c'est géré après.
Ne rejette pas un article parce que l'extrait est incomplet ou orienté « investissement »
plutôt que « construction ». Ne rejette pas non plus une inauguration si elle concerne
un site récemment construit ou agrandi.

Retourne UNIQUEMENT un JSON valide (sans markdown, sans commentaire) :
[{"url": "...", "fetch": true|false, "reason": "raison courte en français"}]
Une entrée par URL fournie, en conservant les URLs EXACTEMENT telles quelles."""


def decisions_from_response(content: str) -> dict[str, tuple[bool, str]]:
    data = parse_json_content(content)
    if isinstance(data, dict):
        # Tolère un objet englobant ({"results": [...]}) ou une entrée unique.
        wrapped = next((v for v in data.values() if isinstance(v, list)), None)
        data = wrapped if wrapped is not None else [data]
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
        country: str = "FR",  # conservé pour compatibilité ; la géo n'est pas filtrée ici
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
