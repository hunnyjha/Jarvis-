"""LangChain tools exposed to JARVIS agents."""
from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import tool


@tool
def analyze_subreddit_tool(subreddit_name: str, time_period: str = "week") -> str:
    """Analyze a Reddit subreddit for insights, trends, and opportunities.

    Args:
        subreddit_name: Name of the subreddit (without r/)
        time_period: Time period: hour, day, week, month, year, all
    """
    return json.dumps({
        "action": "reddit_analyze",
        "subreddit": subreddit_name,
        "time_period": time_period,
    })


@tool
def search_reddit_tool(query: str, subreddit: Optional[str] = None, limit: int = 10) -> str:
    """Search Reddit for posts and discussions on a topic.

    Args:
        query: Search query
        subreddit: Optional subreddit to search within
        limit: Number of results to return
    """
    return json.dumps({
        "action": "reddit_search",
        "query": query,
        "subreddit": subreddit,
        "limit": limit,
    })


@tool
def research_topic_tool(query: str, research_type: str = "web_search") -> str:
    """Conduct multi-source research on a topic.

    Args:
        query: Research query
        research_type: web_search, reddit_analysis, multi_source, competitive
    """
    return json.dumps({
        "action": "research",
        "query": query,
        "research_type": research_type,
    })


@tool
def investigate_account_tool(username: str, investigation_type: str = "account_scan") -> str:
    """Investigate a Reddit account for suspicious behavior patterns.

    Args:
        username: Reddit username to investigate
        investigation_type: account_scan, threat_assessment, osint_collection
    """
    return json.dumps({
        "action": "security_investigate",
        "username": username,
        "investigation_type": investigation_type,
    })


@tool
def search_memory_tool(query: str, limit: int = 5) -> str:
    """Search JARVIS memory for relevant past information.

    Args:
        query: What to search for in memory
        limit: Max number of memories to return
    """
    return json.dumps({
        "action": "memory_search",
        "query": query,
        "limit": limit,
    })


@tool
def store_memory_tool(title: str, content: str, memory_type: str = "insight") -> str:
    """Store important information in JARVIS long-term memory.

    Args:
        title: Short descriptive title for the memory
        content: Full content to remember
        memory_type: note, insight, fact, decision, research
    """
    return json.dumps({
        "action": "memory_store",
        "title": title,
        "content": content,
        "memory_type": memory_type,
    })


@tool
def analyze_strategy_tool(context: str, options: list) -> str:
    """Analyze strategic options and provide recommendations.

    Args:
        context: Description of the decision or challenge
        options: List of options to evaluate
    """
    return json.dumps({
        "action": "strategy_analyze",
        "context": context,
        "options": options,
    })


@tool
def generate_report_tool(report_type: str, source_id: str, format: str = "markdown") -> str:
    """Generate an intelligence report from existing analysis data.

    Args:
        report_type: subreddit_analysis, security_investigation, research_session
        source_id: UUID of the source analysis/session
        format: pdf, markdown, html
    """
    return json.dumps({
        "action": "generate_report",
        "report_type": report_type,
        "source_id": source_id,
        "format": format,
    })


@tool
def scan_viral_opportunities_tool(query: str = "AI social media creator") -> str:
    """Scan all 7 intelligence tiers for viral content opportunities.

    Monitors: Reddit Tier 2 communities, Hacker News, Google Trends,
    industry blogs (Meta, YouTube, TechCrunch). Identifies stories with
    high viral potential 6-48 hours before they peak on Reddit.

    Args:
        query: Topic or keyword to focus the viral scan on
    """
    return json.dumps({
        "action": "viral_scan",
        "query": query,
    })


@tool
def search_hacker_news_tool(query: str, limit: int = 10) -> str:
    """Search Hacker News for tech stories, AI news, and startup launches.

    Best for: AI stories, tech drama, security exploits, startup launches.
    Most Reddit marketers ignore HN — stories here are 12-24h ahead of Reddit.

    Args:
        query: Search topic
        limit: Number of stories to return
    """
    return json.dumps({
        "action": "hacker_news_search",
        "query": query,
        "limit": limit,
    })


@tool
def search_industry_blogs_tool(query: str = "") -> str:
    """Fetch latest posts from platform blogs: Meta, YouTube, TechCrunch, The Verge.

    These announce features before most users know about them.
    Great for: algorithm updates, product launches, policy changes.

    Args:
        query: Filter by topic (leave empty for all latest)
    """
    return json.dumps({
        "action": "industry_blogs_search",
        "query": query,
    })


@tool
def search_google_trends_tool(query: str) -> str:
    """Get rising Google Trends searches for a topic.

    Good for: emerging keywords, rising searches, seasonal topics.
    Use to validate if a story has search demand before creating content.

    Args:
        query: Topic to check trends for
    """
    return json.dumps({
        "action": "google_trends_search",
        "query": query,
    })


# All tools available to the orchestrator
ALL_TOOLS = [
    analyze_subreddit_tool,
    search_reddit_tool,
    research_topic_tool,
    investigate_account_tool,
    search_memory_tool,
    store_memory_tool,
    analyze_strategy_tool,
    generate_report_tool,
    scan_viral_opportunities_tool,
    search_hacker_news_tool,
    search_industry_blogs_tool,
    search_google_trends_tool,
]

TOOL_NAMES = {t.name: t for t in ALL_TOOLS}
