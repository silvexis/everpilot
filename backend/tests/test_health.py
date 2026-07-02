from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_schema(client: TestClient) -> None:
    data = client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "everpilot"
    assert "version" in data


def test_health_version_matches_package(client: TestClient) -> None:
    from everpilot import __version__

    data = client.get("/api/v1/health").json()
    assert data["version"] == __version__
