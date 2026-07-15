"""Rollback: revert-PR service (stubbed GraphQL) and the /tasks/{id}/rollback route."""

import pytest
from fastapi.testclient import TestClient

from everpilot.github.auth import GitHubAppClients
from everpilot.github.rollback import RollbackError, RollbackService
from everpilot.models.capability import Capability, CapabilityMode
from everpilot.models.core import Installation, Repository, TaskState
from everpilot.pipeline import TaskPipeline


class StubGraphQLGitHub:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def async_graphql(self, query: str, variables: dict) -> dict:
        self.calls.append((query, variables))
        return self._responses.pop(0)


class StubClients(GitHubAppClients):
    def __init__(self, github: StubGraphQLGitHub) -> None:
        super().__init__("12345", "fake-key")
        self._github = github

    def installation(self, installation_id: int):  # type: ignore[override]
        return self._github


PR_ID_RESPONSE = {"repository": {"pullRequest": {"id": "PR_node123"}}}
REVERT_RESPONSE = {"revertPullRequest": {"revertPullRequest": {"number": 99, "url": "…"}}}


# --- Service ---


async def test_revert_pr_happy_path() -> None:
    github = StubGraphQLGitHub([PR_ID_RESPONSE, REVERT_RESPONSE])
    service = RollbackService(StubClients(github))
    number = await service.revert_pr(
        github_installation_id=5555,
        repo_full_name="silvexis/alpha",
        pr_number=7,
        reason="broke prod",
    )
    assert number == 99
    _, mutation_vars = github.calls[1]
    assert mutation_vars["input"]["pullRequestId"] == "PR_node123"
    assert "broke prod" in mutation_vars["input"]["body"]


async def test_revert_pr_not_found() -> None:
    github = StubGraphQLGitHub([{"repository": {"pullRequest": None}}])
    service = RollbackService(StubClients(github))
    with pytest.raises(RollbackError, match="not found"):
        await service.revert_pr(
            github_installation_id=5555,
            repo_full_name="silvexis/alpha",
            pr_number=7,
            reason="x",
        )


async def test_revert_pr_no_revert_returned() -> None:
    github = StubGraphQLGitHub([PR_ID_RESPONSE, {"revertPullRequest": None}])
    service = RollbackService(StubClients(github))
    with pytest.raises(RollbackError, match="did not return"):
        await service.revert_pr(
            github_installation_id=5555,
            repo_full_name="silvexis/alpha",
            pr_number=7,
            reason="x",
        )


# --- Route ---


@pytest.fixture
async def merged_app(app):
    """App with tenant state and one merged task with a PR."""
    store = app.state.installation_store
    org_id = await store.upsert_organization(
        __import__("everpilot.models.core", fromlist=["Organization"]).Organization(
            github_org_id=777, login="silvexis"
        )
    )
    installation_db_id = await store.create_installation(
        Installation(github_installation_id=5555, organization_id=org_id)
    )
    await store.add_repositories(
        installation_db_id,
        [Repository(github_repo_id=101, installation_id=0, full_name="silvexis/alpha")],
    )
    repo = next(iter(store._repositories.values()))

    pipeline = TaskPipeline(app.state.task_store, app.state.audit_store)
    task = await pipeline.submit(
        repository_id=repo.id,
        capability=Capability.DEPENDENCIES,
        mode=CapabilityMode.ASSISTED,
        enabled=True,
        trigger="schedule",
        title="Bump httpx",
    )
    for state in (TaskState.QUEUED, TaskState.PLANNING, TaskState.EXECUTING):
        await pipeline.advance(task.id, state)
    await pipeline.open_pr(task.id, pr_number=7)
    await pipeline.resolve_human_review(task.id, approved=True, actor="erik")

    github = StubGraphQLGitHub([PR_ID_RESPONSE, REVERT_RESPONSE])
    app.state.rollback_service = RollbackService(StubClients(github))
    return app


def test_rollback_route_success(merged_app) -> None:
    client = TestClient(merged_app)
    response = client.post("/api/v1/tasks/1/rollback", json={"reason": "bad deploy"})
    assert response.status_code == 200
    assert response.json() == {"revert_pr_number": 99}
    audit = client.get("/api/v1/tasks/1/audit").json()
    assert audit[-1]["event_type"] == "task.rolled_back"
    assert audit[-1]["payload"] == {"reverted_pr": 7, "revert_pr": 99}


def test_rollback_unknown_task_404(merged_app) -> None:
    assert TestClient(merged_app).post("/api/v1/tasks/99/rollback", json={}).status_code == 404


async def test_rollback_unmerged_task_409(app) -> None:
    pipeline = TaskPipeline(app.state.task_store, app.state.audit_store)
    await pipeline.submit(
        repository_id=1,
        capability=Capability.DEPENDENCIES,
        mode=CapabilityMode.ASSISTED,
        enabled=True,
        trigger="schedule",
        title="Bump httpx",
    )
    client = TestClient(app)
    assert client.post("/api/v1/tasks/1/rollback", json={}).status_code == 409


def test_rollback_without_github_credentials_503(merged_app) -> None:
    merged_app.state.rollback_service = None
    client = TestClient(merged_app)
    assert client.post("/api/v1/tasks/1/rollback", json={}).status_code == 503
