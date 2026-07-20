"""Task and audit-event persistence."""

from datetime import UTC, datetime
from typing import Protocol

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from everpilot.models.core import AuditEvent, Task, TaskState


class TaskStore(Protocol):
    async def create(self, task: Task) -> Task:
        """Persist a new task; returns it with id assigned."""
        ...

    async def get(self, task_id: int) -> Task | None: ...

    async def transition(self, task_id: int, current: TaskState, new: TaskState) -> Task | None:
        """Atomically move a task from `current` to `new`.

        Returns the updated task, or None if the task no longer holds `current`
        (lost race) or does not exist.
        """
        ...

    async def set_pr_number(self, task_id: int, pr_number: int) -> None: ...

    async def count_created_today(self, repository_id: int) -> int:
        """Tasks created for a repo in the current UTC day — feeds the daily cap gate."""
        ...

    async def list(
        self,
        repository_id: int | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        """Most-recent-first task listing for the dashboard."""
        ...


class AuditStore(Protocol):
    async def append(self, event: AuditEvent) -> AuditEvent:
        """Persist an event; returns it with id and created_at populated."""
        ...

    async def list_for_task(self, task_id: int, limit: int = 100) -> list[AuditEvent]:
        """Oldest-first audit trail for one task."""
        ...

    async def query(
        self,
        *,
        repository_id: int | None = None,
        organization_id: int | None = None,
        task_id: int | None = None,
        event_type: str | None = None,
        before_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Newest-first audit feed, filterable per repo/org/task, keyset-paginated
        via before_id (pass the smallest id from the previous page)."""
        ...


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id = 1

    async def create(self, task: Task) -> Task:
        task.id = self._next_id
        self._next_id += 1
        self._tasks[task.id] = task
        return task

    async def get(self, task_id: int) -> Task | None:
        # Copies, like rows from a real database: callers never alias stored state
        task = self._tasks.get(task_id)
        return task.model_copy(deep=True) if task is not None else None

    async def transition(self, task_id: int, current: TaskState, new: TaskState) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None or task.state != current:
            return None
        task.state = new
        return task.model_copy(deep=True)

    async def set_pr_number(self, task_id: int, pr_number: int) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.pr_number = pr_number

    async def count_created_today(self, repository_id: int) -> int:
        return sum(1 for t in self._tasks.values() if t.repository_id == repository_id)

    async def list(
        self,
        repository_id: int | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        tasks = [
            t
            for t in self._tasks.values()
            if (repository_id is None or t.repository_id == repository_id)
            and (state is None or t.state == state)
        ]
        return sorted(tasks, key=lambda t: t.id or 0, reverse=True)[:limit]


class InMemoryAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> AuditEvent:
        # Store a copy (re-appending the same instance must not alias entries)
        # and assign like the database would: identity id, insertion timestamp.
        stored = event.model_copy(deep=True)
        stored.id = len(self.events) + 1
        stored.created_at = datetime.now(UTC)
        self.events.append(stored)
        return stored

    async def list_for_task(self, task_id: int, limit: int = 100) -> list[AuditEvent]:
        return [e for e in self.events if e.task_id == task_id][:limit]

    async def query(
        self,
        *,
        repository_id: int | None = None,
        organization_id: int | None = None,
        task_id: int | None = None,
        event_type: str | None = None,
        before_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        # self.events is ascending by id; walk backwards and stop at `limit`
        matches: list[AuditEvent] = []
        for event in reversed(self.events):
            if repository_id is not None and event.repository_id != repository_id:
                continue
            if organization_id is not None and event.organization_id != organization_id:
                continue
            if task_id is not None and event.task_id != task_id:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if before_id is not None and event.id >= before_id:  # type: ignore[operator]
                continue
            matches.append(event)
            if len(matches) >= limit:
                break
        return matches


class PostgresTaskStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(self, task: Task) -> Task:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO tasks (repository_id, capability, state, trigger, title)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at, updated_at",
                (task.repository_id, task.capability, task.state, task.trigger, task.title),
            )
            row = await cur.fetchone()
        task.id, task.created_at, task.updated_at = row
        return task

    async def get(self, task_id: int) -> Task | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, repository_id, capability, state, trigger, title, pr_number,"
                " created_at, updated_at FROM tasks WHERE id = %s",
                (task_id,),
            )
            row = await cur.fetchone()
        return _row_to_task(row) if row is not None else None

    async def transition(self, task_id: int, current: TaskState, new: TaskState) -> Task | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "UPDATE tasks SET state = %s, updated_at = now()"
                " WHERE id = %s AND state = %s"
                " RETURNING id, repository_id, capability, state, trigger, title, pr_number,"
                " created_at, updated_at",
                (new, task_id, current),
            )
            row = await cur.fetchone()
        return _row_to_task(row) if row is not None else None

    async def set_pr_number(self, task_id: int, pr_number: int) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "UPDATE tasks SET pr_number = %s, updated_at = now() WHERE id = %s",
                (pr_number, task_id),
            )

    async def count_created_today(self, repository_id: int) -> int:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT count(*) FROM tasks"
                " WHERE repository_id = %s AND created_at >= date_trunc('day', now())",
                (repository_id,),
            )
            row = await cur.fetchone()
        return row[0]

    async def list(
        self,
        repository_id: int | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        where, params = _build_where([("repository_id = %s", repository_id), ("state = %s", state)])
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, repository_id, capability, state, trigger, title, pr_number,"
                f" created_at, updated_at FROM tasks{where}"
                " ORDER BY id DESC LIMIT %s",
                (*params, limit),
            )
            rows = await cur.fetchall()
        return [_row_to_task(row) for row in rows]


class PostgresAuditStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def append(self, event: AuditEvent) -> AuditEvent:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO audit_events"
                " (organization_id, repository_id, task_id, actor, event_type, payload)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at",
                (
                    event.organization_id,
                    event.repository_id,
                    event.task_id,
                    event.actor,
                    event.event_type,
                    Jsonb(event.payload),
                ),
            )
            row = await cur.fetchone()
        if row is not None:
            event.id, event.created_at = row
        return event

    async def list_for_task(self, task_id: int, limit: int = 100) -> list[AuditEvent]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {_AUDIT_COLUMNS} FROM audit_events"
                " WHERE task_id = %s ORDER BY id ASC LIMIT %s",
                (task_id, limit),
            )
            rows = await cur.fetchall()
        return [_row_to_audit_event(row) for row in rows]

    async def query(
        self,
        *,
        repository_id: int | None = None,
        organization_id: int | None = None,
        task_id: int | None = None,
        event_type: str | None = None,
        before_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        where, params = _build_where(
            [
                ("repository_id = %s", repository_id),
                ("organization_id = %s", organization_id),
                ("task_id = %s", task_id),
                ("event_type = %s", event_type),
                ("id < %s", before_id),
            ]
        )
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {_AUDIT_COLUMNS} FROM audit_events{where} ORDER BY id DESC LIMIT %s",
                (*params, limit),
            )
            rows = await cur.fetchall()
        return [_row_to_audit_event(row) for row in rows]


#: Column order must match _row_to_audit_event's positional mapping.
_AUDIT_COLUMNS = (
    "id, organization_id, repository_id, task_id, actor, event_type, payload, created_at"
)


def _build_where(conditions: list[tuple[str, object | None]]) -> tuple[str, list]:
    """SQL WHERE fragment + params from (clause, value) pairs, skipping None values.

    Clauses are static strings defined in this module; only values are parameterized.
    """
    active = [(clause, value) for clause, value in conditions if value is not None]
    if not active:
        return "", []
    return " WHERE " + " AND ".join(clause for clause, _ in active), [v for _, v in active]


def _row_to_audit_event(row: tuple) -> AuditEvent:
    return AuditEvent(
        id=row[0],
        organization_id=row[1],
        repository_id=row[2],
        task_id=row[3],
        actor=row[4],
        event_type=row[5],
        payload=row[6],
        created_at=row[7],
    )


def _row_to_task(row: tuple) -> Task:
    return Task(
        id=row[0],
        repository_id=row[1],
        capability=row[2],
        state=TaskState(row[3]),
        trigger=row[4],
        title=row[5],
        pr_number=row[6],
        created_at=row[7],
        updated_at=row[8],
    )
