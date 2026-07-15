"""Version comparison per ecosystem: PEP 440 for PyPI, semver for npm."""

import logging

from packaging.version import InvalidVersion, Version
from semantic_version import Version as SemVersion

from everpilot.capabilities.dependencies.lockfiles import Ecosystem

logger = logging.getLogger(__name__)


def is_outdated(ecosystem: Ecosystem, current: str, latest: str) -> bool:
    """True if `latest` is newer than `current`. Unparseable versions are never outdated."""
    try:
        if ecosystem == Ecosystem.PYPI:
            return Version(latest) > Version(current)
        return SemVersion.coerce(latest) > SemVersion.coerce(current)
    except (InvalidVersion, ValueError) as exc:
        logger.warning("Cannot compare %s: %s vs %s (%s)", ecosystem, current, latest, exc)
        return False


def bump_kind(ecosystem: Ecosystem, current: str, latest: str) -> str:
    """'major' | 'minor' | 'patch' — drives the roadmap batching strategy."""
    try:
        if ecosystem == Ecosystem.PYPI:
            current_release, latest_release = Version(current).release, Version(latest).release
            current_parts = (*current_release, 0, 0)[:3]
            latest_parts = (*latest_release, 0, 0)[:3]
        else:
            c, latest_sem = SemVersion.coerce(current), SemVersion.coerce(latest)
            current_parts = (c.major, c.minor, c.patch)
            latest_parts = (latest_sem.major, latest_sem.minor, latest_sem.patch)
    except (InvalidVersion, ValueError):
        return "major"  # unknown = treat with maximum caution

    if latest_parts[0] != current_parts[0]:
        return "major"
    if latest_parts[1] != current_parts[1]:
        return "minor"
    return "patch"
