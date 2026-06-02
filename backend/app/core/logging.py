"""
JARVIS Structured Logging — structlog configuration with JSON/colored output.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Optional

import structlog
from structlog.types import EventDict, Processor


def add_request_id(logger: Any, method: str, event_dict: EventDict) -> EventDict:
    """Add request ID to log context if available."""
    from structlog.contextvars import get_contextvars

    ctx = get_contextvars()
    if "request_id" in ctx:
        event_dict["request_id"] = ctx["request_id"]
    if "user_id" in ctx:
        event_dict["user_id"] = ctx["user_id"]
    return event_dict


def add_app_info(logger: Any, method: str, event_dict: EventDict) -> EventDict:
    """Add application metadata to logs."""
    event_dict.setdefault("service", "jarvis-backend")
    return event_dict


def setup_logging(log_level: str = "INFO", is_production: bool = False) -> None:
    """Configure structlog for the application."""

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Silence noisy loggers
    for noisy_logger in ["uvicorn.access", "uvicorn.error", "sqlalchemy.engine"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_request_id,
        add_app_info,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        # JSON output for production (machine-readable)
        processors: list[Processor] = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored, human-readable output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)


def bind_request_context(request_id: str, user_id: Optional[str] = None) -> None:
    """Bind request context to structlog contextvars."""
    context: dict[str, Any] = {"request_id": request_id}
    if user_id:
        context["user_id"] = user_id
    structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """Clear structlog request context."""
    structlog.contextvars.clear_contextvars()
