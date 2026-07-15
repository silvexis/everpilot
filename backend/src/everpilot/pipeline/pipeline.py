"""The M2 task pipeline: mode enforcement, state transitions, audit trail.

Engine-agnostic by design — the DBOS layer (or a future AWS orchestrator)
drives these methods; they never import an orchestrator.
"""

import logging

from everpilot.db.tasks import AuditStore, TaskStore
from everpilot.models.capability import Capability, CapabilityMode
from everpilot.models.core import AuditEvent, Task, TaskState
from everpilot.pipeline.gates import MergeGates

logger = logging.getLogger(__name__)

ACTOR = "everpilot"


class InvalidTransitionError(Exception):
    def __init__(self, task_id: int, current: TaskState, requested: TaskState) -> None:
        super().__init__(f"task {task_id}: illegal transition {current} → {requested}")
        self.current = current
        self.requested = requested


class TaskPipeline:
    def __init__(self, tasks: TaskStore, audit: AuditStore) -> None:
        self._tasks = tasks
        self._audit = audit

    async def submit(
        self,
        *,
        repository_id: int,
        capability: Capability,
        mode: CapabilityMode,
        enabled: bool,
        trigger: str,
        title: str,
        organization_id: int | None = None,
    ) -> Task | None:
        """Create a task if the capability's mode allows it.

        Off/disabled capabilities record a suppressed audit event and create
        nothing — suppression is visible in the audit trail by design.
        """
        if not enabled or mode == CapabilityMode.OFF:
            await self._audit.append(
                AuditEvent(
                    organization_id=organization_id,
                    repository_id=repository_id,
                    actor=ACTOR,
                    event_type="task.suppressed",
                    payload={"capability": capability, "trigger": trigger, "title": title},
                )
            )
            return None

        task = await self._tasks.create(
            Task(
                repository_id=repository_id,
                capability=capability,
                trigger=trigger,
                title=title,
            )
        )
        await self._audit.append(
            AuditEvent(
                organization_id=organization_id,
                repository_id=repository_id,
                task_id=task.id,
                actor=ACTOR,
                event_type="task.created",
                payload={"capability": capability, "mode": mode, "trigger": trigger},
            )
        )
        return task

    async def advance(self, task_id: int, new_state: TaskState, *, actor: str = ACTOR) -> Task:
        """Move a task to `new_state`, enforcing the state machine atomically."""
        task = await self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"task {task_id} not found")
        current_state = task.state
        if not task.can_transition_to(new_state):
            raise InvalidTransitionError(task_id, current_state, new_state)

        updated = await self._tasks.transition(task_id, current_state, new_state)
        if updated is None:
            # Lost a race: someone else transitioned first. Re-read and refuse.
            refreshed = await self._tasks.get(task_id)
            current = refreshed.state if refreshed else current_state
            raise InvalidTransitionError(task_id, current, new_state)

        await self._audit.append(
            AuditEvent(
                repository_id=updated.repository_id,
                task_id=task_id,
                actor=actor,
                event_type="task.state_changed",
                payload={"from": current_state, "to": new_state},
            )
        )
        return updated

    async def open_pr(self, task_id: int, pr_number: int) -> Task:
        """Record the opened PR and move the task to pr_open."""
        task = await self.advance(task_id, TaskState.PR_OPEN)
        await self._tasks.set_pr_number(task_id, pr_number)
        task.pr_number = pr_number
        return task

    async def autopilot_merge(self, task_id: int, gates: MergeGates) -> Task:
        """Autopilot resolution: merge only if every gate passes; otherwise hold.

        A gate failure is not a task failure — the task stays pr_open for a
        human, and the block is auditable.
        """
        task = await self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"task {task_id} not found")

        if not gates.all_pass:
            await self._audit.append(
                AuditEvent(
                    repository_id=task.repository_id,
                    task_id=task_id,
                    actor=ACTOR,
                    event_type="task.merge_blocked",
                    payload={"failed_gates": gates.failures},
                )
            )
            logger.info("Task %s autopilot merge blocked: %s", task_id, gates.failures)
            return task

        return await self.advance(task_id, TaskState.MERGED)

    async def resolve_human_review(self, task_id: int, *, approved: bool, actor: str) -> Task:
        """Assisted resolution: a human approved (merged) or rejected the PR."""
        new_state = TaskState.MERGED if approved else TaskState.REJECTED
        return await self.advance(task_id, new_state, actor=actor)
