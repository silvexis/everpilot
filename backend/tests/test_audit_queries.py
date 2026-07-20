"""Audit feed queries: per-repo/per-org filters, keyset pagination, API."""

import pytest
from fakes import FakeConnection, FakePool
from fastapi.testclient import TestClient

from everpilot.db.tasks import InMemoryAuditStore, PostgresAuditStore
from everpilot.models.core import AuditEvent


def event(repo: int | None, org: int | None = None, event_type: str = "task.created"):
    return AuditEvent(
        organization_id=org, repository_id=repo, actor="everpilot", event_type=event_type
    )


async def seeded_store() -> InMemoryAuditStore:
    store = InMemoryAuditStore()
    await store.append(event(repo=1, org=10))
    await store.append(event(repo=2, org=10, event_type="task.merge_blocked"))
    await store.append(event(repo=1, org=10, event_type="task.state_changed"))
    await store.append(event(repo=3, org=20))
    return store


# --- In-memory store ---


async def test_query_newest_first() -> None:
    store = await seeded_store()
    results = await store.query()
    assert [e.id for e in results] == [4, 3, 2, 1]


async def test_query_by_repository() -> None:
    store = await seeded_store()
    results = await store.query(repository_id=1)
    assert [e.id for e in results] == [3, 1]


async def test_query_by_organization() -> None:
    store = await seeded_store()
    results = await store.query(organization_id=10)
    assert [e.id for e in results] == [3, 2, 1]


async def test_query_by_event_type() -> None:
    store = await seeded_store()
    results = await store.query(event_type="task.merge_blocked")
    assert [e.id for e in results] == [2]


async def test_query_keyset_pagination() -> None:
    store = await seeded_store()
    first_page = await store.query(limit=2)
    assert [e.id for e in first_page] == [4, 3]
    second_page = await store.query(limit=2, before_id=first_page[-1].id)
    assert [e.id for e in second_page] == [2, 1]


# --- Append contract (both implementations assign id + created_at) ---


async def test_inmemory_append_returns_persisted_copy() -> None:
    store = InMemoryAuditStore()
    original = event(repo=1)
    stored = await store.append(original)
    assert stored.id == 1
    assert stored.created_at is not None
    assert original.id is None  # caller's instance untouched
    # Re-appending the same instance must not alias entries
    again = await store.append(original)
    assert again.id == 2
    assert [e.id for e in store.events] == [1, 2]


async def test_pg_append_uses_returning() -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    conn = FakeConnection([[(7, now)]])
    store = PostgresAuditStore(FakePool(conn))  # type: ignore[arg-type]
    stored = await store.append(event(repo=1))
    assert "RETURNING id, created_at" in conn.queries[0][0]
    assert stored.id == 7
    assert stored.created_at == now


# --- Org stamping via AuditRecorder ---


async def test_recorder_stamps_organization_from_repository() -> None:
    from everpilot.db.audit_recorder import AuditRecorder
    from everpilot.db.installations import InMemoryInstallationStore
    from everpilot.models.core import Installation, Organization, Repository

    installations = InMemoryInstallationStore()
    org_id = await installations.upsert_organization(
        Organization(github_org_id=777, login="silvexis")
    )
    installation_db_id = await installations.create_installation(
        Installation(github_installation_id=5555, organization_id=org_id)
    )
    await installations.add_repositories(
        installation_db_id,
        [Repository(github_repo_id=101, installation_id=0, full_name="silvexis/alpha")],
    )
    repo = next(iter(installations._repositories.values()))

    recorder = AuditRecorder(InMemoryAuditStore(), installations)
    stored = await recorder.append(event(repo=repo.id))
    assert stored.organization_id == org_id

    # And the org feed now includes it
    results = await recorder.query(organization_id=org_id)
    assert [e.id for e in results] == [stored.id]


async def test_recorder_leaves_unresolvable_events_unstamped() -> None:
    from everpilot.db.audit_recorder import AuditRecorder
    from everpilot.db.installations import InMemoryInstallationStore

    recorder = AuditRecorder(InMemoryAuditStore(), InMemoryInstallationStore())
    stored = await recorder.append(event(repo=999))
    assert stored.organization_id is None


# --- Postgres store SQL shape ---


async def test_pg_query_builds_filtered_sql() -> None:
    conn = FakeConnection([[]])
    store = PostgresAuditStore(FakePool(conn))  # type: ignore[arg-type]
    await store.query(repository_id=1, organization_id=10, before_id=50, limit=25)
    sql, params = conn.queries[0]
    assert "repository_id = %s" in sql
    assert "organization_id = %s" in sql
    assert "id < %s" in sql
    assert "ORDER BY id DESC" in sql
    assert params == (1, 10, 50, 25)


async def test_pg_query_no_filters_has_no_where() -> None:
    conn = FakeConnection([[]])
    store = PostgresAuditStore(FakePool(conn))  # type: ignore[arg-type]
    await store.query()
    sql, params = conn.queries[0]
    assert "WHERE" not in sql
    assert params == (100,)


# --- API ---


@pytest.fixture
async def audit_client(app, client: TestClient) -> TestClient:
    store = app.state.audit_store
    await store.append(event(repo=1, org=10))
    await store.append(event(repo=2, org=10))
    return client


def test_audit_endpoint_filters(audit_client: TestClient) -> None:
    response = audit_client.get("/api/v1/audit", params={"repository_id": 1})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["repository_id"] == 1


def test_audit_endpoint_org_feed(audit_client: TestClient) -> None:
    response = audit_client.get("/api/v1/audit", params={"organization_id": 10})
    assert [e["id"] for e in response.json()] == [2, 1]


def test_audit_endpoint_limit_validation(audit_client: TestClient) -> None:
    assert audit_client.get("/api/v1/audit", params={"limit": 0}).status_code == 422
    assert audit_client.get("/api/v1/audit", params={"limit": 501}).status_code == 422


def test_audit_endpoint_unscoped_event_type_rejected(audit_client: TestClient) -> None:
    response = audit_client.get("/api/v1/audit", params={"event_type": "task.created"})
    assert response.status_code == 422


def test_audit_endpoint_scoped_event_type_allowed(audit_client: TestClient) -> None:
    response = audit_client.get(
        "/api/v1/audit", params={"event_type": "task.created", "repository_id": 1}
    )
    assert response.status_code == 200
