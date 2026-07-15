"""Dependency detection: lockfiles, versions, OSV, registries, detector. No real HTTP."""

import json

import httpx
import pytest

from everpilot.capabilities.dependencies import DependencyDetector, Ecosystem
from everpilot.capabilities.dependencies.lockfiles import (
    PinnedDependency,
    parse_package_lock,
    parse_uv_lock,
)
from everpilot.capabilities.dependencies.osv import OSVClient
from everpilot.capabilities.dependencies.registries import RegistryClient
from everpilot.capabilities.dependencies.versions import bump_kind, is_outdated

UV_LOCK = """
version = 1
revision = 3

[[package]]
name = "everpilot"
version = "0.1.0"
source = { editable = "." }

[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "fastapi"
version = "0.139.0"
source = { registry = "https://pypi.org/simple" }
"""

PACKAGE_LOCK = json.dumps(
    {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "frontend", "version": "0.0.0"},
            "node_modules/react": {"version": "19.0.0"},
            "node_modules/@types/node": {"version": "22.1.0"},
        },
    }
)


# --- Lockfile parsing ---


def test_parse_uv_lock_excludes_project_itself() -> None:
    deps = parse_uv_lock(UV_LOCK, project_name="everpilot")
    assert {(d.name, d.version) for d in deps} == {("httpx", "0.28.1"), ("fastapi", "0.139.0")}
    assert all(d.ecosystem == Ecosystem.PYPI for d in deps)


def test_parse_uv_lock_excludes_editable_even_without_name() -> None:
    deps = parse_uv_lock(UV_LOCK)
    assert "everpilot" not in {d.name for d in deps}


def test_parse_package_lock_extracts_scoped_names() -> None:
    deps = parse_package_lock(PACKAGE_LOCK)
    assert {(d.name, d.version) for d in deps} == {
        ("react", "19.0.0"),
        ("@types/node", "22.1.0"),
    }


# --- Version comparison ---


@pytest.mark.parametrize(
    ("ecosystem", "current", "latest", "outdated"),
    [
        (Ecosystem.PYPI, "0.28.1", "0.29.0", True),
        (Ecosystem.PYPI, "0.29.0", "0.29.0", False),
        (Ecosystem.PYPI, "2.0.0", "2.0.0rc1", False),  # pre-release not newer
        (Ecosystem.NPM, "19.0.0", "19.1.2", True),
        (Ecosystem.NPM, "19.1.2", "19.0.0", False),
        (Ecosystem.PYPI, "not-a-version", "1.0", False),  # unparseable = skip
    ],
)
def test_is_outdated(ecosystem: Ecosystem, current: str, latest: str, outdated: bool) -> None:
    assert is_outdated(ecosystem, current, latest) is outdated


@pytest.mark.parametrize(
    ("current", "latest", "kind"),
    [("1.2.3", "2.0.0", "major"), ("1.2.3", "1.3.0", "minor"), ("1.2.3", "1.2.4", "patch")],
)
def test_bump_kind(current: str, latest: str, kind: str) -> None:
    assert bump_kind(Ecosystem.PYPI, current, latest) == kind
    assert bump_kind(Ecosystem.NPM, current, latest) == kind


def test_bump_kind_unparseable_is_major() -> None:
    assert bump_kind(Ecosystem.PYPI, "weird", "1.0") == "major"


# --- OSV client (mocked transport) ---


def osv_transport(results: list[dict]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/querybatch"
        return httpx.Response(200, json={"results": results})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.osv.dev")


async def test_osv_maps_vulns_to_names() -> None:
    client = OSVClient(osv_transport([{"vulns": [{"id": "GHSA-xxxx", "summary": "bad"}]}, {}]))
    deps = [
        PinnedDependency(name="httpx", version="0.1.0", ecosystem=Ecosystem.PYPI),
        PinnedDependency(name="fastapi", version="0.139.0", ecosystem=Ecosystem.PYPI),
    ]
    advisories = await client.check(deps)
    assert list(advisories) == ["httpx"]
    assert advisories["httpx"][0].id == "GHSA-xxxx"


async def test_osv_empty_dependencies_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    client = OSVClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.osv.dev")
    )
    assert await client.check([]) == {}


# --- Registry client (mocked transports) ---


def registry_client(pypi_latest: str = "0.29.0", npm_latest: str = "19.1.0") -> RegistryClient:
    def pypi_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"info": {"version": pypi_latest}})

    def npm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"dist-tags": {"latest": npm_latest}})

    return RegistryClient(
        pypi=httpx.AsyncClient(
            transport=httpx.MockTransport(pypi_handler), base_url="https://pypi.org"
        ),
        npm=httpx.AsyncClient(
            transport=httpx.MockTransport(npm_handler), base_url="https://registry.npmjs.org"
        ),
    )


async def test_latest_versions_both_ecosystems() -> None:
    client = registry_client()
    versions = await client.latest_versions(
        [
            PinnedDependency(name="httpx", version="0.28.1", ecosystem=Ecosystem.PYPI),
            PinnedDependency(name="react", version="19.0.0", ecosystem=Ecosystem.NPM),
        ]
    )
    assert versions == {"httpx": "0.29.0", "react": "19.1.0"}


async def test_failed_lookup_is_omitted_not_fatal() -> None:
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = RegistryClient(
        pypi=httpx.AsyncClient(transport=httpx.MockTransport(failing), base_url="https://pypi.org"),
        npm=httpx.AsyncClient(
            transport=httpx.MockTransport(failing), base_url="https://registry.npmjs.org"
        ),
    )
    versions = await client.latest_versions(
        [PinnedDependency(name="httpx", version="0.28.1", ecosystem=Ecosystem.PYPI)]
    )
    assert versions == {}


# --- Detector end-to-end ---


async def test_detector_reports_outdated_and_vulnerable() -> None:
    detector = DependencyDetector(
        osv=OSVClient(osv_transport([{"vulns": [{"id": "GHSA-yyyy"}]}, {}])),
        registries=registry_client(pypi_latest="0.29.0"),
    )
    report = await detector.scan(uv_lock=UV_LOCK, project_name="everpilot")
    assert report.total_pinned == 2
    assert report.has_findings
    outdated_names = {d.name for d in report.outdated}
    assert "httpx" in outdated_names  # 0.28.1 → 0.29.0
    assert report.outdated[0].bump in {"minor", "patch", "major"}
    assert {v.name for v in report.vulnerable} == {"httpx"}


async def test_detector_empty_lockfiles() -> None:
    detector = DependencyDetector(osv=OSVClient(osv_transport([])), registries=registry_client())
    report = await detector.scan()
    assert report.total_pinned == 0
    assert not report.has_findings
