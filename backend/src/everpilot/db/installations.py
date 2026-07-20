"""Installation/tenant state persistence (organizations, installations, repositories)."""

from typing import Protocol

from psycopg_pool import AsyncConnectionPool

from everpilot.models.core import Installation, Organization, Repository


class InstallationStore(Protocol):
    async def upsert_organization(self, org: Organization) -> int:
        """Insert or refresh an organization; returns its database id."""
        ...

    async def create_installation(self, installation: Installation) -> int:
        """Insert an installation (idempotent on github_installation_id); returns database id."""
        ...

    async def get_installation(self, github_installation_id: int) -> Installation | None: ...

    async def delete_installation(self, github_installation_id: int) -> bool: ...

    async def set_suspended(self, github_installation_id: int, suspended: bool) -> bool: ...

    async def add_repositories(
        self, installation_db_id: int, repositories: list[Repository]
    ) -> None: ...

    async def remove_repositories(self, github_repo_ids: list[int]) -> None: ...

    async def repo_context(self, repository_id: int) -> tuple[str, int] | None:
        """(repo_full_name, github_installation_id) for a repository db id."""
        ...

    async def organization_id_for_repository(self, repository_id: int) -> int | None:
        """Owning organization's db id, resolved repository → installation → org."""
        ...

    async def get_scannable_repository(self, github_repo_id: int) -> tuple[Repository, int] | None:
        """(Repository, github_installation_id), or None if unknown or suspended."""
        ...

    async def list_scannable_repositories(self) -> list[tuple[Repository, int]]:
        """All repositories with their github_installation_id (non-suspended installs)."""
        ...


class InMemoryInstallationStore:
    """Dev/test double."""

    def __init__(self) -> None:
        self._orgs: dict[int, Organization] = {}  # keyed by github_org_id
        self._installations: dict[int, Installation] = {}  # keyed by github_installation_id
        self._repositories: dict[int, Repository] = {}  # keyed by github_repo_id
        self._next_id = 1

    def _allocate_id(self) -> int:
        allocated = self._next_id
        self._next_id += 1
        return allocated

    async def upsert_organization(self, org: Organization) -> int:
        existing = self._orgs.get(org.github_org_id)
        if existing is not None:
            existing.login = org.login
            existing.name = org.name
            return existing.id  # type: ignore[return-value]
        org.id = self._allocate_id()
        self._orgs[org.github_org_id] = org
        return org.id

    async def create_installation(self, installation: Installation) -> int:
        existing = self._installations.get(installation.github_installation_id)
        if existing is not None:
            return existing.id  # type: ignore[return-value]
        installation.id = self._allocate_id()
        self._installations[installation.github_installation_id] = installation
        return installation.id

    async def get_installation(self, github_installation_id: int) -> Installation | None:
        return self._installations.get(github_installation_id)

    async def delete_installation(self, github_installation_id: int) -> bool:
        installation = self._installations.pop(github_installation_id, None)
        if installation is None:
            return False
        self._repositories = {
            repo_id: repo
            for repo_id, repo in self._repositories.items()
            if repo.installation_id != installation.id
        }
        return True

    async def set_suspended(self, github_installation_id: int, suspended: bool) -> bool:
        from datetime import UTC, datetime

        installation = self._installations.get(github_installation_id)
        if installation is None:
            return False
        installation.suspended_at = datetime.now(UTC) if suspended else None
        return True

    async def add_repositories(
        self, installation_db_id: int, repositories: list[Repository]
    ) -> None:
        for repo in repositories:
            repo.installation_id = installation_db_id
            if repo.github_repo_id not in self._repositories:
                repo.id = self._allocate_id()
                self._repositories[repo.github_repo_id] = repo

    async def remove_repositories(self, github_repo_ids: list[int]) -> None:
        for github_repo_id in github_repo_ids:
            self._repositories.pop(github_repo_id, None)

    async def repo_context(self, repository_id: int) -> tuple[str, int] | None:
        repo = next((r for r in self._repositories.values() if r.id == repository_id), None)
        if repo is None:
            return None
        installation = next(
            (i for i in self._installations.values() if i.id == repo.installation_id), None
        )
        if installation is None:
            return None
        return repo.full_name, installation.github_installation_id

    async def organization_id_for_repository(self, repository_id: int) -> int | None:
        repo = next((r for r in self._repositories.values() if r.id == repository_id), None)
        if repo is None:
            return None
        installation = next(
            (i for i in self._installations.values() if i.id == repo.installation_id), None
        )
        return installation.organization_id if installation is not None else None

    async def get_scannable_repository(self, github_repo_id: int) -> tuple[Repository, int] | None:
        repo = self._repositories.get(github_repo_id)
        if repo is None:
            return None
        installation = next(
            (i for i in self._installations.values() if i.id == repo.installation_id), None
        )
        if installation is None or installation.is_suspended:
            return None
        return repo, installation.github_installation_id

    async def list_scannable_repositories(self) -> list[tuple[Repository, int]]:
        results = []
        for repo in self._repositories.values():
            installation = next(
                (i for i in self._installations.values() if i.id == repo.installation_id), None
            )
            if installation is not None and not installation.is_suspended:
                results.append((repo, installation.github_installation_id))
        return results


class PostgresInstallationStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def upsert_organization(self, org: Organization) -> int:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO organizations (github_org_id, login, name) VALUES (%s, %s, %s)"
                " ON CONFLICT (github_org_id)"
                " DO UPDATE SET login = EXCLUDED.login, name = EXCLUDED.name"
                " RETURNING id",
                (org.github_org_id, org.login, org.name),
            )
            row = await cur.fetchone()
        return row[0]

    async def create_installation(self, installation: Installation) -> int:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO installations (github_installation_id, organization_id)"
                " VALUES (%s, %s)"
                " ON CONFLICT (github_installation_id) DO UPDATE"
                " SET organization_id = EXCLUDED.organization_id"
                " RETURNING id",
                (installation.github_installation_id, installation.organization_id),
            )
            row = await cur.fetchone()
        return row[0]

    async def get_installation(self, github_installation_id: int) -> Installation | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, github_installation_id, organization_id, installed_at, suspended_at"
                " FROM installations WHERE github_installation_id = %s",
                (github_installation_id,),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return Installation(
            id=row[0],
            github_installation_id=row[1],
            organization_id=row[2],
            installed_at=row[3],
            suspended_at=row[4],
        )

    async def delete_installation(self, github_installation_id: int) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "DELETE FROM installations WHERE github_installation_id = %s RETURNING id",
                (github_installation_id,),
            )
            row = await cur.fetchone()
        return row is not None

    async def set_suspended(self, github_installation_id: int, suspended: bool) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "UPDATE installations"
                " SET suspended_at = CASE WHEN %s THEN now() ELSE NULL END"
                " WHERE github_installation_id = %s RETURNING id",
                (suspended, github_installation_id),
            )
            row = await cur.fetchone()
        return row is not None

    async def add_repositories(
        self, installation_db_id: int, repositories: list[Repository]
    ) -> None:
        if not repositories:
            return
        async with self._pool.connection() as conn:
            for repo in repositories:
                await conn.execute(
                    "INSERT INTO repositories"
                    " (github_repo_id, installation_id, full_name, default_branch, private)"
                    " VALUES (%s, %s, %s, %s, %s)"
                    " ON CONFLICT (github_repo_id) DO UPDATE"
                    " SET full_name = EXCLUDED.full_name,"
                    "     default_branch = EXCLUDED.default_branch,"
                    "     private = EXCLUDED.private",
                    (
                        repo.github_repo_id,
                        installation_db_id,
                        repo.full_name,
                        repo.default_branch,
                        repo.private,
                    ),
                )

    async def remove_repositories(self, github_repo_ids: list[int]) -> None:
        if not github_repo_ids:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM repositories WHERE github_repo_id = ANY(%s)",
                (github_repo_ids,),
            )

    async def repo_context(self, repository_id: int) -> tuple[str, int] | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT r.full_name, i.github_installation_id"
                " FROM repositories r JOIN installations i ON i.id = r.installation_id"
                " WHERE r.id = %s",
                (repository_id,),
            )
            row = await cur.fetchone()
        return (row[0], row[1]) if row is not None else None

    async def organization_id_for_repository(self, repository_id: int) -> int | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT i.organization_id"
                " FROM repositories r JOIN installations i ON i.id = r.installation_id"
                " WHERE r.id = %s",
                (repository_id,),
            )
            row = await cur.fetchone()
        return row[0] if row is not None else None

    async def get_scannable_repository(self, github_repo_id: int) -> tuple[Repository, int] | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT r.id, r.github_repo_id, r.installation_id, r.full_name,"
                " r.default_branch, r.private, r.created_at, i.github_installation_id"
                " FROM repositories r JOIN installations i ON i.id = r.installation_id"
                " WHERE r.github_repo_id = %s AND i.suspended_at IS NULL",
                (github_repo_id,),
            )
            row = await cur.fetchone()
        return (_row_to_repository(row[:7]), row[7]) if row is not None else None

    async def list_scannable_repositories(self) -> list[tuple[Repository, int]]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT r.id, r.github_repo_id, r.installation_id, r.full_name,"
                " r.default_branch, r.private, r.created_at, i.github_installation_id"
                " FROM repositories r JOIN installations i ON i.id = r.installation_id"
                " WHERE i.suspended_at IS NULL ORDER BY r.id"
            )
            rows = await cur.fetchall()
        return [(_row_to_repository(row[:7]), row[7]) for row in rows]


def _row_to_repository(row: tuple) -> Repository:
    return Repository(
        id=row[0],
        github_repo_id=row[1],
        installation_id=row[2],
        full_name=row[3],
        default_branch=row[4],
        private=row[5],
        created_at=row[6],
    )
