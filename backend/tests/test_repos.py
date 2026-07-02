import pytest
from fastapi.testclient import TestClient

REPO = "silvexis/test-repo"
OWNER, REPO_NAME = REPO.split("/")


@pytest.fixture(autouse=True)
def reset_repo_store():
    """Clear the in-memory store between tests."""
    from everpilot.api import repos as repos_module
    repos_module._repo_configs.clear()
    yield
    repos_module._repo_configs.clear()


def test_list_repos_empty(client: TestClient) -> None:
    response = client.get("/api/v1/repos")
    assert response.status_code == 200
    assert response.json() == []


def test_install_repo(client: TestClient) -> None:
    response = client.post("/api/v1/repos", json={"repo_full_name": REPO})
    assert response.status_code == 201
    data = response.json()
    assert data["repo_full_name"] == REPO
    assert data["active"] is True
    assert len(data["capabilities"]) == 5  # all five capabilities
    # All should be OFF by default
    assert all(c["mode"] == "off" for c in data["capabilities"])


def test_install_repo_conflict(client: TestClient) -> None:
    client.post("/api/v1/repos", json={"repo_full_name": REPO})
    response = client.post("/api/v1/repos", json={"repo_full_name": REPO})
    assert response.status_code == 409


def test_get_repo_config(client: TestClient) -> None:
    client.post("/api/v1/repos", json={"repo_full_name": REPO})
    response = client.get(f"/api/v1/repos/{OWNER}/{REPO_NAME}")
    assert response.status_code == 200
    assert response.json()["repo_full_name"] == REPO


def test_get_repo_config_not_found(client: TestClient) -> None:
    response = client.get(f"/api/v1/repos/{OWNER}/nonexistent")
    assert response.status_code == 404


def test_update_capability_mode(client: TestClient) -> None:
    client.post("/api/v1/repos", json={"repo_full_name": REPO})
    response = client.patch(
        f"/api/v1/repos/{OWNER}/{REPO_NAME}/capabilities",
        json={"capability": "security", "mode": "autopilot", "enabled": True},
    )
    assert response.status_code == 200
    data = response.json()
    security = next(c for c in data["capabilities"] if c["capability"] == "security")
    assert security["mode"] == "autopilot"
    assert security["enabled"] is True


def test_update_capability_not_found(client: TestClient) -> None:
    response = client.patch(
        f"/api/v1/repos/{OWNER}/nonexistent/capabilities",
        json={"capability": "security", "mode": "autopilot", "enabled": True},
    )
    assert response.status_code == 404


def test_uninstall_repo(client: TestClient) -> None:
    client.post("/api/v1/repos", json={"repo_full_name": REPO})
    response = client.delete(f"/api/v1/repos/{OWNER}/{REPO_NAME}")
    assert response.status_code == 204


def test_uninstall_repo_not_found(client: TestClient) -> None:
    response = client.delete(f"/api/v1/repos/{OWNER}/nonexistent")
    assert response.status_code == 404


def test_list_repos_after_install(client: TestClient) -> None:
    client.post("/api/v1/repos", json={"repo_full_name": REPO})
    response = client.get("/api/v1/repos")
    assert REPO in response.json()
