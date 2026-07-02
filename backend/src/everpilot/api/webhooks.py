import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel

from everpilot.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookResponse(BaseModel):
    accepted: bool
    event: str


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate the GitHub X-Hub-Signature-256 header."""
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_event(event: str, payload: dict) -> None:  # type: ignore[type-arg]
    """Dispatch GitHub webhook events to the appropriate handler."""
    logger.info("Processing GitHub event: %s", event)

    match event:
        case "push":
            logger.debug("Push event on %s", payload.get("repository", {}).get("full_name"))
        case "issues":
            action = payload.get("action")
            logger.debug("Issue %s on %s", action, payload.get("repository", {}).get("full_name"))
        case "pull_request":
            action = payload.get("action")
            logger.debug("PR %s on %s", action, payload.get("repository", {}).get("full_name"))
        case "installation" | "installation_repositories":
            logger.info("App installation event: %s", payload.get("action"))
        case _:
            logger.debug("Unhandled event type: %s", event)


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(""),
) -> WebhookResponse:
    """Receive and verify GitHub webhook payloads."""
    settings = get_settings()
    body = await request.body()

    if settings.github_webhook_secret and x_hub_signature_256:
        if not _verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    payload = await request.json()
    background_tasks.add_task(_handle_event, x_github_event, payload)

    return WebhookResponse(accepted=True, event=x_github_event)
