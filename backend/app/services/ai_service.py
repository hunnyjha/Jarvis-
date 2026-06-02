"""AI Service — wraps Google Gemini for all intelligence tasks."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)


class AIService:
    def __init__(self) -> None:
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def _complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """Base completion call."""
        prompt = f"{system}\n\n{user}"
        response = await self.model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=settings.AI_TEMPERATURE,
            ),
        )
        return response.text

    async def _complete_json(self, system: str, user: str, max_tokens: int = 4096) -> Dict[str, Any]:
        """Completion that parses JSON response."""
        system_with_json = system + "\n\nYou MUST respond with valid JSON only. No explanations outside the JSON."
        raw = await self._complete(system_with_json, user, max_tokens)
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
        except json.JSONDecodeError:
            logger.warning("ai.json_parse_failed", raw=raw[:200])
            return {}

    async def analyze_subreddit_posts(
        self, subreddit: str, posts_text: str, subscriber_count: Optional[int]
    ) -> Dict[str, Any]:
        system = """You are JARVIS, an expert Reddit intelligence analyst.
Analyze subreddit data and return structured insights.
Think critically. Identify real patterns, risks, and opportunities.
Do not make assumptions without evidence."""

        user = f"""Analyze r/{subreddit} with {subscriber_count or 'unknown'} subscribers.

Top posts:
{posts_text}

Return JSON with this exact structure:
{{
  "summary": "2-3 sentence executive summary of the community",
  "key_insights": {{
    "community_health": "assessment",
    "growth_trajectory": "assessment",
    "content_quality": "assessment",
    "engagement_patterns": "assessment"
  }},
  "opportunities": {{
    "content_gaps": ["gap1", "gap2"],
    "growth_opportunities": ["opp1", "opp2"],
    "timing_insights": "when to post"
  }},
  "top_topics": {{"topic": 1}},
  "trending_keywords": {{"keyword": 0.8}},
  "sentiment_scores": {{
    "positive": 0.0,
    "neutral": 0.0,
    "negative": 0.0
  }},
  "topics": [
    {{
      "name": "topic name",
      "description": "what this topic is about",
      "frequency": 5,
      "relevance_score": 0.8,
      "keywords": {{"kw": 1}},
      "examples": ["post title example"]
    }}
  ],
  "risks": ["risk1", "risk2"]
}}"""
        return await self._complete_json(system, user)

    async def analyze_security_target(self, target: str, inv_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        system = """You are JARVIS Security Intelligence.
Analyze Reddit accounts and communities for suspicious behavior patterns.
Be factual and evidence-based. Never make unsupported claims.
For every finding, provide confidence level and alternative explanations."""

        user = f"""Security investigation of: {target}
Type: {inv_type}
Collected data: {json.dumps(data, default=str)[:3000]}

Return JSON:
{{
  "executive_summary": "summary of findings",
  "risk_score": 45,
  "risk_level": "medium",
  "findings": [
    {{
      "title": "finding title",
      "description": "detailed description",
      "finding_type": "behavioral_pattern",
      "severity": "medium",
      "evidence": {{"key": "value"}},
      "confidence_score": 0.75,
      "alternative_explanations": ["explanation1"]
    }}
  ],
  "recommendations": {{
    "immediate": ["action1"],
    "monitoring": ["action1"],
    "escalation_criteria": "when to escalate"
  }}
}}"""
        return await self._complete_json(system, user)

    async def research_query(
        self, query: str, sources: List[Dict[str, Any]], research_type: str = "web_search"
    ) -> Dict[str, Any]:
        system = """You are JARVIS Research Intelligence.
Synthesize multiple sources into actionable intelligence.
Sources are labeled by tier (Reddit Tier 2, Hacker News Tier 3, Google Trends Tier 5, Industry Blogs Tier 7).
Separate facts from assumptions. Cite sources. Rate confidence.
Think critically and identify blind spots."""

        sources_text = "\n\n".join(
            f"[{s.get('source', 'unknown')}] {s.get('title', '')} — {s.get('snippet', s.get('content', ''))[:400]}"
            for i, s in enumerate(sources[:15])
        )

        user = f"""Research query: {query}
Research type: {research_type}

Sources gathered across intelligence tiers:
{sources_text}

Return JSON:
{{
  "summary": "executive summary",
  "key_findings": ["finding1", "finding2"],
  "facts": ["confirmed fact1"],
  "assumptions": ["assumption with caveats"],
  "confidence_rating": 0.8,
  "gaps": ["what we don't know"],
  "recommendations": ["next action"],
  "sources_used": {len(sources)}
}}"""
        return await self._complete_json(system, user)

    async def analyze_viral_opportunities(
        self, query: str, sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        system = """You are JARVIS Viral Content Intelligence.
You identify viral opportunities across Reddit, Hacker News, Google Trends, and industry blogs.

Viral content patterns that generate engagement:
- Controversy, leaks, lawsuits, exploits, bans
- AI replacing people, algorithm changes
- Billion-dollar acquisitions, creator drama
- Platform mistakes, security issues
- Breaking product launches

Content structure for maximum engagement:
[PLATFORM] JUST DID SOMETHING INSANE
Short explanation.
• Bullet point 1
• Bullet point 2
• Bullet point 3
Strong closing line.

Look for stories appearing on Tier 1-3 sources that haven't yet reached mainstream Reddit — those are 6-48 hour windows."""

        sources_text = "\n".join(
            f"[{s.get('tier', 'unknown').upper()} | Score: {s.get('viral_signals', 0)} signals] "
            f"{s.get('title', '')} — {s.get('source', '')}"
            for s in sources[:20]
        )

        user = f"""Viral opportunity scan for topic: {query}

Stories detected across intelligence tiers:
{sources_text}

Return JSON:
{{
  "top_opportunities": [
    {{
      "title": "original story title",
      "viral_angle": "how to reframe this for maximum engagement",
      "suggested_headline": "[PLATFORM] JUST DID SOMETHING INSANE",
      "content_structure": {{
        "hook": "first line that grabs attention",
        "bullets": ["point 1", "point 2", "point 3", "point 4"],
        "closing": "strong closing line"
      }},
      "best_subreddits": ["r/sub1", "r/sub2"],
      "urgency": "high|medium|low",
      "viral_signals": ["controversy", "AI", "ban"],
      "tier_source": "Hacker News Tier 3"
    }}
  ],
  "trending_themes": ["theme1", "theme2"],
  "best_posting_window": "description of timing",
  "summary": "2-3 sentence overview of what's hot right now"
}}"""
        return await self._complete_json(system, user)

    async def generate_strategy(self, context: str, options: List[str]) -> Dict[str, Any]:
        system = """You are JARVIS Strategy Intelligence.
Analyze options critically. Challenge assumptions. Identify risks.
Structure advice as evidence-based options with clear tradeoffs."""

        user = f"""Strategic decision context:
{context}

Options to evaluate: {json.dumps(options)}

Return JSON:
{{
  "analysis": "situation assessment",
  "options": [
    {{
      "name": "Option A",
      "description": "what this entails",
      "pros": ["pro1", "pro2"],
      "cons": ["con1", "con2"],
      "risks": ["risk1"],
      "effort": "low|medium|high",
      "impact": "low|medium|high",
      "timeline": "estimate"
    }}
  ],
  "recommendation": {{
    "choice": "Option A",
    "reasoning": "why this is best",
    "conditions": "when this recommendation changes",
    "first_steps": ["step1", "step2"]
  }},
  "risks_to_watch": ["risk1"],
  "assumptions_challenged": ["assumption1"]
}}"""
        return await self._complete_json(system, user)

    async def chat_response(
        self, message: str, context: Optional[Dict[str, Any]], memories: List[str]
    ) -> Dict[str, Any]:
        memory_context = "\n".join(f"- {m}" for m in memories[:5]) if memories else "No relevant memories found."

        system = f"""You are JARVIS, a personal AI intelligence operating system for Reddit community builders and growth strategists.

You are NOT a chatbot. You are an intelligence system that:
- Researches and analyzes Reddit communities
- Discovers trends and viral opportunities
- Investigates security threats
- Remembers everything the user has told you
- Makes evidence-based recommendations

Relevant memories from past sessions:
{memory_context}

Current context: {json.dumps(context or {}, default=str)}

Think critically. Challenge assumptions when warranted. Be specific and actionable.
Identify which agents you're using (research, reddit, security, strategy, memory, report)."""

        response_text = await self._complete(system, message)
        return {
            "message": response_text,
            "agent_used": "orchestrator",
        }
