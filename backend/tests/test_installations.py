"""Installation lifecycle: webhook payloads → tenant state."""

from fakes import FakeConnection, FakePool

from everpilot.db.installations import InMemoryInstallationStore, PostgresInstallationStore
from everpilot.github.installations import InstallationService
from everpilot.models.core import Installation, Organization, Repository

INSTALLATION_ID = 5555
ORG = {"id": 777, "login": "silvexis", "name": "Silvexis"}
REPO_A = {"id": 101, "full_name": "silvexis/alpha", "private": True}
REPO_B = {"id": 102, "full_name": "silvexis/beta", "private": False}


def created_payload() -> dict:
    return {
        "action": "created",
        "installation": {"id": INSTALLATION_ID, "account": ORG},
        "repositories": [REPO_A, REPO_B],
    }


def make_service() -> tuple[InstallationService, InMemoryInstallationStore]:
    store = InMemoryInstallationStore()
    return InstallationService(store), store


# --- InstallationService against the in-memory store ---


async def test_installation_created_creates_tenant_state() -> None:
    service, store = make_service()
    await service.handle_installation(created_payload())

    installation = await store.get_installation(INSTALLATION_ID)
    assert installation is not None
    assert not installation.is_suspended
    assert {r.full_name for r in store._repositories.values()} == {
        "silvexis/alpha",
        "silvexis/beta",
    }


async def test_installation_created_is_idempotent() -> None:
    service, store = make_service()
    await service.handle_installation(created_payload())
    await service.handle_installation(created_payload())  # webhook redelivery
    assert len(store._installations) == 1
    assert len(store._repositories) == 2


async def test_installation_deleted_removes_state() -> None:
    service, store = make_service()
    await service.handle_installation(created_payload())
    await service.handle_installation(
        {"action": "deleted", "installation": {"id": INSTALLATION_ID}}
    )
    assert await store.get_installation(INSTALLATION_ID) is None
    assert store._repositories == {}


async def test_suspend_and_unsuspend() -> None:
    service, store = make_service()
    await service.handle_installation(created_payload())

    await service.handle_installation(
        {"action": "suspend", "installation": {"id": INSTALLATION_ID}}
    )
    installation = await store.get_installation(INSTALLATION_ID)
    assert installation is not None and installation.is_suspended

    await service.handle_installation(
        {"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}
    )
    installation = await store.get_installation(INSTALLATION_ID)
    assert installation is not None and not installation.is_suspended


async def test_repositories_added_and_removed() -> None:
    service, store = make_service()
    await service.handle_installation(created_payload())
    await service.handle_installation_repositories(
        {
            "installation": {"id": INSTALLATION_ID},
            "repositories_added": [{"id": 103, "full_name": "silvexis/gamma"}],
            "repositories_removed": [REPO_A],
        }
    )
    names = {r.full_name for r in store._repositories.values()}
    assert names == {"silvexis/beta", "silvexis/gamma"}


async def test_unknown_installation_repositories_ignored() -> None:
    service, store = make_service()
    await service.handle_installation_repositories(
        {
            "installation": {"id": 9999},
            "repositories_added": [REPO_A],
        }
    )
    assert store._repositories == {}


async def test_missing_installation_id_ignored() -> None:
    service, store = make_service()
    await service.handle_installation({"action": "created"})
    assert store._installations == {}


# --- Postgres store SQL shape ---


async def test_pg_upsert_organization() -> None:
    conn = FakeConnection([[(1,)]])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    org_id = await store.upsert_organization(
        Organization(github_org_id=777, login="silvexis", name="Silvexis")
    )
    assert org_id == 1
    sql, params = conn.queries[0]
    assert "ON CONFLICT (github_org_id)" in sql
    assert params == (777, "silvexis", "Silvexis")


async def test_pg_create_installation_idempotent_upsert() -> None:
    conn = FakeConnection([[(3,)]])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    installation_id = await store.create_installation(
        Installation(github_installation_id=INSTALLATION_ID, organization_id=1)
    )
    assert installation_id == 3
    assert "ON CONFLICT (github_installation_id)" in conn.queries[0][0]


async def test_pg_get_installation_maps_row() -> None:
    conn = FakeConnection([[(3, INSTALLATION_ID, 1, None, None)]])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    installation = await store.get_installation(INSTALLATION_ID)
    assert installation is not None
    assert installation.id == 3
    assert installation.github_installation_id == INSTALLATION_ID


async def test_pg_delete_installation() -> None:
    conn = FakeConnection([[(3,)]])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.delete_installation(INSTALLATION_ID) is True


async def test_pg_set_suspended() -> None:
    conn = FakeConnection([[(3,)]])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.set_suspended(INSTALLATION_ID, True) is True
    assert "suspended_at = CASE WHEN %s THEN now() ELSE NULL END" in conn.queries[0][0]


async def test_pg_add_repositories_upserts_each() -> None:
    conn = FakeConnection([[], []])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    await store.add_repositories(
        3,
        [
            Repository(github_repo_id=101, installation_id=0, full_name="silvexis/alpha"),
            Repository(github_repo_id=102, installation_id=0, full_name="silvexis/beta"),
        ],
    )
    assert len(conn.queries) == 2
    assert all("ON CONFLICT (github_repo_id)" in sql for sql, _ in conn.queries)


async def test_pg_remove_repositories_noop_on_empty() -> None:
    conn = FakeConnection([])
    store = PostgresInstallationStore(FakePool(conn))  # type: ignore[arg-type]
    await store.remove_repositories([])
    assert conn.queries == []
