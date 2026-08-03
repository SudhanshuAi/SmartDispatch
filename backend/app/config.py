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
    # Comma-separated origins for Admin Portal + Guest web (required in production)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:8081,http://127.0.0.1:8081,"
        "http://localhost:19006,http://127.0.0.1:19006"
    )

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
