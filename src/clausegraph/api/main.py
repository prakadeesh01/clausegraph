"""FastAPI application factory and process lifespan.

The application is built by a factory rather than declared at module
scope so that tests can construct an isolated instance, and so that
importing this module has no side effects. Uvicorn is pointed at the
factory with the --factory flag.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from clausegraph.api.routes import health
from config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Run startup and shutdown work exactly once per process.

    Expensive, long-lived resources belong here rather than in a
    request handler: the FAISS index, the BM25 corpus, the Neo4j driver
    and the CrossEncoder are all loaded once at startup in later
    blocks. Loading them per request is the specific mistake that makes
    a retrieval demo unusable as a service.

    Args:
        app: The application instance, used to hold shared state.

    Yields:
        Control to the server for the lifetime of the process.
    """
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger = logging.getLogger(settings.app_name)
    logger.info(
        "Starting %s v%s in %s environment",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    yield

    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A fully wired application with all routers registered.
    """
    settings = get_settings()

    app = FastAPI(
        title="ClauseGraph",
        description=(
            "Multi-agent contract risk analysis with hybrid retrieval "
            "over UK legislation."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.include_router(health.router)

    return app


if __name__ == "__main__":
    # Smoke test: serve the app directly, without Docker, for the
    # fastest possible edit and reload cycle during development.
    import uvicorn

    config = get_settings()
    uvicorn.run(
        "clausegraph.api.main:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        reload=True,
    )