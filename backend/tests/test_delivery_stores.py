"""WebhookDeliveryStore implementations."""

from fakes import FakeConnection, FakePool

from everpilot.db.deliveries import InMemoryWebhookDeliveryStore, PostgresWebhookDeliveryStore


async def test_inmemory_new_then_duplicate() -> None:
    store = InMemoryWebhookDeliveryStore()
    assert await store.record("guid-1", "push") is True
    assert await store.record("guid-1", "push") is False
    assert await store.record("guid-2", "push") is True


async def test_inmemory_eviction_bound() -> None:
    store = InMemoryWebhookDeliveryStore(max_entries=2)
    await store.record("a", "push")
    await store.record("b", "push")
    await store.record("c", "push")  # evicts "a"
    assert await store.record("a", "push") is True  # seen again as new


async def test_postgres_record_new() -> None:
    conn = FakeConnection([[("guid-1",)]])
    store = PostgresWebhookDeliveryStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.record("guid-1", "push") is True
    sql, params = conn.queries[0]
    assert "ON CONFLICT (delivery_id) DO NOTHING" in sql
    assert params == ("guid-1", "push")


async def test_postgres_record_duplicate() -> None:
    conn = FakeConnection([[]])
    store = PostgresWebhookDeliveryStore(FakePool(conn))  # type: ignore[arg-type]
    assert await store.record("guid-1", "push") is False
