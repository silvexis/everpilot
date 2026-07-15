"""Unit tests for RepoConfigStore implementations.

PostgresRepoConfigStore is tested against a fake pool/connection — unit tests
never touch a real database.
"""

from datetime import UTC, datetime

import pytest
from psycopg.types.json import Jsonb

from everpilot.db import InMemoryRepoConfigStore, PostgresRepoConfigStore
from everpilot.models.capability import (
    DEFAULT_CAPABILITIES,
    Capability,
    CapabilityConfig,
    CapabilityMode,
)
from everpilot.models.repo import RepoConfig

REPO = "silvexis/test-repo"


def make_config() -> RepoConfig:
    return RepoConfig(repo_full_name=REPO, capabilities=list(DEFAULT_CAPABILITIES))


def autopilot_security() -> CapabilityConfig:
    return CapabilityConfig(
        capability=Capability.SECURITY, mode=CapabilityMode.AUTOPILOT, enabled=True
    )


# --- In-memory store ---


async def test_inmemory_create_and_get() -> None:
    store = InMemoryRepoConfigStore()
    assert await store.create(make_config()) is True
    config = await store.get(REPO)
    assert config is not None
    assert config.repo_full_name == REPO
    assert len(config.capabilities) == 5


async def test_inmemory_create_conflict() -> None:
    store = InMemoryRepoConfigStore()
    await store.create(make_config())
    assert await store.create(make_config()) is False


async def test_inmemory_list() -> None:
    store = InMemoryRepoConfigStore()
    assert await store.list_repo_names() == []
    await store.create(make_config())
    assert await store.list_repo_names() == [REPO]


async def test_inmemory_set_capability() -> None:
    store = InMemoryRepoConfigStore()
    await store.create(make_config())
    updated = await store.set_capability(REPO, autopilot_security())
    assert updated is not None
    security = next(c for c in updated.capabilities if c.capability == Capability.SECURITY)
    assert security.mode == CapabilityMode.AUTOPILOT
    assert security.enabled is True
    others = [c for c in updated.capabilities if c.capability != Capability.SECURITY]
    assert all(c.mode == CapabilityMode.OFF for c in others)


async def test_inmemory_set_capability_missing_repo() -> None:
    store = InMemoryRepoConfigStore()
    assert await store.set_capability(REPO, autopilot_security()) is None


async def test_inmemory_delete() -> None:
    store = InMemoryRepoConfigStore()
    await store.create(make_config())
    assert await store.delete(REPO) is True
    assert await store.delete(REPO) is False
    assert await store.get(REPO) is None


# --- Postgres store (fake connection; asserts SQL shape and row mapping) ---


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[tuple]:
        return self._rows

    async def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None


class FakeConnection:
    """Stands in for both the pooled connection and its transaction context."""

    def __init__(self, results: list[list[tuple]]) -> None:
        self._results = results
        self.queries: list[tuple[str, tuple | None]] = []

    async def execute(self, sql: str, params: tuple | None = None) -> FakeCursor:
        self.queries.append((" ".join(sql.split()), params))
        rows = self._results.pop(0) if self._results else []
        return FakeCursor(rows)

    def transaction(self) -> "FakeConnection":
        return self

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def connection(self) -> FakeConnection:
        return self._connection


def make_store(results: list[list[tuple]]) -> tuple[PostgresRepoConfigStore, FakeConnection]:
    conn = FakeConnection(results)
    return PostgresRepoConfigStore(FakePool(conn)), conn  # type: ignore[arg-type]


def db_row(config: RepoConfig) -> tuple:
    return (
        config.repo_full_name,
        [c.model_dump(mode="json") for c in config.capabilities],
        config.installed_at,
        config.active,
    )


async def test_pg_list_repo_names() -> None:
    store, conn = make_store([[("a/one",), ("b/two",)]])
    assert await store.list_repo_names() == ["a/one", "b/two"]
    assert "ORDER BY repo_full_name" in conn.queries[0][0]


async def test_pg_get_found_maps_row() -> None:
    store, _ = make_store([[db_row(make_config())]])
    config = await store.get(REPO)
    assert config is not None
    assert config.repo_full_name == REPO
    assert len(config.capabilities) == 5
    assert config.active is True


async def test_pg_get_not_found() -> None:
    store, conn = make_store([[]])
    assert await store.get(REPO) is None
    assert conn.queries[0][1] == (REPO,)


async def test_pg_create_inserts_jsonb() -> None:
    store, conn = make_store([[(1,)]])
    assert await store.create(make_config()) is True
    sql, params = conn.queries[0]
    assert "ON CONFLICT (repo_full_name) DO NOTHING" in sql
    assert params is not None
    assert params[0] == REPO
    assert isinstance(params[1], Jsonb)


async def test_pg_create_conflict_returns_false() -> None:
    store, _ = make_store([[]])
    assert await store.create(make_config()) is False


async def test_pg_set_capability_updates_row() -> None:
    now = datetime.now(UTC)
    config = RepoConfig(
        repo_full_name=REPO,
        capabilities=list(DEFAULT_CAPABILITIES),
        installed_at=now,
    )
    store, conn = make_store([[db_row(config)], []])
    updated = await store.set_capability(REPO, autopilot_security())
    assert updated is not None
    security = next(c for c in updated.capabilities if c.capability == Capability.SECURITY)
    assert security.mode == CapabilityMode.AUTOPILOT
    select_sql, _ = conn.queries[0]
    update_sql, update_params = conn.queries[1]
    assert "FOR UPDATE" in select_sql
    assert update_sql.startswith("UPDATE repo_configs SET capabilities")
    assert isinstance(update_params[0], Jsonb)


async def test_pg_set_capability_missing_repo() -> None:
    store, conn = make_store([[]])
    assert await store.set_capability(REPO, autopilot_security()) is None
    assert len(conn.queries) == 1  # no UPDATE issued


async def test_pg_delete() -> None:
    store, _ = make_store([[(1,)]])
    assert await store.delete(REPO) is True


async def test_pg_delete_not_found() -> None:
    store, _ = make_store([[]])
    assert await store.delete(REPO) is False


@pytest.mark.parametrize("method", ["list_repo_names", "get", "create", "delete"])
async def test_pg_store_satisfies_protocol(method: str) -> None:
    assert hasattr(PostgresRepoConfigStore, method)
    assert hasattr(InMemoryRepoConfigStore, method)
