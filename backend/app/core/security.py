"""
JARVIS Security — JWT tokens, password hashing, auth dependencies.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError

logger = structlog.get_logger(__name__)

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# Redis key prefix for token blacklist
_BLACKLIST_PREFIX = "jarvis:token:blacklist:"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _build_payload(
    sub: str,
    token_type: str,
    expires_delta: timedelta,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return payload


def create_access_token(
    subject: str | uuid.UUID | dict[str, Any],
    additional_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    if isinstance(subject, dict):
        sub = str(subject.get("sub", ""))
        extra = {k: v for k, v in subject.items() if k != "sub"}
        if additional_claims:
            extra.update(additional_claims)
    else:
        sub = str(subject)
        extra = additional_claims or {}

    payload = _build_payload(sub, ACCESS_TOKEN_TYPE, delta, extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    subject: str | uuid.UUID | dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT refresh token."""
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    if isinstance(subject, dict):
        sub = str(subject.get("sub", ""))
    else:
        sub = str(subject)

    payload = _build_payload(sub, REFRESH_TOKEN_TYPE, delta)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def blacklist_token(jti: str, exp: int) -> None:
    """Add a token JTI to the Redis blacklist until its natural expiry."""
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
        if ttl > 0:
            await redis.setex(f"{_BLACKLIST_PREFIX}{jti}", ttl, "1")
    except Exception as exc:
        logger.warning("token.blacklist_failed", jti=jti, error=str(exc))


async def is_token_blacklisted(jti: str) -> bool:
    """Check whether a token JTI has been blacklisted."""
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        return await redis.exists(f"{_BLACKLIST_PREFIX}{jti}") == 1
    except Exception:
        return False


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """FastAPI dependency — validates Bearer token and returns the active User."""
    from app.models.user import User

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check blacklist
    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


async def get_current_superuser(current_user: Any = Depends(get_current_user)) -> Any:
    """Dependency that requires superuser privilege."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return current_user
