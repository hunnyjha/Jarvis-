"""
Security Intelligence Service — Reddit OSINT + behavioral analysis.
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
from app.models.security import (
    FindingType,
    InvestigationStatus,
    SecurityFinding,
    SecurityInvestigation,
    SeverityLevel,
)
from app.services.ai_service import AIService

logger = structlog.get_logger(__name__)


class SecurityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai = AIService()

    async def run_investigation(
        self, inv_id: uuid.UUID, target: str, inv_type: str
    ) -> None:
        result = await self.db.execute(
            select(SecurityInvestigation).where(SecurityInvestigation.id == inv_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            return

        try:
            inv.status = InvestigationStatus.IN_PROGRESS
            await self.db.commit()

            # Collect raw data
            loop = asyncio.get_event_loop()
            collected = await loop.run_in_executor(
                None, self._collect_account_data, target.lstrip("u/")
            )

            # Behavioral analysis
            behavioral = self._analyze_behavior(collected)

            # AI-powered risk assessment
            full_data = {**collected, "behavioral_analysis": behavioral}
            ai_result = await self.ai.analyze_security_target(target, inv_type, full_data)

            # Apply results
            inv.executive_summary = ai_result.get("executive_summary", "")
            risk_score = float(ai_result.get("risk_score", 0))
            inv.risk_score = min(100.0, max(0.0, risk_score))
            risk_level_str = ai_result.get("risk_level", "low")
            inv.risk_level = self._parse_severity(risk_level_str)
            inv.recommendations = ai_result.get("recommendations", {})
            inv.raw_data = collected
            inv.extra_metadata = {"behavioral_analysis": behavioral}

            # Store findings
            for f_data in ai_result.get("findings", [])[:20]:
                finding = SecurityFinding(
                    investigation_id=inv_id,
                    title=str(f_data.get("title", "Finding"))[:500],
                    description=f_data.get("description"),
                    finding_type=self._parse_finding_type(f_data.get("finding_type")),
                    severity=self._parse_severity(f_data.get("severity", "info")),
                    source="Reddit Public API",
                    evidence=f_data.get("evidence"),
                    confidence_score=float(f_data.get("confidence_score", 0.5)),
                    tags={
                        "alternative_explanations": f_data.get("alternative_explanations", []),
                        "ai_generated": True,
                    },
                )
                self.db.add(finding)

            # Also add behavioral findings directly
            for bf in behavioral.get("flags", []):
                finding = SecurityFinding(
                    investigation_id=inv_id,
                    title=bf.get("title", "Behavioral Flag"),
                    description=bf.get("description"),
                    finding_type=FindingType.BEHAVIORAL_PATTERN,
                    severity=self._parse_severity(bf.get("severity", "info")),
                    source="Automated Behavioral Analysis",
                    evidence=bf.get("evidence"),
                    confidence_score=bf.get("confidence", 0.6),
                    tags={"automated": True},
                )
                self.db.add(finding)

            total_findings = len(ai_result.get("findings", [])) + len(behavioral.get("flags", []))
            inv.findings_count = total_findings
            inv.status = InvestigationStatus.COMPLETED
            await self.db.commit()
            logger.info("security.investigation.completed", inv_id=str(inv_id), findings=total_findings)

        except Exception as exc:
            logger.error("security.investigation.failed", inv_id=str(inv_id), error=str(exc))
            try:
                inv.status = InvestigationStatus.FAILED
                inv.error_message = str(exc)[:1000]
                await self.db.commit()
            except Exception:
                pass

    # ─── Data Collection ──────────────────────────────────────────

    def _collect_account_data(self, username: str) -> Dict[str, Any]:
        """Collect public Reddit data about an account via public JSON API."""
        import httpx
        headers = {"User-Agent": settings.REDDIT_USER_AGENT}
        try:
            with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
                about = client.get(f"https://www.reddit.com/user/{username}/about.json")
                about_data = about.json().get("data", {})
                account_info = {
                    "username": username,
                    "account_created_utc": about_data.get("created_utc"),
                    "comment_karma": about_data.get("comment_karma", 0),
                    "link_karma": about_data.get("link_karma", 0),
                    "is_verified": about_data.get("verified", False),
                    "has_premium": about_data.get("is_gold", False),
                }

                posts_resp = client.get(f"https://www.reddit.com/user/{username}/submitted.json?limit=50")
                posts_children = posts_resp.json().get("data", {}).get("children", [])
                posts: List[Dict[str, Any]] = []
                subreddits_posted: Dict[str, int] = {}
                for child in posts_children:
                    p = child.get("data", {})
                    sr = p.get("subreddit", "unknown")
                    subreddits_posted[sr] = subreddits_posted.get(sr, 0) + 1
                    posts.append({
                        "title": p.get("title", ""),
                        "subreddit": sr,
                        "score": p.get("score", 0),
                        "created_utc": p.get("created_utc"),
                        "url": f"https://reddit.com{p.get('permalink', '')}",
                    })

                comments_resp = client.get(f"https://www.reddit.com/user/{username}/comments.json?limit=100")
                comments_children = comments_resp.json().get("data", {}).get("children", [])
                comments: List[Dict[str, Any]] = []
                subreddits_commented: Dict[str, int] = {}
                for child in comments_children:
                    c = child.get("data", {})
                    sr = c.get("subreddit", "unknown")
                    subreddits_commented[sr] = subreddits_commented.get(sr, 0) + 1
                    comments.append({
                        "body": (c.get("body") or "")[:300],
                        "subreddit": sr,
                        "score": c.get("score", 0),
                        "created_utc": c.get("created_utc"),
                    })

                all_timestamps = sorted(
                    [p["created_utc"] for p in posts if p.get("created_utc")] +
                    [c["created_utc"] for c in comments if c.get("created_utc")]
                )
                return {
                    **account_info,
                    "posts_sample": posts[:25],
                    "comments_sample": comments[:50],
                    "subreddits_posted": subreddits_posted,
                    "subreddits_commented": subreddits_commented,
                    "total_subreddits_active": len(set(subreddits_posted) | set(subreddits_commented)),
                    "activity_timestamps": all_timestamps[:100],
                    "collection_timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as exc:
            logger.warning("security.collection_failed", username=username, error=str(exc))
            return {
                "username": username,
                "error": str(exc),
                "collection_timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # ─── Behavioral Analysis ──────────────────────────────────────

    def _analyze_behavior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based behavioral analysis for common red flags."""
        flags: List[Dict[str, Any]] = []
        metrics: Dict[str, Any] = {}

        posts = data.get("posts_sample", [])
        comments = data.get("comments_sample", [])
        subreddits_posted = data.get("subreddits_posted", {})
        subreddits_commented = data.get("subreddits_commented", {})
        timestamps = data.get("activity_timestamps", [])

        # Metric: subreddit concentration
        if subreddits_posted:
            total_posts = sum(subreddits_posted.values())
            max_posts_one_sr = max(subreddits_posted.values())
            concentration = max_posts_one_sr / max(total_posts, 1)
            metrics["post_concentration"] = round(concentration, 2)
            if concentration > 0.8 and total_posts > 10:
                top_sr = max(subreddits_posted, key=subreddits_posted.get)
                flags.append({
                    "title": f"High post concentration in r/{top_sr}",
                    "description": f"{concentration*100:.0f}% of posts are in one subreddit",
                    "severity": "medium",
                    "confidence": 0.7,
                    "evidence": {"concentration": concentration, "subreddit": top_sr},
                })

        # Metric: comment/karma ratio
        comment_karma = data.get("comment_karma", 0)
        link_karma = data.get("link_karma", 0)
        if link_karma > 10000 and comment_karma < 100:
            flags.append({
                "title": "Unusually high link karma with low comment karma",
                "description": "May indicate vote manipulation or single-purpose posting account",
                "severity": "medium",
                "confidence": 0.6,
                "evidence": {"link_karma": link_karma, "comment_karma": comment_karma},
            })

        # Metric: temporal clustering
        if len(timestamps) >= 10:
            clusters = self._detect_burst_activity(timestamps)
            metrics["burst_clusters"] = clusters
            if clusters > 3:
                flags.append({
                    "title": "Burst activity patterns detected",
                    "description": f"Activity appears in {clusters} concentrated time bursts",
                    "severity": "low",
                    "confidence": 0.55,
                    "evidence": {"burst_count": clusters},
                })

        # Metric: account age vs karma
        created_utc = data.get("account_created_utc")
        if created_utc:
            age_days = (datetime.now(timezone.utc).timestamp() - created_utc) / 86400
            total_karma = comment_karma + link_karma
            if age_days < 30 and total_karma > 5000:
                flags.append({
                    "title": "New account with unusually high karma",
                    "description": f"Account is {age_days:.0f} days old with {total_karma} karma",
                    "severity": "high",
                    "confidence": 0.75,
                    "evidence": {"age_days": round(age_days, 1), "total_karma": total_karma},
                })
            metrics["account_age_days"] = round(age_days, 1)

        return {
            "flags": flags,
            "metrics": metrics,
            "risk_indicators": len(flags),
        }

    def _detect_burst_activity(self, timestamps: List[float]) -> int:
        """Count temporal activity clusters (bursts within 1-hour windows)."""
        if not timestamps:
            return 0
        clusters = 1
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] > 3600:
                clusters += 1
        return clusters

    # ─── Enum Parsers ─────────────────────────────────────────────

    @staticmethod
    def _parse_severity(value: Optional[str]) -> SeverityLevel:
        valid = {e.value for e in SeverityLevel}
        return SeverityLevel(value) if value in valid else SeverityLevel.INFO

    @staticmethod
    def _parse_finding_type(value: Optional[str]) -> FindingType:
        valid = {e.value for e in FindingType}
        return FindingType(value) if value in valid else FindingType.BEHAVIORAL_PATTERN
