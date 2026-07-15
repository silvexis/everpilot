"""Postgres task/audit store SQL shape via fake pool."""

from datetime import UTC, datetime

from fakes import FakeConnection, FakePool
from psycopg.types.json import Jsonb

from everpilot.db.tasks import PostgresAuditStore, PostgresTaskStore
from everpilot.models.capability import Capability
from everpilot.models.core import AuditEvent, Task, TaskState

NOW = datetime.now(UTC)


def make_task() -> Task:
    return Task(
        repository_id=42,
        capability=Capability.DEPENDENCIES,
        trigger="webhook:push",
        title="Bump httpx",
    )


def task_row(state: str = "triggered", pr_number: int | None = None) -> tuple:
    return (1, 42, "dependencies", state, "webhook:push", "Bump httpx", pr_number, NOW, NOW)


async def test_create_returns_ids() -> None:
    conn = FakeConnection([[(1, NOW, NOW)]])
    store = PostgresTaskStore(FakePool(conn))  # type: ignore[arg-type]
    task = await store.create(make_task())
    assert task.id == 1
    assert "INSERT INTO tasks" in conn.queries[0][0]


async def test_get_maps_row() -> None:
    conn = FakeConnection([[task_row()]])
    store = PostgresTaskStore(FakePool(conn))  # type: ignore[arg-type]
    task = await store.get(1)
    assert task is not None
    assert task.state == TaskState.TRIGGERED
    assert task.capability == Capability.DEPENDENCIES


async def test_transition_guards_current_state() -> None:
    conn = FakeConnection([[task_row(state="queued")]])
    store = PostgresTaskStore(FakePool(conn))  # type: ignore[arg-type]
    task = await store.transition(1, TaskState.TRIGGERED, TaskState.QUEUED)
    assert task is not None and task.state == TaskState.QUEUED
    sql, params = conn.queries[0]
    assert "WHERE id = %s AND state = %s" in sql
    assert params == (TaskState.QUEUED, 1, TaskState.TRIGGERED)


async def test_transition_lost_race_returns_none() -> None:
    conn = FakeConnection([[]])
    store = PostgresTaskStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.transition(1, TaskState.TRIGGERED, TaskState.QUEUED) is None


async def test_count_created_today_scopes_to_utc_day() -> None:
    conn = FakeConnection([[(3,)]])
    store = PostgresTaskStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.count_created_today(42) == 3
    assert "date_trunc('day', now())" in conn.queries[0][0]


async def test_audit_append_serializes_payload() -> None:
    conn = FakeConnection([[]])
    store = PostgresAuditStore(FakePool(conn))  # type: ignore[arg-type]
    await store.append(
        AuditEvent(repository_id=42, actor="everpilot", event_type="task.created", payload={"a": 1})
    )
    sql, params = conn.queries[0]
    assert "INSERT INTO audit_events" in sql
    assert isinstance(params[-1], Jsonb)
