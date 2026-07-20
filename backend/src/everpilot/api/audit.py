from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from everpilot.api.deps import AuditStoreDep
from everpilot.models.core import AuditEvent

# SECURITY (M4): like every route in this pre-auth API, this endpoint has no
# authn/authz yet — and it is the first cross-tenant query surface. M4's WorkOS
# integration MUST add org-membership enforcement here before any public deploy.
# Tracked in docs/open_questions.md.
router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEvent])
async def query_audit_events(
    store: AuditStoreDep,
    repository_id: int | None = None,
    organization_id: int | None = None,
    task_id: int | None = None,
    event_type: str | None = None,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEvent]:
    """Newest-first audit feed across a repo, org, or task.

    Every trigger, decision, PR, merge, and failure is queryable here (M2).
    Paginate by passing the smallest `id` of the previous page as `before_id`.
    """
    if event_type is not None and not any((repository_id, organization_id, task_id)):
        # An unscoped event_type filter would be an unindexed full-table scan
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="event_type filter requires repository_id, organization_id, or task_id",
        )
    return await store.query(
        repository_id=repository_id,
        organization_id=organization_id,
        task_id=task_id,
        event_type=event_type,
        before_id=before_id,
        limit=limit,
    )
