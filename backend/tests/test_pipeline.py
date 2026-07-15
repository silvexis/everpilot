"""M2 task pipeline: mode enforcement, transitions, gates, audit trail."""

import pytest

from everpilot.db.tasks import InMemoryAuditStore, InMemoryTaskStore
from everpilot.models.capability import Capability, CapabilityMode
from everpilot.models.core import TaskState
from everpilot.pipeline import InvalidTransitionError, MergeGates, TaskPipeline

REPO_ID = 42


def make_pipeline() -> tuple[TaskPipeline, InMemoryTaskStore, InMemoryAuditStore]:
    tasks, audit = InMemoryTaskStore(), InMemoryAuditStore()
    return TaskPipeline(tasks, audit), tasks, audit


async def submit(pipeline: TaskPipeline, mode: CapabilityMode, enabled: bool = True):
    return await pipeline.submit(
        repository_id=REPO_ID,
        capability=Capability.DEPENDENCIES,
        mode=mode,
        enabled=enabled,
        trigger="webhook:push",
        title="Bump httpx",
    )


def all_gates(**overrides: bool) -> MergeGates:
    values = {
        "ci_green": True,
        "no_conflicts": True,
        "respects_branch_protection": True,
        "under_daily_cap": True,
    }
    values.update(overrides)
    return MergeGates(**values)


# --- Mode enforcement ---


async def test_off_mode_suppresses_and_audits() -> None:
    pipeline, tasks, audit = make_pipeline()
    task = await submit(pipeline, CapabilityMode.OFF)
    assert task is None
    assert tasks._tasks == {}
    assert audit.events[0].event_type == "task.suppressed"


async def test_disabled_capability_suppresses_even_in_autopilot() -> None:
    pipeline, _tasks, audit = make_pipeline()
    task = await submit(pipeline, CapabilityMode.AUTOPILOT, enabled=False)
    assert task is None
    assert audit.events[0].event_type == "task.suppressed"


async def test_enabled_capability_creates_task_with_audit() -> None:
    pipeline, _, audit = make_pipeline()
    task = await submit(pipeline, CapabilityMode.ASSISTED)
    assert task is not None
    assert task.state == TaskState.TRIGGERED
    assert audit.events[0].event_type == "task.created"
    assert audit.events[0].task_id == task.id


# --- Transitions ---


async def test_happy_path_to_pr_open() -> None:
    pipeline, _, audit = make_pipeline()
    task = await submit(pipeline, CapabilityMode.ASSISTED)
    assert task is not None and task.id is not None
    for state in (TaskState.QUEUED, TaskState.PLANNING, TaskState.EXECUTING):
        task = await pipeline.advance(task.id, state)
    task = await pipeline.open_pr(task.id, pr_number=7)
    assert task.state == TaskState.PR_OPEN
    assert task.pr_number == 7
    transitions = [e for e in audit.events if e.event_type == "task.state_changed"]
    assert [e.payload["to"] for e in transitions] == ["queued", "planning", "executing", "pr_open"]


async def test_illegal_transition_raises_and_does_not_audit() -> None:
    pipeline, _, audit = make_pipeline()
    task = await submit(pipeline, CapabilityMode.ASSISTED)
    assert task is not None and task.id is not None
    with pytest.raises(InvalidTransitionError):
        await pipeline.advance(task.id, TaskState.MERGED)
    assert all(e.event_type != "task.state_changed" for e in audit.events)


async def test_advance_unknown_task_raises() -> None:
    pipeline, _, _ = make_pipeline()
    with pytest.raises(KeyError):
        await pipeline.advance(999, TaskState.QUEUED)


async def test_lost_race_raises_invalid_transition() -> None:
    pipeline, tasks, _ = make_pipeline()
    task = await submit(pipeline, CapabilityMode.ASSISTED)
    assert task is not None and task.id is not None
    # Simulate a concurrent transition landing between get() and transition()
    original_get = tasks.get

    async def racing_get(task_id: int):
        result = await original_get(task_id)
        if result is not None and result.state == TaskState.TRIGGERED:
            await tasks.transition(task_id, TaskState.TRIGGERED, TaskState.FAILED)
        return result

    tasks.get = racing_get  # type: ignore[method-assign]
    with pytest.raises(InvalidTransitionError):
        await pipeline.advance(task.id, TaskState.QUEUED)


# --- Autopilot gates ---


async def to_pr_open(pipeline: TaskPipeline) -> int:
    task = await submit(pipeline, CapabilityMode.AUTOPILOT)
    assert task is not None and task.id is not None
    for state in (TaskState.QUEUED, TaskState.PLANNING, TaskState.EXECUTING):
        await pipeline.advance(task.id, state)
    await pipeline.open_pr(task.id, pr_number=11)
    return task.id


async def test_autopilot_merges_when_all_gates_pass() -> None:
    pipeline, _, _audit = make_pipeline()
    task_id = await to_pr_open(pipeline)
    task = await pipeline.autopilot_merge(task_id, all_gates())
    assert task.state == TaskState.MERGED


@pytest.mark.parametrize(
    "failing_gate",
    ["ci_green", "no_conflicts", "respects_branch_protection", "under_daily_cap"],
)
async def test_autopilot_blocked_by_any_failing_gate(failing_gate: str) -> None:
    pipeline, _, audit = make_pipeline()
    task_id = await to_pr_open(pipeline)
    task = await pipeline.autopilot_merge(task_id, all_gates(**{failing_gate: False}))
    assert task.state == TaskState.PR_OPEN  # held, not failed
    blocked = [e for e in audit.events if e.event_type == "task.merge_blocked"]
    assert blocked[0].payload["failed_gates"] == [failing_gate]


# --- Assisted resolution ---


async def test_assisted_approval_merges_with_human_actor() -> None:
    pipeline, _, audit = make_pipeline()
    task_id = await to_pr_open(pipeline)
    task = await pipeline.resolve_human_review(task_id, approved=True, actor="erik")
    assert task.state == TaskState.MERGED
    final = [e for e in audit.events if e.event_type == "task.state_changed"][-1]
    assert final.actor == "erik"


async def test_assisted_rejection() -> None:
    pipeline, _, _ = make_pipeline()
    task_id = await to_pr_open(pipeline)
    task = await pipeline.resolve_human_review(task_id, approved=False, actor="erik")
    assert task.state == TaskState.REJECTED
