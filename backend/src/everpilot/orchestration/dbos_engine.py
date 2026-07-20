"""DBOS-backed durable event processing.

Import this module only when DATABASE_URL is configured: DBOS checkpoints
workflow state in Postgres. Workflows wrap the plain handlers — orchestration
stays a thin shell around engine-agnostic logic.
"""

import logging
from datetime import datetime

from dbos import DBOS, DBOSConfig, Queue
from fastapi import FastAPI

from everpilot.capabilities.dependencies.service import DependencyScanService
from everpilot.github.installations import InstallationService
from everpilot.orchestration.handlers import handle_github_event

logger = logging.getLogger(__name__)

#: Webhook events queue. Partitioned per repository once tasks carry a repo
#: key (M2); for M0 a global concurrency cap bounds burst processing.
webhook_queue = Queue("github-webhook-events", concurrency=10)

# Set by the bind_* functions during app startup. DBOS recovery can replay
# workflows before the lifespan runs, so unbound-state must fail (and retry),
# never silently no-op: None after binding means "deliberately not configured".
_installations: InstallationService | None = None
_dependencies: DependencyScanService | None = None
_services_bound = False


def _require_bound() -> None:
    if not _services_bound:
        raise RuntimeError("DBOS services not bound yet — recovery will retry after startup")


async def run_github_event(event: str, payload: dict) -> None:  # type: ignore[type-arg]
    """Plain, testable body of the event workflow."""
    _require_bound()
    if _installations is None:
        raise RuntimeError("installation service missing — call bind_installation_service()")
    await handle_github_event(event, payload, _installations, _dependencies)


async def run_scheduled_scan() -> int:
    """Plain, testable body of the scheduled sweep."""
    _require_bound()
    if _dependencies is None:
        logger.info("Scheduled scan skipped: dependency scanning not configured")
        return 0
    created = await _dependencies.scan_all()
    logger.info("Scheduled dependency scan created %d tasks", created)
    return created


@DBOS.step()
async def _github_event_step(event: str, payload: dict) -> None:  # type: ignore[type-arg]
    # One coarse step: recovery re-runs an incomplete event exactly once more
    # instead of replaying events that already checkpointed as complete.
    await run_github_event(event, payload)


@DBOS.workflow()
async def process_github_event(event: str, payload: dict) -> None:  # type: ignore[type-arg]
    """Durable wrapper: survives crashes/restarts, resumes from the step checkpoint."""
    await _github_event_step(event, payload)


@DBOS.step()
async def _scheduled_scan_step() -> int:
    return await run_scheduled_scan()


@DBOS.scheduled("23 6 * * *")  # daily, off the :00 mark
@DBOS.workflow()
async def scheduled_dependency_scan(scheduled_time: datetime, actual_time: datetime) -> None:
    """Daily dependency sweep across all non-suspended installations (roadmap M3)."""
    await _scheduled_scan_step()


class DBOSEventDispatcher:
    """Enqueues events as durable DBOS workflows."""

    async def dispatch(self, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        webhook_queue.enqueue(process_github_event, event, payload)


def init_dbos(app: FastAPI, app_name: str, database_url: str) -> DBOSEventDispatcher:
    """Configure DBOS against the FastAPI app; DBOS launches with the app lifespan."""
    config: DBOSConfig = {
        "name": app_name,
        "system_database_url": database_url,
    }
    DBOS(fastapi=app, config=config)
    logger.info("DBOS configured (queue=%s)", webhook_queue.name)
    return DBOSEventDispatcher()


def bind_services(
    installations: InstallationService,
    dependencies: DependencyScanService | None,
) -> None:
    """Bind workflow dependencies once at startup; None = deliberately off."""
    global _installations, _dependencies, _services_bound
    _installations = installations
    _dependencies = dependencies
    _services_bound = True
