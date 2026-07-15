"""Domain models mirroring the core schema (migration 0002).

These are transport/domain objects; persistence stores map rows to them.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from everpilot.models.capability import Capability


class OrgRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class TaskState(StrEnum):
    """Lifecycle states from the M2 task pipeline (roadmap)."""

    TRIGGERED = "triggered"
    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    PR_OPEN = "pr_open"
    MERGED = "merged"
    REJECTED = "rejected"
    FAILED = "failed"


#: Legal transitions; the M2 pipeline enforces these.
TASK_STATE_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.TRIGGERED: frozenset({TaskState.QUEUED, TaskState.FAILED}),
    TaskState.QUEUED: frozenset({TaskState.PLANNING, TaskState.FAILED}),
    TaskState.PLANNING: frozenset({TaskState.EXECUTING, TaskState.FAILED}),
    TaskState.EXECUTING: frozenset({TaskState.PR_OPEN, TaskState.FAILED}),
    TaskState.PR_OPEN: frozenset({TaskState.MERGED, TaskState.REJECTED, TaskState.FAILED}),
    TaskState.MERGED: frozenset(),
    TaskState.REJECTED: frozenset(),
    TaskState.FAILED: frozenset(),
}


def is_valid_transition(current: TaskState, new: TaskState) -> bool:
    return new in TASK_STATE_TRANSITIONS[current]


class RunOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class Organization(BaseModel):
    id: int | None = None
    github_org_id: int
    login: str
    name: str | None = None
    created_at: datetime | None = None


class User(BaseModel):
    id: int | None = None
    external_auth_id: str = Field(description="WorkOS user id")
    email: str
    github_login: str | None = None
    created_at: datetime | None = None


class Installation(BaseModel):
    id: int | None = None
    github_installation_id: int
    organization_id: int
    installed_at: datetime | None = None
    suspended_at: datetime | None = None

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None


class Repository(BaseModel):
    id: int | None = None
    github_repo_id: int
    installation_id: int
    full_name: str
    default_branch: str = "main"
    private: bool = True
    created_at: datetime | None = None


class Task(BaseModel):
    id: int | None = None
    repository_id: int
    capability: Capability
    state: TaskState = TaskState.TRIGGERED
    trigger: str = Field(description="What initiated the task, e.g. 'webhook:push', 'schedule'")
    title: str
    pr_number: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def can_transition_to(self, new_state: TaskState) -> bool:
        return is_valid_transition(self.state, new_state)

    @property
    def is_terminal(self) -> bool:
        return not TASK_STATE_TRANSITIONS[self.state]


class Run(BaseModel):
    id: int | None = None
    task_id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome: RunOutcome | None = None
    log_uri: str | None = None
    tokens_used: int | None = None


class AuditEvent(BaseModel):
    id: int | None = None
    organization_id: int | None = None
    repository_id: int | None = None
    task_id: int | None = None
    actor: str = Field(description="'everpilot' or a user identifier")
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
