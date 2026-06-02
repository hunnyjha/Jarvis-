"""
JARVIS Custom Exceptions — Application-specific exception hierarchy.
"""
from __future__ import annotations

from typing import Any, Optional


class JarvisException(Exception):
    """Base exception for all JARVIS errors."""

    def __init__(
        self,
        message: str,
        code: str = "JARVIS_ERROR",
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class NotFoundError(JarvisException):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: Any = None) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": str(resource_id) if resource_id else None},
        )


class UnauthorizedError(JarvisException):
    """Authentication required or failed."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenError(JarvisException):
    """Access to resource is forbidden."""

    def __init__(self, message: str = "Access forbidden") -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class ValidationError(JarvisException):
    """Input validation failed."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        details = {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class ConflictError(JarvisException):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
        )


class RateLimitError(JarvisException):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ) -> None:
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


class AIServiceError(JarvisException):
    """AI service (Claude/OpenAI) error."""

    def __init__(self, message: str, service: str = "ai") -> None:
        super().__init__(
            message=message,
            code="AI_SERVICE_ERROR",
            status_code=502,
            details={"service": service},
        )


class RedditAPIError(JarvisException):
    """Reddit API error."""

    def __init__(self, message: str, endpoint: Optional[str] = None) -> None:
        details: dict[str, Any] = {}
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(
            message=message,
            code="REDDIT_API_ERROR",
            status_code=502,
            details=details,
        )


class DatabaseError(JarvisException):
    """Database operation error."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
        )


class ServiceUnavailableError(JarvisException):
    """External service unavailable."""

    def __init__(self, service: str) -> None:
        super().__init__(
            message=f"Service '{service}' is currently unavailable",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details={"service": service},
        )
