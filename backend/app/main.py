"""
JARVIS AI Operating System — FastAPI Application Entry Point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import close_db, get_db_context, init_db
from app.core.exceptions import JarvisException
from app.core.logging import get_logger, setup_logging
from app.core.middleware import LoggingMiddleware, RequestIDMiddleware, TimingMiddleware
from app.core.redis import close_redis, get_redis_pool
from app.core.websocket import ConnectionManager

logger = get_logger(__name__)

# Global WebSocket connection manager (shared across routes)
ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and graceful shutdown."""
    setup_logging(log_level=settings.LOG_LEVEL, is_production=settings.is_production)
    logger.info("jarvis.startup", version=settings.VERSION, env=settings.ENVIRONMENT)

    # Bring up Redis
    get_redis_pool()
    logger.info("redis.ready")

    # Bring up database
    await init_db()
    logger.info("database.ready")

    logger.info("jarvis.ready", url=settings.BACKEND_URL)
    yield

    logger.info("jarvis.shutdown")
    await close_redis()
    await close_db()
    logger.info("jarvis.shutdown.complete")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=(
            "JARVIS — Personal AI Intelligence Operating System for Reddit community builders, "
            "researchers, and growth strategists."
        ),
        version=settings.VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        contact={"name": "JARVIS", "url": settings.FRONTEND_URL},
    )

    # ── Middleware ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # ── Prometheus Metrics ────────────────────────────────────────
    if settings.ENABLE_METRICS:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator
            Instrumentator(
                should_group_status_codes=True,
                should_ignore_untemplated=True,
                excluded_handlers=["/health", "/metrics", "/ws"],
            ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        except ImportError:
            logger.warning("prometheus_not_available")

    # ── Exception Handlers ────────────────────────────────────────
    @app.exception_handler(JarvisException)
    async def jarvis_exception_handler(request: Request, exc: JarvisException) -> JSONResponse:
        logger.warning(
            "app.error",
            code=exc.code,
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
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("validation.error", errors=exc.errors(), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled.exception", exc_info=exc, path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"},
        )

    # ── Health Endpoints ──────────────────────────────────────────
    @app.get("/health", include_in_schema=False, tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Basic liveness probe — always fast."""
        return {"status": "healthy", "version": settings.VERSION, "env": settings.ENVIRONMENT}

    @app.get("/health/deep", include_in_schema=False, tags=["Health"])
    async def deep_health_check() -> dict[str, Any]:
        """Deep readiness probe — checks all dependencies."""
        from app.db.health import check_database_health
        from app.core.redis import get_redis

        checks: dict[str, Any] = {}

        # Database
        try:
            async with get_db_context() as db:
                result = await check_database_health(db)
            checks["database"] = result
        except Exception as exc:
            checks["database"] = {"status": "error", "detail": str(exc)}

        # Redis
        try:
            redis = await get_redis()
            await redis.ping()
            checks["redis"] = {"status": "ok"}
        except Exception as exc:
            checks["redis"] = {"status": "error", "detail": str(exc)}

        # ChromaDB
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.CHROMADB_URL}/api/v1/heartbeat")
            checks["chromadb"] = {"status": "ok" if resp.status_code == 200 else "error"}
        except Exception as exc:
            checks["chromadb"] = {"status": "error", "detail": str(exc)}

        overall = "healthy" if all(
            v.get("status") in ("ok", "healthy") for v in checks.values()
        ) else "degraded"

        return {
            "status": overall,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        }

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.PROJECT_NAME, "version": settings.VERSION, "docs": "/docs"}

    # ── WebSocket — real-time agent task updates ──────────────────
    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
        """WebSocket endpoint for real-time agent task status updates."""
        await ws_manager.connect(client_id, websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Echo ping/pong for keepalive
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(client_id)

    # ── API Router ────────────────────────────────────────────────
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
