"""Batch planning: security/major solos, per-ecosystem grouping."""

from everpilot.capabilities.dependencies.batching import plan_batches
from everpilot.capabilities.dependencies.detector import (
    DependencyReport,
    OutdatedDependency,
    VulnerableDependency,
)
from everpilot.capabilities.dependencies.lockfiles import Ecosystem
from everpilot.capabilities.dependencies.osv import Advisory


def outdated(name: str, bump: str, ecosystem: Ecosystem = Ecosystem.PYPI) -> OutdatedDependency:
    return OutdatedDependency(
        name=name, ecosystem=ecosystem, current="1.0.0", latest="2.0.0", bump=bump
    )


def vulnerable(name: str) -> VulnerableDependency:
    return VulnerableDependency(
        name=name,
        ecosystem=Ecosystem.PYPI,
        current="1.0.0",
        advisories=[Advisory(id="GHSA-x")],
    )


def test_security_first_then_majors_then_grouped() -> None:
    report = DependencyReport(
        total_pinned=5,
        outdated=[
            outdated("safe-minor", "minor"),
            outdated("big-jump", "major"),
            outdated("cve-pkg", "patch"),
            outdated("safe-patch", "patch"),
        ],
        vulnerable=[vulnerable("cve-pkg")],
    )
    batches = plan_batches(report)
    assert [b.kind for b in batches] == ["security", "major", "grouped"]
    assert batches[0].title == "Bump cve-pkg to 2.0.0 (security)"
    assert batches[1].title == "Bump big-jump to 2.0.0 (major)"
    assert {d.name for d in batches[2].dependencies} == {"safe-minor", "safe-patch"}


def test_grouping_is_per_ecosystem() -> None:
    report = DependencyReport(
        total_pinned=4,
        outdated=[
            outdated("py-a", "minor", Ecosystem.PYPI),
            outdated("py-b", "patch", Ecosystem.PYPI),
            outdated("js-a", "minor", Ecosystem.NPM),
            outdated("js-b", "patch", Ecosystem.NPM),
        ],
    )
    batches = plan_batches(report)
    assert len(batches) == 2
    assert {b.ecosystem for b in batches} == {Ecosystem.PYPI, Ecosystem.NPM}
    assert all(b.kind == "grouped" for b in batches)
    assert batches[0].title.startswith("Bump 2 ")


def test_single_groupable_dep_gets_specific_title() -> None:
    report = DependencyReport(total_pinned=1, outdated=[outdated("httpx", "minor")])
    batches = plan_batches(report)
    assert batches[0].title == "Bump httpx to 2.0.0"


def test_vulnerable_major_is_security_not_major() -> None:
    report = DependencyReport(
        total_pinned=1,
        outdated=[outdated("cve-major", "major")],
        vulnerable=[vulnerable("cve-major")],
    )
    batches = plan_batches(report)
    assert [b.kind for b in batches] == ["security"]


def test_empty_report_plans_nothing() -> None:
    assert plan_batches(DependencyReport()) == []
