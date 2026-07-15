from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from everpilot.db import RepoConfigStore
from everpilot.models.capability import (
    DEFAULT_CAPABILITIES,
    Capability,
    CapabilityConfig,
    CapabilityMode,
)
from everpilot.models.repo import RepoConfig

router = APIRouter(prefix="/repos", tags=["repos"])


def get_repo_store(request: Request) -> RepoConfigStore:
    return request.app.state.repo_store


StoreDep = Annotated[RepoConfigStore, Depends(get_repo_store)]


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
async def list_installed_repos(store: StoreDep) -> list[str]:
    """Return all repos where Everpilot is installed."""
    return await store.list_repo_names()


@router.post("", response_model=RepoConfigResponse, status_code=status.HTTP_201_CREATED)
async def install_repo(body: InstallRepoRequest, store: StoreDep) -> RepoConfigResponse:
    """Install Everpilot on a repository (all capabilities start as OFF)."""
    config = RepoConfig(
        repo_full_name=body.repo_full_name,
        capabilities=list(DEFAULT_CAPABILITIES),
    )
    created = await store.create(config)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Everpilot already installed on {body.repo_full_name}",
        )
    return RepoConfigResponse(**config.model_dump())


@router.get("/{owner}/{repo}", response_model=RepoConfigResponse)
async def get_repo_config(owner: str, repo: str, store: StoreDep) -> RepoConfigResponse:
    """Retrieve the Everpilot configuration for a specific repo."""
    full_name = f"{owner}/{repo}"
    config = await store.get(full_name)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )
    return RepoConfigResponse(**config.model_dump())


@router.patch("/{owner}/{repo}/capabilities", response_model=RepoConfigResponse)
async def update_capability(
    owner: str, repo: str, body: UpdateCapabilityRequest, store: StoreDep
) -> RepoConfigResponse:
    """Toggle or reconfigure a single capability for a repo."""
    full_name = f"{owner}/{repo}"
    config = await store.set_capability(
        full_name,
        CapabilityConfig(capability=body.capability, mode=body.mode, enabled=body.enabled),
    )
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )
    return RepoConfigResponse(**config.model_dump())


@router.delete("/{owner}/{repo}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_repo(owner: str, repo: str, store: StoreDep) -> None:
    """Uninstall Everpilot from a repository."""
    full_name = f"{owner}/{repo}"
    deleted = await store.delete(full_name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Everpilot not installed on {full_name}",
        )
