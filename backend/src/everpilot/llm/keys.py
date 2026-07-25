"""Anthropic API key management (locked decisions, 2026-07-25).

Two kinds of key:
- The **platform key**, set by Silvexis administrators through the admin API.
  Customer usage on this key is billed at cost plus a 20% uplift (pricing.py).
- **BYOK**: an organization brings its own key and pays no LLM costs through
  Everpilot.

Resolution order for a task: the org's own key if present, else the platform
key. Keys live in SSM SecureStrings under the standard config path — the
platform key uses the same parameter the deployment prereqs already declare
(/cz/{feature}/{ns}/anthropic-api-key), so admin-set and deploy-provisioned
keys are one mechanism, not two.
"""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class KeySource(StrEnum):
    PLATFORM = "platform"  # billed with uplift
    BYOK = "byok"  # customer's key; no LLM cost pass-through


@dataclass(frozen=True)
class ResolvedKey:
    # repr=False: this object travels through the task pipeline; its default
    # repr must never print the key into logs or exception tracebacks.
    api_key: str = field(repr=False)
    source: KeySource


class LlmKeyStore(Protocol):
    async def get_platform_key(self) -> str | None: ...

    async def set_platform_key(self, api_key: str) -> None: ...

    async def get_org_key(self, organization_id: int) -> str | None: ...

    async def set_org_key(self, organization_id: int, api_key: str) -> None: ...

    async def delete_org_key(self, organization_id: int) -> bool: ...


async def resolve_llm_key(store: LlmKeyStore, organization_id: int | None) -> ResolvedKey | None:
    """The key a task for this org should use: BYOK first, else platform.

    A blank stored value counts as absent, so the admin API's BYOK-presence
    report and this resolution agree on what "configured" means.
    """
    if organization_id is not None:
        org_key = await store.get_org_key(organization_id)
        if org_key:
            return ResolvedKey(api_key=org_key, source=KeySource.BYOK)
    platform_key = await store.get_platform_key()
    if platform_key:
        return ResolvedKey(api_key=platform_key, source=KeySource.PLATFORM)
    return None


class InMemoryLlmKeyStore:
    """Dev/test double."""

    def __init__(self, platform_key: str | None = None) -> None:
        self._platform_key = platform_key
        self._org_keys: dict[int, str] = {}

    async def get_platform_key(self) -> str | None:
        return self._platform_key

    async def set_platform_key(self, api_key: str) -> None:
        self._platform_key = api_key

    async def get_org_key(self, organization_id: int) -> str | None:
        return self._org_keys.get(organization_id)

    async def set_org_key(self, organization_id: int, api_key: str) -> None:
        self._org_keys[organization_id] = api_key

    async def delete_org_key(self, organization_id: int) -> bool:
        return self._org_keys.pop(organization_id, None) is not None


class SsmLlmKeyStore:
    """SSM SecureString-backed store, path scheme per infra-ssm-parameters.

    boto3 is synchronous, so every call is offloaded with asyncio.to_thread to
    keep the event loop free — resolve() is the per-task hot path in M1.
    """

    def __init__(self, feature: str, namespace: str) -> None:
        self._prefix = f"/cz/{feature}/{namespace}"
        self._cached_client = None

    def _client(self):
        if self._cached_client is None:
            import boto3  # deployments only (aws extra)

            self._cached_client = boto3.client("ssm")
        return self._cached_client

    def _platform_path(self) -> str:
        return f"{self._prefix}/anthropic-api-key"

    def _org_path(self, organization_id: int) -> str:
        return f"{self._prefix}/org-keys/{organization_id}/anthropic-api-key"

    async def get_platform_key(self) -> str | None:
        return await asyncio.to_thread(self._get, self._platform_path())

    async def set_platform_key(self, api_key: str) -> None:
        await asyncio.to_thread(self._put, self._platform_path(), api_key)

    async def get_org_key(self, organization_id: int) -> str | None:
        return await asyncio.to_thread(self._get, self._org_path(organization_id))

    async def set_org_key(self, organization_id: int, api_key: str) -> None:
        await asyncio.to_thread(self._put, self._org_path(organization_id), api_key)

    async def delete_org_key(self, organization_id: int) -> bool:
        return await asyncio.to_thread(self._delete, self._org_path(organization_id))

    def _get(self, path: str) -> str | None:
        client = self._client()
        try:
            response = client.get_parameter(Name=path, WithDecryption=True)
        except client.exceptions.ParameterNotFound:
            return None
        return response["Parameter"]["Value"]

    def _put(self, path: str, value: str) -> None:
        self._client().put_parameter(Name=path, Value=value, Type="SecureString", Overwrite=True)

    def _delete(self, path: str) -> bool:
        client = self._client()
        try:
            client.delete_parameter(Name=path)
            return True
        except client.exceptions.ParameterNotFound:
            return False


def mask_key(api_key: str) -> str:
    """Display form: never reveal enough of a key to reconstruct it.

    Shows at most the first 6 and last 4 characters, and only when that leaves
    a genuine gap — short keys are fully hidden so overlapping slices can't
    echo the whole secret.
    """
    if len(api_key) <= 14:  # 6 + 4 shown must leave >=4 hidden
        return "****"
    return f"{api_key[:6]}…{api_key[-4:]}"
