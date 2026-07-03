from app.data.search_anchors_loader import anchors_for_codes, anchors_for_country
from app.schemas import RegionAnchorRead
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/search-anchors", tags=["search-anchors"])


@router.get("", response_model=dict[str, RegionAnchorRead])
def read_search_anchors(
    country: str = Query("FR", min_length=2, max_length=2),
    codes: list[str] | None = Query(None),
):
    """Top villes (et métropole FR) par département ou Land."""
    country = country.upper()
    if codes:
        return anchors_for_codes(codes, country)
    return anchors_for_country(country)
