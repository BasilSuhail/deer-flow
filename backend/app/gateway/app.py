import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.gateway.routers import models, stats, threads
from deerflow.config.app_config import get_app_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    try:
        get_app_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e

    logger.info("Starting Deep Research Engine API Gateway")
    yield
    logger.info("Shutting down API Gateway")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Deep Research Engine API",
        description="API Gateway for the Deep Research Engine — local AI-powered deep research with Ollama.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "models", "description": "Available AI models"},
            {"name": "threads", "description": "Research thread management"},
            {"name": "health", "description": "Health check"},
        ],
    )

    app.include_router(models.router)
    app.include_router(stats.router)
    app.include_router(threads.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        return {"status": "healthy", "service": "deep-research-engine"}

    return app


app = create_app()
