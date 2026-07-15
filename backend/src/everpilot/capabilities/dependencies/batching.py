"""Upgrade batching (roadmap M3): how findings become PR-sized units.

Rules:
- Security fixes ship solo, first — smallest possible diff to review/merge fast.
- Major bumps ship solo — breaking-change review must not hide in a group.
- Remaining minor/patch bumps group per ecosystem (one PR touches one lockfile).
"""

from pydantic import BaseModel

from everpilot.capabilities.dependencies.detector import DependencyReport, OutdatedDependency
from everpilot.capabilities.dependencies.lockfiles import Ecosystem

_ECOSYSTEM_LABEL = {Ecosystem.PYPI: "Python", Ecosystem.NPM: "JavaScript"}


class UpgradeBatch(BaseModel):
    kind: str  # "security" | "major" | "grouped"
    ecosystem: Ecosystem
    title: str
    dependencies: list[OutdatedDependency]


def plan_batches(report: DependencyReport) -> list[UpgradeBatch]:
    """Order: security solos, then major solos, then one grouped batch per ecosystem."""
    vulnerable_names = {v.name for v in report.vulnerable}
    security: list[UpgradeBatch] = []
    majors: list[UpgradeBatch] = []
    groupable: dict[Ecosystem, list[OutdatedDependency]] = {}

    for dep in report.outdated:
        if dep.name in vulnerable_names:
            security.append(
                UpgradeBatch(
                    kind="security",
                    ecosystem=dep.ecosystem,
                    title=f"Bump {dep.name} to {dep.latest} (security)",
                    dependencies=[dep],
                )
            )
        elif dep.bump == "major":
            majors.append(
                UpgradeBatch(
                    kind="major",
                    ecosystem=dep.ecosystem,
                    title=f"Bump {dep.name} to {dep.latest} (major)",
                    dependencies=[dep],
                )
            )
        else:
            groupable.setdefault(dep.ecosystem, []).append(dep)

    grouped = []
    for ecosystem, deps in groupable.items():
        if len(deps) == 1:
            only = deps[0]
            title = f"Bump {only.name} to {only.latest}"
        else:
            label = _ECOSYSTEM_LABEL[ecosystem]
            title = f"Bump {len(deps)} {label} dependencies (minor/patch)"
        grouped.append(
            UpgradeBatch(kind="grouped", ecosystem=ecosystem, title=title, dependencies=deps)
        )

    return security + majors + grouped
