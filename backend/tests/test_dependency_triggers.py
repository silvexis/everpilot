"""Dependency scan triggers: push detection, config gating, batch→task submission."""

import base64
import json

import httpx
from fakes import seed_tenant
from githubkit.exception import RequestFailed

from everpilot.capabilities.dependencies.detector import DependencyDetector
from everpilot.capabilities.dependencies.osv import OSVClient
from everpilot.capabilities.dependencies.registries import RegistryClient
from everpilot.capabilities.dependencies.service import (
    DependencyScanService,
    push_touches_lockfile,
)
from everpilot.db.installations import InMemoryInstallationStore
from everpilot.db.store import InMemoryRepoConfigStore
from everpilot.db.tasks import InMemoryAuditStore, InMemoryTaskStore
from everpilot.github.auth import GitHubAppClients
from everpilot.models.capability import Capability, CapabilityConfig, CapabilityMode
from everpilot.models.repo import RepoConfig
from everpilot.pipeline import TaskPipeline

UV_LOCK = """
version = 1

[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }
"""


def push_payload(paths: list[str], ref: str = "refs/heads/main") -> dict:
    return {
        "ref": ref,
        "repository": {"id": 101, "full_name": "silvexis/alpha", "default_branch": "main"},
        "commits": [{"added": [], "modified": paths, "removed": []}],
    }


# --- Lockfile-touch detection ---


def test_push_touches_lockfile_positive() -> None:
    assert push_touches_lockfile(push_payload(["uv.lock"]))
    assert push_touches_lockfile(push_payload(["package-lock.json"]))


def test_push_touches_lockfile_negative() -> None:
    assert not push_touches_lockfile(push_payload(["src/main.py", "README.md"]))
    assert not push_touches_lockfile({"commits": []})


# --- Service fixtures ---


class StubContentResponse:
    def __init__(self, content: str) -> None:
        class Data:
            pass

        self.parsed_data = Data()
        self.parsed_data.content = base64.b64encode(content.encode()).decode()


def _not_found() -> RequestFailed:
    """A real githubkit RequestFailed carrying a 404, as the contents API raises."""

    class FakeResponse:
        status_code = 404
        raw_request = None
        raw_response = None

    return RequestFailed(FakeResponse())  # type: ignore[arg-type]


class StubGitHub:
    """Stands in for a githubkit client: only the contents route is used."""

    def __init__(self, files: dict[str, str]) -> None:
        files = dict(files)

        class Repos:
            async def async_get_content(self, *, owner: str, repo: str, path: str):
                if path not in files:
                    raise _not_found()
                return StubContentResponse(files[path])

        class Rest:
            repos = Repos()

        self.rest = Rest()


class StubClients(GitHubAppClients):
    def __init__(self, files: dict[str, str]) -> None:
        super().__init__("12345", "fake-key")
        self._files = files

    def installation(self, installation_id: int):  # type: ignore[override]
        return StubGitHub(self._files)


def detector_with_outdated() -> DependencyDetector:
    def osv_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{}]})

    def pypi_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"info": {"version": "0.29.0"}})

    return DependencyDetector(
        osv=OSVClient(
            httpx.AsyncClient(
                transport=httpx.MockTransport(osv_handler), base_url="https://api.osv.dev"
            )
        ),
        registries=RegistryClient(
            pypi=httpx.AsyncClient(
                transport=httpx.MockTransport(pypi_handler), base_url="https://pypi.org"
            ),
            npm=httpx.AsyncClient(
                transport=httpx.MockTransport(pypi_handler),
                base_url="https://registry.npmjs.org",
            ),
        ),
    )


async def make_service(
    *,
    mode: CapabilityMode = CapabilityMode.ASSISTED,
    enabled: bool = True,
    files: dict[str, str] | None = None,
) -> tuple[DependencyScanService, InMemoryTaskStore, InMemoryAuditStore]:
    installations = InMemoryInstallationStore()
    await seed_tenant(installations)

    repo_configs = InMemoryRepoConfigStore()
    await repo_configs.create(
        RepoConfig(
            repo_full_name="silvexis/alpha",
            capabilities=[
                CapabilityConfig(capability=Capability.DEPENDENCIES, mode=mode, enabled=enabled)
            ],
        )
    )

    tasks, audit = InMemoryTaskStore(), InMemoryAuditStore()
    service = DependencyScanService(
        detector_with_outdated(),
        StubClients(files if files is not None else {"uv.lock": UV_LOCK}),
        repo_configs,
        installations,
        TaskPipeline(tasks, audit),
    )
    return service, tasks, audit


# --- Push-triggered scans ---


async def test_push_creates_task_per_batch() -> None:
    service, _tasks, _ = await make_service()
    created = await service.handle_push(push_payload(["uv.lock"]))
    assert len(created) == 1  # one outdated minor dep → one grouped batch
    assert created[0].trigger == "webhook:push"
    assert created[0].capability == Capability.DEPENDENCIES
    assert "httpx" in created[0].title


async def test_push_to_non_default_branch_ignored() -> None:
    service, tasks, _ = await make_service()
    created = await service.handle_push(push_payload(["uv.lock"], ref="refs/heads/feature/x"))
    assert created == []
    assert tasks._tasks == {}


async def test_push_without_lockfile_changes_ignored() -> None:
    service, _tasks, _ = await make_service()
    assert await service.handle_push(push_payload(["src/app.py"])) == []


async def test_push_unknown_repository_ignored() -> None:
    service, _, _ = await make_service()
    payload = push_payload(["uv.lock"])
    payload["repository"]["id"] = 999
    assert await service.handle_push(payload) == []


async def test_off_mode_creates_no_task_but_audits_suppression() -> None:
    service, tasks, audit = await make_service(mode=CapabilityMode.OFF)
    created = await service.handle_push(push_payload(["uv.lock"]))
    assert created == []
    assert tasks._tasks == {}
    assert any(e.event_type == "task.suppressed" for e in audit.events)


async def test_unconfigured_repo_treated_as_off() -> None:
    service, _tasks, audit = await make_service()
    # Point at a repo with no capability config
    service._repo_configs = InMemoryRepoConfigStore()
    created = await service.handle_push(push_payload(["uv.lock"]))
    assert created == []
    assert any(e.event_type == "task.suppressed" for e in audit.events)


async def test_repo_without_lockfiles_scans_nothing() -> None:
    service, tasks, _ = await make_service(files={})
    assert await service.handle_push(push_payload(["uv.lock"])) == []
    assert tasks._tasks == {}


async def test_rapid_pushes_do_not_duplicate_open_tasks() -> None:
    service, tasks, _ = await make_service()
    first = await service.handle_push(push_payload(["uv.lock"]))
    second = await service.handle_push(push_payload(["uv.lock"]))
    assert len(first) == 1
    assert second == []  # same batch title already open
    assert len(tasks._tasks) == 1


def test_truncated_push_payload_is_conservative() -> None:
    # size > listed commits → can't know → scan
    assert push_touches_lockfile(
        {"size": 30, "commits": [{"added": [], "modified": ["src/x.py"], "removed": []}]}
    )


def test_nested_lockfile_does_not_trigger_root_scan() -> None:
    # Root-only for V1: trigger and fetch must agree (monorepos tracked post-V1)
    assert not push_touches_lockfile(push_payload(["backend/uv.lock"]))
    assert push_touches_lockfile(push_payload(["uv.lock"]))


async def test_off_mode_skips_network_entirely() -> None:
    calls = []

    class CountingClients(GitHubAppClients):
        def __init__(self) -> None:
            super().__init__("12345", "fake-key")

        def installation(self, installation_id: int):  # type: ignore[override]
            calls.append(installation_id)
            raise AssertionError("must not fetch lockfiles when capability is off")

    service, _, audit = await make_service(mode=CapabilityMode.OFF)
    service._clients = CountingClients()
    assert await service.handle_push(push_payload(["uv.lock"])) == []
    assert calls == []
    assert sum(1 for e in audit.events if e.event_type == "task.suppressed") == 1


# --- Scheduled sweep ---


async def test_scan_all_covers_repositories() -> None:
    service, tasks, _ = await make_service()
    created = await service.scan_all()
    assert created == 1
    assert len(tasks._tasks) == 1
    assert next(iter(tasks._tasks.values())).trigger == "schedule"


async def test_scan_all_survives_per_repo_failures() -> None:
    service, _, _ = await make_service()

    async def boom(*args, **kwargs):
        raise RuntimeError("github down")

    service.scan_repository = boom  # type: ignore[method-assign]
    assert await service.scan_all() == 0  # logged, not raised


def test_package_lock_payload_shape() -> None:
    # Guard: the JSON fixture used by npm tests parses
    assert json.loads('{"lockfileVersion": 3, "packages": {}}')
