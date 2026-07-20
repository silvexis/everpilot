"""Shared FastAPI dependencies resolving services from app.state."""

from typing import Annotated

from fastapi import Depends, Request

from everpilot.db.tasks import AuditStore, TaskStore


def get_task_store(request: Request) -> TaskStore:
    return request.app.state.task_store


def get_audit_store(request: Request) -> AuditStore:
    return request.app.state.audit_store


TaskStoreDep = Annotated[TaskStore, Depends(get_task_store)]
AuditStoreDep = Annotated[AuditStore, Depends(get_audit_store)]
