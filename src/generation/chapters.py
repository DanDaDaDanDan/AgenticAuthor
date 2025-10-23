"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline
from rich.console import Console
from .lod_context import LODContextBuilder
from .depth_calculator import DepthCalculator
from ..prompts import get_prompt_loader


class ChapterGenerator:
    """
    Generator for chapter outlines (LOD2) using single-shot generation.

    SINGLE-SHOT GENERATION ARCHITECTURE:
    ===================================
    Generates ALL chapters in ONE LLM call with global arc planning.

    This prevents event duplication by giving the LLM a complete view of
    the entire story structure before generating any individual chapter.

    File Structure (NEW MARKDOWN FORMAT):
    - chapter-beats/foundation.md       (metadata + characters + world - RAW MARKDOWN)
    - chapter-beats/chapter-01.md       (chapter 1 outline - RAW MARKDOWN)
    - chapter-beats/chapter-02.md       (chapter 2 outline - RAW MARKDOWN)
    - chapter-beats/chapter-NN.md       (chapter N outline - RAW MARKDOWN)

    Benefits:
    - Global arc planning prevents duplicate events
    - Natural character progression (no repeated development beats)
    - Each chapter has unique plot role
    - Simple key_events format (proven quality from historical testing)
    - LLM plans complete story before generating details
    - Raw markdown storage for better debugging (see exactly what LLM generated)

    TOKEN REQUIREMENTS PER GENERATION:
    ==================================
    Foundation generation: ~2,000 tokens output
      - metadata: ~500 tokens
      - characters: ~1,000 tokens
      - world: ~500 tokens

    All chapters generation: ~600-800 tokens per chapter
      - Example: 15 chapters = ~12,000 tokens output
      - Single call with complete context

    STORAGE ARCHITECTURE:
    ====================
    - STORAGE: Raw markdown files (.md) - human-readable, lossless
    - RUNTIME: Parse on-the-fly using MarkdownExtractor - code gets structured dicts
    - DEBUGGING: Can see exact LLM output without YAML conversion artifacts

    BACKWARD COMPATIBILITY:
    =======================
    Old formats supported for READING:
    - chapters.yaml (legacy unified file)
    - chapter-beats/*.yaml (legacy individual files)
    New generations write ONLY markdown (.md files).
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize chapter generator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation (required)
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.project = project
        self.model = model
        self.console = Console()
        self.context_builder = LODContextBuilder()
        self.prompt_loader = get_prompt_loader()

    def _calculate_structure(self, total_words: int, pacing: str, length_scope: Optional[str] = None) -> Dict:
        """
        Calculate complete story structure using DepthCalculator.

        Args:
            total_words: Target total word count for the book
            pacing: Pacing from taxonomy (fast, moderate, slow)
            length_scope: Optional taxonomy length_scope (overrides auto-detection)

        Returns:
            Dict with form, chapter_count, base_ws, etc.
        """
        return DepthCalculator.calculate_structure(total_words, pacing, length_scope=length_scope)

    async def _generate_foundation(
        self,
        context_markdown: str,
        taxonomy_data: Dict[str, Any],
        total_words: int,
        chapter_count: int,
        original_concept: str = '',
        unique_elements: List[str] = None,
        feedback: Optional[str] = None,
        is_initial_generation: bool = False,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        genre_baseline: Optional[int] = None,
        length_scope: Optional[str] = None,
        genre: Optional[str] = None
    ) -> str:
        """
        Generate ONLY the foundation (metadata + characters + world), no chapters.

        Args:
            context_markdown: Full premise + treatment as markdown
            taxonomy_data: Taxonomy selections
            total_words: Target total word count
            chapter_count: Number of chapters (for metadata)
            original_concept: Original user concept (verbatim)
            unique_elements: LLM-identified unique story elements
            feedback: Iteration feedback (if iterating)
            is_initial_generation: True if first-time generation (no stored target)
            min_words: Minimum allowed word count from form range
            max_words: Maximum allowed word count from form range
            genre_baseline: Genre-based default word count (for reference)
            length_scope: Form name (e.g., "novel", "novella")
            genre: Genre name for context

        Returns:
            Raw markdown string (not dict) - will be saved as-is for debugging
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if unique_elements is None:
            unique_elements = []

        if logger:
            logger.debug(f"Generating foundation (metadata + characters + world)")

        # Build unique elements context
        unique_context = ""
        if original_concept or unique_elements:
            unique_context = "\n\nORIGINAL CONCEPT & UNIQUE ELEMENTS:\n"
            if original_concept:
                unique_context += f'Original Concept: "{original_concept}"\n'
                unique_context += "This reference should inform the scale, tone, and setting of the story.\n"
            if unique_elements:
                unique_context += f"Unique Elements: {', '.join(unique_elements)}\n"
                unique_context += "These elements must be central to character design, world-building, and chapter planning.\n"

        # Build metadata YAML example with optional fields
        # NOTE: target_word_count and chapter_count are NOT generated by LLM
        # They're calculated mathematically and injected after generation
        metadata_yaml_example = f"""metadata:
  genre: "..."
  subgenre: "..."
  tone: "..."
  pacing: "..."
  themes:
    - "..."
  story_structure: "..."
  narrative_style: "..."
  target_audience: "..."
  act_weights: [0.25, 0.50, 0.25]  # Act I, Act II, Act III percentages
  setting_period: "..."
  setting_location: "..."
  content_warnings: []"""

        if original_concept:
            metadata_yaml_example += f'\n  original_concept: "{original_concept}"'
        if unique_elements:
            metadata_yaml_example += '\n  core_unique_elements:'
            for elem in unique_elements:
                metadata_yaml_example += f'\n    - "{elem}"'

        # Prepare taxonomy as markdown (constraints/preferences)
        import yaml as _yaml
        taxonomy_markdown = ""
        try:
            if taxonomy_data:
                taxonomy_markdown = _yaml.dump({'selections': taxonomy_data}, sort_keys=False, allow_unicode=True)
        except Exception:
            taxonomy_markdown = str(taxonomy_data)

        # Render foundation prompt from template
        prompts = self.prompt_loader.render(
            "generation/chapter_foundation",
            context_markdown=context_markdown,
            taxonomy_markdown=taxonomy_markdown,
            unique_context=unique_context,
            metadata_yaml_example=metadata_yaml_example,
            total_words=total_words,
            chapter_count=chapter_count,
            feedback=feedback or "",
            is_initial_generation=is_initial_generation,
            min_words=min_words or 0,
            max_words=max_words or 0,
            genre_baseline=genre_baseline or 0,
            length_scope=length_scope or "",
            genre=genre or ""
        )

        # Generate foundation
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=0.6,  # Balanced creativity with adherence to treatment
            stream=True,
            display=True,
            display_label="Generating foundation",
            reserve_tokens=2000
        )

        if not result:
            raise Exception("No response from API for foundation generation")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Validate that response contains required sections (parse to check, but don't store dict)
        from ..utils.markdown_extractors import MarkdownExtractor

        try:
            # Parse markdown to validate structure (temporary - for validation only)
            foundation_data = MarkdownExtractor.extract_foundation(response_text)

            # Validate we got all required sections
            if not foundation_data.get('metadata'):
                raise ValueError("Missing metadata section in foundation")
            if not foundation_data.get('characters'):
                raise ValueError("Missing characters section in foundation")
            if not foundation_data.get('world'):
                raise ValueError("Missing world section in foundation")

            if logger:
                logger.debug(f"Foundation markdown validated successfully")

        except Exception as e:
            # Save raw response for debugging before failing
            from ..config import get_settings
            settings = get_settings()
            debug_dir = settings.get_debug_dir(self.project.name)
            debug_file = debug_dir / f'foundation_failed_{datetime.now().strftime("%Y%m%d_%H%M%S")}_raw.md'
            debug_file.write_text(response_text, encoding='utf-8')

            if logger:
                logger.error(f"Foundation validation failed: {e}")
                logger.info(f"Raw response saved to: {debug_file}")

            raise Exception(f"Failed to validate foundation from response: {str(e)}")

        if logger:
            logger.debug(f"Foundation generated successfully")
            logger.debug(f"Structure will be calculated: {total_words} words, {chapter_count} chapters")

        # Return RAW MARKDOWN (not dict) - will be saved as-is for debugging
        return response_text

    def _format_validation_issues(self, issues: List[Dict[str, Any]]) -> str:
        """
        Format validation issues for readable display in iteration prompt.

        Args:
            issues: List of validation issues from _validate_foundation_fidelity()
                    Each issue has: type, severity, element, reasoning, recommendation

        Returns:
            Formatted string with numbered issues ready for prompt inclusion
        """
        if not issues:
            return "No issues detected."

        formatted = []

        for i, issue in enumerate(issues, 1):
            issue_type = issue.get('type', 'unknown')
            element = issue.get('element', 'Unknown element')
            reasoning = issue.get('reasoning', 'No reasoning provided')
            recommendation = issue.get('recommendation', 'Fix this issue')

            # Format type nicely (e.g., "character_contradiction" -> "Character Contradiction")
            issue_type_formatted = issue_type.replace('_', ' ').title()

            formatted.append(
                f"Issue #{i}: {issue_type_formatted}\n"
                f"  Element: {element}\n"
                f"  Problem: {reasoning}\n"
                f"  Fix: {recommendation}"
            )

        return "\n\n".join(formatted)

    def _select_validation_issues(self, issues: List[Dict[str, Any]], context: str = "validation") -> List[Dict[str, Any]]:
        """
        Display validation issues and let user select which ones to incorporate.

        Args:
            issues: List of validation issues
            context: Context string for display (e.g., "foundation", "chapter 3")

        Returns:
            Filtered list of selected issues (or all issues if user selects all)
        """
        if not issues:
            return []

        self.console.print(f"\n[yellow]Detected {len(issues)} validation issue(s) in {context}:[/yellow]\n")

        # Display all issues with numbers
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get('type', 'unknown')
            element = issue.get('element', 'Unknown element')
            reasoning = issue.get('reasoning', 'No reasoning provided')
            severity = issue.get('severity', 'medium')

            # Format type nicely
            issue_type_formatted = issue_type.replace('_', ' ').title()

            # Color code by severity
            severity_color = "red" if severity == "critical" else "yellow" if severity == "high" else "dim"

            self.console.print(f"[cyan]{i}.[/cyan] [{severity_color}]{issue_type_formatted}[/{severity_color}]")
            self.console.print(f"   Element: {element}")
            self.console.print(f"   Problem: {reasoning}")
            self.console.print()

        # Prompt for selection
        self.console.print("[yellow]Which issues should be incorporated into iteration?[/yellow]")
        self.console.print("[dim]Options:[/dim]")
        self.console.print("  • Enter numbers (e.g., '1,3,5' or '1-3')")
        self.console.print("  • Enter 'all' to include all issues")
        self.console.print("  • Press Enter to include all issues (default)")
        self.console.print()

        try:
            selection = input("Enter selection: ").strip()
        except (KeyboardInterrupt, EOFError):
            # User cancelled - abort the entire operation
            self.console.print(f"\n[yellow]Selection cancelled by user.[/yellow]")
            raise KeyboardInterrupt("User cancelled issue selection")

        # Default to all if empty
        if not selection or selection.lower() == 'all':
            self.console.print(f"[green]✓[/green] Including all {len(issues)} issues\n")
            return issues

        # Parse selection
        selected_indices = set()
        try:
            parts = selection.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range (e.g., "1-3")
                    start, end = part.split('-')
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())

                    # Validate range direction
                    if start_idx > end_idx:
                        self.console.print(f"[yellow]⚠️  Range '{part}' is reversed. Did you mean {end_idx}-{start_idx}?[/yellow]")
                        # Swap to make it work
                        start_idx, end_idx = end_idx, start_idx

                    for idx in range(start_idx, end_idx + 1):
                        if 1 <= idx <= len(issues):
                            selected_indices.add(idx)
                else:
                    # Single number
                    idx = int(part)
                    if 1 <= idx <= len(issues):
                        selected_indices.add(idx)
        except ValueError:
            self.console.print(f"[red]Invalid selection format. Including all issues.[/red]\n")
            return issues

        # Filter issues
        selected_issues = [issues[i - 1] for i in sorted(selected_indices)]

        if selected_issues:
            self.console.print(f"[green]✓[/green] Selected {len(selected_issues)} of {len(issues)} issues\n")
        else:
            self.console.print(f"[yellow]No valid issues selected. Including all issues.[/yellow]\n")
            return issues

        return selected_issues

    async def _validate_foundation_fidelity(
        self,
        foundation_data: Dict[str, Any],
        treatment_text: str
    ) -> tuple[bool, List[Dict[str, Any]]]:
        """
        Validate foundation against treatment for contradictions (separate LLM call).

        This is a POST-GENERATION validation that detects contradictions between foundation and treatment.
        Uses low temperature (0.1) for consistent, strict evaluation.

        Args:
            foundation_data: Generated foundation dict with metadata, characters, world
            treatment_text: Full treatment text (source of truth)

        Returns:
            Tuple of (is_valid: bool, issues: List[Dict])
            Issues have: type, severity, element, reasoning, recommendation
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.debug(f"Validating foundation fidelity against treatment")

        # Convert foundation to markdown for validator
        from ..utils.markdown_extractors import MarkdownFormatter
        foundation_markdown = MarkdownFormatter.format_foundation(foundation_data)

        # Render validation prompt from template
        prompts = self.prompt_loader.render(
            "validation/treatment_fidelity",
            treatment_text=treatment_text,
            foundation_markdown=foundation_markdown
        )

        # Get configuration from config
        config = self.prompt_loader.get_metadata("validation/treatment_fidelity")
        temperature = config.get('temperature', 0.1)
        reserve_tokens = config.get('reserve_tokens', 200)
        use_structured_output = config.get('structured_output', False)

        # Make validation call with LOW temperature for consistency
        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompts['user']}
                ],
                temperature=temperature,
                stream=False,  # No streaming for validation
                display=False,  # Don't display during validation
                reserve_tokens=reserve_tokens,
                response_format={"type": "json_object"} if use_structured_output else None
            )

            if not result:
                raise Exception("No response from validator")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Parse JSON response
            try:
                # Strip markdown fences if present
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    # Remove fences
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)

                # Try strict parsing first, then non-strict if control characters present
                try:
                    validation_result = json.loads(response_text)
                except json.JSONDecodeError as strict_error:
                    if 'control character' in str(strict_error).lower():
                        validation_result = json.loads(response_text, strict=False)
                    else:
                        raise
            except json.JSONDecodeError as e:
                if logger:
                    logger.warning(f"Failed to parse foundation validation JSON: {e}")
                # If parsing fails, assume valid (don't block on validator errors)
                return (True, [])

            is_valid = validation_result.get('valid', True)
            critical_issues = validation_result.get('critical_issues', [])
            warnings = validation_result.get('warnings', [])

            if logger:
                logger.debug(f"Foundation validation result: valid={is_valid}, critical={len(critical_issues)}, warnings={len(warnings)}")

            return (is_valid, critical_issues)

        except Exception as e:
            if logger:
                logger.warning(f"Foundation validation call failed: {e}")

            # Validator failed - prompt user for action
            self.console.print(f"\n[bold yellow]{'='*70}[/bold yellow]")
            self.console.print(f"[bold yellow]⚠️  FOUNDATION VALIDATOR FAILURE[/bold yellow]")
            self.console.print(f"[bold yellow]{'='*70}[/bold yellow]\n")

            self.console.print(f"[yellow]Problem:[/yellow]")
            self.console.print(f"  The foundation fidelity validator encountered an error: {e}\n")

            self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
            self.console.print(f"  [cyan]1.[/cyan] Retry validation")
            self.console.print(f"  [cyan]2.[/cyan] Continue without validation [bold](NOT recommended)[/bold]")
            self.console.print(f"  [cyan]3.[/cyan] Abort generation")

            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                # Retry validation
                self.console.print(f"\n[cyan]Retrying foundation validation...[/cyan]")
                # Recursive retry - if it fails, user will be prompted again
                return await self._validate_foundation_fidelity(
                    foundation_data=foundation_data,
                    treatment_text=treatment_text
                )

            elif choice == "2":
                # Continue without validation
                self.console.print(f"\n[yellow]⚠️  Continuing without foundation validation...[/yellow]")
                self.console.print(f"[yellow]Foundation may contain treatment contradictions.[/yellow]\n")
                return (True, [])

            elif choice == "3":
                # Abort generation
                self.console.print(f"\n[red]Generation aborted due to foundation validator failure[/red]")
                raise Exception(f"User aborted generation due to foundation validator failure")

            else:
                # Invalid choice - treat as abort
                self.console.print(f"\n[red]Invalid choice, aborting generation[/red]")
                raise Exception("Invalid foundation validator failure choice")

    async def generate(
        self,
        chapter_count: Optional[int] = None,
        total_words: Optional[int] = None,
        template: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate chapter outlines using single-shot generation.

        All chapters are generated in ONE LLM call with global arc planning.
        This prevents event duplication and ensures each chapter has a unique role.

        **Architecture:**
        - Phase 1: Foundation (metadata + characters + world)
        - Phase 2: All chapters generated together with global view

        **Benefits:**
        - Prevents duplicate events across chapters
        - Natural character arc progression
        - Each chapter has unique plot role
        - LLM plans complete story before generating details

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count (auto-calculated if not provided)
            template: Optional custom template (currently unused)
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            Dict with: count, files_saved, total_words
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        try:
            # Build context (premise + treatment for chapter generation)
            context = self.context_builder.build_context(
                project=self.project,
                context_level='treatment',  # Include premise+treatment as input context
                include_downstream=False
            )

            if 'premise' not in context:
                raise Exception("No premise found. Generate premise first with /generate premise")
            if 'treatment' not in context:
                raise Exception("No treatment found. Generate treatment first with /generate treatment")

            # Get taxonomy and genre for smart defaults
            taxonomy_data = self.project.get_taxonomy() or {}
            premise_metadata = context.get('premise', {}).get('metadata', {})

            # Extract genre (with fallback detection from taxonomy)
            genre = premise_metadata.get('genre')
            if not genre and self.project.metadata:
                genre = self.project.metadata.genre

            # Infer genre from taxonomy selections if not explicitly set
            if not genre:
                from .taxonomies import TaxonomyLoader
                genre = TaxonomyLoader.infer_genre_from_selections(taxonomy_data)

            # Extract pacing (handle list format from taxonomy)
            pacing_value = taxonomy_data.get('pacing', 'moderate')
            if isinstance(pacing_value, list) and pacing_value:
                pacing = pacing_value[0]
            else:
                pacing = pacing_value if isinstance(pacing_value, str) else 'moderate'

            # Extract length_scope (handle list format from taxonomy)
            length_scope_value = taxonomy_data.get('length_scope')
            if isinstance(length_scope_value, list) and length_scope_value:
                length_scope = length_scope_value[0]
            else:
                length_scope = length_scope_value if isinstance(length_scope_value, str) else None

            # Calculate total_words if not provided
            if total_words is None:
                # Try stored value first (from previous generation)
                chapters_yaml = self.project.get_chapters_yaml()
                if chapters_yaml and isinstance(chapters_yaml, dict):
                    metadata = chapters_yaml.get('metadata', {})
                    stored_target = metadata.get('target_word_count')
                    if stored_target:
                        total_words = int(stored_target)
                        if logger:
                            logger.debug(f"Found stored target_word_count: {total_words}")

                # Calculate intelligent default if no stored value
                if total_words is None:
                    total_words = DepthCalculator.get_default_word_count(
                        length_scope or 'novel',
                        genre
                    )
                    if logger:
                        logger.debug(f"Using default word count for {genre} {length_scope or 'novel'}: {total_words}")

            # Calculate chapter count if not provided
            if not chapter_count:
                structure = self._calculate_structure(total_words, pacing, length_scope)
                chapter_count = structure['chapter_count']

            if logger:
                logger.debug(f"Structure: {chapter_count} chapters, {total_words:,} words total")

            # Serialize context to markdown for prompts
            context_markdown = self.context_builder.build_markdown_context(
                project=self.project,
                context_level='treatment'
            )

            # Extract original concept and unique elements from premise metadata
            original_concept = premise_metadata.get('original_concept', '')
            unique_elements = premise_metadata.get('unique_elements', [])

            # Check for existing foundation (prompt user if found and not iterating)
            existing_foundation = self.project.get_foundation()

            if existing_foundation and not feedback:
                # Found existing foundation - ask user what to do
                self.console.print(f"\n[yellow]⚠️  Found existing foundation (metadata + characters + world)[/yellow]")
                self.console.print(f"\nWhat would you like to do?")
                self.console.print(f"  [cyan]1.[/cyan] Use existing foundation (continue)")
                self.console.print(f"  [cyan]2.[/cyan] Regenerate foundation from scratch")
                self.console.print(f"  [cyan]3.[/cyan] Abort generation")

                choice = input("\nEnter choice (1-3): ").strip()

                if choice == "1":
                    # Use existing foundation
                    self.console.print(f"\n[cyan][1/2] Loading existing foundation...[/cyan]")
                    foundation = existing_foundation
                    self.console.print(f"[green]✓[/green] Foundation loaded")

                    if logger:
                        logger.debug("Using existing foundation from chapter-beats/foundation.yaml")
                        logger.debug(f"Structure recalculated from taxonomy: {total_words} words, {chapter_count} chapters")

                elif choice == "2":
                    # Regenerate foundation
                    self.console.print(f"\n[yellow]Regenerating foundation from scratch...[/yellow]")
                    existing_foundation = None  # Force regeneration below
                elif choice == "3":
                    # Abort
                    self.console.print(f"[yellow]Generation aborted[/yellow]")
                    raise Exception("User aborted generation")
                else:
                    self.console.print(f"[yellow]Invalid choice, aborting[/yellow]")
                    raise Exception("Invalid foundation choice")

            if not existing_foundation or feedback:
                # Generate foundation (initial generation or iteration)
                if existing_foundation and feedback:
                    self.console.print(f"\n[cyan][1/2] Regenerating foundation (iteration mode)...[/cyan]")
                else:
                    self.console.print(f"\n[cyan][1/2] Generating foundation (metadata + characters + world)...[/cyan]")

                foundation = await self._generate_foundation(
                    context_markdown=context_markdown,
                    taxonomy_data=taxonomy_data,
                    total_words=total_words,
                    chapter_count=chapter_count,
                    original_concept=original_concept,
                    unique_elements=unique_elements,
                    feedback=feedback,
                    genre=genre
                )

                # Save foundation as raw markdown (NEW FORMAT)
                self.project.save_foundation_markdown(foundation)
                self.console.print(f"[green]✓[/green] Foundation complete")

                # Parse markdown to dict for use in chapter generation
                from ..utils.markdown_extractors import MarkdownExtractor
                foundation = MarkdownExtractor.extract_foundation(foundation)


            # Generate all chapters with single-shot method
            self.console.print(f"[cyan][2/2] Generating all {chapter_count} chapters in one call...[/cyan]")
            self.console.print(f"[dim]Using classic key_events format (proven quality)[/dim]\n")

            chapters = await self._generate_single_shot(
                context=context,
                foundation=foundation,
                total_words=total_words,
                chapter_count=chapter_count,
                genre=genre,
                pacing=pacing,
                feedback=feedback
            )

            return chapters

        except Exception as e:
            raise Exception(f"Failed to generate chapters: {e}")

    def _extract_chapters_by_pattern(self, response_text: str) -> List[tuple[int, str]]:
        """
        Extract chapters by finding '- number: N' boundaries.

        Used as fallback when strict YAML parsing fails. This method finds chapter
        boundaries by pattern matching and extracts raw YAML text between them.

        Args:
            response_text: Raw LLM response text containing chapters

        Returns:
            List of (chapter_num, raw_yaml_text) tuples

        Note: Does NOT validate YAML - just extracts text between boundaries.
              Validation happens per-chapter when this data is used.
        """
        import re
        from ..utils.logging import get_logger
        logger = get_logger()

        lines = response_text.split('\n')

        # Find all chapter start lines: "- number: N" or "  - number: N"
        chapter_starts = []
        pattern = r'^\s*-\s*number:\s*(\d+)'

        for line_num, line in enumerate(lines):
            match = re.match(pattern, line)
            if match:
                chapter_num = int(match.group(1))
                chapter_starts.append((line_num, chapter_num))

                if logger:
                    logger.debug(f"Found chapter {chapter_num} at line {line_num + 1}")

        if not chapter_starts:
            if logger:
                logger.warning("Pattern extraction found no chapters")
            return []

        if logger:
            logger.info(f"Pattern extraction found {len(chapter_starts)} chapter boundaries")

        # Extract text between chapter boundaries
        chapters = []
        for i, (start_line, chapter_num) in enumerate(chapter_starts):
            if i + 1 < len(chapter_starts):
                end_line = chapter_starts[i + 1][0]
            else:
                end_line = len(lines)

            chapter_lines = lines[start_line:end_line]
            chapter_yaml = '\n'.join(chapter_lines).strip()

            chapters.append((chapter_num, chapter_yaml))

            if logger:
                logger.debug(f"Extracted chapter {chapter_num}: {len(chapter_yaml)} characters")

        return chapters

    async def _generate_single_shot(
        self,
        context: Dict[str, Any],
        foundation: Dict[str, Any],
        total_words: Optional[int],
        chapter_count: Optional[int],
        genre: str,
        pacing: str,
        feedback: Optional[str] = None,
        temperature: float = 0.7,
        output_dir: Optional[Path] = None,
        auto_plan: bool = False,
        act_weights: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Generate all chapters in a single LLM call using OLD PROVEN FORMAT.

        This prevents duplication of character development beats and plot events
        by giving the LLM a global view of the entire story structure.

        Uses simple key_events format (not complex scenes structure) which has
        historically produced higher quality results with less duplication.

        Args:
            context: Story context (premise + treatment)
            foundation: Foundation data (metadata + characters + world)
            total_words: Target total word count
            chapter_count: Number of chapters
            genre: Story genre
            pacing: Story pacing
            feedback: Optional feedback for iteration
            temperature: LLM temperature (default 0.7, higher = more creative)
            output_dir: Custom output directory (default: project.chapter_beats_dir)

        Returns:
            Dict with: count, files_saved, total_words
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        # Calculate defaults if not provided
        if total_words is None:
            # Use intelligent default based on genre
            total_words = DepthCalculator.get_default_word_count('novel', genre)
            if logger:
                logger.debug(f"Using default word count for {genre} novel: {total_words}")

        if chapter_count is None:
            # Calculate baseline chapter count for estimates only (auto-plan may override)
            structure = self._calculate_structure(total_words, pacing, length_scope=None)
            chapter_count = structure['chapter_count']
            if logger:
                logger.debug(f"Calculated baseline chapter count: {chapter_count}")

        count_label = f"auto" if auto_plan else f"{chapter_count}"
        self.console.print(f"\n[cyan]Generating chapters in single call (count: {count_label})...[/cyan]")
        if total_words and not auto_plan:
            self.console.print(f"[dim]Target: {total_words:,} words (chapter count from baseline)")
        self.console.print(f"[dim]Using classic key_events format (proven quality)[/dim]\n")

        # Load context as markdown (premise + treatment)
        context_markdown = self.context_builder.build_markdown_context(
            project=self.project,
            context_level='treatment'
        )

        # Convert foundation dict to markdown for prompt
        from ..utils.markdown_extractors import MarkdownFormatter
        foundation_markdown = MarkdownFormatter.format_foundation(foundation)

        # Load taxonomy selections and format as markdown
        taxonomy_data = self.project.get_taxonomy() or {}
        import yaml as _yaml
        taxonomy_markdown = ""
        try:
            if taxonomy_data:
                taxonomy_markdown = _yaml.dump({'selections': taxonomy_data}, sort_keys=False, allow_unicode=True)
        except Exception:
            taxonomy_markdown = str(taxonomy_data)

        # Default act weights if not provided
        if not act_weights:
            act_weights = [0.25, 0.50, 0.25]

        # Render chapters generation prompt from template
        prompts = self.prompt_loader.render(
            "generation/chapter_single_shot",
            context_markdown=context_markdown,
            foundation_markdown=foundation_markdown,
            taxonomy_markdown=taxonomy_markdown,
            chapter_count=chapter_count,
            total_words=total_words or 0,
            act_weights=act_weights,
            auto_plan=auto_plan,
            feedback=feedback or ""
        )

        # Generate with API
        try:
            # Estimate tokens
            from ..utils.tokens import estimate_messages_tokens
            prompt_tokens = estimate_messages_tokens([{"role": "user", "content": prompts['user']}])

            # Response needs ~600-800 tokens per chapter for rich outlines
            # Plus overhead for structure
            estimated_response_tokens = 2000 + (chapter_count * 700)

            if logger:
                logger.debug(f"Single-shot generation: ~{prompt_tokens} prompt tokens, ~{estimated_response_tokens} response tokens")

            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompts['user']}
                ],
                temperature=temperature,  # Use parameter for temperature variation
                display=True,
                display_label=f"Generating all {'auto' if auto_plan else chapter_count} chapters",
                reserve_tokens=estimated_response_tokens
            )

            if not result:
                raise Exception("No response from API")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Parse the chapters using markdown extractor (for validation and metadata)
            from ..utils.markdown_extractors import MarkdownExtractor
            warnings = []  # Track any extraction issues

            try:
                # Validate structure by parsing to dicts
                chapters_data = MarkdownExtractor.extract_chapters(response_text)

                if not chapters_data:
                    raise ValueError("No chapters extracted from response")

                if logger:
                    logger.debug(f"Markdown extraction succeeded: {len(chapters_data)} chapters")

                # Extract individual chapter markdown sections (raw text)
                chapter_markdown_sections = MarkdownExtractor.split_chapters_only(response_text)

                if len(chapter_markdown_sections) != len(chapters_data):
                    raise ValueError(
                        f"Mismatch between parsed chapters ({len(chapters_data)}) "
                        f"and markdown sections ({len(chapter_markdown_sections)})"
                    )

            except Exception as extract_error:
                # Extraction failed - save raw response and show error
                if logger:
                    logger.error(f"Markdown extraction failed: {extract_error}")

                # Save raw response for debugging
                from ..config import get_settings
                settings = get_settings()
                debug_dir = settings.get_debug_dir(self.project.name)
                debug_file = debug_dir / f'chapters_failed_{datetime.now().strftime("%Y%m%d_%H%M%S")}_raw.md'
                debug_file.write_text(response_text, encoding='utf-8')

                self.console.print(f"[red]Failed to extract chapters from response[/red]")
                self.console.print(f"[yellow]Raw response saved to: {debug_file.relative_to(self.project.path)}[/yellow]")

                raise Exception(
                    f"Failed to extract chapters from markdown response: {extract_error}\n"
                    f"Response preview (first 500 chars):\n{response_text[:500]}"
                )

            # Save individual chapter beat files as markdown (NEW FORMAT)
            # Use custom output_dir if provided, otherwise use default chapter-beats/
            if output_dir is None:
                beats_dir = self.project.chapter_beats_dir
            else:
                beats_dir = output_dir

            beats_dir.mkdir(parents=True, exist_ok=True)

            # Clean up old chapter files before saving new ones
            # This prevents stale files from previous generations
            for old_chapter in beats_dir.glob('chapter-*.md'):
                old_chapter.unlink()
                if logger:
                    logger.debug(f"Removed old chapter file: {old_chapter.name}")

            # Save each chapter as raw markdown
            for i, chapter in enumerate(chapters_data):
                chapter_num = chapter.get('number', 0)
                if chapter_num:
                    # Get the corresponding markdown section
                    chapter_markdown = chapter_markdown_sections[i]

                    # Save directly to beats_dir (supports both default and custom paths)
                    chapter_path = beats_dir / f'chapter-{chapter_num:02d}.md'
                    chapter_path.write_text(chapter_markdown, encoding='utf-8')

            if logger:
                logger.debug(f"Saved {len(chapters_data)} chapters to individual beat files")

            # Basic validation (no ChapterOutline conversion - files are source of truth)
            chapter_count_saved = len(chapters_data)

            # Use calculated total_words (not from foundation - foundation only has creative content)
            avg_words_per_chapter = total_words // chapter_count_saved if chapter_count_saved > 0 else 0

            self.console.print(f"\n[green]✓[/green] Generated {chapter_count_saved} chapters successfully")
            self.console.print(f"[dim]Overall target: {total_words:,} words for {chapter_count_saved} chapters (~{avg_words_per_chapter:,} words/chapter average)[/dim]")

            # Display warnings if any YAML issues were encountered
            if warnings:
                self.console.print(f"\n[yellow]⚠️  YAML Warnings ({len(warnings)} chapter(s) with issues):[/yellow]")
                for warning in warnings:
                    chapter_num = warning.get('chapter', 'unknown')
                    issue = warning.get('issue', 'No issue details')
                    self.console.print(f"  [yellow]•[/yellow] Chapter {chapter_num}: {issue}")

                self.console.print(f"\n[cyan]Note: {len(chapters_data)} chapters saved, {len(warnings)} chapters skipped due to YAML errors[/cyan]")

                if logger:
                    logger.warning(f"Generated with {len(warnings)} YAML warnings - manual review recommended")

            # Return summary dict (not ChapterOutline objects)
            return {
                'count': len(chapters_data),
                'files_saved': chapter_count_saved,
                'total_words': total_words,  # Use calculated value, not from foundation
                'warnings': warnings  # Include warnings for caller
            }

        except Exception as e:
            if logger:
                logger.error(f"Single-shot generation failed: {e}")
            raise Exception(f"Failed to generate chapters: {e}")
