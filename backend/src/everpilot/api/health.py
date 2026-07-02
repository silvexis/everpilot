from fastapi import APIRouter
from pydantic import BaseModel

from everpilot import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe — always returns 200 when the service is up."""
    return HealthResponse(status="ok", version=__version__, service="everpilot")
