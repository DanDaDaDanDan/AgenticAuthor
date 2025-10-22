"""LLM-based judging for multi-variant chapter generation."""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import yaml
import shutil

from rich.console import Console

from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader


class JudgingCoordinator:
    """
    Coordinate LLM-based evaluation and selection of chapter outline variants.

    Uses minimal structure to give LLM freedom in judging criteria and reasoning.
    Saves judging decisions for transparency and reproducibility.
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize judging coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for judging
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        self.client = client
        self.project = project
        self.model = model
        self.console = Console()
        self.prompt_loader = get_prompt_loader()
        self.variants_dir = project.path / 'chapter-beats-variants'
        self.decisions_file = self.variants_dir / 'decision.json'

    def _build_judging_prompt(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> Dict[str, str]:
        """
        Build judging prompt with minimal structure using PromptLoader.

        User requirement: "allow the LLM freedom to judge how it sees fit; no need to overly provide structure"

        This prompt provides context and asks for evaluation, but doesn't prescribe
        specific criteria, scoring systems, or weights. LLM decides what matters.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Dict with 'system' and 'user' prompts
        """
        from .variants import VARIANT_CONFIGS
        from ..utils.markdown_extractors import MarkdownFormatter

        # Convert foundation dict back to markdown
        foundation_markdown = MarkdownFormatter.format_foundation(foundation)

        # Build variants sections by loading markdown files
        variants_sections = ""
        for variant_num in sorted(variants_data.keys()):
            # Find config for this variant
            config = next((c for c in VARIANT_CONFIGS if c['variant'] == variant_num), None)
            temp_label = ""
            if config:
                temp_label = f" - Temperature: {config['temperature']} ({config['label']})"

            # Load chapter markdown files for this variant
            variant_dir = self.variants_dir / f'variant-{variant_num}'
            chapter_files = sorted(variant_dir.glob('chapter-*.md'))

            chapters_markdown = ""
            for chapter_file in chapter_files:
                chapter_text = chapter_file.read_text(encoding='utf-8')
                chapters_markdown += chapter_text + "\n\n---\n\n"

            variants_sections += f"""VARIANT {variant_num}{temp_label}:

{chapters_markdown}

---

"""

        # Build list of actual variant numbers (e.g., "1, 3, 4" if variant 2 failed)
        variant_numbers = ', '.join(map(str, sorted(variants_data.keys())))

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "analysis/chapter_judging",
            variants_count=len(variants_data),
            foundation_markdown=foundation_markdown,
            variants_sections=variants_sections,
            variant_numbers=variant_numbers
        )

        return prompts

    async def judge_variants(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> Tuple[int, str]:
        """
        Call LLM to judge variants and select winner.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Tuple of (winner_variant_num, reasoning)

        Raises:
            Exception: If judging fails or returns invalid response
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== VARIANT JUDGING START ===")
            logger.info(f"Judging {len(variants_data)} variants")
            logger.info(f"Using model: {self.model}")

        # Build prompt
        prompts = self._build_judging_prompt(foundation, variants_data)

        if logger:
            logger.debug(f"Judging prompt length: {len(prompts['user'])} characters")

        # Get configuration from config
        config = self.prompt_loader.get_metadata("analysis/chapter_judging")
        temperature = config.get('temperature', 0.1)
        reserve_tokens = config.get('reserve_tokens', 100)
        use_structured_output = config.get('structured_output', False)

        # Make judging call with LOW temperature for consistency
        self.console.print(f"\n[cyan]Judging {len(variants_data)} variants...[/cyan]")
        self.console.print(f"[dim]Using model: {self.model}[/dim]\n")

        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompts['user']}
                ],
                temperature=temperature,
                stream=False,  # No streaming for judging (want complete response)
                display=False,  # Don't display during judging
                reserve_tokens=reserve_tokens,
                response_format={"type": "json_object"} if use_structured_output else None
            )

            if not result:
                raise Exception("No response from LLM judge")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            if logger:
                logger.debug(f"Judging response length: {len(response_text)} characters")
                logger.debug(f"Judging response preview: {response_text[:500]}...")

            # Parse JSON response
            try:
                # Strip markdown fences if present
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    # Remove fences
                    lines = response_text.split('\n')
                    # Skip first and last lines (fences)
                    response_text = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)
                    response_text = response_text.strip()

                # Remove 'json' language identifier if present
                if response_text.startswith('json'):
                    response_text = response_text[4:].strip()

                # Try strict parsing first
                try:
                    judging_result = json.loads(response_text)
                except json.JSONDecodeError as strict_error:
                    # If strict parsing fails due to control characters, try non-strict
                    if 'control character' in str(strict_error).lower():
                        if logger:
                            logger.warning(f"JSON contains control characters, using non-strict parsing")
                        judging_result = json.loads(response_text, strict=False)
                    else:
                        # Other JSON error - re-raise
                        raise

            except json.JSONDecodeError as e:
                if logger:
                    logger.error(f"Failed to parse judging JSON: {e}")
                    logger.error(f"Response text: {response_text}")

                # Check for truncated response (unterminated string)
                error_str = str(e).lower()
                if 'unterminated string' in error_str or 'unterminated' in error_str:
                    raise Exception(
                        f"Judging response was truncated (incomplete JSON). "
                        f"The LLM hit the token limit mid-response. "
                        f"Error: {e}\n"
                        f"Response length: {len(response_text)} characters\n"
                        f"This should not happen with reserve_tokens={reserve_tokens}. "
                        f"Consider increasing reserve_tokens in src/prompts/config.yaml"
                    )

                raise Exception(f"Failed to parse judging response as JSON: {e}")

            # Extract winner and reasoning
            winner = judging_result.get('winner')
            reasoning = judging_result.get('reasoning', 'No reasoning provided')

            if not winner:
                raise Exception("Judging response missing 'winner' field")

            # Convert winner to int (LLM might return string "1" instead of int 1)
            try:
                winner = int(winner)
            except (TypeError, ValueError) as e:
                raise Exception(
                    f"Invalid winner type: {type(winner).__name__} (value: {winner}). "
                    f"Expected integer variant number."
                )

            # Validate winner is in valid range
            if winner not in variants_data:
                raise Exception(
                    f"Invalid winner variant number: {winner}. "
                    f"Must be one of: {list(variants_data.keys())}"
                )

            if logger:
                logger.info(f"Judging complete: Winner is Variant {winner}")
                logger.debug(f"Reasoning: {reasoning}")

            # Display results
            self.console.print(f"[green]✓ Judging complete[/green]\n")
            self.console.print(f"[bold cyan]Winner: Variant {winner}[/bold cyan]")
            self.console.print(f"\n[white]Reasoning:[/white]")
            self.console.print(f"[dim]{reasoning}[/dim]\n")

            return (winner, reasoning)

        except Exception as e:
            if logger:
                logger.error(f"Judging failed: {e}")
            raise

    def _save_decision(
        self,
        winner: int,
        reasoning: str,
        variants_evaluated: List[int],
        timestamp: Optional[str] = None
    ):
        """
        Save judging decision to decision.json for transparency.

        Args:
            winner: Winning variant number
            reasoning: LLM's reasoning for selection
            variants_evaluated: List of variant numbers that were evaluated
            timestamp: Optional timestamp (defaults to now)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if timestamp is None:
            timestamp = datetime.now().isoformat()

        decision_data = {
            'timestamp': timestamp,
            'model': self.model,
            'winner': winner,
            'reasoning': reasoning,
            'variants_evaluated': variants_evaluated,
            'decision_method': 'llm_judging'
        }

        # Ensure variants directory exists
        self.variants_dir.mkdir(exist_ok=True)

        # Save decision
        with open(self.decisions_file, 'w', encoding='utf-8') as f:
            json.dump(decision_data, f, indent=2)

        if logger:
            logger.info(f"Saved judging decision to: {self.decisions_file}")

    def _generate_combined_chapters_md(self, beats_dir: Path, foundation_path: Path):
        """
        Generate a combined chapters.md file with all chapter outlines in readable format.

        Args:
            beats_dir: Directory containing chapter-*.md files
            foundation_path: Path to foundation.md file
        """
        from ..utils.logging import get_logger
        from ..utils.markdown_extractors import MarkdownExtractor

        logger = get_logger()

        if logger:
            logger.debug("Generating combined chapters.md from chapter beats")

        # Read foundation from markdown
        try:
            with open(foundation_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
            foundation = MarkdownExtractor.extract_foundation(markdown_text)
        except Exception as e:
            if logger:
                logger.warning(f"Failed to load foundation for chapters.md: {e}")
            foundation = {}

        # Read all chapter files from markdown
        chapter_files = sorted(beats_dir.glob('chapter-*.md'))
        chapters_data = []

        for chapter_file in chapter_files:
            try:
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()
                # Parse individual chapter markdown
                chapter_dicts = MarkdownExtractor.extract_chapters(markdown_text)
                if chapter_dicts:
                    chapters_data.append(chapter_dicts[0])  # Each file has one chapter
            except Exception as e:
                if logger:
                    logger.warning(f"Failed to load {chapter_file.name}: {e}")

        if not chapters_data:
            if logger:
                logger.warning("No chapter data found for chapters.md generation")
            return

        # Build combined markdown
        lines = []
        lines.append("# Chapter Outlines\n")
        lines.append(f"*Generated from {len(chapters_data)} chapter beats*\n")
        lines.append("---\n")

        # Add foundation summary
        if foundation:
            metadata = foundation.get('metadata', {})
            if metadata:
                lines.append("## Story Metadata\n")
                for key, value in metadata.items():
                    if isinstance(value, list):
                        lines.append(f"**{key.replace('_', ' ').title()}:**")
                        for item in value:
                            lines.append(f"  - {item}")
                        lines.append("")
                    else:
                        lines.append(f"**{key.replace('_', ' ').title()}:** {value}\n")
                lines.append("---\n")

        # Add each chapter
        for chapter in chapters_data:
            chapter_num = chapter.get('number', '?')
            title = chapter.get('title', 'Untitled')
            summary = chapter.get('summary', '')
            key_events = chapter.get('key_events', [])
            character_development = chapter.get('character_development', [])
            emotional_beats = chapter.get('emotional_beats', [])

            lines.append(f"## Chapter {chapter_num}: {title}\n")

            if summary:
                lines.append(f"**Summary:** {summary}\n")

            if key_events:
                lines.append("**Key Events:**")
                for event in key_events:
                    lines.append(f"  - {event}")
                lines.append("")

            if character_development:
                lines.append("**Character Development:**")
                for dev in character_development:
                    lines.append(f"  - {dev}")
                lines.append("")

            if emotional_beats:
                lines.append("**Emotional Beats:**")
                for beat in emotional_beats:
                    lines.append(f"  - {beat}")
                lines.append("")

            lines.append("---\n")

        # Write to chapters/ directory
        chapters_dir = self.project.path / 'chapters'
        chapters_dir.mkdir(exist_ok=True)

        output_file = chapters_dir / 'chapters.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        if logger:
            logger.info(f"Generated combined chapters.md: {output_file}")

    def finalize_winner(
        self,
        winner_variant_num: int,
        reasoning: str,
        variants_evaluated: List[int]
    ):
        """
        Copy winning variant to chapter-beats/ directory and save decision.

        Args:
            winner_variant_num: Winning variant number
            reasoning: LLM's reasoning for selection
            variants_evaluated: List of variant numbers that were evaluated
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== FINALIZING WINNER: Variant {winner_variant_num} ===")

        # Source: chapter-beats-variants/variant-N/
        variant_dir = self.variants_dir / f'variant-{winner_variant_num}'

        # Destination: chapter-beats/
        beats_dir = self.project.chapter_beats_dir

        if not variant_dir.exists():
            raise Exception(f"Winner variant directory not found: {variant_dir}")

        # Ensure chapter-beats/ directory exists
        beats_dir.mkdir(exist_ok=True)

        # Copy foundation (shared by all variants) - markdown format
        foundation_src = self.variants_dir / 'foundation.md'
        foundation_dst = beats_dir / 'foundation.md'

        if foundation_src.exists():
            shutil.copy2(foundation_src, foundation_dst)

            if logger:
                logger.debug(f"Copied foundation: {foundation_src} -> {foundation_dst}")
        else:
            if logger:
                logger.warning(f"Foundation not found at {foundation_src}")

        # Copy all chapter files from winner variant - markdown format
        chapter_files = sorted(variant_dir.glob('chapter-*.md'))

        if logger:
            logger.debug(f"Copying {len(chapter_files)} chapter files from variant {winner_variant_num}")

        for chapter_file in chapter_files:
            dst_file = beats_dir / chapter_file.name
            shutil.copy2(chapter_file, dst_file)

            if logger:
                logger.debug(f"Copied: {chapter_file.name}")

        # Save decision record
        self._save_decision(
            winner=winner_variant_num,
            reasoning=reasoning,
            variants_evaluated=variants_evaluated
        )

        # Generate combined chapters.md file in chapters/ directory
        self._generate_combined_chapters_md(beats_dir, foundation_src if foundation_src.exists() else foundation_dst)

        self.console.print(f"[green]✓ Finalized Variant {winner_variant_num} to chapter-beats/[/green]")
        self.console.print(f"[dim]Copied {len(chapter_files)} chapter files + foundation + chapters.md[/dim]\n")

        if logger:
            logger.info(f"=== FINALIZATION COMPLETE ===")

    async def judge_and_finalize(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> int:
        """
        Complete workflow: judge variants and finalize winner.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Winner variant number

        Raises:
            Exception: If judging or finalization fails
        """
        # Judge variants
        winner, reasoning = await self.judge_variants(foundation, variants_data)

        # Finalize winner
        self.finalize_winner(
            winner_variant_num=winner,
            reasoning=reasoning,
            variants_evaluated=list(variants_data.keys())
        )

        return winner

    def get_decision(self) -> Optional[Dict[str, Any]]:
        """
        Load saved judging decision.

        Returns:
            Decision dict with winner, reasoning, timestamp, etc., or None if not found
        """
        if self.decisions_file.exists():
            with open(self.decisions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
