from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Everpilot"
    app_env: str = "development"
    debug: bool = False

    # GitHub App
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_webhook_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # Database (empty = in-memory store, development only)
    database_url: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "https://everpilot.ai",
        "https://everpilot.dev",
        "https://everpilot.io",
    ]

    # Auth / JWT
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 hours


@lru_cache
def get_settings() -> Settings:
    return Settings()
