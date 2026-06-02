"""
JARVIS Security — JWT token handling, password hashing, OAuth2 scheme.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 bearer token scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)

# Token types
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | UUID | dict[str, Any],
    additional_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    `subject` can be a user ID string/UUID, or a dict with a 'sub' key.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Support both create_access_token(user_id) and create_access_token({"sub": user_id})
    if isinstance(subject, dict):
        payload: dict[str, Any] = {**subject, "iat": now, "exp": expire, "type": ACCESS_TOKEN_TYPE}
        if "sub" not in payload:
            raise ValueError("subject dict must contain 'sub' key")
    else:
        payload = {
            "sub": str(subject),
            "iat": now,
            "exp": expire,
            "type": ACCESS_TOKEN_TYPE,
        }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    subject: str | UUID | dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.
    `subject` can be a user ID string/UUID, or a dict with a 'sub' key.
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    if isinstance(subject, dict):
        payload: dict[str, Any] = {**subject, "iat": now, "exp": expire, "type": REFRESH_TOKEN_TYPE}
    else:
        payload = {
            "sub": str(subject),
            "iat": now,
            "exp": expire,
            "type": REFRESH_TOKEN_TYPE,
        }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises UnauthorizedError if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")


def get_token_subject(token: str) -> str:
    """Extract and return the subject (user ID) from a token."""
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing subject claim")
    return sub


def get_token_type(token: str) -> str:
    """Get the type of a token (access or refresh)."""
    payload = decode_token(token)
    return payload.get("type", "")


async def get_current_user_id(
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    """
    FastAPI dependency that extracts and validates the current user ID from JWT.
    """
    if not token:
        raise UnauthorizedError("Authentication required")

    payload = decode_token(token)

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    return user_id


def create_token_pair(user_id: str | UUID) -> dict[str, str]:
    """Create both access and refresh tokens for a user."""
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Any:
    """
    FastAPI dependency that returns the current authenticated User model.
    Imports User lazily to avoid circular imports.
    """
    from sqlalchemy import select

    from app.core.database import get_session_factory
    from app.models.user import User

    if not token:
        raise UnauthorizedError("Authentication required")

    payload = decode_token(token)
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    return user
