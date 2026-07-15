"""Core domain models: task state machine and model invariants."""

import pytest

from everpilot.models.capability import Capability
from everpilot.models.core import (
    TASK_STATE_TRANSITIONS,
    AuditEvent,
    Installation,
    Task,
    TaskState,
    is_valid_transition,
)


def make_task(state: TaskState = TaskState.TRIGGERED) -> Task:
    return Task(
        repository_id=1,
        capability=Capability.DEPENDENCIES,
        state=state,
        trigger="webhook:push",
        title="Bump httpx to 0.29",
    )


HAPPY_PATH = [
    (TaskState.TRIGGERED, TaskState.QUEUED),
    (TaskState.QUEUED, TaskState.PLANNING),
    (TaskState.PLANNING, TaskState.EXECUTING),
    (TaskState.EXECUTING, TaskState.PR_OPEN),
    (TaskState.PR_OPEN, TaskState.MERGED),
]


@pytest.mark.parametrize(("current", "new"), HAPPY_PATH)
def test_happy_path_transitions_are_valid(current: TaskState, new: TaskState) -> None:
    assert is_valid_transition(current, new)


@pytest.mark.parametrize("state", list(TaskState))
def test_every_state_has_transition_entry(state: TaskState) -> None:
    assert state in TASK_STATE_TRANSITIONS


@pytest.mark.parametrize(
    "state", [s for s in TaskState if s not in (TaskState.MERGED, TaskState.REJECTED)]
)
def test_non_terminal_states_can_fail(state: TaskState) -> None:
    if state == TaskState.FAILED:
        pytest.skip("failed is itself terminal")
    assert is_valid_transition(state, TaskState.FAILED)


def test_no_skipping_states() -> None:
    assert not is_valid_transition(TaskState.TRIGGERED, TaskState.EXECUTING)
    assert not is_valid_transition(TaskState.QUEUED, TaskState.PR_OPEN)
    assert not is_valid_transition(TaskState.PLANNING, TaskState.MERGED)


def test_terminal_states_have_no_exits() -> None:
    for terminal in (TaskState.MERGED, TaskState.REJECTED, TaskState.FAILED):
        assert TASK_STATE_TRANSITIONS[terminal] == frozenset()
        assert make_task(terminal).is_terminal


def test_task_can_transition_to() -> None:
    task = make_task()
    assert task.can_transition_to(TaskState.QUEUED)
    assert not task.can_transition_to(TaskState.MERGED)
    assert not task.is_terminal


def test_installation_suspension() -> None:
    installation = Installation(github_installation_id=42, organization_id=1)
    assert installation.is_suspended is False


def test_audit_event_defaults() -> None:
    event = AuditEvent(actor="everpilot", event_type="task.created")
    assert event.payload == {}
    assert event.organization_id is None
