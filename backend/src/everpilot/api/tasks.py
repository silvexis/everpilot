from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from everpilot.db.tasks import AuditStore, TaskStore
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
