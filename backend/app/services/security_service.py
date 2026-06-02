"""
JARVIS Security Service — OSINT investigation and Reddit account scanning.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.security import (
    FindingType,
    InvestigationStatus,
    SecurityFinding,
    SecurityInvestigation,
    SeverityLevel,
)

logger = structlog.get_logger(__name__)


class SecurityService:
    """Service for OSINT investigations and security analysis."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_investigation(
        self, inv_id: uuid.UUID, target: str, inv_type: str
    ) -> None:
        """Run a full security investigation."""
        await self.db.execute(
            update(SecurityInvestigation)
            .where(SecurityInvestigation.id == inv_id)
            .values(status=InvestigationStatus.IN_PROGRESS)
        )
        await self.db.commit()

        try:
            findings: List[Dict[str, Any]] = []

            if inv_type == "account_scan":
                findings = await self._scan_reddit_account(target)
            elif inv_type == "osint_collection":
                findings = await self._collect_osint(target)
            else:
                findings = await self._general_investigation(target)

            # Calculate risk score
            severity_weights = {
                "critical": 100, "high": 70, "medium": 40, "low": 20, "info": 5
            }
            risk_score = 0.0
            if findings:
                total_weight = sum(severity_weights.get(f.get("severity", "info"), 5) for f in findings)
                risk_score = min(100.0, total_weight / len(findings) * (len(findings) / 10))

            risk_level = (
                SeverityLevel.CRITICAL if risk_score >= 80
                else SeverityLevel.HIGH if risk_score >= 60
                else SeverityLevel.MEDIUM if risk_score >= 40
                else SeverityLevel.LOW if risk_score >= 20
                else SeverityLevel.INFO
            )

            # Store findings
            finding_models = [
                SecurityFinding(
                    investigation_id=inv_id,
                    title=f["title"],
                    description=f.get("description"),
                    finding_type=f.get("finding_type", FindingType.BEHAVIORAL_PATTERN),
                    severity=f.get("severity", SeverityLevel.INFO),
                    source=f.get("source"),
                    source_url=f.get("source_url"),
                    evidence=f.get("evidence"),
                    confidence_score=f.get("confidence_score", 0.7),
                )
                for f in findings
            ]
            self.db.add_all(finding_models)

            # AI executive summary
            exec_summary = await self._generate_executive_summary(target, findings)

            await self.db.execute(
                update(SecurityInvestigation)
                .where(SecurityInvestigation.id == inv_id)
                .values(
                    status=InvestigationStatus.COMPLETED,
                    findings_count=len(findings),
                    risk_score=risk_score,
                    risk_level=risk_level,
                    executive_summary=exec_summary,
                    recommendations={"steps": self._get_recommendations(risk_level, findings)},
                )
            )
            await self.db.commit()
            logger.info("security.investigation.completed", inv_id=str(inv_id))

        except Exception as exc:
            logger.error("security.investigation.failed", inv_id=str(inv_id), error=str(exc))
            await self.db.execute(
                update(SecurityInvestigation)
                .where(SecurityInvestigation.id == inv_id)
                .values(status=InvestigationStatus.FAILED, error_message=str(exc))
            )
            await self.db.commit()
            raise

    async def _scan_reddit_account(self, username: str) -> List[Dict[str, Any]]:
        """Collect and analyze a Reddit account's public data."""
        import asyncpraw
        from datetime import datetime, timezone

        findings: List[Dict[str, Any]] = []
        username = username.lstrip("u/").lstrip("/")

        try:
            reddit = asyncpraw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT,
            )

            redditor = await reddit.redditor(username)
            await redditor.load()

            # Account age analysis
            account_age_days = (datetime.now(timezone.utc).timestamp() - redditor.created_utc) / 86400
            if account_age_days < 30:
                findings.append({
                    "title": "New Account",
                    "description": f"Account is only {int(account_age_days)} days old",
                    "finding_type": FindingType.RISK_INDICATOR,
                    "severity": SeverityLevel.MEDIUM,
                    "source": "Reddit",
                    "evidence": {"age_days": account_age_days},
                    "confidence_score": 0.95,
                })

            # Karma analysis
            findings.append({
                "title": "Account Karma Summary",
                "description": f"Post karma: {redditor.link_karma}, Comment karma: {redditor.comment_karma}",
                "finding_type": FindingType.SOCIAL_PRESENCE,
                "severity": SeverityLevel.INFO,
                "source": "Reddit",
                "source_url": f"https://reddit.com/u/{username}",
                "evidence": {
                    "link_karma": redditor.link_karma,
                    "comment_karma": redditor.comment_karma,
                    "account_age_days": account_age_days,
                },
                "confidence_score": 1.0,
            })

            # Recent posts
            posts = []
            async for submission in redditor.submissions.new(limit=25):
                posts.append({
                    "title": submission.title,
                    "subreddit": str(submission.subreddit),
                    "score": submission.score,
                    "url": f"https://reddit.com{submission.permalink}",
                })

            if posts:
                subreddits = list(set(p["subreddit"] for p in posts))
                findings.append({
                    "title": "Active Subreddits",
                    "description": f"Posts in {len(subreddits)} subreddits",
                    "finding_type": FindingType.BEHAVIORAL_PATTERN,
                    "severity": SeverityLevel.INFO,
                    "source": "Reddit",
                    "evidence": {"subreddits": subreddits, "post_count": len(posts)},
                    "confidence_score": 0.9,
                })

            await reddit.close()

        except Exception as e:
            logger.warning("Reddit account scan failed", username=username, error=str(e))
            findings.append({
                "title": "Scan Error",
                "description": f"Could not fully scan account: {str(e)}",
                "finding_type": FindingType.ANOMALY,
                "severity": SeverityLevel.LOW,
                "source": "JARVIS",
                "confidence_score": 0.5,
            })

        return findings

    async def _collect_osint(self, target: str) -> List[Dict[str, Any]]:
        """Collect OSINT data about a target."""
        findings: List[Dict[str, Any]] = []

        # Basic presence check via web search
        from app.services.research_service import ResearchService
        research = ResearchService(None)
        results = await research.web_search(query=target, max_results=10)

        if results:
            findings.append({
                "title": "Web Presence",
                "description": f"Found {len(results)} web references to the target",
                "finding_type": FindingType.SOCIAL_PRESENCE,
                "severity": SeverityLevel.INFO,
                "source": "Web Search",
                "evidence": {"results": results[:5]},
                "confidence_score": 0.7,
            })

        return findings

    async def _general_investigation(self, target: str) -> List[Dict[str, Any]]:
        """General investigation combining multiple sources."""
        findings = await self._collect_osint(target)
        if target.startswith("u/") or "/" not in target:
            reddit_findings = await self._scan_reddit_account(target.lstrip("u/"))
            findings.extend(reddit_findings)
        return findings

    async def _generate_executive_summary(
        self, target: str, findings: List[Dict[str, Any]]
    ) -> str:
        """Generate an AI executive summary of the investigation."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        findings_text = "\n".join([
            f"- [{f.get('severity', 'info').upper()}] {f['title']}: {f.get('description', '')}"
            for f in findings
        ])

        try:
            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": f"""Write a 2-3 sentence executive summary of this security investigation.

Target: {target}
Findings:
{findings_text}

Be concise, professional, and factual.""",
                }],
            )
            return response.content[0].text.strip()
        except Exception:
            return f"Investigation of {target} completed. Found {len(findings)} items requiring attention."

    def _get_recommendations(
        self, risk_level: SeverityLevel, findings: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on risk level."""
        recommendations = ["Document and monitor the target's online activity"]

        if risk_level in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            recommendations.extend([
                "Consider escalating to appropriate authorities",
                "Implement additional monitoring measures",
                "Review access controls and security policies",
            ])
        elif risk_level == SeverityLevel.MEDIUM:
            recommendations.extend([
                "Continue monitoring for escalating behavior",
                "Review any shared information or access",
            ])
        else:
            recommendations.append("No immediate action required — maintain awareness")

        return recommendations
