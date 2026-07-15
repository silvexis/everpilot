from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from everpilot.models.capability import CapabilityConfig
from everpilot.models.repo import RepoConfig


def create_pool(database_url: str) -> AsyncConnectionPool:
    """Build an (unopened) async connection pool; open/close it in the app lifespan."""
    return AsyncConnectionPool(database_url, open=False, kwargs={"autocommit": True})


def _capabilities_jsonb(capabilities: list[CapabilityConfig]) -> Jsonb:
    return Jsonb([c.model_dump(mode="json") for c in capabilities])


class PostgresRepoConfigStore:
    """psycopg3-backed store; schema is managed by Alembic (see migrations/)."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_repo_names(self) -> list[str]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT repo_full_name FROM repo_configs ORDER BY repo_full_name"
            )
            rows = await cur.fetchall()
        return [row[0] for row in rows]

    async def get(self, repo_full_name: str) -> RepoConfig | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT repo_full_name, capabilities, installed_at, active"
                " FROM repo_configs WHERE repo_full_name = %s",
                (repo_full_name,),
            )
            row = await cur.fetchone()
        return _row_to_config(row) if row is not None else None

    async def create(self, config: RepoConfig) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO repo_configs (repo_full_name, capabilities, installed_at, active)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT (repo_full_name) DO NOTHING RETURNING id",
                (
                    config.repo_full_name,
                    _capabilities_jsonb(config.capabilities),
                    config.installed_at,
                    config.active,
                ),
            )
            row = await cur.fetchone()
        return row is not None

    async def set_capability(
        self, repo_full_name: str, capability_config: CapabilityConfig
    ) -> RepoConfig | None:
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "SELECT repo_full_name, capabilities, installed_at, active"
                " FROM repo_configs WHERE repo_full_name = %s FOR UPDATE",
                (repo_full_name,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            config = _row_to_config(row)
            config.capabilities = [
                capability_config if c.capability == capability_config.capability else c
                for c in config.capabilities
            ]
            await conn.execute(
                "UPDATE repo_configs SET capabilities = %s WHERE repo_full_name = %s",
                (_capabilities_jsonb(config.capabilities), repo_full_name),
            )
        return config

    async def delete(self, repo_full_name: str) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "DELETE FROM repo_configs WHERE repo_full_name = %s RETURNING id",
                (repo_full_name,),
            )
            row = await cur.fetchone()
        return row is not None


def _row_to_config(row: tuple) -> RepoConfig:
    repo_full_name, capabilities, installed_at, active = row
    return RepoConfig(
        repo_full_name=repo_full_name,
        capabilities=[CapabilityConfig(**c) for c in capabilities],
        installed_at=installed_at,
        active=active,
    )
