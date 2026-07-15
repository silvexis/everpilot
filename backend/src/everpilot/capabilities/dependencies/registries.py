"""Latest-version lookups straight from the package registries (Renovate-style)."""

import asyncio
import logging

import httpx

from everpilot.capabilities.dependencies.lockfiles import Ecosystem, PinnedDependency

logger = logging.getLogger(__name__)

PYPI_BASE_URL = "https://pypi.org"
NPM_BASE_URL = "https://registry.npmjs.org"
_CONCURRENCY = 10


class RegistryClient:
    def __init__(
        self,
        pypi: httpx.AsyncClient | None = None,
        npm: httpx.AsyncClient | None = None,
    ) -> None:
        self._pypi = pypi or httpx.AsyncClient(base_url=PYPI_BASE_URL, timeout=30)
        self._npm = npm or httpx.AsyncClient(base_url=NPM_BASE_URL, timeout=30)

    async def latest_version(self, dependency: PinnedDependency) -> str | None:
        """Latest published version, or None if the lookup fails (skip, don't crash)."""
        try:
            if dependency.ecosystem == Ecosystem.PYPI:
                response = await self._pypi.get(f"/pypi/{dependency.name}/json")
                response.raise_for_status()
                return response.json()["info"]["version"]
            response = await self._npm.get(f"/{dependency.name}")
            response.raise_for_status()
            return response.json()["dist-tags"]["latest"]
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Latest-version lookup failed for %s: %s", dependency.name, exc)
            return None

    async def latest_versions(self, dependencies: list[PinnedDependency]) -> dict[str, str]:
        """Concurrent lookups (bounded); failed lookups are omitted."""
        semaphore = asyncio.Semaphore(_CONCURRENCY)

        async def lookup(dep: PinnedDependency) -> tuple[str, str | None]:
            async with semaphore:
                return dep.name, await self.latest_version(dep)

        pairs = await asyncio.gather(*(lookup(d) for d in dependencies))
        return {name: version for name, version in pairs if version is not None}
