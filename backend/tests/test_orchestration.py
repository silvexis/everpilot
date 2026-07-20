"""Event dispatch: inline path and DBOS enqueue wiring (no Postgres in unit tests)."""

from everpilot.db.installations import InMemoryInstallationStore
from everpilot.github.installations import InstallationService
from everpilot.orchestration import InlineEventDispatcher, dbos_engine


async def test_inline_dispatcher_routes_installation_events() -> None:
    store = InMemoryInstallationStore()
    dispatcher = InlineEventDispatcher(InstallationService(store))
    await dispatcher.dispatch(
        "installation",
        {
            "action": "created",
            "installation": {"id": 5555, "account": {"id": 777, "login": "silvexis"}},
            "repositories": [{"id": 101, "full_name": "silvexis/alpha"}],
        },
    )
    assert await store.get_installation(5555) is not None


async def test_inline_dispatcher_ignores_unknown_events() -> None:
    store = InMemoryInstallationStore()
    dispatcher = InlineEventDispatcher(InstallationService(store))
    await dispatcher.dispatch("watch", {"action": "started"})
    assert store._installations == {}


def test_dbos_queue_configuration() -> None:
    assert dbos_engine.webhook_queue.name == "github-webhook-events"


async def test_dbos_dispatcher_enqueues_durable_workflow(monkeypatch) -> None:
    enqueued: list[tuple] = []

    class StubQueue:
        def enqueue(self, fn, *args):
            enqueued.append((fn, args))

    monkeypatch.setattr(dbos_engine, "webhook_queue", StubQueue())
    dispatcher = dbos_engine.DBOSEventDispatcher()
    await dispatcher.dispatch("push", {"ref": "refs/heads/main"})

    assert len(enqueued) == 1
    fn, args = enqueued[0]
    assert fn is dbos_engine.process_github_event
    assert args == ("push", {"ref": "refs/heads/main"})


async def test_run_github_event_raises_until_services_bound(monkeypatch) -> None:
    """Recovery replaying a workflow before startup binding must retry, not no-op."""
    import pytest

    monkeypatch.setattr(dbos_engine, "_services_bound", False)
    with pytest.raises(RuntimeError, match="not bound"):
        await dbos_engine.run_github_event("push", {})


async def test_run_scheduled_scan_skips_when_dependencies_off(monkeypatch) -> None:
    monkeypatch.setattr(dbos_engine, "_services_bound", True)
    monkeypatch.setattr(dbos_engine, "_dependencies", None)
    assert await dbos_engine.run_scheduled_scan() == 0


async def test_run_scheduled_scan_delegates_to_service(monkeypatch) -> None:
    class StubScanService:
        async def scan_all(self) -> int:
            return 7

    monkeypatch.setattr(dbos_engine, "_services_bound", True)
    monkeypatch.setattr(dbos_engine, "_dependencies", StubScanService())
    assert await dbos_engine.run_scheduled_scan() == 7


async def test_bind_services(monkeypatch) -> None:
    monkeypatch.setattr(dbos_engine, "_services_bound", False)
    service = InstallationService(InMemoryInstallationStore())
    dbos_engine.bind_services(service, None)
    assert dbos_engine._installations is service
    assert dbos_engine._dependencies is None
    assert dbos_engine._services_bound is True
    monkeypatch.setattr(dbos_engine, "_installations", None)
    monkeypatch.setattr(dbos_engine, "_services_bound", False)
