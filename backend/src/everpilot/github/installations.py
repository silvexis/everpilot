"""Translate GitHub App installation webhook events into tenant state."""

import logging

from everpilot.db.installations import InstallationStore
from everpilot.models.core import Installation, Organization, Repository

logger = logging.getLogger(__name__)


def _parse_repository(data: dict, installation_db_id: int = 0) -> Repository:  # type: ignore[type-arg]
    return Repository(
        github_repo_id=data["id"],
        installation_id=installation_db_id,
        full_name=data["full_name"],
        private=data.get("private", True),
        default_branch=data.get("default_branch", "main"),
    )


class InstallationService:
    """Handles `installation` and `installation_repositories` webhook events."""

    def __init__(self, store: InstallationStore) -> None:
        self._store = store

    async def handle_installation(self, payload: dict) -> None:  # type: ignore[type-arg]
        action = payload.get("action")
        installation_data = payload.get("installation") or {}
        github_installation_id = installation_data.get("id")
        if github_installation_id is None:
            logger.warning("installation event without installation.id — ignored")
            return

        match action:
            case "created":
                account = installation_data.get("account") or {}
                org_id = await self._store.upsert_organization(
                    Organization(
                        github_org_id=account.get("id", 0),
                        login=account.get("login", ""),
                        name=account.get("name"),
                    )
                )
                installation_db_id = await self._store.create_installation(
                    Installation(
                        github_installation_id=github_installation_id,
                        organization_id=org_id,
                    )
                )
                repositories = [
                    _parse_repository(r, installation_db_id)
                    for r in payload.get("repositories", [])
                ]
                await self._store.add_repositories(installation_db_id, repositories)
                logger.info(
                    "Installation %s created for %s with %d repos",
                    github_installation_id,
                    account.get("login"),
                    len(repositories),
                )
            case "deleted":
                removed = await self._store.delete_installation(github_installation_id)
                logger.info("Installation %s deleted (found=%s)", github_installation_id, removed)
            case "suspend":
                await self._store.set_suspended(github_installation_id, True)
                logger.info("Installation %s suspended", github_installation_id)
            case "unsuspend":
                await self._store.set_suspended(github_installation_id, False)
                logger.info("Installation %s unsuspended", github_installation_id)
            case _:
                logger.debug("Unhandled installation action: %s", action)

    async def handle_installation_repositories(self, payload: dict) -> None:  # type: ignore[type-arg]
        installation_data = payload.get("installation") or {}
        github_installation_id = installation_data.get("id")
        if github_installation_id is None:
            logger.warning("installation_repositories event without installation.id — ignored")
            return

        installation = await self._store.get_installation(github_installation_id)
        if installation is None or installation.id is None:
            logger.warning(
                "installation_repositories for unknown installation %s — ignored",
                github_installation_id,
            )
            return

        added = [
            _parse_repository(r, installation.id) for r in payload.get("repositories_added", [])
        ]
        if added:
            await self._store.add_repositories(installation.id, added)
        removed_ids = [r["id"] for r in payload.get("repositories_removed", [])]
        if removed_ids:
            await self._store.remove_repositories(removed_ids)
        logger.info(
            "Installation %s repositories updated: +%d/-%d",
            github_installation_id,
            len(added),
            len(removed_ids),
        )
