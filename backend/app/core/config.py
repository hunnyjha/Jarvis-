"""
JARVIS Configuration — Pydantic Settings with environment variable support.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    PROJECT_NAME: str = "JARVIS AI Operating System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ── Database ─────────────────────────────────────────────────
    POSTGRES_USER: str = Field(default="jarvis")
    POSTGRES_PASSWORD: str = Field(default="jarvis_secret")
    POSTGRES_DB: str = Field(default="jarvis_db")
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    DATABASE_URL: Optional[str] = Field(default=None)
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: Optional[str], info: Any) -> str:
        if isinstance(v, str) and v:
            return v
        # Build from components
        values = info.data if hasattr(info, "data") else {}
        user = values.get("POSTGRES_USER", "jarvis")
        password = values.get("POSTGRES_PASSWORD", "jarvis_secret")
        host = values.get("POSTGRES_HOST", "postgres")
        port = values.get("POSTGRES_PORT", 5432)
        db = values.get("POSTGRES_DB", "jarvis_db")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    REDIS_CACHE_TTL: int = Field(default=3600, description="Default cache TTL in seconds")

    # ── ChromaDB ─────────────────────────────────────────────────
    CHROMADB_URL: str = Field(default="http://chromadb:8000")
    CHROMA_AUTH_TOKEN: Optional[str] = Field(default=None)
    CHROMA_COLLECTION_NAME: str = Field(default="jarvis_memories")

    # ── AI APIs ──────────────────────────────────────────────────
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    AI_MAX_TOKENS: int = Field(default=4096)
    AI_TEMPERATURE: float = Field(default=0.7)

    # ── JWT Authentication ────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-in-production-at-least-32-chars-long")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # ── Reddit Public API ─────────────────────────────────────────
    REDDIT_USER_AGENT: str = Field(default="JARVIS:v1.0 (personal assistant)")

    # ── URLs ─────────────────────────────────────────────────────
    BACKEND_URL: str = Field(default="http://localhost:8000")
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return [origin.strip() for origin in v.split(",")]
        return v

    # ── Security ─────────────────────────────────────────────────
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1", "0.0.0.0"])
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_BURST: int = Field(default=100)

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return [host.strip() for host in v.split(",")]
        return v

    # ── Storage ──────────────────────────────────────────────────
    REPORTS_DIR: str = Field(default="/app/storage/reports")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50)

    # ── Feature Flags ────────────────────────────────────────────
    ENABLE_METRICS: bool = Field(default=True)
    ENABLE_AUDIT_LOG: bool = Field(default=True)
    ENABLE_RATE_LIMITING: bool = Field(default=True)

    # ── Computed Properties ───────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace(
                "postgresql+asyncpg://", "postgresql+psycopg2://"
            )
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
