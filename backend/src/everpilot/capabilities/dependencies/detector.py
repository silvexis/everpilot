"""Outdated/vulnerable dependency detection: lockfile → report."""

from pydantic import BaseModel, Field

from everpilot.capabilities.dependencies.lockfiles import (
    Ecosystem,
    PinnedDependency,
    parse_package_lock,
    parse_uv_lock,
)
from everpilot.capabilities.dependencies.osv import Advisory, OSVClient
from everpilot.capabilities.dependencies.registries import RegistryClient
from everpilot.capabilities.dependencies.versions import bump_kind, is_outdated


class OutdatedDependency(BaseModel):
    name: str
    ecosystem: Ecosystem
    current: str
    latest: str
    bump: str  # major | minor | patch


class VulnerableDependency(BaseModel):
    name: str
    ecosystem: Ecosystem
    current: str
    advisories: list[Advisory]


class DependencyReport(BaseModel):
    total_pinned: int = 0
    outdated: list[OutdatedDependency] = Field(default_factory=list)
    vulnerable: list[VulnerableDependency] = Field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.outdated or self.vulnerable)


class DependencyDetector:
    def __init__(self, osv: OSVClient, registries: RegistryClient) -> None:
        self._osv = osv
        self._registries = registries

    async def scan(
        self,
        *,
        uv_lock: str | None = None,
        package_lock: str | None = None,
        project_name: str | None = None,
    ) -> DependencyReport:
        dependencies: list[PinnedDependency] = []
        if uv_lock is not None:
            dependencies += parse_uv_lock(uv_lock, project_name=project_name)
        if package_lock is not None:
            dependencies += parse_package_lock(package_lock)
        if not dependencies:
            return DependencyReport()

        latest_versions = await self._registries.latest_versions(dependencies)
        advisories = await self._osv.check(dependencies)

        report = DependencyReport(total_pinned=len(dependencies))
        for dep in dependencies:
            latest = latest_versions.get(dep.name)
            if latest is not None and is_outdated(dep.ecosystem, dep.version, latest):
                report.outdated.append(
                    OutdatedDependency(
                        name=dep.name,
                        ecosystem=dep.ecosystem,
                        current=dep.version,
                        latest=latest,
                        bump=bump_kind(dep.ecosystem, dep.version, latest),
                    )
                )
            if dep.name in advisories:
                report.vulnerable.append(
                    VulnerableDependency(
                        name=dep.name,
                        ecosystem=dep.ecosystem,
                        current=dep.version,
                        advisories=advisories[dep.name],
                    )
                )
        return report
