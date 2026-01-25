"""Main analysis coordinator."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

from ...api import OpenRouterClient
from ...models import Project
from .base import AnalysisResult, Issue, Severity
from .unified_analyzer import UnifiedAnalyzer
from .treatment_deviation_analyzer import TreatmentDeviationAnalyzer


class AnalysisCoordinator:
    """Coordinates story analysis using unified analyzer."""

    def __init__(
        self,
        client: OpenRouterClient,
        project: Project,
        model: str
    ):
        """
        Initialize analysis coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for analysis (required)
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.project = project
        self.model = model

        # Initialize analyzers
        self.analyzer = UnifiedAnalyzer(client, self.model)
        self.treatment_analyzer = TreatmentDeviationAnalyzer(client, self.model)

    async def analyze(
        self,
        content_type: str,
        target_id: Optional[str] = None,
        dimensions: Optional[List[str]] = None,  # Kept for backward compatibility, ignored
        exclude_treatment: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze content using unified analyzer.

        Args:
            content_type: Type (premise/treatment/chapters/chapter/prose)
            target_id: Specific ID (e.g., chapter number)
            dimensions: Ignored (kept for backward compatibility)
            exclude_treatment: If True, exclude treatment from analysis context

        Returns:
            Analysis results dict

        Raises:
            ValueError: If content not found or invalid type
        """
        # Get content and context
        content, context = self._get_content_and_context(content_type, target_id, exclude_treatment)

        if not content:
            raise ValueError(
                f"No {content_type} content found. Generate it first."
            )

        # Run unified analysis
        result = await self.analyzer.analyze(content, content_type, context)

        # Run treatment deviation analysis for chapters (if treatment exists and not excluded)
        treatment_result = None
        if content_type == 'chapters' and 'treatment' in context and not exclude_treatment:
            treatment_result = await self.treatment_analyzer.analyze(content, content_type, context)

        # Build aggregated response
        if treatment_result:
            # Combine both analyses
            aggregated = self._build_combined_result_dict(result, treatment_result, content_type, target_id)
        else:
            # Single result (backward compatibility)
            aggregated = self._build_result_dict(result, content_type, target_id)

        # Generate report
        report_path = await self._generate_report(
            aggregated, content_type, target_id
        )

        aggregated['report_path'] = str(report_path)

        return aggregated

    def _get_content_and_context(
        self,
        content_type: str,
        target_id: Optional[str] = None,
        exclude_treatment: bool = False
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Get content to analyze and build context.

        Args:
            content_type: Type of content to analyze
            target_id: Optional specific target ID
            exclude_treatment: If True, exclude treatment from context
        """
        context = {}

        # Get premise for context (always helpful)
        premise = self.project.get_premise()
        if premise:
            context['premise'] = premise

        # Get genre
        if self.project.metadata and self.project.metadata.genre:
            context['genre'] = self.project.metadata.genre

        # Get the actual content to analyze
        content = None

        # Short story handling: redirect plan analysis to prose
        if self.project.is_short_form() and content_type == 'plan':
            content_type = 'prose'

        if content_type == 'premise':
            content = premise

        elif content_type == 'treatment':
            content = self.project.get_treatment()
            # Add taxonomy to context
            taxonomy = self.project.get_taxonomy()
            if taxonomy:
                context['taxonomy'] = taxonomy

        elif content_type == 'plan':
            # Analyze structure plan
            content = self.project.get_structure_plan()
            if not exclude_treatment:
                treatment = self.project.get_treatment()
                if treatment:
                    context['treatment'] = treatment

        elif content_type == 'prose':
            # Analyze prose (short story or chapter)
            if self.project.is_short_form():
                # Short story: analyze story.md
                content = self.project.get_story()
                if not exclude_treatment:
                    context['treatment'] = self.project.get_treatment()
            else:
                # Long-form: analyze specific chapter or all chapters
                if target_id is None:
                    # Analyze ALL prose chapters
                    chapter_files = sorted(self.project.chapters_dir.glob('chapter-*.md'))
                    if chapter_files:
                        chapter_texts = []
                        for chapter_file in chapter_files:
                            chapter_text = chapter_file.read_text(encoding='utf-8')
                            chapter_texts.append(chapter_text)

                        # Concatenate all chapters with clear separators
                        content = '\n\n---\n\n'.join(chapter_texts)
                        if not exclude_treatment:
                            context['treatment'] = self.project.get_treatment()

                        # Load structure plan for context
                        structure_plan = self.project.get_structure_plan()
                        if structure_plan:
                            context['structure_plan'] = structure_plan
                else:
                    # Analyze specific chapter
                    chapter_num = int(target_id)
                    chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                    if chapter_file.exists():
                        content = chapter_file.read_text(encoding='utf-8')
                        if not exclude_treatment:
                            context['treatment'] = self.project.get_treatment()

                        # Load structure plan for context
                        structure_plan = self.project.get_structure_plan()
                        if structure_plan:
                            context['structure_plan'] = structure_plan

        return content, context

    def _build_combined_result_dict(
        self,
        unified_result: AnalysisResult,
        treatment_result: AnalysisResult,
        content_type: str,
        target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build result dictionary from combined analyses."""
        # Combine issues from both analyses
        all_issues = unified_result.issues + treatment_result.issues

        # Sort by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3
        }
        all_issues = sorted(all_issues, key=lambda i: severity_order[i.severity])

        # Priority issues (top 10)
        priority_issues = all_issues[:10]

        # Combine strengths
        all_strengths = unified_result.strengths + treatment_result.strengths

        # Average the scores
        overall_score = (unified_result.score + treatment_result.score) / 2

        # Build result dict
        result_dict = {
            'content_type': content_type,
            'target_id': target_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': self.model,
            'overall_score': overall_score,
            'overall_grade': self._score_to_grade(overall_score),
            'dimension_results': [
                unified_result.to_dict(),
                treatment_result.to_dict()
            ],
            'priority_issues': [i.to_dict() for i in priority_issues],
            'all_issues': [i.to_dict() for i in all_issues],
            'highlights': [s.to_dict() for s in all_strengths[:5]],
            'total_issues': len(all_issues),
            'critical_issues': len([i for i in all_issues if i.severity == Severity.CRITICAL]),
            'high_issues': len([i for i in all_issues if i.severity == Severity.HIGH]),
        }

        # Add path_to_a_plus if present
        if unified_result.path_to_a_plus:
            result_dict['path_to_a_plus'] = unified_result.path_to_a_plus.to_dict()

        return result_dict

    def _build_result_dict(
        self,
        result: AnalysisResult,
        content_type: str,
        target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build result dictionary from single unified analysis."""
        # Sort issues by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3
        }
        all_issues = sorted(result.issues, key=lambda i: severity_order[i.severity])

        # Priority issues are all issues (already limited to 0-7 by analyzer)
        priority_issues = all_issues

        # Build result dict
        result_dict = {
            'content_type': content_type,
            'target_id': target_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': self.model,
            'overall_score': result.score,
            'overall_grade': self._score_to_grade(result.score),
            'dimension_results': [result.to_dict()],  # Single unified result
            'priority_issues': [i.to_dict() for i in priority_issues],
            'all_issues': [i.to_dict() for i in all_issues],
            'highlights': [s.to_dict() for s in result.strengths[:5]],
            'total_issues': len(all_issues),
            'critical_issues': len([i for i in all_issues if i.severity == Severity.CRITICAL]),
            'high_issues': len([i for i in all_issues if i.severity == Severity.HIGH]),
        }

        # Add path_to_a_plus if present
        if result.path_to_a_plus:
            result_dict['path_to_a_plus'] = result.path_to_a_plus.to_dict()

        return result_dict

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 9.0:
            return "A (Excellent)"
        elif score >= 8.0:
            return "B+ (Very Good)"
        elif score >= 7.0:
            return "B (Good)"
        elif score >= 6.0:
            return "C+ (Above Average)"
        elif score >= 5.0:
            return "C (Average)"
        elif score >= 4.0:
            return "D+ (Below Average)"
        elif score >= 3.0:
            return "D (Poor)"
        else:
            return "F (Needs Major Revision)"

    async def _generate_report(
        self,
        aggregated: Dict[str, Any],
        content_type: str,
        target_id: Optional[str] = None
    ) -> Path:
        """Generate markdown report and save to analysis/ directory."""
        # Ensure analysis directory exists
        analysis_dir = self.project.analysis_dir
        analysis_dir.mkdir(exist_ok=True)

        # Generate filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if target_id:
            filename = f"{content_type}-{target_id}-{timestamp}.md"
        else:
            filename = f"{content_type}-{timestamp}.md"

        report_path = analysis_dir / filename

        # Get git SHA if available
        git_sha = "N/A"
        # Check if books/ level has git (shared repo)
        git_dir = self.project.path.parent / ".git"
        if git_dir.exists():
            try:
                import subprocess
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.project.path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    git_sha = result.stdout.strip()[:8]
            except:
                pass

        # Generate markdown report
        report = self._format_report(aggregated, git_sha)

        # Write report
        report_path.write_text(report, encoding='utf-8')

        return report_path

    def _format_report(self, aggregated: Dict[str, Any], git_sha: str) -> str:
        """Format analysis results as markdown report."""
        lines = []

        # Header
        content_desc = aggregated['content_type'].title()
        if aggregated.get('target_id'):
            content_desc += f" {aggregated['target_id']}"

        lines.append(f"# Analysis Report: {content_desc}")
        lines.append(f"")
        lines.append(f"**Generated**: {aggregated['timestamp']}")
        lines.append(f"**Model**: {aggregated['model']}")
        lines.append(f"**Git SHA**: {git_sha}")
        lines.append(f"")
        lines.append("---")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(f"**Overall Grade**: {aggregated['overall_grade']}")
        lines.append(f"**Overall Score**: {aggregated['overall_score']:.1f}/10")
        lines.append("")
        lines.append(f"**Issues Found**: {aggregated['total_issues']} total")
        lines.append(f"- Critical: {aggregated['critical_issues']}")
        lines.append(f"- High: {aggregated['high_issues']}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Detailed Analysis by Dimension
        lines.append("## Detailed Analysis")
        lines.append("")

        for dimension in aggregated['dimension_results']:
            lines.append(f"### {dimension['dimension']} [Score: {dimension['score']:.1f}/10]")
            lines.append("")
            lines.append(f"**Summary**: {dimension['summary']}")
            lines.append("")

            # Strengths
            if dimension['strengths']:
                lines.append("#### Strengths")
                for strength in dimension['strengths']:
                    loc = f" ({strength['location']})" if strength.get('location') else ""
                    lines.append(f"- ✓ **{strength['category']}**: {strength['description']}{loc}")
                lines.append("")

            # Group issues by severity
            if dimension['issues']:
                issues_by_severity = {
                    'CRITICAL': [],
                    'HIGH': [],
                    'MEDIUM': [],
                    'LOW': []
                }

                for issue in dimension['issues']:
                    severity = issue['severity'].upper()
                    issues_by_severity.get(severity, issues_by_severity['MEDIUM']).append(issue)

                lines.append("#### Issues Found")
                lines.append("")

                # Display issues grouped by severity
                for severity_level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                    issues = issues_by_severity[severity_level]
                    if not issues:
                        continue

                    # Severity header with emoji
                    severity_emoji = {
                        'CRITICAL': '🔴',
                        'HIGH': '🟠',
                        'MEDIUM': '🟡',
                        'LOW': '🔵'
                    }
                    lines.append(f"**{severity_emoji[severity_level]} {severity_level}**")
                    lines.append("")

                    for issue in issues:
                        # Remove "General:" prefix from location
                        location = issue['location']
                        if location == "General":
                            location = "Overall"

                        # Remove "General" category prefix if present
                        category = issue['category']
                        if category.startswith("General:"):
                            category = category.replace("General:", "").strip()

                        lines.append(f"**{category}** _{location}_")
                        if issue.get('description'):
                            lines.append(f"- **Issue**: {issue['description']}")
                        if issue.get('impact'):
                            lines.append(f"- **Impact**: {issue['impact']}")
                        if issue.get('suggestion'):
                            lines.append(f"- **Fix**: {issue['suggestion']}")
                        lines.append("")

            # Notes
            if dimension.get('notes'):
                lines.append("#### Notes")
                for note in dimension['notes']:
                    lines.append(f"- {note}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Positive Highlights
        if aggregated['highlights']:
            lines.append("## Positive Highlights")
            lines.append("")
            for strength in aggregated['highlights']:
                loc = f" ({strength['location']})" if strength.get('location') else ""
                lines.append(f"- {strength['description']}{loc}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Path to A+ Grade
        if 'path_to_a_plus' in aggregated and aggregated['path_to_a_plus']:
            path = aggregated['path_to_a_plus']
            lines.append("## 🎯 Path to A+ Grade")
            lines.append("")

            # Current assessment
            if path.get('current_assessment'):
                lines.append("### Current Assessment")
                lines.append("")
                lines.append(path['current_assessment'])
                lines.append("")

            # Recommendations or unable to determine
            if path.get('unable_to_determine'):
                lines.append("### Analysis")
                lines.append("")
                lines.append("⚠️ Unable to determine clear path to A+ grade.")
                lines.append("")
                if path.get('reasoning'):
                    lines.append(f"**Reasoning**: {path['reasoning']}")
                    lines.append("")
            else:
                if path.get('recommendations'):
                    lines.append("### Recommendations")
                    lines.append("")
                    for i, rec in enumerate(path['recommendations'], 1):
                        confidence = rec.get('confidence', 0)
                        lines.append(f"{i}. **{rec['description']}** _(Confidence: {confidence}%)_")
                        if rec.get('rationale'):
                            lines.append(f"   - {rec['rationale']}")
                        lines.append("")

            lines.append("---")
            lines.append("")

        # Footer
        lines.append(f"*Analysis completed at {aggregated['timestamp']}*")

        return "\n".join(lines)
