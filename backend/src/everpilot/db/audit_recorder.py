"""Org-stamping wrapper around an AuditStore.

Producers (pipeline transitions, merge gates, rollbacks) know the repository
but not the organization. Stamping organization_id here — the single append
path — keeps the org-filtered audit feed complete without every producer
carrying tenant context.
"""

from everpilot.db.installations import InstallationStore
from everpilot.db.tasks import AuditStore
from everpilot.models.core import AuditEvent


class AuditRecorder:
    """AuditStore implementation that resolves organization_id before appending."""

    def __init__(self, store: AuditStore, installations: InstallationStore) -> None:
        self._store = store
        self._installations = installations

    async def append(self, event: AuditEvent) -> AuditEvent:
        if event.organization_id is None and event.repository_id is not None:
            event.organization_id = await self._installations.organization_id_for_repository(
                event.repository_id
            )
        return await self._store.append(event)

    async def list_for_task(self, task_id: int, limit: int = 100) -> list[AuditEvent]:
        return await self._store.list_for_task(task_id, limit=limit)

    async def query(self, **kwargs) -> list[AuditEvent]:
        return await self._store.query(**kwargs)
