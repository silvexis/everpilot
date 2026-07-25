"""LLM key management: resolution order, uplift billing, admin API guard. No AWS calls."""

import sys
import types

import pytest
from fastapi.testclient import TestClient

from everpilot.config import get_settings
from everpilot.llm import (
    InMemoryLlmKeyStore,
    KeySource,
    ResolvedKey,
    SsmLlmKeyStore,
    billable_llm_cost,
    resolve_llm_key,
)
from everpilot.llm.keys import mask_key
from everpilot.main import create_app

# --- Resolution order ---


async def test_byok_wins_over_platform() -> None:
    store = InMemoryLlmKeyStore(platform_key="sk-ant-platform")
    await store.set_org_key(7, "sk-ant-customer")
    resolved = await resolve_llm_key(store, 7)
    assert resolved is not None
    assert resolved.source == KeySource.BYOK
    assert resolved.api_key == "sk-ant-customer"


async def test_platform_fallback_without_byok() -> None:
    store = InMemoryLlmKeyStore(platform_key="sk-ant-platform")
    resolved = await resolve_llm_key(store, 7)
    assert resolved is not None
    assert resolved.source == KeySource.PLATFORM


async def test_no_keys_resolves_none() -> None:
    assert await resolve_llm_key(InMemoryLlmKeyStore(), 7) is None


async def test_deleted_byok_falls_back_to_platform() -> None:
    store = InMemoryLlmKeyStore(platform_key="sk-ant-platform")
    await store.set_org_key(7, "sk-ant-customer")
    assert await store.delete_org_key(7) is True
    resolved = await resolve_llm_key(store, 7)
    assert resolved is not None and resolved.source == KeySource.PLATFORM


async def test_blank_org_key_falls_through_to_platform() -> None:
    store = InMemoryLlmKeyStore(platform_key="sk-ant-platform")
    await store.set_org_key(7, "")  # blank counts as absent
    resolved = await resolve_llm_key(store, 7)
    assert resolved is not None and resolved.source == KeySource.PLATFORM


def test_resolved_key_repr_hides_api_key() -> None:
    resolved = ResolvedKey(api_key="sk-ant-supersecret", source=KeySource.PLATFORM)
    assert "supersecret" not in repr(resolved)


# --- Uplift billing ---


@pytest.mark.parametrize(
    ("raw_cents", "expected"),
    [(100, 120), (0, 0), (1, 1), (5, 6), (333, 400)],  # 333*1.2=399.6 → 400 (half-up)
)
def test_platform_uplift_20_percent(raw_cents: int, expected: int) -> None:
    assert billable_llm_cost(raw_cents, KeySource.PLATFORM) == expected


def test_byok_bills_zero_regardless_of_usage() -> None:
    assert billable_llm_cost(10_000, KeySource.BYOK) == 0


def test_negative_cost_rejected() -> None:
    with pytest.raises(ValueError):
        billable_llm_cost(-1, KeySource.PLATFORM)


@pytest.mark.parametrize("length", range(1, 30))
def test_mask_never_reconstructs_key(length: int) -> None:
    key = "".join(chr(ord("a") + i % 26) for i in range(length))
    masked = mask_key(key)
    # The masked form must never let you reconstruct the original: either fully
    # hidden, or shown chars leave a genuine hidden gap.
    if masked == "****":
        return
    shown = masked.replace("…", "")
    assert len(shown) < len(key)  # strictly fewer chars than the key
    assert key not in masked


def test_mask_short_key_fully_hidden() -> None:
    assert mask_key("sk-ant-short") == "****"  # 12 chars → hidden
    assert mask_key("short") == "****"


# --- SSM store (fake boto3) ---


def fake_ssm_module(parameters: dict[str, str]) -> types.ModuleType:
    # Arg/class names mirror boto3's PascalCase API — naming lints don't apply
    class ParameterNotFound(Exception):  # noqa: N818
        pass

    class Exceptions:
        pass

    Exceptions.ParameterNotFound = ParameterNotFound

    class FakeClient:
        exceptions = Exceptions

        def get_parameter(self, Name, WithDecryption):  # noqa: N803
            if Name not in parameters:
                raise ParameterNotFound()
            return {"Parameter": {"Value": parameters[Name]}}

        def put_parameter(self, Name, Value, Type, Overwrite):  # noqa: N803
            assert Type == "SecureString"
            parameters[Name] = Value

        def delete_parameter(self, Name):  # noqa: N803
            if Name not in parameters:
                raise ParameterNotFound()
            del parameters[Name]

    module = types.ModuleType("boto3")
    module.client = lambda service: FakeClient()
    return module


async def test_ssm_store_paths_and_roundtrip(monkeypatch) -> None:
    parameters: dict[str, str] = {}
    monkeypatch.setitem(sys.modules, "boto3", fake_ssm_module(parameters))
    store = SsmLlmKeyStore("everpilot", "alfa")

    await store.set_platform_key("sk-ant-platform")
    assert parameters["/cz/everpilot/alfa/anthropic-api-key"] == "sk-ant-platform"

    await store.set_org_key(7, "sk-ant-org")
    assert parameters["/cz/everpilot/alfa/org-keys/7/anthropic-api-key"] == "sk-ant-org"

    resolved = await resolve_llm_key(store, 7)
    assert resolved is not None and resolved.source == KeySource.BYOK
    assert await store.delete_org_key(7) is True
    assert await store.delete_org_key(7) is False


# --- Admin API ---


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def admin_client(monkeypatch, token: str | None) -> TestClient:
    # Full env isolation: an ambient ANTHROPIC_API_KEY / EVERPILOT_SSM_CONFIG
    # (common on dev machines, and Erik will add the former) must not seed the
    # store or route to real SSM. Env vars beat any .env value in precedence.
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ADMIN_TOKEN", token or "")
    app = create_app()
    # Deterministic empty store regardless of any .env seeding
    app.state.llm_key_store = InMemoryLlmKeyStore()
    return TestClient(app)


def test_admin_api_disabled_without_token(monkeypatch) -> None:
    client = admin_client(monkeypatch, None)
    response = client.get("/api/v1/admin/llm-key", headers={"X-Admin-Token": "anything"})
    assert response.status_code == 503


def test_admin_api_rejects_wrong_token(monkeypatch) -> None:
    client = admin_client(monkeypatch, "correct-token")
    response = client.get("/api/v1/admin/llm-key", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 401
    assert client.get("/api/v1/admin/llm-key").status_code == 401  # missing header


def test_admin_guard_non_ascii_token_raises_401_not_typeerror(monkeypatch) -> None:
    # Starlette decodes header bytes as latin-1, so require_admin can receive a
    # non-ASCII str; hmac.compare_digest on non-ASCII *str* would raise
    # TypeError (→500). The guard must encode to bytes and cleanly 401.
    from fastapi import HTTPException

    from everpilot.api.admin import require_admin

    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "")
    with pytest.raises(HTTPException) as exc:
        require_admin(x_admin_token="café-tøken")
    assert exc.value.status_code == 401


def test_admin_surface_absent_from_openapi(monkeypatch) -> None:
    # Debug on so the schema is served at all; admin routes must still be hidden
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    monkeypatch.setenv("EVERPILOT_SSM_CONFIG", "")
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    assert not any("/admin/" in path for path in schema["paths"])


def test_admin_can_set_and_inspect_platform_key(monkeypatch) -> None:
    client = admin_client(monkeypatch, "correct-token")
    headers = {"X-Admin-Token": "correct-token"}

    status = client.get("/api/v1/admin/llm-key", headers=headers).json()
    assert status == {"configured": False, "masked_key": None}

    response = client.put(
        "/api/v1/admin/llm-key",
        headers=headers,
        json={"api_key": "sk-ant-api03-abcdefghijkl"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert "abcdefgh" not in (body["masked_key"] or "")

    status = client.get("/api/v1/admin/llm-key", headers=headers).json()
    assert status["configured"] is True


def test_admin_byok_lifecycle(monkeypatch) -> None:
    client = admin_client(monkeypatch, "correct-token")
    headers = {"X-Admin-Token": "correct-token"}

    assert client.get("/api/v1/admin/orgs/7/llm-key", headers=headers).json()["byok"] is False
    response = client.put(
        "/api/v1/admin/orgs/7/llm-key",
        headers=headers,
        json={"api_key": "sk-ant-api03-customerkey00"},
    )
    assert response.json()["byok"] is True
    assert client.delete("/api/v1/admin/orgs/7/llm-key", headers=headers).status_code == 204
    assert client.delete("/api/v1/admin/orgs/7/llm-key", headers=headers).status_code == 404


def test_short_key_rejected_without_echoing_it(monkeypatch) -> None:
    client = admin_client(monkeypatch, "correct-token")
    secret = "too-short-secret"  # < 20 chars
    response = client.put(
        "/api/v1/admin/llm-key",
        headers={"X-Admin-Token": "correct-token"},
        json={"api_key": secret},
    )
    assert response.status_code == 422
    assert secret not in response.text  # the raw key must not be echoed back
