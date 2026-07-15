"""Webhook endpoint: signature enforcement, replay protection, dispatch."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from everpilot.config import get_settings
from everpilot.main import create_app

SECRET = "test-webhook-secret"
PAYLOAD = {"action": "opened", "repository": {"full_name": "silvexis/test-repo"}}
BODY = json.dumps(PAYLOAD).encode()


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def secured_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    return TestClient(create_app())


def post_webhook(client: TestClient, headers: dict[str, str]) -> object:
    return client.post(
        "/api/v1/webhooks/github",
        content=BODY,
        headers={"Content-Type": "application/json", **headers},
    )


def test_valid_signature_accepted(secured_client: TestClient) -> None:
    response = post_webhook(
        secured_client,
        {
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": sign(BODY),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "event": "pull_request", "duplicate": False}


def test_invalid_signature_rejected(secured_client: TestClient) -> None:
    response = post_webhook(
        secured_client,
        {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sign(BODY, "wrong-secret"),
        },
    )
    assert response.status_code == 401


def test_missing_signature_rejected_when_secret_configured(secured_client: TestClient) -> None:
    """Fail closed: no signature header must not bypass verification."""
    response = post_webhook(secured_client, {"X-GitHub-Event": "push"})
    assert response.status_code == 401


def test_no_secret_rejected_outside_development(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    client = TestClient(create_app())
    response = post_webhook(client, {"X-GitHub-Event": "push"})
    assert response.status_code == 503


def test_no_secret_accepted_in_development(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    client = TestClient(create_app())
    response = post_webhook(client, {"X-GitHub-Event": "push"})
    assert response.status_code == 200


def test_duplicate_delivery_ignored(secured_client: TestClient) -> None:
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "same-guid",
        "X-Hub-Signature-256": sign(BODY),
    }
    first = post_webhook(secured_client, headers)
    second = post_webhook(secured_client, headers)
    assert first.json()["accepted"] is True
    assert second.json() == {"accepted": False, "event": "push", "duplicate": True}


@pytest.mark.parametrize("event", ["push", "issues", "pull_request", "installation", "unknown"])
def test_event_types_dispatch(secured_client: TestClient, event: str) -> None:
    response = post_webhook(
        secured_client,
        {
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": f"delivery-{event}",
            "X-Hub-Signature-256": sign(BODY),
        },
    )
    assert response.status_code == 200
    assert response.json()["event"] == event
