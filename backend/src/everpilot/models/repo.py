from datetime import UTC, datetime

from pydantic import BaseModel, Field

from everpilot.models.capability import DEFAULT_CAPABILITIES, CapabilityConfig


class RepoSummary(BaseModel):
    """Lightweight repo representation from GitHub."""

    id: int
    full_name: str = Field(description="owner/repo")
    description: str | None = None
    private: bool = False
    html_url: str
    default_branch: str = "main"
    language: str | None = None
    stargazers_count: int = 0
    updated_at: datetime | None = None


class RepoConfig(BaseModel):
    """User-configured settings for a specific repository."""

    repo_full_name: str
    capabilities: list[CapabilityConfig] = Field(default_factory=lambda: list(DEFAULT_CAPABILITIES))
    installed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


class Repo(BaseModel):
    """Combined repo info + configuration."""

    summary: RepoSummary
    config: RepoConfig

    @property
    def full_name(self) -> str:
        return self.summary.full_name

    @property
    def active_capabilities(self) -> list[CapabilityConfig]:
        return [c for c in self.config.capabilities if c.is_active]
