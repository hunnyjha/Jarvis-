"""Central API v1 router — mounts all sub-routers."""
from fastapi import APIRouter

from app.api.v1.routes import agents, auth, dashboard, memory, reddit, reports, research, security

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(reddit.router, prefix="/reddit", tags=["Reddit Intelligence"])
api_router.include_router(research.router, prefix="/research", tags=["Research"])
api_router.include_router(security.router, prefix="/security", tags=["Security"])
api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
