"""Engine-agnostic webhook event handling.

Plain functions with no DBOS (or other orchestrator) coupling: the roadmap
locks DBOS now with a possible move to native AWS orchestration at scale, so
orchestration layers wrap these instead of absorbing them.
"""

import logging

from everpilot.github.installations import InstallationService

logger = logging.getLogger(__name__)


async def handle_github_event(
    event: str,
    payload: dict,  # type: ignore[type-arg]
    installations: InstallationService,
) -> None:
    """Dispatch a verified, deduplicated GitHub webhook event."""
    logger.info("Processing GitHub event: %s", event)

    match event:
        case "push":
            logger.debug("Push event on %s", payload.get("repository", {}).get("full_name"))
        case "issues":
            action = payload.get("action")
            logger.debug("Issue %s on %s", action, payload.get("repository", {}).get("full_name"))
        case "pull_request":
            action = payload.get("action")
            logger.debug("PR %s on %s", action, payload.get("repository", {}).get("full_name"))
        case "installation":
            await installations.handle_installation(payload)
        case "installation_repositories":
            await installations.handle_installation_repositories(payload)
        case _:
            logger.debug("Unhandled event type: %s", event)
