"""Multi-variant chapter generation for AgenticAuthor."""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import yaml

from rich.console import Console
from rich.table import Table
from rich.live import Live

from ..models import Project
from .chapters import ChapterGenerator


# Variant configuration with temperature variation
VARIANT_CONFIGS = [
    {"variant": 1, "temperature": 0.55, "label": "Conservative"},
    {"variant": 2, "temperature": 0.60, "label": "Balanced-Conservative"},
    {"variant": 3, "temperature": 0.65, "label": "Balanced-Creative"},
    {"variant": 4, "temperature": 0.70, "label": "Creative"},
]


class VariantManager:
    """
    Manage parallel generation of multiple chapter outline variants.

    Generates 4 variants with different temperatures in parallel,
    providing variety for LLM-based judging and selection.

    Architecture:
    - Reuses ChapterGenerator._generate_single_shot() for generation logic
    - Only varies temperature and output directory
    - No code duplication - pure composition pattern
    """

    def __init__(self, chapter_generator: ChapterGenerator, project: Project):
        """
        Initialize variant manager.

        Args:
            chapter_generator: Existing ChapterGenerator instance to reuse
            project: Current project
        """
        self.generator = chapter_generator
        self.project = project
        self.console = Console()
        self.variants_dir = project.path / 'chapter-beats-variants'

    def _get_variant_dir(self, variant_num: int) -> Path:
        """
        Get path to variant subdirectory.

        Args:
            variant_num: Variant number (1-4)

        Returns:
            Path to variant-N/ directory
        """
        return self.variants_dir / f'variant-{variant_num}'

    def _get_foundation_path(self) -> Path:
        """
        Get path to shared foundation file.

        Returns:
            Path to chapter-beats-variants/foundation.md
        """
        return self.variants_dir / 'foundation.md'

    async def _generate_single_variant(
        self,
        variant_num: int,
        temperature: float,
        context: Dict[str, Any],
        foundation: Dict[str, Any],
        total_words: int,
        chapter_count: Optional[int],
        genre: str,
        pacing: str,
        feedback: Optional[str] = None,
        auto_plan: bool = False,
        act_weights: Optional[list] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Generate a single variant using ChapterGenerator.

        This method wraps ChapterGenerator._generate_single_shot() with
        variant-specific parameters (temperature, output_dir).

        Args:
            variant_num: Variant number (1-4)
            temperature: LLM temperature for this variant
            context: Story context (premise + treatment)
            foundation: Foundation data (metadata + characters + world)
            total_words: Target total word count
            chapter_count: Number of chapters
            genre: Story genre
            pacing: Story pacing
            feedback: Optional feedback for iteration

        Returns:
            Tuple of (variant_num, result_dict)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        variant_dir = self._get_variant_dir(variant_num)

        if logger:
            logger.debug(f"Variant {variant_num}: Starting generation with temperature {temperature}")
            logger.debug(f"Variant {variant_num}: Output directory: {variant_dir}")

        try:
            # Call existing _generate_single_shot() with variant-specific params
            result = await self.generator._generate_single_shot(
                context=context,
                foundation=foundation,
                total_words=total_words,
                chapter_count=chapter_count,
                genre=genre,
                pacing=pacing,
                feedback=feedback,
                temperature=temperature,  # VARIANT-SPECIFIC
                output_dir=variant_dir,   # VARIANT-SPECIFIC
                auto_plan=auto_plan,
                act_weights=act_weights
            )

            if logger:
                logger.debug(f"Variant {variant_num}: Generation complete - {result.get('files_saved', 0)} chapters")

            return (variant_num, result)

        except Exception as e:
            if logger:
                logger.error(f"Variant {variant_num}: Generation failed - {e}")
            raise Exception(f"Variant {variant_num} failed: {e}")

    async def generate_variants(
        self,
        context: Dict[str, Any],
        foundation: Dict[str, Any],
        total_words: int,
        chapter_count: Optional[int],
        genre: str,
        pacing: str,
        feedback: Optional[str] = None,
        auto_plan: bool = False,
        act_weights: Optional[list] = None
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Generate 4 variants in parallel with different temperatures.

        Uses asyncio.gather() for concurrent execution with visual progress display.

        Args:
            context: Story context (premise + treatment)
            foundation: Foundation data (metadata + characters + world)
            total_words: Target total word count
            chapter_count: Number of chapters
            genre: Story genre
            pacing: Story pacing
            feedback: Optional feedback for iteration

        Returns:
            List of (variant_num, result_dict) tuples for successful variants

        Raises:
            Exception: If fewer than 2 variants succeed (minimum requirement)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== VARIANT GENERATION START ===")
            logger.info(f"Target: {'auto chapters' if auto_plan else f'{chapter_count} chapters'}, {total_words:,} words")
            logger.info(f"Variants: {len(VARIANT_CONFIGS)} parallel generations")

        # Ensure variants directory exists
        self.variants_dir.mkdir(exist_ok=True)

        # Save shared foundation as markdown (NEW FORMAT)
        # Convert dict back to markdown using MarkdownFormatter
        from ..utils.markdown_extractors import MarkdownFormatter
        foundation_markdown = MarkdownFormatter.format_foundation(foundation)

        foundation_path = self._get_foundation_path()
        foundation_path.write_text(foundation_markdown, encoding='utf-8')

        if logger:
            logger.debug(f"Saved shared foundation to: {foundation_path}")

        # Create progress table
        table = Table(title=f"Generating {len(VARIANT_CONFIGS)} Variants in Parallel", show_header=True)
        table.add_column("Variant", style="cyan", width=10)
        table.add_column("Temp", style="dim", width=6)
        table.add_column("Label", style="white", width=22)
        table.add_column("Status", style="white", width=30)

        # Add initial rows
        for config in VARIANT_CONFIGS:
            table.add_row(
                f"Variant {config['variant']}",
                str(config['temperature']),
                config['label'],
                "[yellow]Starting...[/yellow]"
            )

        # Build tasks for parallel execution
        tasks = []
        for config in VARIANT_CONFIGS:
            task = self._generate_single_variant(
                variant_num=config['variant'],
                temperature=config['temperature'],
                context=context,
                foundation=foundation,
                total_words=total_words,
                chapter_count=chapter_count,
                genre=genre,
                pacing=pacing,
                feedback=feedback,
                auto_plan=auto_plan,
                act_weights=act_weights
            )
            tasks.append(task)

        # Display progress and execute in parallel
        self.console.print()  # Blank line
        self.console.print(table)
        self.console.print()

        # Note: Rich Live Display with dynamic updates would be ideal here,
        # but requires complex streaming coordination. For now, use simple
        # sequential completion display.

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful = []
        failed = []

        for i, result in enumerate(results, 1):
            config = VARIANT_CONFIGS[i-1]

            if isinstance(result, Exception):
                error_msg = str(result)
                self.console.print(f"[red]✗ Variant {i} ({config['label']}) failed:[/red] {error_msg}")
                failed.append((i, result))

                if logger:
                    logger.error(f"Variant {i} failed: {error_msg}")
            else:
                variant_num, result_dict = result
                files_saved = result_dict.get('files_saved', 0)
                total_words_target = result_dict.get('total_words', 0)

                self.console.print(
                    f"[green]✓ Variant {variant_num} ({config['label']}) complete:[/green] "
                    f"{files_saved} chapters, {total_words_target:,} words"
                )
                successful.append(result)

                if logger:
                    logger.info(f"Variant {variant_num} succeeded: {files_saved} chapters")

        # Check minimum requirement (2+ variants)
        if len(successful) < 2:
            error_msg = f"Only {len(successful)}/4 variants succeeded. Need at least 2 to continue."
            self.console.print(f"\n[red]ERROR: {error_msg}[/red]")

            if logger:
                logger.error(error_msg)

            raise Exception(error_msg)

        # Summary
        self.console.print()
        self.console.print(f"[cyan]Generated {len(successful)}/4 variants successfully[/cyan]")

        if failed:
            self.console.print(f"[yellow]⚠ {len(failed)} variant(s) failed but continuing with {len(successful)}[/yellow]")

        if logger:
            logger.info(f"=== VARIANT GENERATION COMPLETE: {len(successful)}/4 succeeded ===")

        return successful

    def list_variants(self) -> List[int]:
        """
        List available variant numbers in variants directory.

        Returns:
            List of variant numbers (e.g., [1, 2, 3, 4])
        """
        if not self.variants_dir.exists():
            return []

        variants = []
        for variant_dir in self.variants_dir.glob('variant-*'):
            if variant_dir.is_dir():
                try:
                    variant_num = int(variant_dir.name.split('-')[1])
                    variants.append(variant_num)
                except (IndexError, ValueError):
                    # Skip malformed directory names
                    continue

        return sorted(variants)

    def get_variant_data(self, variant_num: int) -> Optional[List[Dict[str, Any]]]:
        """
        Load chapter data for a specific variant.

        Args:
            variant_num: Variant number (1-4)

        Returns:
            List of chapter dicts, or None if variant not found
        """
        variant_dir = self._get_variant_dir(variant_num)

        if not variant_dir.exists():
            return None

        # Load from markdown files (NEW FORMAT)
        from ..utils.markdown_extractors import MarkdownExtractor

        chapters = []
        for chapter_file in sorted(variant_dir.glob('chapter-*.md')):
            with open(chapter_file, 'r', encoding='utf-8') as f:
                markdown_text = f.read()

            # Parse individual chapter markdown to dict
            chapter_dicts = MarkdownExtractor.extract_chapters(markdown_text)
            if chapter_dicts:
                # Each file contains one chapter, but extract_chapters returns a list
                chapters.append(chapter_dicts[0])

        if chapters:
            return sorted(chapters, key=lambda x: x.get('number', 0))

        return None

    def get_all_variants_data(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Load chapter data for all available variants.

        Returns:
            Dict mapping variant_num -> list of chapter dicts
        """
        variants_data = {}

        for variant_num in self.list_variants():
            variant_data = self.get_variant_data(variant_num)
            if variant_data:
                variants_data[variant_num] = variant_data

        return variants_data

    def get_foundation(self) -> Optional[Dict[str, Any]]:
        """
        Load shared foundation data.

        Returns:
            Foundation dict with metadata, characters, world, or None if not found
        """
        foundation_path = self._get_foundation_path()

        if foundation_path.exists():
            # Load from markdown file (NEW FORMAT)
            from ..utils.markdown_extractors import MarkdownExtractor

            with open(foundation_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()

            return MarkdownExtractor.extract_foundation(markdown_text)

        return None
