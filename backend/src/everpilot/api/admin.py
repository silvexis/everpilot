"""Silvexis-administrator endpoints (platform LLM key management).

INTERIM AUTH: guarded by a shared admin token (SSM SecureString `admin-token`)
compared in constant time. Fails closed — if no token is configured the
endpoints return 503. The real gate is Silvexis-employee SSO, which lands with
M4's WorkOS integration (docs/open_questions.md); the admin *frontend* page is
deliberately deferred until then.

OPERATIONAL WARNING: because the whole API is pre-auth until M4 and served on an
internet-facing ALB, do NOT set an admin token until the ALB has TLS (a cert),
and prefer restricting these paths to Silvexis network ranges. The token is
read from cached settings, so rotation takes effect on the next restart.

`include_in_schema=False` keeps the admin surface out of /openapi.json so it
isn't enumerable pre-auth.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, SecretStr

from everpilot.api.deps import LlmKeyStoreDep
from everpilot.config import get_settings
from everpilot.llm.keys import mask_key

router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)

_MIN_KEY_LEN = 20  # real Anthropic keys are ~100 chars; reject obvious mistakes


def require_admin(x_admin_token: str = Header("")) -> None:
    admin_token = get_settings().admin_token
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API disabled: no admin token configured",
        )
    # Compare bytes: hmac.compare_digest raises TypeError on non-ASCII str,
    # and header values can carry non-ASCII (latin-1) bytes.
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode("utf-8", "ignore"), admin_token.encode("utf-8", "ignore")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


AdminDep = Annotated[None, Depends(require_admin)]


class SetKeyRequest(BaseModel):
    # SecretStr so the raw value never lands in logs, reprs, or 422 error bodies
    api_key: SecretStr


def _validated_key(body: SetKeyRequest) -> str:
    key = body.api_key.get_secret_value()
    if len(key) < _MIN_KEY_LEN:
        # Manual check (not a pydantic constraint) so the raw value is never
        # echoed back in a 422 validation error.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="api_key too short"
        )
    return key


class KeyStatusResponse(BaseModel):
    configured: bool
    masked_key: str | None = None


@router.get("/llm-key", response_model=KeyStatusResponse)
async def platform_key_status(_: AdminDep, store: LlmKeyStoreDep) -> KeyStatusResponse:
    """Whether a platform key is configured. Never returns the key itself."""
    key = await store.get_platform_key()
    return KeyStatusResponse(configured=bool(key), masked_key=mask_key(key) if key else None)


@router.put("/llm-key", response_model=KeyStatusResponse)
async def set_platform_key(
    body: SetKeyRequest, _: AdminDep, store: LlmKeyStoreDep
) -> KeyStatusResponse:
    """Set/rotate the platform Anthropic key (customer usage bills at cost +20%)."""
    key = _validated_key(body)
    await store.set_platform_key(key)
    return KeyStatusResponse(configured=True, masked_key=mask_key(key))


class OrgKeyStatusResponse(BaseModel):
    organization_id: int
    byok: bool
    masked_key: str | None = None


@router.get("/orgs/{organization_id}/llm-key", response_model=OrgKeyStatusResponse)
async def org_key_status(
    organization_id: int, _: AdminDep, store: LlmKeyStoreDep
) -> OrgKeyStatusResponse:
    key = await store.get_org_key(organization_id)
    return OrgKeyStatusResponse(
        organization_id=organization_id,
        byok=bool(key),  # blank counts as absent, matching resolve_llm_key
        masked_key=mask_key(key) if key else None,
    )


@router.put("/orgs/{organization_id}/llm-key", response_model=OrgKeyStatusResponse)
async def set_org_key(
    organization_id: int, body: SetKeyRequest, _: AdminDep, store: LlmKeyStoreDep
) -> OrgKeyStatusResponse:
    """BYOK: store an organization's own key (their tasks bill no LLM cost).

    Admin-set for now; customer self-service arrives with M4 auth.
    """
    key = _validated_key(body)
    await store.set_org_key(organization_id, key)
    return OrgKeyStatusResponse(
        organization_id=organization_id, byok=True, masked_key=mask_key(key)
    )


@router.delete("/orgs/{organization_id}/llm-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_key(organization_id: int, _: AdminDep, store: LlmKeyStoreDep) -> None:
    """Remove BYOK; the org falls back to the platform key (with uplift billing)."""
    if not await store.delete_org_key(organization_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {organization_id} has no BYOK key",
        )
