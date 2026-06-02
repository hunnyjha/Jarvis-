"""
JARVIS Database Seeder — creates initial admin user and default data.
Run: python -m app.db.seed
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as script
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.memory import MemoryCollection, MemoryType
from app.models.user import User

logger = structlog.get_logger(__name__)

ADMIN_EMAIL = "admin@jarvis.local"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "JarvisAdmin2024!"

DEFAULT_COLLECTIONS = [
    {
        "name": "Research",
        "description": "Research findings and notes",
        "color": "#3b82f6",
        "icon": "search",
        "is_default": False,
    },
    {
        "name": "Reddit Intelligence",
        "description": "Subreddit insights and analysis notes",
        "color": "#f97316",
        "icon": "reddit",
        "is_default": False,
    },
    {
        "name": "Security",
        "description": "Security investigation notes",
        "color": "#ef4444",
        "icon": "shield",
        "is_default": False,
    },
    {
        "name": "Strategy",
        "description": "Strategic decisions and growth plans",
        "color": "#8b5cf6",
        "icon": "brain",
        "is_default": True,
    },
]

INITIAL_MEMORIES = [
    {
        "title": "JARVIS System Initialized",
        "content": (
            "JARVIS has been initialized. This is your personal AI intelligence operating system. "
            "Use the Research Center to conduct multi-source research, Reddit Intelligence to analyze "
            "communities, Security Center to investigate accounts, and Memory Vault to store knowledge."
        ),
        "memory_type": MemoryType.NOTE,
        "importance_score": 0.9,
        "is_pinned": True,
    },
    {
        "title": "Reddit Analysis Best Practices",
        "content": (
            "For best results when analyzing subreddits: use 'month' or 'year' time period for trend analysis, "
            "use 'week' for current pulse, analyze 100-200 posts minimum, compare multiple related subreddits "
            "to identify cross-community patterns."
        ),
        "memory_type": MemoryType.INSIGHT,
        "importance_score": 0.8,
        "is_pinned": False,
    },
]


async def seed() -> None:
    """Seed the database with initial data."""
    logger.info("database.seed.start")

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin = result.scalar_one_or_none()

        if admin:
            logger.info("database.seed.admin_exists", user_id=str(admin.id))
        else:
            admin = User(
                email=ADMIN_EMAIL,
                username=ADMIN_USERNAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                full_name="JARVIS Admin",
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
            db.add(admin)
            await db.flush()
            logger.info("database.seed.admin_created", user_id=str(admin.id))

        # Create default memory collections
        for col_data in DEFAULT_COLLECTIONS:
            existing = await db.execute(
                select(MemoryCollection).where(
                    MemoryCollection.user_id == admin.id,
                    MemoryCollection.name == col_data["name"],
                )
            )
            if not existing.scalar_one_or_none():
                collection = MemoryCollection(user_id=admin.id, **col_data)
                db.add(collection)

        await db.flush()

        # Get default collection for initial memories
        default_col_result = await db.execute(
            select(MemoryCollection).where(
                MemoryCollection.user_id == admin.id,
                MemoryCollection.is_default == True,
            )
        )
        default_col = default_col_result.scalar_one_or_none()

        # Create initial memories
        from app.models.memory import Memory
        for mem_data in INITIAL_MEMORIES:
            existing = await db.execute(
                select(Memory).where(
                    Memory.user_id == admin.id,
                    Memory.title == mem_data["title"],
                )
            )
            if not existing.scalar_one_or_none():
                memory = Memory(
                    user_id=admin.id,
                    collection_id=default_col.id if default_col else None,
                    **mem_data,
                )
                db.add(memory)

        await db.commit()
        logger.info("database.seed.complete", admin_email=ADMIN_EMAIL)

    print(f"\n✅ Database seeded successfully!")
    print(f"   Admin email:    {ADMIN_EMAIL}")
    print(f"   Admin password: {ADMIN_PASSWORD}")
    print(f"   ⚠️  Change the admin password immediately in production!\n")


if __name__ == "__main__":
    asyncio.run(seed())
