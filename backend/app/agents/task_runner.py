"""
JARVIS Task Runner — Executes agent tasks asynchronously.
"""
from __future__ import annotations

from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)


async def run_agent_task(
    agent: str,
    task: str,
    params: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """Route and execute an agent task."""
    logger.info("agent.task.running", agent=agent, user_id=user_id)

    if agent == "research":
        return await _run_research_task(task, params, user_id)
    elif agent == "reddit":
        return await _run_reddit_task(task, params, user_id)
    elif agent == "security":
        return await _run_security_task(task, params, user_id)
    elif agent == "memory":
        return await _run_memory_task(task, params, user_id)
    elif agent == "report":
        return await _run_report_task(task, params, user_id)
    else:
        raise ValueError(f"Unknown agent: {agent}")


async def _run_research_task(
    task: str, params: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    from app.services.research_service import ResearchService

    service = ResearchService(None)
    max_results = params.get("max_results", 10)
    results = await service.web_search(query=task, max_results=max_results)
    synthesis = await service._synthesize_results(task, results)

    return {
        "type": "research",
        "query": task,
        "results_count": len(results),
        "summary": synthesis.get("summary"),
        "key_findings": synthesis.get("key_findings", []),
        "results": results[:5],
    }


async def _run_reddit_task(
    task: str, params: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    subreddit = params.get("subreddit", task)
    time_period = params.get("time_period", "week")
    post_limit = params.get("post_limit", 50)

    return {
        "type": "reddit",
        "message": f"Reddit analysis for r/{subreddit} queued",
        "subreddit": subreddit,
        "time_period": time_period,
        "status": "use POST /api/v1/reddit/analyze to start full analysis",
    }


async def _run_security_task(
    task: str, params: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    target = params.get("target", task)
    return {
        "type": "security",
        "message": f"Security investigation for '{target}' queued",
        "target": target,
        "status": "use POST /api/v1/security/investigate to start full investigation",
    }


async def _run_memory_task(
    task: str, params: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    from app.schemas.memory import MemorySearchRequest
    import uuid

    return {
        "type": "memory",
        "query": task,
        "message": "Memory search - use POST /api/v1/memory/search for semantic search",
    }


async def _run_report_task(
    task: str, params: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    return {
        "type": "report",
        "title": task,
        "message": "Report generation - use POST /api/v1/reports/generate to create a report",
        "suggested_types": ["subreddit_analysis", "research_session", "security_investigation"],
    }
