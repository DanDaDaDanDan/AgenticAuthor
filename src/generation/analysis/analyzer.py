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
        dimensions: Optional[List[str]] = None  # Kept for backward compatibility, ignored
    ) -> Dict[str, Any]:
        """
        Analyze content using unified analyzer.

        Args:
            content_type: Type (premise/treatment/chapters/chapter/prose)
            target_id: Specific ID (e.g., chapter number)
            dimensions: Ignored (kept for backward compatibility)

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

        # Run unified analysis
        result = await self.analyzer.analyze(content, content_type, context)

        # Run treatment deviation analysis for chapters (if treatment exists)
        treatment_result = None
        if content_type == 'chapters' and 'treatment' in context:
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
        target_id: Optional[str] = None
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """Get content to analyze and build context."""
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

        # Short story handling: redirect chapters analysis to prose
        if self.project.is_short_form() and content_type in ['chapters', 'chapter']:
            content_type = 'prose'
            # Note: This allows /analyze chapters to work on short stories
            # by analyzing the prose instead

        if content_type == 'premise':
            content = premise

        elif content_type == 'treatment':
            content = self.project.get_treatment()
            # Add taxonomy to context
            taxonomy = self.project.get_taxonomy()
            if taxonomy:
                context['taxonomy'] = taxonomy

        elif content_type == 'chapters':
            # Analyze chapter outlines - load from markdown files directly
            foundation_file = self.project.chapter_beats_dir / 'foundation.md'
            chapter_files = sorted(self.project.chapter_beats_dir.glob('chapter-*.md'))

            if foundation_file.exists() and chapter_files:
                # NEW markdown-based format: Load foundation + individual chapter markdown files
                foundation_md, chapters_md = self._build_chapters_analysis_sections(foundation_file, chapter_files)
                context['foundation'] = foundation_md
                content = chapters_md
                # Add treatment for deviation analysis
                treatment = self.project.get_treatment()
                if treatment:
                    context['treatment'] = treatment
            else:
                # LEGACY fallback: Try chapters.yaml
                chapters_yaml = self.project.get_chapters_yaml()
                if chapters_yaml:
                    # Split into clear sections and provide a compact index
                    foundation_text, chapters_text = self._split_foundation_and_chapters_text(chapters_yaml)
                    context['foundation'] = foundation_text
                    context['chapters_index'] = self._format_chapters_index(chapters_yaml)
                    content = chapters_text
                    # Add treatment for deviation analysis
                    treatment = self.project.get_treatment()
                    if treatment:
                        context['treatment'] = treatment
                else:
                    # OLDER legacy: Try old chapters list
                    chapters = self.project.get_chapters()
                    if chapters:
                        content = self._chapters_to_text(chapters)
                        context['treatment'] = self.project.get_treatment()

        elif content_type == 'chapter':
            # Analyze specific chapter outline - load markdown directly
            chapter_num = int(target_id) if target_id else 1
            chapter_file = self.project.chapter_beats_dir / f'chapter-{chapter_num:02d}.md'
            if chapter_file.exists():
                content = chapter_file.read_text(encoding='utf-8')
                context['treatment'] = self.project.get_treatment()
                # Load all chapters for context
                all_chapters_md = []
                for ch_file in sorted(self.project.chapter_beats_dir.glob('chapter-*.md')):
                    all_chapters_md.append(ch_file.read_text(encoding='utf-8'))
                if all_chapters_md:
                    context['all_chapters'] = '\n\n---\n\n'.join(all_chapters_md)

        elif content_type == 'prose':
            # Analyze prose (short story or chapter)
            if self.project.is_short_form():
                # Short story: analyze story.md
                content = self.project.get_story()
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
                        context['treatment'] = self.project.get_treatment()

                        # Load all chapter outlines for context
                        outline_files = sorted(self.project.chapter_beats_dir.glob('chapter-*.md'))
                        if outline_files:
                            outline_texts = []
                            for outline_file in outline_files:
                                outline_texts.append(outline_file.read_text(encoding='utf-8'))
                            context['chapter_outline'] = '\n\n---\n\n'.join(outline_texts)
                else:
                    # Analyze specific chapter
                    chapter_num = int(target_id)
                    chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                    if chapter_file.exists():
                        content = chapter_file.read_text(encoding='utf-8')
                        context['treatment'] = self.project.get_treatment()

                        # Get chapter outline for context - load markdown directly
                        chapter_outline_file = self.project.chapter_beats_dir / f'chapter-{chapter_num:02d}.md'
                        if chapter_outline_file.exists():
                            context['chapter_outline'] = chapter_outline_file.read_text(encoding='utf-8')

        return content, context

    def _build_chapters_analysis_content(self, foundation_file: Path, chapter_files: List[Path]) -> str:
        """
        Build chapters analysis content from markdown files with clear box structure.

        This mirrors the variant judging prompt structure for consistency.

        Args:
            foundation_file: Path to foundation.md
            chapter_files: List of paths to chapter-NN.md files

        Returns:
            Formatted markdown string with boxes
        """
        sections = []

        # Load foundation markdown
        foundation_md = foundation_file.read_text(encoding='utf-8')

        # Add foundation section with box
        sections.append(f"""════════════════════════════════════════════════════════════════════════════════
FOUNDATION
════════════════════════════════════════════════════════════════════════════════

{foundation_md}""")

        # Load all chapter markdown files
        chapter_texts = []
        for chapter_file in chapter_files:
            chapter_text = chapter_file.read_text(encoding='utf-8')
            chapter_texts.append(chapter_text)

        # Join chapters with blank lines (markdown headers provide structure)
        chapters_markdown = "\n\n".join(chapter_texts)

        # Add chapters section with box
        sections.append(f"""════════════════════════════════════════════════════════════════════════════════
CHAPTER OUTLINES
════════════════════════════════════════════════════════════════════════════════

{chapters_markdown}""")

        return "\n\n".join(sections)

    def _build_chapters_analysis_sections(self, foundation_file: Path, chapter_files: List[Path]) -> tuple[str, str]:
        """Return foundation markdown and concatenated chapter markdown separately."""
        foundation_md = foundation_file.read_text(encoding='utf-8')
        chapter_texts = []
        for chapter_file in chapter_files:
            chapter_texts.append(chapter_file.read_text(encoding='utf-8'))
        chapters_markdown = "\n\n".join(chapter_texts)
        return foundation_md, chapters_markdown

    def _chapters_to_text(self, chapters: List[Dict[str, Any]]) -> str:
        """Convert chapters list to readable text (legacy format)."""
        lines = []
        for ch in chapters:
            lines.append(f"Chapter {ch.get('number', '?')}: {ch.get('title', 'Untitled')}")
            lines.append(f"Summary: {ch.get('summary', '')}")
            lines.append("")
        return "\n".join(lines)

    def _chapters_yaml_to_text(self, chapters_yaml: Dict[str, Any]) -> str:
        """Convert self-contained chapters.yaml to markdown (new format)."""
        sections = []

        # BUILD ENTIRE FOUNDATION AS SINGLE SECTION
        foundation_lines = []

        # Metadata subsection
        metadata = chapters_yaml.get('metadata', {})
        if metadata:
            foundation_lines.append("# FOUNDATION\n")
            foundation_lines.append("## Metadata\n")
            foundation_lines.append(f"**Genre:** {metadata.get('genre', 'N/A')}")
            foundation_lines.append(f"**Subgenre:** {metadata.get('subgenre', 'N/A')}")
            foundation_lines.append(f"**Tone:** {metadata.get('tone', 'N/A')}")
            foundation_lines.append(f"**Pacing:** {metadata.get('pacing', 'N/A')}")
            themes = metadata.get('themes', [])
            if themes:
                foundation_lines.append(f"**Themes:** {', '.join(themes)}")
            foundation_lines.append(f"**Narrative Style:** {metadata.get('narrative_style', 'N/A')}")
            # Format word count with commas
            target_wc = metadata.get('target_word_count', 'N/A')
            if isinstance(target_wc, int):
                foundation_lines.append(f"**Target Word Count:** {target_wc:,}")
            else:
                foundation_lines.append(f"**Target Word Count:** {target_wc}")
            foundation_lines.append(f"**Setting:** {metadata.get('setting_location', 'N/A')} ({metadata.get('setting_period', 'N/A')})")
            foundation_lines.append("")  # Blank line after metadata

        # Characters subsection
        characters = chapters_yaml.get('characters', [])
        if characters:
            foundation_lines.append("## Characters\n")
            for char in characters:
                foundation_lines.append(f"### {char.get('name', 'Unknown')} ({char.get('role', 'N/A')})\n")
                if char.get('age'):
                    foundation_lines.append(f"**Age:** {char.get('age')}")
                foundation_lines.append(f"**Background:** {char.get('background', 'N/A')}")
                foundation_lines.append(f"**Motivation:** {char.get('motivation', 'N/A')}")
                foundation_lines.append(f"**Character Arc:** {char.get('character_arc', 'N/A')}")
                foundation_lines.append(f"**Internal Conflict:** {char.get('internal_conflict', 'N/A')}\n")
            foundation_lines.append("")  # Blank line after characters

        # World subsection
        world = chapters_yaml.get('world', {})
        if world:
            foundation_lines.append("## World\n")
            foundation_lines.append(f"**Setting Overview:** {world.get('setting_overview', 'N/A')}\n")

            key_locations = world.get('key_locations', [])
            if key_locations:
                foundation_lines.append("**Key Locations:**")
                for loc in key_locations:
                    foundation_lines.append(f"- **{loc.get('name', 'Unknown')}:** {loc.get('description', 'N/A')}")
                foundation_lines.append("")

            systems = world.get('systems_and_rules', [])
            if systems:
                foundation_lines.append("**Systems and Rules:**")
                # Handle both list format (new) and dict format (legacy)
                if isinstance(systems, list):
                    for system in systems:
                        if isinstance(system, dict):
                            system_name = system.get('system', 'Unknown')
                            system_desc = system.get('description', 'N/A')
                            foundation_lines.append(f"- **{system_name}:** {system_desc}")
                        else:
                            foundation_lines.append(f"- {system}")
                else:
                    # Legacy dict format
                    for key, value in systems.items():
                        foundation_lines.append(f"- **{key}:** {value}")
                foundation_lines.append("")

            social_context = world.get('social_context', [])
            if social_context:
                foundation_lines.append("**Social Context:**")
                # Handle both list format (new) and dict format (legacy)
                if isinstance(social_context, list):
                    for context in social_context:
                        if isinstance(context, dict):
                            # If it's a dict, format it
                            for key, value in context.items():
                                foundation_lines.append(f"- {key}: {value}")
                        else:
                            # If it's a string, just add it
                            foundation_lines.append(f"- {context}")
                else:
                    # Legacy dict format
                    for key, value in social_context.items():
                        foundation_lines.append(f"- {key}: {value}")

        # Add complete foundation as single section
        if foundation_lines:
            sections.append("\n".join(foundation_lines))

        # CHAPTERS SECTION
        chapters = chapters_yaml.get('chapters', [])
        if chapters:
            chapter_lines = ["# CHAPTER OUTLINES\n"]
            for ch in chapters:
                chapter_lines.append(f"## Chapter {ch.get('number', '?')}: {ch.get('title', 'Untitled')}\n")
                chapter_lines.append(f"**POV:** {ch.get('pov', 'N/A')}")
                chapter_lines.append(f"**Act:** {ch.get('act', 'N/A')}")
                chapter_lines.append(f"**Summary:** {ch.get('summary', 'N/A')}\n")

                # Support both scenes (new) and key_events (old) formats
                scenes = ch.get('scenes', ch.get('key_events', []))
                if scenes:
                    chapter_lines.append(f"**Scenes ({len(scenes)} total):**")
                    # Check if structured scenes or simple list
                    if isinstance(scenes, list) and len(scenes) > 0 and isinstance(scenes[0], dict):
                        # Include scene details for duplicate detection
                        for i, scene in enumerate(scenes, 1):
                            scene_title = scene.get('scene', 'Untitled')
                            location = scene.get('location', 'N/A')
                            pov_goal = scene.get('pov_goal', 'N/A')
                            chapter_lines.append(f"{i}. **{scene_title}** @ {location}")
                            chapter_lines.append(f"   *Goal:* {pov_goal}")
                    else:
                        for i, scene in enumerate(scenes, 1):
                            chapter_lines.append(f"{i}. {scene}")
                    chapter_lines.append("")

                char_devs = ch.get('character_developments', [])
                if char_devs:
                    chapter_lines.append(f"**Character Developments:** {len(char_devs)} total\n")

                # Add separator between chapters
                chapter_lines.append("---\n")

            sections.append("\n".join(chapter_lines))

        # Join sections with clear separator (only one --- between FOUNDATION and CHAPTERS)
        return "\n\n---\n\n".join(sections)

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

            # Issues
            if dimension['issues']:
                lines.append("#### Issues Found")
                for issue in dimension['issues']:
                    confidence = issue.get('confidence', 100)
                    lines.append(f"- ⚠️ **[{issue['severity']}] {issue['category']}** _(Confidence: {confidence}%)_")
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

    def _format_chapters_index(self, chapters_yaml: Dict[str, Any]) -> str:
        """Build compact table of chapter number, title, and act."""
        lines = ["CHAPTER INDEX:"]
        for ch in chapters_yaml.get('chapters', []):
            lines.append(f"- {ch.get('number','?')}: {ch.get('title','Untitled')} — {ch.get('act','N/A')}")
        return "\n".join(lines)

    def _split_foundation_and_chapters_text(self, chapters_yaml: Dict[str, Any]) -> tuple[str, str]:
        """Split chapters.yaml into FOUNDATION (context) and CHAPTERS (to analyze) text blocks."""
        foundation_lines: list[str] = []
        chapters_lines: list[str] = []

        # FOUNDATION (concise)
        metadata = chapters_yaml.get('metadata', {})
        if metadata:
            foundation_lines.append("# FOUNDATION\n")
            foundation_lines.append("## Metadata\n")
            foundation_lines.append(f"**Genre:** {metadata.get('genre', 'N/A')}")
            foundation_lines.append(f"**Tone:** {metadata.get('tone', 'N/A')}")
            foundation_lines.append(f"**Pacing:** {metadata.get('pacing', 'N/A')}")
            themes = metadata.get('themes', [])
            if themes:
                foundation_lines.append(f"**Themes:** {', '.join(themes)}")
            foundation_lines.append("")

        characters = chapters_yaml.get('characters', [])
        if characters:
            foundation_lines.append("## Characters\n")
            for char in characters[:6]:
                foundation_lines.append(f"- {char.get('name','Unknown')} ({char.get('role','N/A')}): {char.get('motivation','N/A')}")
            foundation_lines.append("")

        world = chapters_yaml.get('world', {})
        if world and world.get('setting_overview'):
            foundation_lines.append("## World\n")
            foundation_lines.append(f"**Setting Overview:** {world.get('setting_overview')}")
            foundation_lines.append("")

        # CHAPTERS (concise)
        for ch in chapters_yaml.get('chapters', []):
            chapters_lines.append(f"# Chapter {ch.get('number','?')}: {ch.get('title','Untitled')}")
            chapters_lines.append(f"**Act:** {ch.get('act','N/A')}")
            # summary first 2 sentences
            summary = (ch.get('summary','') or '').split('.')
            trimmed = '. '.join(s.strip() for s in summary[:2] if s.strip())
            if trimmed:
                chapters_lines.append(f"**Summary:** {trimmed}.")
            events = ch.get('key_events', [])
            if events:
                chapters_lines.append("**Key Events:**")
                for ev in events[:5]:
                    chapters_lines.append(f"- {ev}")
            chapters_lines.append("")

        return "\n".join(foundation_lines).strip(), "\n".join(chapters_lines).strip()
