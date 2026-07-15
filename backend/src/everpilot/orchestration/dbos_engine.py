"""DBOS-backed durable event processing.

Import this module only when DATABASE_URL is configured: DBOS checkpoints
workflow state in Postgres. The workflow wraps the plain handler in
handlers.py — orchestration stays a thin shell around engine-agnostic logic.
"""

import logging

from dbos import DBOS, DBOSConfig, Queue
from fastapi import FastAPI

from everpilot.github.installations import InstallationService
from everpilot.orchestration.handlers import handle_github_event

logger = logging.getLogger(__name__)

#: Webhook events queue. Partitioned per repository once tasks carry a repo
#: key (M2); for M0 a global concurrency cap bounds burst processing.
webhook_queue = Queue("github-webhook-events", concurrency=10)

# Set by init_dbos(); DBOS workflows recover after restarts, so dependencies
# must be reachable at module scope rather than captured per-request.
_installations: InstallationService | None = None


@DBOS.workflow()
async def process_github_event(event: str, payload: dict) -> None:  # type: ignore[type-arg]
    """Durable wrapper: survives crashes/restarts, retries from checkpoint."""
    if _installations is None:
        raise RuntimeError("DBOS engine not initialized — call init_dbos() first")
    await handle_github_event(event, payload, _installations)


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


def bind_installation_service(installations: InstallationService) -> None:
    global _installations
    _installations = installations
