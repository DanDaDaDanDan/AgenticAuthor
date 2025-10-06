"""Main analysis coordinator."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

from ...api import OpenRouterClient
from ...models import Project
from .base import AnalysisResult, Issue, Severity
from .plot_analyzer import PlotAnalyzer
from .character_analyzer import CharacterAnalyzer
from .worldbuilding_analyzer import WorldBuildingAnalyzer
from .dialogue_analyzer import DialogueAnalyzer
from .prose_analyzer import ProseAnalyzer
from .theme_analyzer import ThemeAnalyzer
from .narrative_analyzer import NarrativeAnalyzer
from .commercial_analyzer import CommercialAnalyzer


class AnalysisCoordinator:
    """Coordinates story analysis across multiple dimensions."""

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

        # Initialize all analyzers
        self.plot_analyzer = PlotAnalyzer(client, self.model)
        self.character_analyzer = CharacterAnalyzer(client, self.model)
        self.worldbuilding_analyzer = WorldBuildingAnalyzer(client, self.model)
        self.dialogue_analyzer = DialogueAnalyzer(client, self.model)
        self.prose_analyzer = ProseAnalyzer(client, self.model)
        self.theme_analyzer = ThemeAnalyzer(client, self.model)
        self.narrative_analyzer = NarrativeAnalyzer(client, self.model)
        self.commercial_analyzer = CommercialAnalyzer(client, self.model)

    async def analyze(
        self,
        content_type: str,
        target_id: Optional[str] = None,
        dimensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze content.

        Args:
            content_type: Type (premise/treatment/chapters/chapter/prose)
            target_id: Specific ID (e.g., chapter number)
            dimensions: Specific dimensions to analyze (None = all applicable)

        Returns:
            Analysis results dict

        Raises:
            ValueError: If content not found or invalid type
        """
        # Get content and context
        content, context = self._get_content_and_context(content_type, target_id)

        if not content:
            raise ValueError(
                f"No {content_type} content found. Generate it first."
            )

        # Determine which analyzers to run
        analyzers_to_run = self._determine_analyzers(
            content_type, dimensions
        )

        # Run analyses
        results = await self._run_analyses(
            content, content_type, context, analyzers_to_run
        )

        # Aggregate results
        aggregated = self._aggregate_results(
            results, content_type, target_id
        )

        # Generate report
        report_path = await self._generate_report(
            aggregated, content_type, target_id
        )

        aggregated['report_path'] = str(report_path)

        return aggregated

    def _get_content_and_context(
        self,
        content_type: str,
        target_id: Optional[str] = None
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """Get content to analyze and build context."""
        context = {}

        # Get premise for context (always helpful)
        premise = self.project.get_premise()
        if premise:
            context['premise'] = premise

        # Get genre
        if self.project.metadata:
            context['genre'] = self.project.metadata.genre

        # Get the actual content to analyze
        content = None

        if content_type == 'premise':
            content = premise

        elif content_type == 'treatment':
            content = self.project.get_treatment()
            # Add taxonomy to context
            taxonomy = self.project.get_taxonomy()
            if taxonomy:
                context['taxonomy'] = taxonomy

        elif content_type == 'chapters':
            # Analyze chapter outlines
            chapters = self.project.get_chapters()
            if chapters:
                # Convert to text format
                content = self._chapters_to_text(chapters)
                context['treatment'] = self.project.get_treatment()

        elif content_type == 'chapter':
            # Analyze specific chapter outline
            chapter_num = int(target_id) if target_id else 1
            chapters = self.project.get_chapters()
            if chapters:
                chapter = next(
                    (c for c in chapters if c.get('number') == chapter_num),
                    None
                )
                if chapter:
                    content = yaml.dump(chapter, default_flow_style=False)
                    context['treatment'] = self.project.get_treatment()
                    context['all_chapters'] = self._chapters_to_text(chapters)

        elif content_type == 'prose':
            # Analyze specific prose chapter
            chapter_num = int(target_id) if target_id else 1
            chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
            if chapter_file.exists():
                content = chapter_file.read_text(encoding='utf-8')
                context['treatment'] = self.project.get_treatment()

                # Get chapter outline for context
                chapters = self.project.get_chapters()
                if chapters:
                    chapter = next(
                        (c for c in chapters if c.get('number') == chapter_num),
                        None
                    )
                    if chapter:
                        context['chapter_outline'] = yaml.dump(
                            chapter, default_flow_style=False
                        )

        return content, context

    def _chapters_to_text(self, chapters: List[Dict[str, Any]]) -> str:
        """Convert chapters list to readable text."""
        lines = []
        for ch in chapters:
            lines.append(f"Chapter {ch.get('number', '?')}: {ch.get('title', 'Untitled')}")
            lines.append(f"Summary: {ch.get('summary', '')}")
            lines.append(f"Target words: {ch.get('word_count_target', 'N/A')}")
            lines.append("")
        return "\n".join(lines)

    def _determine_analyzers(
        self,
        content_type: str,
        dimensions: Optional[List[str]] = None
    ) -> List[str]:
        """Determine which analyzers to run based on content type."""
        # Default analyzers for each content type
        defaults = {
            'premise': ['plot', 'theme', 'commercial'],
            'treatment': ['plot', 'character', 'worldbuilding', 'theme', 'commercial'],
            'chapters': ['plot', 'character', 'worldbuilding', 'theme'],
            'chapter': ['plot', 'character', 'worldbuilding'],
            'prose': ['plot', 'character', 'worldbuilding', 'dialogue', 'prose', 'theme', 'narrative'],
        }

        # All possible analyzers
        all_analyzers = [
            'plot', 'character', 'worldbuilding', 'dialogue',
            'prose', 'theme', 'narrative', 'commercial'
        ]

        if dimensions:
            # Use specified dimensions
            return [d for d in dimensions if d in all_analyzers]
        else:
            # Use defaults for content type
            return defaults.get(content_type, all_analyzers)

    async def _run_analyses(
        self,
        content: str,
        content_type: str,
        context: Dict[str, Any],
        analyzers_to_run: List[str]
    ) -> List[AnalysisResult]:
        """Run specified analyzers."""
        tasks = []
        analyzer_map = {
            'plot': self.plot_analyzer,
            'character': self.character_analyzer,
            'worldbuilding': self.worldbuilding_analyzer,
            'dialogue': self.dialogue_analyzer,
            'prose': self.prose_analyzer,
            'theme': self.theme_analyzer,
            'narrative': self.narrative_analyzer,
            'commercial': self.commercial_analyzer,
        }

        for analyzer_name in analyzers_to_run:
            analyzer = analyzer_map.get(analyzer_name)
            if analyzer:
                tasks.append(
                    analyzer.analyze(content, content_type, context)
                )

        # Run all analyses concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Warning: {analyzers_to_run[i]} analysis failed: {str(result)}")
            else:
                valid_results.append(result)

        return valid_results

    def _aggregate_results(
        self,
        results: List[AnalysisResult],
        content_type: str,
        target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate analysis results."""
        # Calculate overall score (average of all dimension scores)
        scores = [r.score for r in results]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        # Determine overall grade
        overall_grade = self._score_to_grade(overall_score)

        # Collect all issues by severity
        all_issues = []
        for result in results:
            all_issues.extend(result.issues)

        # Sort by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3
        }
        all_issues.sort(key=lambda i: severity_order[i.severity])

        # Get top 5 priority issues
        priority_issues = all_issues[:5]

        # Collect strengths
        all_strengths = []
        for result in results:
            all_strengths.extend(result.strengths)

        # Build aggregated result
        return {
            'content_type': content_type,
            'target_id': target_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': self.model,
            'overall_score': overall_score,
            'overall_grade': overall_grade,
            'dimension_results': [r.to_dict() for r in results],
            'priority_issues': [i.to_dict() for i in priority_issues],
            'all_issues': [i.to_dict() for i in all_issues],
            'highlights': [s.to_dict() for s in all_strengths[:5]],
            'total_issues': len(all_issues),
            'critical_issues': len([i for i in all_issues if i.severity == Severity.CRITICAL]),
            'high_issues': len([i for i in all_issues if i.severity == Severity.HIGH]),
        }

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

            # Issues
            if dimension['issues']:
                lines.append("#### Issues Found")
                for issue in dimension['issues']:
                    lines.append(f"- ⚠️ **[{issue['severity']}] {issue['category']}**")
                    lines.append(f"  - **Location**: {issue['location']}")
                    lines.append(f"  - **Issue**: {issue['description']}")
                    lines.append(f"  - **Impact**: {issue['impact']}")
                    lines.append(f"  - **Suggestion**: {issue['suggestion']}")
                    lines.append("")

            # Notes
            if dimension.get('notes'):
                lines.append("#### Notes")
                for note in dimension['notes']:
                    lines.append(f"- {note}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Priority Issues
        if aggregated['priority_issues']:
            lines.append("## Priority Issues (Top 5)")
            lines.append("")
            for i, issue in enumerate(aggregated['priority_issues'], 1):
                lines.append(f"### {i}. [{issue['severity']}] {issue['category']}")
                lines.append(f"- **Location**: {issue['location']}")
                lines.append(f"- **Issue**: {issue['description']}")
                lines.append(f"- **Fix**: {issue['suggestion']}")
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

        # Footer
        lines.append(f"*Analysis completed at {aggregated['timestamp']}*")

        return "\n".join(lines)
