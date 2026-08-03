from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://smartdispatch:smartdispatch@localhost:5432/smartdispatch"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    auth_stub_default_role: str = "admin"
    # Kill-switch for graceful degradation drills (in-progress trips + overrides still work)
    matching_engine_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
