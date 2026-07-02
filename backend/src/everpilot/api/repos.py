from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from everpilot.models.capability import (
    DEFAULT_CAPABILITIES,
    Capability,
    CapabilityConfig,
    CapabilityMode,
)
from everpilot.models.repo import RepoConfig

router = APIRouter(prefix="/repos", tags=["repos"])

# In-memory store for boilerplate; replace with DB in production
_repo_configs: dict[str, RepoConfig] = {}


class UpdateCapabilityRequest(BaseModel):
    capability: Capability
    mode: CapabilityMode
    enabled: bool


class InstallRepoRequest(BaseModel):
    repo_full_name: str


class RepoConfigResponse(BaseModel):
    repo_full_name: str
    capabilities: list[CapabilityConfig]
    active: bool


@router.get("", response_model=list[str])
async def list_installed_repos() -> list[str]:
    """Return all repos where Everpilot is installed."""
    return list(_repo_configs.keys())


@router.post("", response_model=RepoConfigResponse, status_code=status.HTTP_201_CREATED)
async def install_repo(body: InstallRepoRequest) -> RepoConfigResponse:
    """Install Everpilot on a repository (all capabilities start as OFF)."""
    if body.repo_full_name in _repo_configs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Everpilot already installed on {body.repo_full_name}",
        )
    config = RepoConfig(
        repo_full_name=body.repo_full_name,
        capabilities=list(DEFAULT_CAPABILITIES),
    )
    _repo_configs[body.repo_full_name] = config
    return RepoConfigResponse(**config.model_dump())


@router.get("/{owner}/{repo}", response_model=RepoConfigResponse)
async def get_repo_config(owner: str, repo: str) -> RepoConfigResponse:
    """Retrieve the Everpilot configuration for a specific repo."""
    full_name = f"{owner}/{repo}"
    config = _repo_configs.get(full_name)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )
    return RepoConfigResponse(**config.model_dump())


@router.patch("/{owner}/{repo}/capabilities", response_model=RepoConfigResponse)
async def update_capability(
    owner: str, repo: str, body: UpdateCapabilityRequest
) -> RepoConfigResponse:
    """Toggle or reconfigure a single capability for a repo."""
    full_name = f"{owner}/{repo}"
    config = _repo_configs.get(full_name)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )

    updated = []
    for cap_cfg in config.capabilities:
        if cap_cfg.capability == body.capability:
            updated.append(
                CapabilityConfig(capability=body.capability, mode=body.mode, enabled=body.enabled)
            )
        else:
            updated.append(cap_cfg)

    config.capabilities = updated
    _repo_configs[full_name] = config
    return RepoConfigResponse(**config.model_dump())


@router.delete("/{owner}/{repo}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_repo(owner: str, repo: str) -> None:
    """Uninstall Everpilot from a repository."""
    full_name = f"{owner}/{repo}"
    if full_name not in _repo_configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )
    del _repo_configs[full_name]
