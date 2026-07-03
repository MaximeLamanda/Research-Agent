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
