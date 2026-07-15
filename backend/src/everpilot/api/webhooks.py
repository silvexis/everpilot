import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from everpilot.config import get_settings
from everpilot.db.deliveries import WebhookDeliveryStore
from everpilot.github.installations import InstallationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_delivery_store(request: Request) -> WebhookDeliveryStore:
    return request.app.state.webhook_deliveries


DeliveryStoreDep = Annotated[WebhookDeliveryStore, Depends(get_delivery_store)]


class WebhookResponse(BaseModel):
    accepted: bool
    event: str
    duplicate: bool = False


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate the GitHub X-Hub-Signature-256 header."""
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_event(
    event: str,
    payload: dict,  # type: ignore[type-arg]
    installations: InstallationService,
) -> None:
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
        case "installation":
            await installations.handle_installation(payload)
        case "installation_repositories":
            await installations.handle_installation_repositories(payload)
        case _:
            logger.debug("Unhandled event type: %s", event)


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    deliveries: DeliveryStoreDep,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(""),
    x_hub_signature_256: str = Header(""),
) -> WebhookResponse:
    """Receive, verify, and deduplicate GitHub webhook payloads."""
    settings = get_settings()
    body = await request.body()

    if settings.github_webhook_secret:
        # Fail closed: a configured secret means every delivery must carry a valid signature.
        if not x_hub_signature_256 or not _verify_signature(
            body, x_hub_signature_256, settings.github_webhook_secret
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    elif settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )
    else:
        logger.warning("Accepting unverified webhook (no secret configured, development mode)")

    if x_github_delivery and not await deliveries.record(x_github_delivery, x_github_event):
        logger.info("Duplicate delivery %s (%s) ignored", x_github_delivery, x_github_event)
        return WebhookResponse(accepted=False, event=x_github_event, duplicate=True)

    payload = await request.json()
    background_tasks.add_task(
        _handle_event, x_github_event, payload, request.app.state.installation_service
    )

    return WebhookResponse(accepted=True, event=x_github_event)
