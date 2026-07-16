from app.agent.published_date_presets import resolve_published_date_range
from app.models.config import Config
from app.schemas import ConfigRead, ConfigUpdate
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/api/config", tags=["config"])

GEOGRAPHICAL_GRANULARITY_LARGE = "large"


def normalize_config(config: Config) -> bool:
    """Applique les valeurs supportées (city_focus retiré, deep → auto)."""
    changed = False
    if config.geographical_granularity != GEOGRAPHICAL_GRANULARITY_LARGE:
        config.geographical_granularity = GEOGRAPHICAL_GRANULARITY_LARGE
        changed = True
    if config.region_cities:
        config.region_cities = {}
        changed = True
    if config.exa_search_type == "deep":
        config.exa_search_type = "auto"
        changed = True
    return changed


def get_or_create_config(db: Session) -> Config:
    config = db.query(Config).first()
    if config is None:
        config = Config(departments=[])
        db.add(config)
        db.commit()
        db.refresh(config)
    elif normalize_config(config):
        db.commit()
        db.refresh(config)
    return config


def config_to_read(config: Config) -> ConfigRead:
    effective_start, effective_end = resolve_published_date_range(
        config.exa_published_date_preset,
        config.exa_start_published_date,
        config.exa_end_published_date,
    )
    return ConfigRead(
        id=config.id,
        country=config.country,
        departments=config.departments,
        region_cities=config.region_cities or {},
        cron_day=config.cron_day,
        cron_hour=config.cron_hour,
        sectors=config.sectors,
        exa_search_type=config.exa_search_type,
        exa_category=config.exa_category,
        geographical_granularity=config.geographical_granularity or "large",
        exa_published_date_preset=config.exa_published_date_preset,
        exa_start_published_date=config.exa_start_published_date,
        exa_end_published_date=config.exa_end_published_date,
        exa_published_date_effective_start=effective_start,
        exa_published_date_effective_end=effective_end,
        updated_at=config.updated_at,
    )


@router.get("", response_model=ConfigRead)
def read_config(db: Session = Depends(get_db)):
    return config_to_read(get_or_create_config(db))


@router.put("", response_model=ConfigRead)
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)):
    config = get_or_create_config(db)
    data = payload.model_dump(exclude_unset=True)
    data.pop("geographical_granularity", None)
    data.pop("region_cities", None)
    for key, value in data.items():
        setattr(config, key, value)
    normalize_config(config)
    db.commit()
    db.refresh(config)
    return config_to_read(config)
