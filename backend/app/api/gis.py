from fastapi import APIRouter, HTTPException, Query

from app.gis.constants import AGRICULTURAL_LANDUSE_TAGS, DEFAULT_MIN_FOOTPRINT_M2
from app.gis.service import GisDatabaseNotConfiguredError, count_agricultural_footprints
from app.schemas import AgriculturalFootprintStatsRead

router = APIRouter(prefix="/api/gis", tags=["gis"])


@router.get("/agricultural-footprints", response_model=AgriculturalFootprintStatsRead)
def get_agricultural_footprints(
    department: str = Query(..., description="Code ou libellé département, ex. 33 ou 33 - Gironde"),
    min_m2: float = Query(DEFAULT_MIN_FOOTPRINT_M2, gt=0, description="Seuil emprise en m²"),
    filter_by_department: bool = Query(
        True,
        description="Filtrer via code_insee LIKE dep% (désactiver si code_insee souvent NULL)",
    ),
):
    try:
        stats = count_agricultural_footprints(
            department,
            min_footprint_m2=min_m2,
            filter_by_department=filter_by_department,
        )
    except GisDatabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur PostGIS: {exc}",
        ) from exc

    return AgriculturalFootprintStatsRead(
        department_code=stats.department_code,
        min_footprint_m2=stats.min_footprint_m2,
        total=stats.total,
        by_landuse=stats.by_landuse,
        filter_by_department=stats.filter_by_department,
        agricultural_landuse_tags=list(AGRICULTURAL_LANDUSE_TAGS),
    )
