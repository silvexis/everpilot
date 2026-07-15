"""OSV.dev vulnerability lookups (free, no auth, batch API)."""

import httpx
from pydantic import BaseModel

from everpilot.capabilities.dependencies.lockfiles import PinnedDependency

OSV_BASE_URL = "https://api.osv.dev"
_BATCH_LIMIT = 1000  # documented querybatch maximum


class Advisory(BaseModel):
    id: str
    summary: str | None = None


class OSVClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=OSV_BASE_URL, timeout=30)

    async def check(self, dependencies: list[PinnedDependency]) -> dict[str, list[Advisory]]:
        """Map dependency name → advisories. Names absent from the map are clean."""
        results: dict[str, list[Advisory]] = {}
        for start in range(0, len(dependencies), _BATCH_LIMIT):
            batch = dependencies[start : start + _BATCH_LIMIT]
            response = await self._client.post(
                "/v1/querybatch",
                json={
                    "queries": [
                        {
                            "package": {"name": d.name, "ecosystem": d.ecosystem},
                            "version": d.version,
                        }
                        for d in batch
                    ]
                },
            )
            response.raise_for_status()
            for dependency, result in zip(batch, response.json().get("results", []), strict=True):
                vulns = result.get("vulns") or []
                if vulns:
                    results[dependency.name] = [
                        Advisory(id=v["id"], summary=v.get("summary")) for v in vulns
                    ]
        return results
