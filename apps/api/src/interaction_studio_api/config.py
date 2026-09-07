from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    auth_mode: Literal["local", "authenticated"] = "authenticated"
    session_cookie_secure: bool = False

    @model_validator(mode="after")
    def require_production_auth(self):
        if self.app_env != "development" and (
            self.auth_mode != "authenticated" or not self.session_cookie_secure
        ):
            raise ValueError("production requires authentication and HTTPS cookies")
        return self

    log_level: str = "INFO"
    external_inference_enabled: bool = False
    artifact_root: Path = Path(".")
    web_dist_root: Path = Path("apps/web/dist")
    database_url: str = (
        "postgresql+psycopg://interaction_studio:change-me-for-nonlocal-use"
        "@localhost:5432/interaction_studio"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
