"""Task and audit-event persistence."""

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


class AuditStore(Protocol):
    async def append(self, event: AuditEvent) -> None: ...


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
        return self._tasks.get(task_id)

    async def transition(self, task_id: int, current: TaskState, new: TaskState) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None or task.state != current:
            return None
        task.state = new
        return task

    async def set_pr_number(self, task_id: int, pr_number: int) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.pr_number = pr_number

    async def count_created_today(self, repository_id: int) -> int:
        return sum(1 for t in self._tasks.values() if t.repository_id == repository_id)


class InMemoryAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


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


class PostgresAuditStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def append(self, event: AuditEvent) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO audit_events"
                " (organization_id, repository_id, task_id, actor, event_type, payload)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    event.organization_id,
                    event.repository_id,
                    event.task_id,
                    event.actor,
                    event.event_type,
                    Jsonb(event.payload),
                ),
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
