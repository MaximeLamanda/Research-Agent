from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://research:research@db:5432/research_agent"
    gis_database_url: str = ""
    gis_buildings_table: str = "public.osm_building_footprints"
    gis_landuse_table: str = "public.osm_landuse_areas"
    exa_api_key: str = ""
    ai_gateway_api_key: str = ""
    ai_model: str = "deepseek/deepseek-v4-flash"
    ai_prefilter_model: str = "openai/gpt-4o-mini"
    testing: bool = False

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
