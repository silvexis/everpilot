"""Settings: SSM source (mocked boto3) and DATABASE_URL composition. No AWS calls."""

import sys
import types

import pytest

from everpilot.config import Settings, SsmParameterSource


def fake_boto3(parameters: dict[str, str]) -> types.ModuleType:
    class FakePaginator:
        def paginate(self, **kwargs):
            self.path = kwargs["Path"]
            assert kwargs["WithDecryption"] is True
            yield {
                "Parameters": [
                    {"Name": f"{kwargs['Path']}{key}", "Value": value}
                    for key, value in parameters.items()
                ]
            }

    class FakeClient:
        def get_paginator(self, name):
            assert name == "get_parameters_by_path"
            return FakePaginator()

    module = types.ModuleType("boto3")
    module.client = lambda service: FakeClient()
    return module


# --- DATABASE_URL composition ---


def test_url_composed_from_host_and_password() -> None:
    settings = Settings(db_host="db.internal", db_master_password="secret", _env_file=None)
    assert settings.database_url == "postgresql://everpilot:secret@db.internal:5432/everpilot"


def test_explicit_url_wins_over_parts() -> None:
    settings = Settings(
        database_url="postgresql://explicit",
        db_host="db.internal",
        db_master_password="secret",
        _env_file=None,
    )
    assert settings.database_url == "postgresql://explicit"


def test_host_without_password_raises() -> None:
    with pytest.raises(ValueError, match="db_master_password"):
        Settings(db_host="db.internal", _env_file=None)


def test_no_db_config_leaves_url_empty() -> None:
    assert Settings(_env_file=None).database_url == ""


# --- SSM source ---


def test_ssm_source_disabled_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("EVERPILOT_SSM_CONFIG", raising=False)
    assert SsmParameterSource.enabled() is False
    assert SsmParameterSource(Settings)() == {}


def test_ssm_source_requires_namespace(monkeypatch) -> None:
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "true")
    monkeypatch.delenv("CZ_NAMESPACE", raising=False)
    with pytest.raises(RuntimeError, match="CZ_NAMESPACE"):
        SsmParameterSource(Settings)()


def test_ssm_source_maps_kebab_keys_to_fields(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        fake_boto3({"secret-key": "s3cr3t", "db-master-password": "pw", "unrelated": "x"}),
    )
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "true")
    monkeypatch.setenv("CZ_NAMESPACE", "alfa")

    values = SsmParameterSource(Settings)()
    assert values == {"secret_key": "s3cr3t", "db_master_password": "pw"}


def test_ssm_source_fails_closed_when_empty(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3({}))
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "true")
    monkeypatch.setenv("CZ_NAMESPACE", "live")
    with pytest.raises(RuntimeError, match="refusing to start"):
        SsmParameterSource(Settings)()


def test_ssm_values_flow_into_settings(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        fake_boto3({"db-master-password": "pw", "github-app-id": "42"}),
    )
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "true")
    monkeypatch.setenv("CZ_NAMESPACE", "alfa")
    monkeypatch.setenv("DB_HOST", "db.internal")

    settings = Settings()
    assert settings.github_app_id == "42"
    # password from SSM composes the URL with the env-provided host
    assert settings.database_url == "postgresql://everpilot:pw@db.internal:5432/everpilot"
    # secret landed in the object, never in the process environment
    import os

    assert "DB_MASTER_PASSWORD" not in os.environ
    assert "SECRET_KEY" not in os.environ
