"""
JARVIS Reddit Models — SubredditAnalysis, TopicDiscovery, RedditPost.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SentimentLabel(str, enum.Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"
    MIXED = "mixed"


class SubredditAnalysis(BaseModel):
    """Analysis of a Reddit subreddit."""

    __tablename__ = "subreddit_analyses"
    __table_args__ = {"comment": "Subreddit analysis results"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subreddit_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Subreddit name without r/ prefix",
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum"),
        nullable=False,
        default=AnalysisStatus.PENDING,
        index=True,
    )

    # Subreddit metadata
    subscriber_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_utc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Analysis parameters
    time_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="week",
        comment="Analysis time period: hour, day, week, month, year, all",
    )
    post_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    posts_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Sentiment analysis
    overall_sentiment: Mapped[Optional[SentimentLabel]] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label_enum"),
        nullable=True,
    )
    sentiment_scores: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed sentiment breakdown",
    )

    # Topic analysis
    top_topics: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top topics and their frequency",
    )
    trending_keywords: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Trending keywords with scores",
    )

    # Engagement metrics
    avg_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_comments: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    engagement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # AI insights
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_insights: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    opportunities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Full analysis data
    raw_analysis: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete analysis data",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    posts: Mapped[List["RedditPost"]] = relationship(
        "RedditPost",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    topics: Mapped[List["TopicDiscovery"]] = relationship(
        "TopicDiscovery",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SubredditAnalysis id={self.id} subreddit=r/{self.subreddit_name}>"


class TopicDiscovery(BaseModel):
    """Discovered topic within a subreddit analysis."""

    __tablename__ = "topic_discoveries"
    __table_args__ = {"comment": "Topics discovered within subreddit analyses"}

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddit_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sentiment: Mapped[Optional[SentimentLabel]] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label_enum"),
        nullable=True,
    )
    related_posts_count: Mapped[int] = mapped_column(Integer, default=0)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    examples: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    analysis: Mapped["SubredditAnalysis"] = relationship(
        "SubredditAnalysis", back_populates="topics"
    )


class RedditPost(BaseModel):
    """Individual Reddit post stored during analysis."""

    __tablename__ = "reddit_posts"
    __table_args__ = {"comment": "Reddit posts collected during analysis"}

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddit_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reddit_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Reddit post ID (e.g., t3_abc123)",
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permalink: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selftext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    upvote_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    is_self: Mapped[bool] = mapped_column(default=False)
    flair: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_utc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment: Mapped[Optional[SentimentLabel]] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label_enum"),
        nullable=True,
    )
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    top_comments: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    analysis: Mapped["SubredditAnalysis"] = relationship(
        "SubredditAnalysis", back_populates="posts"
    )

    def __repr__(self) -> str:
        return f"<RedditPost id={self.id} reddit_id={self.reddit_id}>"
