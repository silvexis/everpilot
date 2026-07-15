"""Task/audit read API for the dashboard."""

import pytest
from fastapi.testclient import TestClient

from everpilot.models.capability import Capability, CapabilityMode
from everpilot.pipeline import TaskPipeline


@pytest.fixture
async def seeded_app(app):
    """App with two tasks (one advanced to queued) created through the pipeline."""
    pipeline = TaskPipeline(app.state.task_store, app.state.audit_store)
    for title in ("Bump httpx", "Bump polars"):
        await pipeline.submit(
            repository_id=42,
            capability=Capability.DEPENDENCIES,
            mode=CapabilityMode.ASSISTED,
            enabled=True,
            trigger="schedule",
            title=title,
        )
    from everpilot.models.core import TaskState

    await pipeline.advance(1, TaskState.QUEUED)
    return app


@pytest.fixture
def seeded_client(seeded_app) -> TestClient:
    return TestClient(seeded_app)


def test_list_tasks_most_recent_first(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/v1/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert [t["id"] for t in tasks] == [2, 1]


def test_list_tasks_filters_by_state(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/v1/tasks", params={"state": "queued"})
    assert [t["id"] for t in response.json()] == [1]


def test_list_tasks_filters_by_repository(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/v1/tasks", params={"repository_id": 999})
    assert response.json() == []


def test_get_task(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/v1/tasks/1")
    assert response.status_code == 200
    assert response.json()["state"] == "queued"


def test_get_task_not_found(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/v1/tasks/99").status_code == 404


def test_task_audit_trail(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/v1/tasks/1/audit")
    assert response.status_code == 200
    events = response.json()
    assert [e["event_type"] for e in events] == ["task.created", "task.state_changed"]
    assert events[1]["payload"] == {"from": "triggered", "to": "queued"}


def test_task_audit_unknown_task_404(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/v1/tasks/99/audit").status_code == 404
