import json
import re
import time
from collections.abc import Awaitable, Callable

import httpx

from app.agent.schemas import ProjectExtraction
from app.config import settings

StepLogger = Callable[[str, dict | None, int | None], Awaitable[None]]

_LANGUAGE_RULES = """LANGUE — OBLIGATOIRE pour tous les champs texte remplis :
- Extraire les informations de l'article et les renseigner EN ANGLAIS (traduire si la source est en français, allemand ou autre langue).
- Conserver l'orthographe originale des noms propres (entreprises, marques, personnes, toponymes officiels : ex. Lyon, München, Amazon).
- Traduire les libellés descriptifs, rôles, mois/trimestres et formulations génériques (ex. « entrepôt logistique » → « logistics warehouse », « juin 2026 » → « June 2026 », « Mitte 2028 » → « mid 2028 »).
- Les enums status et sector gardent leurs valeurs françaises exactes : conception|travaux|livraison, industriel|logistique|retail."""

_BASE_PROMPT = """Tu es un assistant pour un installateur solaire C&I (Commercial & Industrial).
Analyse l'article fourni et retourne UNIQUEMENT un JSON valide (sans markdown, sans commentaire) avec les champs:

is_relevant (true|false) — OBLIGATOIRE. true UNIQUEMENT si l'article décrit un projet de NOUVELLE construction, extension, agrandissement ou création de bâtiment industriel, logistique ou retail (entrepôt, usine, plateforme logistique, centre commercial neuf, bâtiment tertiaire neuf, etc.) offrant un potentiel toiture/ombrières pour le solaire C&I.
false si l'article concerne notamment : aménagement routier ou voirie (ex. transformation de RN, contournement), rénovation légère sans extension de surface, simple ouverture d'une boutique ou enseigne dans un centre déjà existant, concertation publique sans chantier neuf, inauguration ou événement sans construction, politique publique sans bâtiment neuf, entrepôt ou site déjà en exploitation sans extension, fermeture, cession, ou actualité sans projet de construction.

name, company, surface_m2, delivery_date (commissioning / go-live — en anglais, ex. June 2026, mid 2028, end 2027, ou YYYY-MM-DD ; si plusieurs dates, la plus proche opérationnelle ; ou null), city, address, department ({department_format}),
status (conception|travaux|livraison ou null), sector (industriel|logistique|retail ou null),
people (liste de {{name, role, company}} — responsables du projet cités dans l'article ; role en anglais),
lead_pitch (si is_relevant=true : 1 à 2 phrases EN ANGLAIS sur des éléments de l'article absents des autres champs — toiture, parkings/ombrières, consommation énergétique, usage du bâtiment, engagements RSE, investissement — qui justifient l'intérêt solaire C&I ; ne répète pas surface, dates, secteur, localisation, statut, entreprise ni contacts ; sinon null).

Si is_relevant=false, mets null ou [] pour les autres champs (name peut être un libellé court de l'article pour référence, en anglais).
Si une info est absente, mets null ou [].
{language_rules}
{department_rules}
"""

_DEPARTMENT_RULES_FR = """Pour department, déduis-le de la localisation précise du chantier (ville, adresse, contexte géographique). Ne devine pas : mets null si le département n'est pas identifiable dans l'article.
Utilise toujours le format "code - nom" avec le code département à 2 caractères (ex. "69 - Rhône")."""

_DEPARTMENT_RULES_DE = """Pour department, déduis le Bundesland de la localisation précise du chantier (ville, adresse, contexte géographique). Ne devine pas : mets null si le Land n'est pas identifiable dans l'article.
Utilise toujours le format "code - nom" avec le code Land à 2 lettres (ex. "BY - Bayern", "NW - Nordrhein-Westfalen")."""

_DEPARTMENT_FORMATS = {
    "FR": 'format OBLIGATOIRE si connu : "XX - Nom", ex. "69 - Rhône", "38 - Isère" ; jamais le nom seul ni le code seul',
    "DE": 'format OBLIGATOIRE si connu : "XX - Nom", ex. "BY - Bayern", "NW - Nordrhein-Westfalen" ; jamais le nom seul ni le code seul',
}

_DEPARTMENT_RULES_BY_COUNTRY = {
    "FR": _DEPARTMENT_RULES_FR,
    "DE": _DEPARTMENT_RULES_DE,
}

SYSTEM_PROMPT = _BASE_PROMPT.format(
    department_format=_DEPARTMENT_FORMATS["FR"],
    language_rules=_LANGUAGE_RULES,
    department_rules=_DEPARTMENT_RULES_FR,
)


def system_prompt_for_country(country: str = "FR") -> str:
    normalized = country.upper()
    return _BASE_PROMPT.format(
        department_format=_DEPARTMENT_FORMATS.get(normalized, _DEPARTMENT_FORMATS["FR"]),
        language_rules=_LANGUAGE_RULES,
        department_rules=_DEPARTMENT_RULES_BY_COUNTRY.get(normalized, _DEPARTMENT_RULES_FR),
    )


def parse_json_content(content: str) -> dict:
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


class LLMExtractor:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.ai_gateway_api_key
        self.model = model or settings.ai_model

    async def extract(
        self,
        article_text: str,
        title: str = "",
        country: str = "FR",
        step_logger: StepLogger | None = None,
    ) -> ProjectExtraction:
        user_content = f"Titre: {title}\n\nArticle:\n{article_text}"
        if step_logger:
            await step_logger("llm_extract_start", {"model": self.model, "title": title})
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
                        {"role": "system", "content": system_prompt_for_country(country)},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = parse_json_content(content)
            extraction = ProjectExtraction.model_validate(data, context={"country": country})
        if step_logger:
            await step_logger(
                "llm_extract_done",
                {
                    "model": self.model,
                    "title": title,
                    "is_relevant": extraction.is_relevant,
                },
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return extraction
