"""GitHubAppClients factory — credential binding, no network calls."""

import pytest
from githubkit import AppAuthStrategy, AppInstallationAuthStrategy

from everpilot.github import GitHubAppClients

# Throwaway RSA key material is not needed: strategies bind credentials lazily,
# so a placeholder string exercises the wiring without signing anything.
APP_ID = "12345"
PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nplaceholder\n-----END RSA PRIVATE KEY-----"


def test_requires_credentials() -> None:
    with pytest.raises(ValueError):
        GitHubAppClients("", PRIVATE_KEY)
    with pytest.raises(ValueError):
        GitHubAppClients(APP_ID, "")


def test_app_client_uses_app_auth() -> None:
    clients = GitHubAppClients(APP_ID, PRIVATE_KEY)
    github = clients.app()
    assert isinstance(github.auth, AppAuthStrategy)
    assert github.auth.app_id == APP_ID


def test_installation_client_binds_installation_id() -> None:
    clients = GitHubAppClients(APP_ID, PRIVATE_KEY)
    github = clients.installation(9876)
    assert isinstance(github.auth, AppInstallationAuthStrategy)
    assert github.auth.installation_id == 9876
