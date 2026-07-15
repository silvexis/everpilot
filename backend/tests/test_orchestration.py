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


def test_bind_installation_service() -> None:
    service = InstallationService(InMemoryInstallationStore())
    dbos_engine.bind_installation_service(service)
    assert dbos_engine._installations is service
    dbos_engine.bind_installation_service(None)  # type: ignore[arg-type]
