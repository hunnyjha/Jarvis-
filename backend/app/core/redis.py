"""
JARVIS Redis — Connection pool, cache decorator, rate limiting utilities.
"""
from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable, Optional, TypeVar

import redis.asyncio as aioredis
from fastapi import Depends

from app.core.config import settings
from app.core.exceptions import RateLimitError, ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Global Redis connection pool
_redis_pool: Optional[aioredis.ConnectionPool] = None
_redis_client: Optional[aioredis.Redis] = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Get or create the Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
    return _redis_pool


def get_redis_client() -> aioredis.Redis:
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis(connection_pool=get_redis_pool())
    return _redis_client


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency that provides a Redis client."""
    client = get_redis_client()
    try:
        await client.ping()
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        raise ServiceUnavailableError("redis")
    return client


async def close_redis() -> None:
    """Close Redis connections on shutdown."""
    global _redis_pool, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
    logger.info("Redis connections closed")


class CacheManager:
    """High-level cache operations with JSON serialization."""

    def __init__(self, redis: aioredis.Redis, prefix: str = "jarvis") -> None:
        self.redis = redis
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        raw = await self.redis.get(self._make_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = settings.REDIS_CACHE_TTL,
    ) -> None:
        """Set a value in cache with TTL."""
        serialized = json.dumps(value, default=str)
        await self.redis.setex(self._make_key(key), ttl, serialized)

    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        await self.redis.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return bool(await self.redis.exists(self._make_key(key)))

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        keys = await self.redis.keys(self._make_key(pattern))
        if keys:
            return await self.redis.delete(*keys)
        return 0


class RateLimiter:
    """Sliding window rate limiter using Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int = settings.RATE_LIMIT_PER_MINUTE,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Check if an identifier (e.g., IP or user_id) has exceeded the rate limit.
        Returns (is_allowed, requests_remaining).
        """
        key = f"ratelimit:{identifier}:{window_seconds}"

        pipe = self.redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        current_count = results[0]
        remaining = max(0, limit - current_count)
        is_allowed = current_count <= limit

        return is_allowed, remaining

    async def enforce_rate_limit(
        self,
        identifier: str,
        limit: int = settings.RATE_LIMIT_PER_MINUTE,
        window_seconds: int = 60,
    ) -> None:
        """
        Enforce rate limit — raises RateLimitError if limit exceeded.
        """
        is_allowed, remaining = await self.check_rate_limit(
            identifier, limit, window_seconds
        )
        if not is_allowed:
            raise RateLimitError(
                message=f"Rate limit of {limit} requests per {window_seconds}s exceeded",
                retry_after=window_seconds,
            )


def cache_response(key_prefix: str, ttl: int = 300) -> Callable[[F], F]:
    """
    Decorator that caches function results in Redis.
    Cache key is built from the prefix + hash of the function arguments.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from args
            cache_key_data = json.dumps(
                {"args": str(args), "kwargs": str(kwargs)}, sort_keys=True
            )
            key_hash = hashlib.md5(cache_key_data.encode()).hexdigest()[:12]
            cache_key = f"{key_prefix}:{key_hash}"

            redis = get_redis_client()
            manager = CacheManager(redis)

            cached = await manager.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit", key=cache_key)
                return cached

            result = await func(*args, **kwargs)
            await manager.set(cache_key, result, ttl=ttl)
            logger.debug("Cache miss — stored result", key=cache_key)
            return result

        return wrapper  # type: ignore[return-value]
    return decorator
