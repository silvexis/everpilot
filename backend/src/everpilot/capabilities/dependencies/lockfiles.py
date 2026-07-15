"""Lockfile parsing: exact pinned versions from uv.lock and package-lock.json."""

import json
import tomllib
from enum import StrEnum

from pydantic import BaseModel


class Ecosystem(StrEnum):
    """Values match OSV.dev ecosystem identifiers."""

    PYPI = "PyPI"
    NPM = "npm"


class PinnedDependency(BaseModel):
    name: str
    version: str
    ecosystem: Ecosystem


def parse_uv_lock(content: str, *, project_name: str | None = None) -> list[PinnedDependency]:
    """Parse uv.lock (TOML, schema v1). Excludes the project's own package."""
    data = tomllib.loads(content)
    dependencies = []
    for package in data.get("package", []):
        name = package.get("name", "")
        version = package.get("version", "")
        if not name or not version or name == project_name:
            continue
        # The project itself has a non-registry source (editable/virtual)
        source = package.get("source", {})
        if source.get("editable") is not None or source.get("virtual") is not None:
            continue
        dependencies.append(PinnedDependency(name=name, version=version, ecosystem=Ecosystem.PYPI))
    return dependencies


def parse_package_lock(content: str) -> list[PinnedDependency]:
    """Parse package-lock.json (lockfileVersion 2/3 `packages` map)."""
    data = json.loads(content)
    dependencies = []
    for path, info in data.get("packages", {}).items():
        if not path.startswith("node_modules/"):
            continue  # "" is the root project; nested paths carry the real deps
        name = path.rsplit("node_modules/", 1)[-1]
        version = info.get("version", "")
        if not version:
            continue
        dependencies.append(PinnedDependency(name=name, version=version, ecosystem=Ecosystem.NPM))
    return dependencies
