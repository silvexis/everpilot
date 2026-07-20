from fastapi import APIRouter

from everpilot.api.audit import router as audit_router
from everpilot.api.health import router as health_router
from everpilot.api.repos import router as repos_router
from everpilot.api.tasks import router as tasks_router
from everpilot.api.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(audit_router)
api_router.include_router(health_router)
api_router.include_router(repos_router)
api_router.include_router(tasks_router)
api_router.include_router(webhooks_router)
