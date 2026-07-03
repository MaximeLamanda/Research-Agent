"""Traduit les champs texte des projets en anglais directement en base."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from typing import Any

import httpx

from app.config import settings
from app.db.session import SessionLocal
from app.models.project import Project

SECTOR_TO_ENGLISH = {
    "industriel": "Industrial",
    "logistique": "Logistics",
    "retail": "Retail",
    "commerce": "Retail",
}

STATUS_TO_ENGLISH = {
    "conception": "Design",
    "travaux": "Construction",
    "livraison": "Delivery",
}

TRANSLATE_SYSTEM_PROMPT = """You translate construction-project database fields into English for export.
Return ONLY valid JSON (no markdown) with the same keys as the input.
Rules:
- Translate project names when they are in French (e.g. « Nouvelle usine X » → « New X factory », « Extension des Y » → « Extension of Y »).
- Translate descriptive text; keep proper nouns unchanged (company names, people names, city names like Lyon, München).
- Translate roles in people[].role to English.
- Translate months/quarters in delivery_date (e.g. « juin 2026 » → « June 2026 », « Mitte 2028 » → « mid 2028 »).
- If a value is already English or null, return it unchanged.
- Do not invent information."""

BATCH_SIZE = 8


FRENCH_NAME_HINT = re.compile(
    r"\b(nouvelle|nouveau|nouveaux|extension|agrandissement|reconstruction|centre|plateforme|usine|entrepôt|projet)\b",
    re.I,
)


def _needs_llm(project: Project) -> bool:
    if project.lead_pitch:
        return True
    if project.name and (
        re.search(r"[àâäéèêëïîôùûüçœæ]", project.name, re.I)
        or FRENCH_NAME_HINT.search(project.name)
    ):
        return True
    if project.address and re.search(r"[àâäéèêëïîôùûüçœæ]", project.address, re.I):
        return True
    if project.delivery_date and re.search(r"[àâäéèêëïîôùûüçœæ]", project.delivery_date, re.I):
        return True
    for person in project.people or []:
        role = person.get("role") if isinstance(person, dict) else None
        if role and re.search(r"[àâäéèêëïîôùûüçœæ]", role, re.I):
            return True
    return False


def _project_payload(project: Project) -> dict[str, Any]:
    return {
        "lead_pitch": project.lead_pitch,
        "name": project.name,
        "address": project.address,
        "delivery_date": project.delivery_date,
        "people": project.people or [],
    }


def _parse_json_content(content: str) -> dict:
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


async def _translate_batch(
    client: httpx.AsyncClient,
    items: list[tuple[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    user_content = json.dumps(
        {project_id: payload for project_id, payload in items},
        ensure_ascii=False,
    )
    response = await client.post(
        "https://ai-gateway.vercel.sh/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.ai_gateway_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Translate these project fields to English:\n{user_content}",
                },
            ],
        },
        timeout=120.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    data = _parse_json_content(content)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _apply_enum_maps(session, *, dry_run: bool) -> tuple[int, int]:
    projects = session.query(Project).filter(Project.merged_into_id.is_(None)).all()
    sector_updates = 0
    status_updates = 0
    for project in projects:
        new_sector = SECTOR_TO_ENGLISH.get(project.sector or "")
        if new_sector and project.sector != new_sector:
            sector_updates += 1
            if not dry_run:
                project.sector = new_sector
        new_status = STATUS_TO_ENGLISH.get(project.status or "")
        if new_status and project.status != new_status:
            status_updates += 1
            if not dry_run:
                project.status = new_status
    return sector_updates, status_updates


async def _translate_text_fields(
    session,
    *,
    dry_run: bool,
    limit: int | None,
) -> int:
    if not settings.ai_gateway_api_key:
        print("AI_GATEWAY_API_KEY manquant — traduction texte ignorée.", file=sys.stderr)
        return 0

    query = session.query(Project).filter(Project.merged_into_id.is_(None))
    if limit is not None:
        query = query.limit(limit)
    projects = [p for p in query.all() if _needs_llm(p)]
    if not projects:
        return 0

    updated = 0
    async with httpx.AsyncClient() as client:
        for offset in range(0, len(projects), BATCH_SIZE):
            batch = projects[offset : offset + BATCH_SIZE]
            items = [(str(p.id), _project_payload(p)) for p in batch]
            try:
                translated = await _translate_batch(client, items)
            except Exception as exc:
                print(f"Erreur LLM batch {offset // BATCH_SIZE + 1}: {exc}", file=sys.stderr)
                continue

            for project in batch:
                key = str(project.id)
                fields = translated.get(key)
                if not isinstance(fields, dict):
                    print(f"Pas de traduction pour {project.name[:50]} ({key})", file=sys.stderr)
                    continue

                changed = False
                for field in ("lead_pitch", "name", "address", "delivery_date"):
                    new_value = fields.get(field)
                    if new_value and getattr(project, field) != new_value:
                        changed = True
                        if not dry_run:
                            setattr(project, field, new_value)

                new_people = fields.get("people")
                if isinstance(new_people, list) and new_people != (project.people or []):
                    changed = True
                    if not dry_run:
                        project.people = new_people

                if changed:
                    updated += 1
                    print(f"  ✓ {project.name[:60]}", flush=True)

            if offset + BATCH_SIZE < len(projects):
                await asyncio.sleep(0.5)

    return updated


async def run(*, dry_run: bool, limit: int | None) -> None:
    session = SessionLocal()
    try:
        total = (
            session.query(Project)
            .filter(Project.merged_into_id.is_(None))
            .count()
        )
        print(f"Projets actifs: {total}")
        if dry_run:
            print("Mode dry-run — aucune écriture en base.", flush=True)

        sector_updates, status_updates = _apply_enum_maps(session, dry_run=dry_run)
        print(f"Secteurs à traduire: {sector_updates}", flush=True)
        print(f"Statuts à traduire: {status_updates}", flush=True)

        text_updates = await _translate_text_fields(session, dry_run=dry_run, limit=limit)
        print(f"Projets texte traduits: {text_updates}", flush=True)

        if not dry_run:
            session.commit()
            print("Commit OK.", flush=True)
        else:
            session.rollback()
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les changements sans écrire en base",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de projets pour la traduction LLM",
    )
    args = parser.parse_args()
    started = time.monotonic()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))
    print(f"Terminé en {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
