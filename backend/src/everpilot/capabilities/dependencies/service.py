"""Dependency scan triggers: lockfile-touching pushes and scheduled sweeps.

Detection runs entirely here (no agent engine): fetch lockfiles, detect
outdated/vulnerable dependencies, plan upgrade batches, and submit one pipeline
task per batch. Executing the upgrades is the M1 engine's job and stays stubbed.
"""

import asyncio
import base64
import binascii
import logging

from githubkit.exception import RequestFailed

from everpilot.capabilities.dependencies.batching import plan_batches
from everpilot.capabilities.dependencies.detector import DependencyDetector
from everpilot.capabilities.dependencies.lockfiles import Ecosystem
from everpilot.db.installations import InstallationStore
from everpilot.db.store import RepoConfigStore
from everpilot.github.auth import GitHubAppClients
from everpilot.models.capability import Capability, CapabilityMode
from everpilot.models.core import Repository, Task
from everpilot.pipeline import TaskPipeline

logger = logging.getLogger(__name__)

LOCKFILES = {"uv.lock": Ecosystem.PYPI, "package-lock.json": Ecosystem.NPM}

#: GitHub truncates the push payload's commits array at this many entries.
_PUSH_COMMITS_CAP = 20


def push_touches_lockfile(payload: dict) -> bool:  # type: ignore[type-arg]
    """True if the push plausibly changed a repo-root lockfile.

    Root paths only — the scanner fetches root lockfiles, and trigger and fetch
    must agree (nested/monorepo lockfiles are a tracked post-V1 gap). When the
    payload's commit list is truncated (size > listed commits, or at GitHub's
    cap) we can't know, so answer True and let the scan decide.
    """
    commits = payload.get("commits", [])
    size = payload.get("size")
    if isinstance(size, int) and size > len(commits):
        return True
    if len(commits) >= _PUSH_COMMITS_CAP:
        return True
    head_commit = payload.get("head_commit") or {}
    for commit in [*commits, head_commit]:
        for change_list in ("added", "modified", "removed"):
            for path in commit.get(change_list, []):
                if path in LOCKFILES:
                    return True
    return False


class DependencyScanService:
    def __init__(
        self,
        detector: DependencyDetector,
        clients: GitHubAppClients,
        repo_configs: RepoConfigStore,
        installations: InstallationStore,
        pipeline: TaskPipeline,
    ) -> None:
        self._detector = detector
        self._clients = clients
        self._repo_configs = repo_configs
        self._installations = installations
        self._pipeline = pipeline

    async def handle_push(self, payload: dict) -> list[Task]:  # type: ignore[type-arg]
        """Scan on lockfile-touching pushes to the default branch."""
        if not push_touches_lockfile(payload):
            return []
        repo_data = payload.get("repository") or {}
        ref = payload.get("ref", "")
        default_branch = repo_data.get("default_branch", "main")
        if ref != f"refs/heads/{default_branch}":
            return []
        github_repo_id = repo_data.get("id")
        if github_repo_id is None:
            return []
        context = await self._installations.get_scannable_repository(github_repo_id)
        if context is None:
            logger.warning("Push for unknown repository %s — ignored", github_repo_id)
            return []
        repository, github_installation_id = context
        return await self.scan_repository(
            repository, github_installation_id, trigger="webhook:push"
        )

    async def scan_repository(
        self, repository: Repository, github_installation_id: int, *, trigger: str
    ) -> list[Task]:
        """Fetch lockfiles, detect, batch, and submit one task per planned batch."""
        mode, enabled = await self._dependencies_config(repository.full_name)
        if not enabled or mode == CapabilityMode.OFF:
            # Gate before any network I/O; one auditable suppression per scan
            await self._pipeline.submit(
                repository_id=repository.id,  # type: ignore[arg-type]
                capability=Capability.DEPENDENCIES,
                mode=mode,
                enabled=enabled,
                trigger=trigger,
                title=f"Dependency scan of {repository.full_name}",
            )
            return []

        github = self._clients.installation(github_installation_id)
        owner, _, repo = repository.full_name.partition("/")
        uv_lock, package_lock = await asyncio.gather(
            _fetch_file(github, owner, repo, "uv.lock"),
            _fetch_file(github, owner, repo, "package-lock.json"),
        )
        if uv_lock is None and package_lock is None:
            logger.info("No lockfiles in %s — nothing to scan", repository.full_name)
            return []

        report = await self._detector.scan(uv_lock=uv_lock, package_lock=package_lock)
        if not report.has_findings:
            logger.info(
                "%s: %d pinned deps, no findings", repository.full_name, report.total_pinned
            )
            return []

        open_titles = await self._open_task_titles(repository.id)  # type: ignore[arg-type]
        batches = plan_batches(report)
        tasks = []
        for batch in batches:
            if batch.title in open_titles:
                logger.info("Skipping duplicate open task: %s", batch.title)
                continue
            task = await self._pipeline.submit(
                repository_id=repository.id,  # type: ignore[arg-type]
                capability=Capability.DEPENDENCIES,
                mode=mode,
                enabled=enabled,
                trigger=trigger,
                title=batch.title,
            )
            if task is not None:
                tasks.append(task)
        logger.info(
            "%s scan (%s): %d batches planned, %d tasks created",
            repository.full_name,
            trigger,
            len(batches),
            len(tasks),
        )
        return tasks

    async def scan_all(self) -> int:
        """Scheduled sweep across every non-suspended installation's repos."""
        count = 0
        for (
            repository,
            github_installation_id,
        ) in await self._installations.list_scannable_repositories():
            try:
                count += len(
                    await self.scan_repository(
                        repository, github_installation_id, trigger="schedule"
                    )
                )
            except Exception:
                logger.exception("Scheduled scan failed for %s", repository.full_name)
        return count

    async def _open_task_titles(self, repository_id: int) -> set[str]:
        """Titles of non-terminal dependency tasks — dedup for rapid re-scans."""
        tasks = await self._pipeline.list_open_tasks(repository_id)
        return {t.title for t in tasks if t.capability == Capability.DEPENDENCIES}

    async def _dependencies_config(self, full_name: str) -> tuple[CapabilityMode, bool]:
        config = await self._repo_configs.get(full_name)
        if config is None:
            return CapabilityMode.OFF, False
        for capability_config in config.capabilities:
            if capability_config.capability == Capability.DEPENDENCIES:
                return capability_config.mode, capability_config.enabled
        return CapabilityMode.OFF, False


async def _fetch_file(github, owner: str, repo: str, path: str) -> str | None:
    """Fetch a file's text via the contents API.

    Returns None for a missing file (404) or undecodable content; re-raises
    everything else (auth failures, rate limits) so callers see real outages
    instead of an empty scan.
    """
    try:
        response = await github.rest.repos.async_get_content(owner=owner, repo=repo, path=path)
    except RequestFailed as exc:
        if exc.response.status_code == 404:
            logger.debug("No %s in %s/%s", path, owner, repo)
            return None
        raise
    data = response.parsed_data
    content = getattr(data, "content", None)
    if not content:
        if getattr(data, "size", 0):
            # Contents API returns empty content for files >1MB (encoding "none")
            logger.warning(
                "%s in %s/%s exceeds the contents-API size limit — skipping"
                " (large-lockfile support tracked in docs/open_questions.md)",
                path,
                owner,
                repo,
            )
        return None  # directories/submodules also have no content field
    try:
        return base64.b64decode(content).decode()
    except (binascii.Error, UnicodeDecodeError):
        logger.warning("Undecodable %s in %s/%s — skipping", path, owner, repo)
        return None
