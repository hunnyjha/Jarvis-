"""
JARVIS Report Service — Generate PDF/Markdown/HTML reports.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.report import Report, ReportFormat, ReportStatus

logger = structlog.get_logger(__name__)


class ReportService:
    """Service for generating and managing reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(self, report_id: uuid.UUID, payload: Any) -> None:
        """Generate a report based on the request payload."""
        try:
            # Fetch report record
            from sqlalchemy import select
            result = await self.db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                logger.error("Report not found for generation", report_id=str(report_id))
                return

            # Gather source data
            content = await self._gather_content(report, payload)

            # Generate AI narrative
            ai_content = await self._generate_ai_narrative(report.title, content)

            # Render to file
            file_path = await self._render_report(report_id, report.format, ai_content, content)

            # Update report record
            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            await self.db.execute(
                update(Report)
                .where(Report.id == report_id)
                .values(
                    status=ReportStatus.COMPLETED,
                    content=content,
                    file_path=file_path,
                    file_size_bytes=file_size,
                    executive_summary=ai_content.get("executive_summary"),
                    extra_metadata={"ai_model": settings.ANTHROPIC_MODEL},
                )
            )
            await self.db.commit()
            logger.info("report.generation.completed", report_id=str(report_id))

        except Exception as exc:
            logger.error("report.generation.failed", report_id=str(report_id), error=str(exc))
            await self.db.execute(
                update(Report)
                .where(Report.id == report_id)
                .values(status=ReportStatus.FAILED, error_message=str(exc))
            )
            await self.db.commit()

    async def _gather_content(self, report: Report, payload: Any) -> Dict[str, Any]:
        """Gather data from the source entity."""
        from sqlalchemy import select

        content: Dict[str, Any] = {
            "title": report.title,
            "report_type": str(report.report_type),
            "source_id": str(report.source_id) if report.source_id else None,
        }

        if report.source_id:
            # Try to find the source data
            source_id_str = report.source_id

            # Try SubredditAnalysis
            try:
                from app.models.reddit import SubredditAnalysis
                from sqlalchemy.orm import selectinload
                r = await self.db.execute(
                    select(SubredditAnalysis)
                    .options(selectinload(SubredditAnalysis.posts), selectinload(SubredditAnalysis.topics))
                    .where(SubredditAnalysis.id == source_id_str)
                )
                src = r.scalar_one_or_none()
                if src:
                    content["subreddit_analysis"] = {
                        "subreddit": src.subreddit_name,
                        "posts_analyzed": src.posts_analyzed,
                        "overall_sentiment": str(src.overall_sentiment) if src.overall_sentiment else None,
                        "ai_summary": src.ai_summary,
                        "key_insights": src.key_insights,
                        "top_topics": src.top_topics,
                        "trending_keywords": src.trending_keywords,
                        "opportunities": src.opportunities,
                    }
            except Exception:
                pass

        return content

    async def _generate_ai_narrative(
        self, title: str, content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use Claude to write the report narrative."""
        import anthropic
        import json

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        content_summary = json.dumps(content, indent=2)[:3000]

        try:
            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": f"""Write a professional intelligence report for: "{title}"

Data:
{content_summary}

Return JSON with:
{{
    "executive_summary": "2-3 paragraph executive summary",
    "key_findings": ["finding1", "finding2"],
    "analysis": "detailed analysis section (3-4 paragraphs)",
    "conclusions": "conclusions section",
    "recommendations": ["recommendation1", "recommendation2"]
}}""",
                }],
            )
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end]) if start >= 0 else {"executive_summary": text[:500]}
        except Exception as e:
            logger.warning("AI report generation failed", error=str(e))
            return {"executive_summary": f"Report generated for: {title}"}

    async def _render_report(
        self,
        report_id: uuid.UUID,
        format: ReportFormat,
        ai_content: Dict[str, Any],
        data_content: Dict[str, Any],
    ) -> str:
        """Render the report to a file."""
        import json
        import markdown

        reports_dir = Path(settings.REPORTS_DIR)
        reports_dir.mkdir(parents=True, exist_ok=True)

        if format == ReportFormat.MARKDOWN:
            md_content = self._render_markdown(ai_content, data_content)
            file_path = reports_dir / f"report_{report_id}.md"
            file_path.write_text(md_content, encoding="utf-8")

        elif format == ReportFormat.HTML:
            md_content = self._render_markdown(ai_content, data_content)
            html_content = markdown.markdown(md_content)
            html_page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{data_content.get('title', 'Report')}</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.6;}}</style>
</head><body>{html_content}</body></html>"""
            file_path = reports_dir / f"report_{report_id}.html"
            file_path.write_text(html_page, encoding="utf-8")

        elif format == ReportFormat.PDF:
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

                file_path = reports_dir / f"report_{report_id}.pdf"
                doc = SimpleDocTemplate(str(file_path), pagesize=letter)
                styles = getSampleStyleSheet()
                story = []

                title = data_content.get("title", "JARVIS Report")
                story.append(Paragraph(title, styles["Title"]))
                story.append(Spacer(1, 12))

                for section, text in ai_content.items():
                    if isinstance(text, str) and text:
                        story.append(Paragraph(section.replace("_", " ").title(), styles["Heading2"]))
                        story.append(Paragraph(text[:2000], styles["Normal"]))
                        story.append(Spacer(1, 8))
                    elif isinstance(text, list):
                        story.append(Paragraph(section.replace("_", " ").title(), styles["Heading2"]))
                        for item in text:
                            story.append(Paragraph(f"• {item}", styles["Normal"]))
                        story.append(Spacer(1, 8))

                doc.build(story)
            except Exception as e:
                logger.warning("PDF generation failed, falling back to markdown", error=str(e))
                md_content = self._render_markdown(ai_content, data_content)
                file_path = reports_dir / f"report_{report_id}.md"
                file_path.write_text(md_content, encoding="utf-8")

        else:  # JSON
            combined = {**data_content, "ai_analysis": ai_content}
            file_path = reports_dir / f"report_{report_id}.json"
            file_path.write_text(json.dumps(combined, indent=2, default=str), encoding="utf-8")

        return str(file_path)

    def _render_markdown(
        self, ai_content: Dict[str, Any], data_content: Dict[str, Any]
    ) -> str:
        """Render report as Markdown."""
        import json

        title = data_content.get("title", "JARVIS Intelligence Report")
        lines = [
            f"# {title}",
            "",
            f"**Report Type:** {data_content.get('report_type', 'N/A')}",
            f"**Generated by:** JARVIS AI Operating System",
            "",
            "---",
            "",
        ]

        for section, content in ai_content.items():
            lines.append(f"## {section.replace('_', ' ').title()}")
            lines.append("")
            if isinstance(content, str):
                lines.append(content)
            elif isinstance(content, list):
                for item in content:
                    lines.append(f"- {item}")
            elif isinstance(content, dict):
                lines.append(f"```json\n{json.dumps(content, indent=2)}\n```")
            lines.append("")

        return "\n".join(lines)
