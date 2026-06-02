"""Reddit analysis Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.reddit import AnalysisStatus, SentimentLabel


class SubredditAnalyzeRequest(BaseModel):
    subreddit_name: str = Field(min_length=1, max_length=100)
    time_period: str = Field(default="week", pattern=r"^(hour|day|week|month|year|all)$")
    post_limit: int = Field(default=100, ge=10, le=500)


class TopicDiscoverySchema(BaseModel):
    id: UUID
    topic_name: str
    topic_description: Optional[str]
    frequency: int
    relevance_score: float
    sentiment: Optional[SentimentLabel]
    related_posts_count: int
    keywords: Optional[Dict[str, Any]]
    examples: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class RedditPostSchema(BaseModel):
    id: UUID
    reddit_id: str
    title: str
    author: Optional[str]
    url: Optional[str]
    permalink: Optional[str]
    score: int
    upvote_ratio: Optional[float]
    num_comments: int
    is_self: bool
    flair: Optional[str]
    created_utc: Optional[float]
    sentiment: Optional[SentimentLabel]
    ai_analysis: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True}


class SubredditAnalysisResponse(BaseModel):
    id: UUID
    user_id: UUID
    subreddit_name: str
    status: AnalysisStatus
    subscriber_count: Optional[int]
    active_users: Optional[int]
    description: Optional[str]
    time_period: str
    posts_analyzed: int
    overall_sentiment: Optional[SentimentLabel]
    sentiment_scores: Optional[Dict[str, Any]]
    top_topics: Optional[Dict[str, Any]]
    trending_keywords: Optional[Dict[str, Any]]
    avg_score: Optional[float]
    avg_comments: Optional[float]
    engagement_rate: Optional[float]
    ai_summary: Optional[str]
    key_insights: Optional[Dict[str, Any]]
    opportunities: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubredditAnalysisDetail(SubredditAnalysisResponse):
    posts: List[RedditPostSchema] = []
    topics: List[TopicDiscoverySchema] = []


class TopicDiscoverRequest(BaseModel):
    subreddit_name: str = Field(min_length=1, max_length=100)
    time_period: str = Field(default="month", pattern=r"^(hour|day|week|month|year|all)$")
    min_posts: int = Field(default=5, ge=1)
