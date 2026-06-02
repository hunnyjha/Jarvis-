"""
JARVIS Reddit Service — Subreddit analysis using asyncpraw and Claude AI.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpraw
import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RedditAPIError
from app.models.reddit import AnalysisStatus, RedditPost, SentimentLabel, SubredditAnalysis, TopicDiscovery

logger = structlog.get_logger(__name__)


class RedditService:
    """Service for Reddit data collection and AI analysis."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._reddit: Optional[asyncpraw.Reddit] = None

    def _get_reddit(self) -> asyncpraw.Reddit:
        if self._reddit is None:
            self._reddit = asyncpraw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT,
                username=settings.REDDIT_USERNAME,
                password=settings.REDDIT_PASSWORD,
            )
        return self._reddit

    async def analyze_subreddit(
        self,
        db: AsyncSession,
        analysis_id: uuid.UUID,
        subreddit_name: str,
        time_period: str,
        post_limit: int,
    ) -> None:
        """Full subreddit analysis pipeline."""
        self.db = db

        await db.execute(
            update(SubredditAnalysis)
            .where(SubredditAnalysis.id == analysis_id)
            .values(status=AnalysisStatus.IN_PROGRESS)
        )
        await db.commit()

        try:
            reddit = self._get_reddit()
            subreddit = await reddit.subreddit(subreddit_name)

            # Fetch subreddit metadata
            await subreddit.load()
            sub_meta = {
                "subscriber_count": subreddit.subscribers,
                "active_users": subreddit.active_user_count,
                "description": subreddit.public_description[:500] if subreddit.public_description else None,
                "created_utc": subreddit.created_utc,
            }

            # Fetch posts
            posts_data: List[Dict[str, Any]] = []
            async for post in subreddit.top(time_filter=time_period, limit=post_limit):
                posts_data.append({
                    "reddit_id": post.id,
                    "title": post.title,
                    "author": str(post.author) if post.author else "[deleted]",
                    "url": post.url,
                    "permalink": f"https://reddit.com{post.permalink}",
                    "selftext": post.selftext[:2000] if post.selftext else None,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "is_self": post.is_self,
                    "flair": post.link_flair_text,
                    "created_utc": post.created_utc,
                })
                await asyncio.sleep(settings.REDDIT_REQUEST_DELAY)

            await reddit.close()

            # AI Analysis
            ai_analysis = await self._analyze_with_ai(subreddit_name, posts_data)

            # Store posts
            post_models = [
                RedditPost(
                    analysis_id=analysis_id,
                    reddit_id=p["reddit_id"],
                    title=p["title"],
                    author=p.get("author"),
                    url=p.get("url"),
                    permalink=p.get("permalink"),
                    selftext=p.get("selftext"),
                    score=p["score"],
                    upvote_ratio=p.get("upvote_ratio"),
                    num_comments=p["num_comments"],
                    is_self=p["is_self"],
                    flair=p.get("flair"),
                    created_utc=p.get("created_utc"),
                    sentiment=ai_analysis.get("post_sentiments", {}).get(p["reddit_id"]),
                )
                for p in posts_data
            ]
            db.add_all(post_models)

            # Store topics
            topics = ai_analysis.get("topics", [])
            topic_models = [
                TopicDiscovery(
                    analysis_id=analysis_id,
                    topic_name=t["name"],
                    topic_description=t.get("description"),
                    frequency=t.get("frequency", 0),
                    relevance_score=t.get("relevance_score", 0.5),
                    sentiment=t.get("sentiment"),
                    related_posts_count=t.get("related_posts_count", 0),
                    keywords=t.get("keywords"),
                    examples=t.get("examples"),
                )
                for t in topics
            ]
            db.add_all(topic_models)

            # Update analysis record
            await db.execute(
                update(SubredditAnalysis)
                .where(SubredditAnalysis.id == analysis_id)
                .values(
                    status=AnalysisStatus.COMPLETED,
                    posts_analyzed=len(posts_data),
                    subscriber_count=sub_meta.get("subscriber_count"),
                    active_users=sub_meta.get("active_users"),
                    description=sub_meta.get("description"),
                    created_utc=sub_meta.get("created_utc"),
                    overall_sentiment=ai_analysis.get("overall_sentiment"),
                    sentiment_scores=ai_analysis.get("sentiment_scores"),
                    top_topics=ai_analysis.get("top_topics"),
                    trending_keywords=ai_analysis.get("trending_keywords"),
                    avg_score=ai_analysis.get("avg_score"),
                    avg_comments=ai_analysis.get("avg_comments"),
                    engagement_rate=ai_analysis.get("engagement_rate"),
                    ai_summary=ai_analysis.get("summary"),
                    key_insights=ai_analysis.get("key_insights"),
                    opportunities=ai_analysis.get("opportunities"),
                )
            )
            await db.commit()
            logger.info("reddit.analysis.completed", analysis_id=str(analysis_id))

        except Exception as exc:
            logger.error("reddit.analysis.failed", analysis_id=str(analysis_id), error=str(exc))
            await db.execute(
                update(SubredditAnalysis)
                .where(SubredditAnalysis.id == analysis_id)
                .values(status=AnalysisStatus.FAILED, error_message=str(exc))
            )
            await db.commit()
            raise

    async def _analyze_with_ai(
        self, subreddit_name: str, posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use Claude AI to analyze posts and extract insights."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        posts_text = "\n".join([
            f"- [{p['score']}↑ | {p['num_comments']} comments] {p['title']}"
            for p in posts[:50]
        ])

        if posts:
            avg_score = sum(p["score"] for p in posts) / len(posts)
            avg_comments = sum(p["num_comments"] for p in posts) / len(posts)
        else:
            avg_score = avg_comments = 0

        prompt = f"""Analyze the following Reddit posts from r/{subreddit_name} and provide a structured JSON analysis.

Posts (format: [score | comments] title):
{posts_text}

Provide a JSON response with these fields:
{{
    "overall_sentiment": "positive|negative|neutral|mixed",
    "sentiment_scores": {{"positive": 0.0, "negative": 0.0, "neutral": 0.0}},
    "summary": "2-3 sentence summary of the subreddit's current state",
    "top_topics": {{"topic_name": frequency_count}},
    "trending_keywords": {{"keyword": relevance_score}},
    "key_insights": ["insight1", "insight2", "insight3"],
    "opportunities": ["opportunity1", "opportunity2"],
    "topics": [
        {{
            "name": "topic_name",
            "description": "brief description",
            "frequency": 10,
            "relevance_score": 0.8,
            "sentiment": "positive|negative|neutral",
            "related_posts_count": 5,
            "keywords": {{"kw": score}},
            "examples": ["example post title"]
        }}
    ]
}}

Respond with valid JSON only."""

        try:
            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            content = response.content[0].text
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
            else:
                result = {}
        except Exception as e:
            logger.warning("AI analysis failed, using defaults", error=str(e))
            result = {
                "overall_sentiment": "neutral",
                "sentiment_scores": {"positive": 0.33, "negative": 0.33, "neutral": 0.34},
                "summary": f"Analysis of r/{subreddit_name} with {len(posts)} posts.",
                "top_topics": {},
                "trending_keywords": {},
                "key_insights": [],
                "opportunities": [],
                "topics": [],
            }

        result["avg_score"] = avg_score
        result["avg_comments"] = avg_comments
        result["engagement_rate"] = avg_comments / max(avg_score, 1) if avg_score else 0
        return result

    async def analyze_post_by_url(
        self, post_url: str, include_comments: bool = True, max_comments: int = 50
    ) -> Dict[str, Any]:
        """Analyze a specific Reddit post by URL."""
        import anthropic

        reddit = self._get_reddit()
        try:
            submission = await reddit.submission(url=post_url)
            await submission.load()

            post_data: Dict[str, Any] = {
                "id": submission.id,
                "title": submission.title,
                "author": str(submission.author) if submission.author else "[deleted]",
                "url": submission.url,
                "score": submission.score,
                "upvote_ratio": submission.upvote_ratio,
                "num_comments": submission.num_comments,
                "selftext": submission.selftext[:3000] if submission.selftext else None,
                "flair": submission.link_flair_text,
                "created_utc": submission.created_utc,
            }

            comments_data: List[Dict[str, Any]] = []
            if include_comments:
                await submission.comments.replace_more(limit=0)
                for comment in submission.comments.list()[:max_comments]:
                    comments_data.append({
                        "id": comment.id,
                        "author": str(comment.author) if comment.author else "[deleted]",
                        "body": comment.body[:500],
                        "score": comment.score,
                    })

            await reddit.close()

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            prompt = f"""Analyze this Reddit post and its comments:

Title: {post_data['title']}
Score: {post_data['score']} | Comments: {post_data['num_comments']}
Content: {post_data.get('selftext', 'N/A')[:1000]}

Top comments:
{chr(10).join([f"- [{c['score']}] {c['body']}" for c in comments_data[:20]])}

Provide JSON with: sentiment, main_themes (list), key_takeaways (list), engagement_analysis, controversy_score (0-1)."""

            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            content = response.content[0].text
            start = content.find("{")
            end = content.rfind("}") + 1
            ai_result = json.loads(content[start:end]) if start >= 0 and end > start else {}

            return {
                "post": post_data,
                "comments": comments_data[:20],
                "ai_analysis": ai_result,
            }

        except Exception as exc:
            await reddit.close()
            raise RedditAPIError(f"Failed to analyze post: {str(exc)}", endpoint=post_url)

    async def run_analysis(self, analysis_id: uuid.UUID, request: Any) -> None:
        """Compatibility wrapper for background task."""
        await self.analyze_subreddit(
            db=self.db,
            analysis_id=analysis_id,
            subreddit_name=request.subreddit_name,
            time_period=request.time_period,
            post_limit=request.post_limit,
        )
