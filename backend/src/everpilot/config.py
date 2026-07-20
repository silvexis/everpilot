import logging
import os
from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


class SsmParameterSource(PydanticBaseSettingsSource):
    """Settings source reading SSM SecureStrings under /cz/{feature}/{namespace}/.

    Active only when EVERPILOT_SSM_CONFIG=true (set explicitly by the ECS task
    definition — never inferred from ambient variables). Values flow straight
    into Settings without touching os.environ, so secrets are never inherited
    by child processes (cz-standards security-secrets Principle 5).

    Fails closed: an enabled source that finds no parameters raises instead of
    letting the app boot on development defaults.
    """

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("EVERPILOT_SSM_CONFIG", "").lower() in ("1", "true")

    def __call__(self) -> dict[str, Any]:
        if not self.enabled():
            return {}
        feature = os.environ.get("CZ_FEATURE", "everpilot")
        namespace = os.environ.get("CZ_NAMESPACE", "")
        if not namespace:
            raise RuntimeError("EVERPILOT_SSM_CONFIG is set but CZ_NAMESPACE is missing")
        prefix = f"/cz/{feature}/{namespace}/"

        import boto3  # only deployments (uv --extra aws images) reach this import

        client = boto3.client("ssm")
        values: dict[str, Any] = {}
        field_names = set(Settings.model_fields)
        for page in client.get_paginator("get_parameters_by_path").paginate(
            Path=prefix, WithDecryption=True
        ):
            for parameter in page["Parameters"]:
                # kebab-case SSM key → snake_case Settings field; single scheme,
                # no hand-maintained mapping to drift (see infra/ssm-prereqs.conf)
                field = parameter["Name"].removeprefix(prefix).replace("-", "_")
                if field in field_names:
                    values[field] = parameter["Value"]
        if not values:
            raise RuntimeError(
                f"SSM config enabled but no parameters found under {prefix} — "
                "refusing to start on development defaults"
            )
        logger.info("Loaded %d settings from SSM prefix %s", len(values), prefix)
        return values

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        # Unused: __call__ is overridden wholesale.
        return None, field_name, False


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

    # Database. Either a full URL, or composed from parts: the deployment
    # passes DB_HOST (from CloudFormation) and the password arrives via SSM —
    # no hand-maintained database-url parameter to go stale when RDS endpoints
    # change (empty = in-memory store, development only).
    database_url: str = ""
    db_host: str = ""
    db_name: str = "everpilot"
    db_user: str = "everpilot"
    db_master_password: str = ""

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

    # Agent engine (M1+)
    anthropic_api_key: str = ""

    @model_validator(mode="after")
    def compose_database_url(self) -> "Settings":
        if not self.database_url and self.db_host:
            if not self.db_master_password:
                raise ValueError("db_host is set but db_master_password is missing")
            self.database_url = (
                f"postgresql://{self.db_user}:{self.db_master_password}"
                f"@{self.db_host}:5432/{self.db_name}"
            )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Explicit env beats SSM beats .env — deployments can still override
        # a single value via task-definition environment when debugging.
        return (
            init_settings,
            env_settings,
            SsmParameterSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
