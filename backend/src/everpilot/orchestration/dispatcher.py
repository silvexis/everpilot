"""Event dispatch: how a verified webhook event reaches the handler.

InlineEventDispatcher awaits the handler directly (development/tests).
DBOSEventDispatcher (dbos_engine.py) enqueues a durable workflow instead, so
no work executes inside the request path and events survive restarts.
"""

from typing import Protocol

from everpilot.capabilities.dependencies.service import DependencyScanService
from everpilot.github.installations import InstallationService
from everpilot.orchestration.handlers import handle_github_event


class EventDispatcher(Protocol):
    async def dispatch(self, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        ...


class InlineEventDispatcher:
    """Executes the handler in-process. Development and tests only."""

    def __init__(
        self,
        installations: InstallationService,
        dependencies: DependencyScanService | None = None,
    ) -> None:
        self._installations = installations
        self._dependencies = dependencies

    async def dispatch(self, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        await handle_github_event(event, payload, self._installations, self._dependencies)
