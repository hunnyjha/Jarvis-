"""Research Service — 7-tier content intelligence + multi-source research."""
from __future__ import annotations

import asyncio
import urllib.parse
import uuid
from typing import Any, Dict, List

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.research import ResearchResult, ResearchSession, ResearchStatus
from app.services.ai_service import AIService

logger = structlog.get_logger(__name__)

# ── Tier 2: High-signal subreddits ────────────────────────────────────────────
TIER2_SUBREDDITS = [
    "technology", "marketing", "socialmedia", "Entrepreneur",
    "artificial", "Futurology", "ChatGPT", "Creator",
]

# ── Tier 7: Industry blog RSS feeds ──────────────────────────────────────────
INDUSTRY_RSS_FEEDS = [
    ("Meta Newsroom",         "https://about.fb.com/feed/"),
    ("YouTube Blog",          "https://blog.youtube/feeds/posts/default"),
    ("TechCrunch AI",         "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge Tech",        "https://www.theverge.com/tech/rss/index.xml"),
    ("Social Media Today",    "https://www.socialmediatoday.com/rss.xml"),
]

# ── Viral topic signals ────────────────────────────────────────────────────────
VIRAL_SIGNALS = [
    "controversy", "leak", "lawsuit", "exploit", "ban", "banned",
    "AI replacing", "algorithm change", "acquisition", "drama",
    "platform mistake", "insane", "breaking", "just happened",
    "security", "hack", "outrage", "scandal",
]


class ResearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai = AIService()

    # ─── Main Session Pipeline ────────────────────────────────────

    async def run_session(self, session_id: uuid.UUID, query: str, research_type: str) -> None:
        result = await self.db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return

        try:
            session.status = ResearchStatus.IN_PROGRESS
            await self.db.commit()

            sources: List[Dict[str, Any]] = []

            if research_type == "viral_scan":
                # Full 7-tier viral opportunity scan
                sources = await self._full_viral_scan(query)
            elif research_type == "multi_source":
                # Reddit + HN + blogs
                reddit_results, hn_results, blog_results = await asyncio.gather(
                    self._search_reddit(query),
                    self._search_hacker_news(query),
                    self._search_industry_blogs(query),
                )
                sources = reddit_results + hn_results + blog_results
            else:
                # Default: Reddit + HN
                reddit_results, hn_results = await asyncio.gather(
                    self._search_reddit(query),
                    self._search_hacker_news(query),
                )
                sources = reddit_results + hn_results

            # AI synthesis
            ai_result = await self.ai.research_query(query, sources, research_type)

            # Persist results
            for src in sources:
                research_result = ResearchResult(
                    session_id=session_id,
                    title=src.get("title", "Untitled"),
                    url=src.get("url"),
                    source=src.get("source"),
                    content=src.get("content", "")[:10000],
                    snippet=src.get("snippet", "")[:500],
                    relevance_score=src.get("relevance_score", 0.5),
                )
                self.db.add(research_result)

            session.summary = ai_result.get("summary", "")
            session.sources_count = len(sources)
            session.extra_metadata = ai_result
            session.status = ResearchStatus.COMPLETED
            await self.db.commit()
            logger.info("research.session.completed", session_id=str(session_id), sources=len(sources))

        except Exception as exc:
            logger.error("research.session.failed", session_id=str(session_id), error=str(exc))
            session.status = ResearchStatus.FAILED
            session.error_message = str(exc)[:1000]
            await self.db.commit()

    # ─── Tier 1 (partial): Hacker News ───────────────────────────

    async def _search_hacker_news(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch top Hacker News stories. Great for AI, tech drama, startup launches."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
                story_ids = resp.json()[:60]

                results = []
                query_words = [w.lower() for w in query.split()[:4]] if query else []

                for story_id in story_ids:
                    if len(results) >= limit:
                        break
                    try:
                        story_resp = await client.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                        )
                        story = story_resp.json()
                        if not story or story.get("type") != "story":
                            continue
                        title = story.get("title", "")
                        title_lower = title.lower()
                        if query_words and not any(w in title_lower for w in query_words):
                            continue
                        results.append({
                            "title": title,
                            "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                            "source": "Hacker News (Tier 3)",
                            "content": title,
                            "snippet": f"[HN] Score:{story.get('score',0)} | Comments:{story.get('descendants',0)} | {title}",
                            "relevance_score": min(1.0, story.get("score", 0) / 500),
                            "tier": "hacker_news",
                        })
                    except Exception:
                        continue

                results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                return results

        except Exception as exc:
            logger.warning("research.hn_failed", error=str(exc))
            return []

    # ─── Tier 2: Reddit High-Signal Communities ────────────────────

    async def _search_reddit(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Reddit via public JSON API."""
        headers = {"User-Agent": settings.REDDIT_USER_AGENT}
        url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(query)}&sort=relevance&limit={limit}"
        try:
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                children = resp.json().get("data", {}).get("children", [])
                return [
                    {
                        "title": p.get("data", {}).get("title", ""),
                        "url": f"https://reddit.com{p.get('data', {}).get('permalink', '')}",
                        "source": f"r/{p.get('data', {}).get('subreddit', 'unknown')} (Tier 2)",
                        "content": (p.get("data", {}).get("selftext") or "")[:2000],
                        "snippet": (p.get("data", {}).get("selftext") or p.get("data", {}).get("title", ""))[:200],
                        "relevance_score": min(1.0, (p.get("data", {}).get("score") or 0) / 1000),
                        "tier": "reddit",
                    }
                    for p in children
                ]
        except Exception as exc:
            logger.warning("research.reddit_search_failed", error=str(exc))
            return []

    async def _scan_tier2_reddit(self, limit_per_sub: int = 5) -> List[Dict[str, Any]]:
        """Scan high-signal subreddits for today's top posts (Tier 2 monitoring)."""
        headers = {"User-Agent": settings.REDDIT_USER_AGENT}
        results = []

        async def _fetch_sub(sub: str) -> List[Dict[str, Any]]:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit_per_sub}"
            try:
                async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url)
                    children = resp.json().get("data", {}).get("children", [])
                    return [
                        {
                            "title": p.get("data", {}).get("title", ""),
                            "url": f"https://reddit.com{p.get('data', {}).get('permalink', '')}",
                            "source": f"r/{sub} (Tier 2)",
                            "content": (p.get("data", {}).get("selftext") or "")[:500],
                            "snippet": p.get("data", {}).get("title", ""),
                            "relevance_score": min(1.0, (p.get("data", {}).get("score") or 0) / 5000),
                            "score": p.get("data", {}).get("score", 0),
                            "tier": "reddit_tier2",
                        }
                        for p in children
                    ]
            except Exception:
                return []

        sub_results = await asyncio.gather(*[_fetch_sub(s) for s in TIER2_SUBREDDITS])
        for sub_posts in sub_results:
            results.extend(sub_posts)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    # ─── Tier 3: Hacker News (top stories, no filter) ─────────────

    async def _scan_hacker_news_top(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Scan HN top stories regardless of query — for viral opportunity discovery."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
                story_ids = resp.json()[:30]

                tasks = [
                    client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                    for sid in story_ids[:30]
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                results = []
                for r in responses:
                    if isinstance(r, Exception):
                        continue
                    try:
                        story = r.json()
                        if story and story.get("type") == "story" and story.get("score", 0) > 50:
                            results.append({
                                "title": story.get("title", ""),
                                "url": story.get("url", f"https://news.ycombinator.com/item?id={story.get('id')}"),
                                "source": "Hacker News (Tier 3)",
                                "content": story.get("title", ""),
                                "snippet": f"Score:{story.get('score',0)} | Comments:{story.get('descendants',0)}",
                                "relevance_score": min(1.0, story.get("score", 0) / 500),
                                "score": story.get("score", 0),
                                "tier": "hacker_news",
                            })
                    except Exception:
                        continue

                results.sort(key=lambda x: x.get("score", 0), reverse=True)
                return results[:limit]

        except Exception as exc:
            logger.warning("research.hn_scan_failed", error=str(exc))
            return []

    # ─── Tier 5: Google Trends ────────────────────────────────────

    async def _search_google_trends(self, query: str) -> List[Dict[str, Any]]:
        """Get rising Google Trends for a topic."""
        def _sync_trends() -> List[Dict[str, Any]]:
            try:
                from pytrends.request import TrendReq
                pt = TrendReq(hl="en-US", tz=0)
                kw = query[:100]
                pt.build_payload([kw], timeframe="now 7-d")
                related = pt.related_queries()
                results = []
                if kw in related and related[kw].get("rising") is not None:
                    df = related[kw]["rising"]
                    for _, row in df.head(8).iterrows():
                        results.append({
                            "title": f"Rising search: {row['query']}",
                            "url": f"https://trends.google.com/trends/explore?q={urllib.parse.quote(row['query'])}",
                            "source": "Google Trends (Tier 5)",
                            "content": f"Rising search trend '{row['query']}' — relative value {row['value']}",
                            "snippet": f"Rising trend: {row['query']} (value: {row['value']})",
                            "relevance_score": min(1.0, row["value"] / 100),
                            "tier": "google_trends",
                        })
                return results
            except Exception as exc:
                logger.warning("research.trends_sync_failed", error=str(exc))
                return []

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _sync_trends)
        except Exception as exc:
            logger.warning("research.trends_failed", error=str(exc))
            return []

    # ─── Tier 7: Industry Blog RSS Feeds ─────────────────────────

    async def _search_industry_blogs(self, query: str = "") -> List[Dict[str, Any]]:
        """Fetch latest posts from platform/industry blogs via RSS."""
        def _parse_feeds() -> List[Dict[str, Any]]:
            try:
                import feedparser
            except ImportError:
                return []

            results = []
            query_words = [w.lower() for w in query.split()[:4]] if query else []

            for source_name, feed_url in INDUSTRY_RSS_FEEDS:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:8]:
                        title = entry.get("title", "")
                        summary = entry.get("summary", "")
                        # If query given, loosely filter; if no query, return all
                        if query_words:
                            combined = (title + " " + summary).lower()
                            if not any(w in combined for w in query_words):
                                continue
                        results.append({
                            "title": title,
                            "url": entry.get("link", ""),
                            "source": f"{source_name} (Tier 7)",
                            "content": summary[:2000],
                            "snippet": summary[:200],
                            "relevance_score": 0.75,
                            "tier": "industry_blog",
                        })
                except Exception as exc:
                    logger.warning("research.rss_failed", source=source_name, error=str(exc))

            return results

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _parse_feeds)
        except Exception as exc:
            logger.warning("research.blogs_failed", error=str(exc))
            return []

    # ─── Full 7-Tier Viral Opportunity Scan ───────────────────────

    async def _full_viral_scan(self, query: str) -> List[Dict[str, Any]]:
        """Run all tiers simultaneously and rank by viral signal strength."""
        reddit_general, reddit_tier2, hn_top, trends, blogs = await asyncio.gather(
            self._search_reddit(query, limit=8),
            self._scan_tier2_reddit(limit_per_sub=3),
            self._scan_hacker_news_top(limit=15),
            self._search_google_trends(query),
            self._search_industry_blogs(query),
        )

        all_sources = reddit_general + reddit_tier2 + hn_top + trends + blogs

        # Boost viral signal items
        for item in all_sources:
            title_lower = item.get("title", "").lower()
            viral_boost = sum(1 for signal in VIRAL_SIGNALS if signal in title_lower)
            item["relevance_score"] = min(1.0, item.get("relevance_score", 0.5) + viral_boost * 0.1)
            item["viral_signals"] = viral_boost

        all_sources.sort(key=lambda x: (x.get("viral_signals", 0), x.get("relevance_score", 0)), reverse=True)
        return all_sources[:50]

    # ─── Public helpers for direct agent tool calls ───────────────

    async def scan_viral_opportunities(self, query: str = "AI social media") -> Dict[str, Any]:
        """Entry point for the viral scanner tool."""
        sources = await self._full_viral_scan(query)
        ai_result = await self.ai.analyze_viral_opportunities(query, sources)
        return {
            "sources_scanned": len(sources),
            "tiers_covered": ["Reddit (Tier 2)", "Hacker News (Tier 3)", "Google Trends (Tier 5)", "Industry Blogs (Tier 7)"],
            "top_opportunities": sources[:10],
            "ai_analysis": ai_result,
        }
