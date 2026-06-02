"""
JARVIS AI Operating System — FastAPI Application Entry Point.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import JarvisException
from app.core.logging import get_logger, setup_logging
from app.core.middleware import LoggingMiddleware, RequestIDMiddleware, TimingMiddleware
from app.core.redis import close_redis, get_redis_pool

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown events."""
    # ── Startup ──────────────────────────────────────────────────
    setup_logging(
        log_level=settings.LOG_LEVEL,
        is_production=settings.is_production,
    )
    logger.info(
        "Starting JARVIS",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Initialize Redis connection pool
    get_redis_pool()
    logger.info("Redis connection pool initialized")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    logger.info("JARVIS is ready", url=settings.BACKEND_URL)
    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("Shutting down JARVIS...")
    await close_redis()
    await close_db()
    logger.info("JARVIS shutdown complete")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="JARVIS AI Operating System — Reddit Intelligence Platform",
        version=settings.VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters — outermost first) ───────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # ── Prometheus Metrics ────────────────────────────────────────
    if settings.ENABLE_METRICS:
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/health", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # ── Exception Handlers ───────────────────────────────────────
    @app.exception_handler(JarvisException)
    async def jarvis_exception_handler(
        request: Request, exc: JarvisException
    ) -> JSONResponse:
        logger.warning(
            "Application error",
            error_code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            errors=exc.errors(),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )

    # ── Health Check ─────────────────────────────────────────────
    @app.get("/health", include_in_schema=False)
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
        }

    # ── API Router ───────────────────────────────────────────────
    from app.api.v1.router import api_router

    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
