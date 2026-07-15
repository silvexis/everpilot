"""GitHub App authentication via githubkit.

githubkit's auth strategies handle JWT signing and installation-token
acquisition/refresh internally; this factory just binds our app credentials.
"""

from githubkit import AppAuthStrategy, AppInstallationAuthStrategy, GitHub


class GitHubAppClients:
    """Builds authenticated GitHub clients for app-level and per-installation calls."""

    def __init__(self, app_id: str, private_key: str) -> None:
        if not app_id or not private_key:
            raise ValueError("GitHub App id and private key are required")
        self._app_id = app_id
        self._private_key = private_key

    def app(self) -> GitHub:
        """Client authenticated as the App itself (JWT) — manage installations, app metadata."""
        return GitHub(AppAuthStrategy(app_id=self._app_id, private_key=self._private_key))

    def installation(self, installation_id: int) -> GitHub:
        """Client authenticated as one installation — repo contents, PRs, issues, checks."""
        return GitHub(
            AppInstallationAuthStrategy(
                app_id=self._app_id,
                private_key=self._private_key,
                installation_id=installation_id,
            )
        )
