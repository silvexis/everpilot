import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from everpilot import __description__, __version__
from everpilot.api import api_router
from everpilot.config import get_settings
from everpilot.db import InMemoryRepoConfigStore, PostgresRepoConfigStore, create_pool
from everpilot.db.deliveries import InMemoryWebhookDeliveryStore, PostgresWebhookDeliveryStore
from everpilot.db.installations import InMemoryInstallationStore, PostgresInstallationStore
from everpilot.db.tasks import (
    InMemoryAuditStore,
    InMemoryTaskStore,
    PostgresAuditStore,
    PostgresTaskStore,
)
from everpilot.github.installations import InstallationService
from everpilot.orchestration import InlineEventDispatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Everpilot API v%s starting in %s mode", __version__, settings.app_env)
        pool = None
        if settings.database_url:
            pool = create_pool(settings.database_url)
            await pool.open(wait=True)
            app.state.repo_store = PostgresRepoConfigStore(pool)
            app.state.webhook_deliveries = PostgresWebhookDeliveryStore(pool)
            app.state.installation_store = PostgresInstallationStore(pool)
            app.state.installation_service = InstallationService(app.state.installation_store)
            app.state.task_store = PostgresTaskStore(pool)
            app.state.audit_store = PostgresAuditStore(pool)
            from everpilot.orchestration import dbos_engine

            dbos_engine.bind_installation_service(app.state.installation_service)
            logger.info("Connected to Postgres")
        else:
            logger.warning("DATABASE_URL not set — using in-memory store (development only)")
        yield
        if pool is not None:
            await pool.close()
        logger.info("Everpilot API shutting down")

    app = FastAPI(
        title="Everpilot API",
        description=__description__,
        version=__version__,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Default stores; the lifespan swaps in Postgres when DATABASE_URL is set
    app.state.repo_store = InMemoryRepoConfigStore()
    app.state.webhook_deliveries = InMemoryWebhookDeliveryStore()
    app.state.installation_store = InMemoryInstallationStore()
    app.state.installation_service = InstallationService(app.state.installation_store)
    app.state.rollback_service = None
    if settings.github_app_id and settings.github_app_private_key:
        from everpilot.github import GitHubAppClients
        from everpilot.github.rollback import RollbackService

        app.state.rollback_service = RollbackService(
            GitHubAppClients(settings.github_app_id, settings.github_app_private_key)
        )
    app.state.task_store = InMemoryTaskStore()
    app.state.audit_store = InMemoryAuditStore()
    app.state.event_dispatcher = InlineEventDispatcher(app.state.installation_service)

    if settings.database_url:
        # Durable event processing: DBOS checkpoints workflows in Postgres and
        # hooks the app lifespan itself.
        from everpilot.orchestration import dbos_engine

        app.state.event_dispatcher = dbos_engine.init_dbos(
            app, settings.app_name, settings.database_url
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "everpilot.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
