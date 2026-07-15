from typing import Protocol

from everpilot.models.capability import CapabilityConfig
from everpilot.models.repo import RepoConfig


class RepoConfigStore(Protocol):
    """Persistence interface for per-repository Everpilot configuration."""

    async def list_repo_names(self) -> list[str]: ...

    async def get(self, repo_full_name: str) -> RepoConfig | None: ...

    async def create(self, config: RepoConfig) -> bool:
        """Persist a new config. Returns False if the repo is already installed."""
        ...

    async def set_capability(
        self, repo_full_name: str, capability_config: CapabilityConfig
    ) -> RepoConfig | None:
        """Replace one capability's config. Returns the updated config, or None if not installed."""
        ...

    async def delete(self, repo_full_name: str) -> bool:
        """Remove a repo's config. Returns False if the repo was not installed."""
        ...


class InMemoryRepoConfigStore:
    """Dict-backed store for local development and tests."""

    def __init__(self) -> None:
        self._configs: dict[str, RepoConfig] = {}

    async def list_repo_names(self) -> list[str]:
        return list(self._configs.keys())

    async def get(self, repo_full_name: str) -> RepoConfig | None:
        return self._configs.get(repo_full_name)

    async def create(self, config: RepoConfig) -> bool:
        if config.repo_full_name in self._configs:
            return False
        self._configs[config.repo_full_name] = config
        return True

    async def set_capability(
        self, repo_full_name: str, capability_config: CapabilityConfig
    ) -> RepoConfig | None:
        config = self._configs.get(repo_full_name)
        if config is None:
            return None
        config.capabilities = [
            capability_config if c.capability == capability_config.capability else c
            for c in config.capabilities
        ]
        return config

    async def delete(self, repo_full_name: str) -> bool:
        return self._configs.pop(repo_full_name, None) is not None
