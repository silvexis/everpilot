"""Webhook delivery log — idempotency/replay protection keyed on X-GitHub-Delivery."""

from collections import OrderedDict
from typing import Protocol

from psycopg_pool import AsyncConnectionPool


class WebhookDeliveryStore(Protocol):
    async def record(self, delivery_id: str, event: str) -> bool:
        """Record a delivery. Returns True if new, False if already seen (replay)."""
        ...


class InMemoryWebhookDeliveryStore:
    """Bounded LRU set for development and tests."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._max_entries = max_entries
        self._seen: OrderedDict[str, None] = OrderedDict()

    async def record(self, delivery_id: str, event: str) -> bool:
        if delivery_id in self._seen:
            self._seen.move_to_end(delivery_id)
            return False
        self._seen[delivery_id] = None
        while len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return True


class PostgresWebhookDeliveryStore:
    """Durable delivery log; survives restarts and multiple API replicas."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def record(self, delivery_id: str, event: str) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO webhook_deliveries (delivery_id, event) VALUES (%s, %s)"
                " ON CONFLICT (delivery_id) DO NOTHING RETURNING delivery_id",
                (delivery_id, event),
            )
            row = await cur.fetchone()
        return row is not None
