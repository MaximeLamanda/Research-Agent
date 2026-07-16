import json
import time
from collections.abc import Awaitable, Callable

import httpx
from pydantic import ValidationError

from app.agent.entreprise_client import CompanyCandidate
from app.agent.llm_extractor import parse_json_content
from app.agent.schemas import CompanyResolution
from app.config import settings

StepLogger = Callable[[str, dict | None, int | None], Awaitable[None]]

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
        step_logger: StepLogger | None = None,
    ) -> CompanyResolution:
        if not candidates:
            return CompanyResolution(matched=False, reason="Aucun candidat trouvé dans l'API gouv.")

        payload = {
            "company_name": company_name,
            "city": city,
            "article_excerpt": article_context[:1500],
            "candidates": [c.model_dump() for c in candidates],
        }
        if step_logger:
            await step_logger(
                "llm_company_resolve_start",
                {"company": company_name, "candidate_count": len(candidates)},
            )
        started = time.monotonic()
        try:
            content = await self._call_llm(json.dumps(payload, ensure_ascii=False))
            data = parse_json_content(content)
            resolution = CompanyResolution.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            resolution = CompanyResolution(
                matched=False,
                reason=f"Réponse LLM invalide : {exc}",
            )
        if step_logger:
            await step_logger(
                "llm_company_resolve_done",
                {
                    "company": company_name,
                    "matched": resolution.matched,
                    "siren": resolution.siren,
                },
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return resolution
