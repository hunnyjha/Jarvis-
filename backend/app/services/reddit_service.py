"""
Reddit Intelligence Service — PRAW data collection + AI analysis pipeline.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reddit import (
    AnalysisStatus,
    RedditPost,
    SentimentLabel,
    SubredditAnalysis,
    TopicDiscovery,
)
from app.schemas.reddit import SubredditAnalyzeRequest
from app.services.ai_service import AIService

logger = structlog.get_logger(__name__)


def _reddit():
    import praw
    return praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
        ratelimit_seconds=settings.REDDIT_REQUEST_DELAY,
    )


class RedditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai = AIService()

    # ─── Main Analysis Pipeline ───────────────────────────────────

    async def run_analysis(
        self, analysis_id: uuid.UUID, request: SubredditAnalyzeRequest
    ) -> None:
        result = await self.db.execute(
            select(SubredditAnalysis).where(SubredditAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            return

        try:
            analysis.status = AnalysisStatus.IN_PROGRESS
            await self.db.commit()

            # 1. Fetch posts from Reddit (blocking I/O → thread pool)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self._fetch_subreddit_data,
                analysis.subreddit_name,
                request.time_period,
                request.post_limit,
            )

            if data.get("error"):
                raise RuntimeError(data["error"])

            # 2. Populate metadata
            meta = data.get("meta", {})
            analysis.subscriber_count = meta.get("subscribers")
            analysis.active_users = meta.get("active_user_count")
            analysis.description = (meta.get("public_description") or "")[:2000]
            analysis.created_utc = meta.get("created_utc")
            posts_raw = data.get("posts", [])
            analysis.posts_analyzed = len(posts_raw)

            # 3. Compute engagement metrics
            if posts_raw:
                scores = [p.get("score", 0) for p in posts_raw]
                comments = [p.get("num_comments", 0) for p in posts_raw]
                analysis.avg_score = sum(scores) / len(scores)
                analysis.avg_comments = sum(comments) / len(comments)
                total_votes = sum(scores)
                total_comments = sum(comments)
                analysis.engagement_rate = (
                    (total_votes + total_comments * 2) / max(analysis.posts_analyzed, 1) / 100
                )

            # 4. Persist posts
            await self._store_posts(analysis_id, posts_raw)
            await self.db.flush()

            # 5. Build AI analysis prompt
            posts_summary = self._build_posts_summary(posts_raw[:75])
            ai_result = await self.ai.analyze_subreddit_posts(
                subreddit=analysis.subreddit_name,
                posts_text=posts_summary,
                subscriber_count=analysis.subscriber_count,
            )

            # 6. Apply AI results
            analysis.ai_summary = ai_result.get("summary", "")
            analysis.key_insights = ai_result.get("key_insights", {})
            analysis.opportunities = ai_result.get("opportunities", {})
            analysis.top_topics = ai_result.get("top_topics", {})
            analysis.trending_keywords = ai_result.get("trending_keywords", {})

            # Sentiment
            sentiment_scores = ai_result.get("sentiment_scores", {})
            analysis.sentiment_scores = sentiment_scores
            pos = sentiment_scores.get("positive", 0)
            neg = sentiment_scores.get("negative", 0)
            if pos > 0.6:
                analysis.overall_sentiment = SentimentLabel.POSITIVE
            elif pos > 0.4:
                analysis.overall_sentiment = SentimentLabel.NEUTRAL
            elif neg > 0.4:
                analysis.overall_sentiment = SentimentLabel.NEGATIVE
            else:
                analysis.overall_sentiment = SentimentLabel.MIXED

            # 7. Persist discovered topics
            for topic_data in ai_result.get("topics", [])[:20]:
                topic = TopicDiscovery(
                    analysis_id=analysis_id,
                    topic_name=topic_data.get("name", "Unknown")[:255],
                    topic_description=topic_data.get("description"),
                    frequency=int(topic_data.get("frequency", 1)),
                    relevance_score=float(topic_data.get("relevance_score", 0.5)),
                    keywords=topic_data.get("keywords"),
                    examples={"posts": topic_data.get("examples", [])[:5]},
                )
                self.db.add(topic)

            analysis.status = AnalysisStatus.COMPLETED
            await self.db.commit()
            logger.info("reddit.analysis.completed", analysis_id=str(analysis_id), posts=analysis.posts_analyzed)

        except Exception as exc:
            logger.error("reddit.analysis.failed", analysis_id=str(analysis_id), error=str(exc))
            try:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = str(exc)[:1000]
                await self.db.commit()
            except Exception:
                pass

    # ─── PRAW Data Collection ─────────────────────────────────────

    def _fetch_subreddit_data(
        self, subreddit_name: str, time_period: str, limit: int
    ) -> Dict[str, Any]:
        try:
            reddit = _reddit()
            sub = reddit.subreddit(subreddit_name)

            # Fetch metadata
            try:
                meta = {
                    "subscribers": sub.subscribers,
                    "active_user_count": sub.active_user_count,
                    "public_description": sub.public_description,
                    "created_utc": sub.created_utc,
                    "over18": sub.over18,
                    "subreddit_type": sub.subreddit_type,
                }
            except Exception:
                meta = {}

            posts = []
            seen_ids = set()

            for submission in sub.top(time_filter=time_period, limit=limit):
                if submission.id in seen_ids:
                    continue
                seen_ids.add(submission.id)

                # Fetch top 3 comments
                top_comments = []
                try:
                    submission.comments.replace_more(limit=0)
                    for comment in list(submission.comments)[:3]:
                        if hasattr(comment, "body"):
                            top_comments.append({
                                "author": str(comment.author) if comment.author else "[deleted]",
                                "body": comment.body[:300],
                                "score": comment.score,
                            })
                except Exception:
                    pass

                posts.append({
                    "id": submission.id,
                    "title": submission.title,
                    "author": str(submission.author) if submission.author else None,
                    "url": submission.url,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "selftext": (submission.selftext or "")[:3000],
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "is_self": submission.is_self,
                    "link_flair_text": submission.link_flair_text,
                    "created_utc": submission.created_utc,
                    "top_comments": top_comments,
                })

            return {"meta": meta, "posts": posts}

        except Exception as exc:
            logger.error("reddit.fetch.failed", subreddit=subreddit_name, error=str(exc))
            return {"error": str(exc), "meta": {}, "posts": []}

    async def _store_posts(
        self, analysis_id: uuid.UUID, posts_raw: List[Dict[str, Any]]
    ) -> None:
        for post_data in posts_raw:
            post = RedditPost(
                analysis_id=analysis_id,
                reddit_id=post_data["id"],
                title=post_data["title"][:2000],
                author=post_data.get("author"),
                url=post_data.get("url"),
                permalink=post_data.get("permalink"),
                selftext=(post_data.get("selftext") or "")[:5000],
                score=post_data.get("score", 0),
                upvote_ratio=post_data.get("upvote_ratio"),
                num_comments=post_data.get("num_comments", 0),
                is_self=post_data.get("is_self", False),
                flair=post_data.get("link_flair_text"),
                created_utc=post_data.get("created_utc"),
                top_comments={"comments": post_data.get("top_comments", [])},
            )
            self.db.add(post)

    def _build_posts_summary(self, posts: List[Dict[str, Any]]) -> str:
        lines = []
        for i, p in enumerate(posts, 1):
            lines.append(
                f"{i}. [{p.get('score', 0)} pts | {p.get('num_comments', 0)} comments] "
                f"{p['title']}"
            )
            if p.get("selftext") and len(p["selftext"]) > 20:
                lines.append(f"   Body: {p['selftext'][:150]}...")
            if p.get("top_comments"):
                for c in p["top_comments"][:2]:
                    lines.append(f"   Comment [{c.get('score',0)}]: {c.get('body','')[:100]}")
        return "\n".join(lines)
