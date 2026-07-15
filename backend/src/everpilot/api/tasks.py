from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from everpilot.db.tasks import AuditStore, TaskStore
from everpilot.github.rollback import RollbackError
from everpilot.models.core import AuditEvent, Task, TaskState

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_store(request: Request) -> TaskStore:
    return request.app.state.task_store


def get_audit_store(request: Request) -> AuditStore:
    return request.app.state.audit_store


TaskStoreDep = Annotated[TaskStore, Depends(get_task_store)]
AuditStoreDep = Annotated[AuditStore, Depends(get_audit_store)]


@router.get("", response_model=list[Task])
async def list_tasks(
    store: TaskStoreDep,
    repository_id: int | None = None,
    state: TaskState | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Task]:
    """Most-recent-first tasks, filterable by repository and state."""
    return await store.list(repository_id=repository_id, state=state, limit=limit)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int, store: TaskStoreDep) -> Task:
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )
    return task


@router.get("/{task_id}/audit", response_model=list[AuditEvent])
async def get_task_audit(
    task_id: int,
    store: TaskStoreDep,
    audit: AuditStoreDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEvent]:
    """Oldest-first audit trail for one task."""
    if await store.get(task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )
    return await audit.list_for_task(task_id, limit=limit)


class RollbackRequest(BaseModel):
    reason: str = "requested via dashboard"
    actor: str = "dashboard"


class RollbackResponse(BaseModel):
    revert_pr_number: int


@router.post("/{task_id}/rollback", response_model=RollbackResponse)
async def rollback_task(
    task_id: int,
    body: RollbackRequest,
    request: Request,
    store: TaskStoreDep,
    audit: AuditStoreDep,
) -> RollbackResponse:
    """Open a revert PR for a merged Everpilot task. The revert PR is not auto-merged."""
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )
    if task.state != TaskState.MERGED or task.pr_number is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only merged tasks with a PR can be rolled back",
        )

    rollback = getattr(request.app.state, "rollback_service", None)
    if rollback is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rollback unavailable: GitHub App credentials not configured",
        )

    context = await request.app.state.installation_store.repo_context(task.repository_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository is no longer installed",
        )
    repo_full_name, github_installation_id = context

    try:
        revert_pr_number = await rollback.revert_pr(
            github_installation_id=github_installation_id,
            repo_full_name=repo_full_name,
            pr_number=task.pr_number,
            reason=body.reason,
        )
    except RollbackError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    await audit.append(
        AuditEvent(
            repository_id=task.repository_id,
            task_id=task_id,
            actor=body.actor,
            event_type="task.rolled_back",
            payload={"reverted_pr": task.pr_number, "revert_pr": revert_pr_number},
        )
    )
    return RollbackResponse(revert_pr_number=revert_pr_number)
