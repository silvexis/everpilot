"""Lifespan wiring: Postgres store is installed when DATABASE_URL is set."""

import pytest
from fastapi.testclient import TestClient

from everpilot import main as main_module
from everpilot.config import get_settings
from everpilot.db import InMemoryRepoConfigStore, PostgresRepoConfigStore


class FakePool:
    def __init__(self) -> None:
        self.opened = False
        self.closed = False

    async def open(self, wait: bool = False) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_lifespan_uses_postgres_store_when_database_url_set(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://everpilot:x@localhost:5432/everpilot")
    fake_pool = FakePool()
    monkeypatch.setattr(main_module, "create_pool", lambda url: fake_pool)
    # Keep DBOS out of unit tests: it would connect to the (fake) database URL.
    from everpilot.orchestration import dbos_engine

    monkeypatch.setattr(
        dbos_engine, "init_dbos", lambda app, name, url: dbos_engine.DBOSEventDispatcher()
    )

    app = main_module.create_app()
    with TestClient(app) as client:
        assert isinstance(app.state.repo_store, PostgresRepoConfigStore)
        assert fake_pool.opened is True
        assert client.get("/api/v1/health").status_code == 200
    assert fake_pool.closed is True


def test_lifespan_defaults_to_in_memory_store(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    app = main_module.create_app()
    with TestClient(app):
        assert isinstance(app.state.repo_store, InMemoryRepoConfigStore)
