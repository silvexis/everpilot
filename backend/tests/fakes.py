"""Shared fakes: psycopg pool/connection stand-ins so unit tests never touch a DB."""


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
