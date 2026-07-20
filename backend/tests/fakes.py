"""Shared fakes: psycopg pool/connection stand-ins so unit tests never touch a DB,
plus the standard tenant fixture (org 777 / installation 5555 / repo 101)."""

from everpilot.models.core import Installation, Organization, Repository

STANDARD_ORG_GITHUB_ID = 777
STANDARD_INSTALLATION_GITHUB_ID = 5555
STANDARD_REPO_GITHUB_ID = 101
STANDARD_REPO_FULL_NAME = "silvexis/alpha"


async def seed_tenant(installations) -> Repository:
    """Create the standard org→installation→repo tenant in an installation store."""
    org_id = await installations.upsert_organization(
        Organization(github_org_id=STANDARD_ORG_GITHUB_ID, login="silvexis")
    )
    installation_db_id = await installations.create_installation(
        Installation(github_installation_id=STANDARD_INSTALLATION_GITHUB_ID, organization_id=org_id)
    )
    await installations.add_repositories(
        installation_db_id,
        [
            Repository(
                github_repo_id=STANDARD_REPO_GITHUB_ID,
                installation_id=0,
                full_name=STANDARD_REPO_FULL_NAME,
            )
        ],
    )
    return next(iter(installations._repositories.values()))


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[tuple]:
        return self._rows

    async def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None


class FakeConnection:
    """Stands in for both the pooled connection and its transaction context."""

    def __init__(self, results: list[list[tuple]]) -> None:
        self._results = results
        self.queries: list[tuple[str, tuple | None]] = []

    async def execute(self, sql: str, params: tuple | None = None) -> FakeCursor:
        self.queries.append((" ".join(sql.split()), params))
        rows = self._results.pop(0) if self._results else []
        return FakeCursor(rows)

    def transaction(self) -> "FakeConnection":
        return self

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def connection(self) -> FakeConnection:
        return self._connection
