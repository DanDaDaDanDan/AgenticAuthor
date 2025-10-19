"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline
from rich.console import Console
from .lod_context import LODContextBuilder
from .depth_calculator import DepthCalculator


class ChapterGenerator:
    """
    Generator for chapter outlines (LOD2) using single-shot generation.

    SINGLE-SHOT GENERATION ARCHITECTURE:
    ===================================
    Generates ALL chapters in ONE LLM call with global arc planning.

    This prevents event duplication by giving the LLM a complete view of
    the entire story structure before generating any individual chapter.

    File Structure:
    - chapter-beats/foundation.yaml     (metadata + characters + world)
    - chapter-beats/chapter-01.yaml     (chapter 1 outline)
    - chapter-beats/chapter-02.yaml     (chapter 2 outline)
    - chapter-beats/chapter-NN.yaml     (chapter N outline)

    Benefits:
    - Global arc planning prevents duplicate events
    - Natural character progression (no repeated development beats)
    - Each chapter has unique plot role
    - Simple key_events format (proven quality from historical testing)
    - LLM plans complete story before generating details

    TOKEN REQUIREMENTS PER GENERATION:
    ==================================
    Foundation generation: ~2,000 tokens output
      - metadata: ~500 tokens
      - characters: ~1,000 tokens
      - world: ~500 tokens

    All chapters generation: ~600-800 tokens per chapter
      - Example: 15 chapters = ~12,000 tokens output
      - Single call with complete context

    BACKWARD COMPATIBILITY:
    =======================
    Old format (chapters.yaml) supported for READING legacy projects only.
    New generations write ONLY to chapter-beats/ directory (never chapters.yaml).
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

    def _is_yaml_truncated(self, error: yaml.YAMLError) -> bool:
        """
        Detect if YAML parsing error is due to truncation/network interruption.

        Args:
            error: The YAML parsing error

        Returns:
            True if error indicates truncation, False otherwise
        """
        if not error:
            return False

        truncation_indicators = [
            "found unexpected end of stream",
            "unexpected end of stream",
            "while scanning a quoted scalar",
            "unclosed quoted scalar",
            "mapping values are not allowed here",
            "expected <block end>",
        ]
        error_str = str(error).lower()
        return any(indicator in error_str for indicator in truncation_indicators)

    # Removed _find_last_complete_chapter() and _fix_truncated_yaml() - no longer needed with sequential generation
    # Old batched generation used these for truncation recovery
    # Sequential generation has built-in resume via generate() loop

    # Removed _calculate_batch_size() and _summarize_chapters() - no longer needed with sequential generation
    # Sequential generation passes full chapter context (100% of data) to each new chapter

    def _save_partial(self, data: Dict[str, Any], phase: str):
        """
        Save partial generation progress.

        Args:
            data: Partial data to save
            phase: Phase identifier (e.g., 'foundation', 'batch_1')
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        partial_path = self.project.path / f'chapters.partial.{phase}.yaml'

        try:
            import yaml
            with open(partial_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            if logger:
                logger.debug(f"Saved partial progress: {partial_path}")

        except Exception as e:
            if logger:
                logger.warning(f"Failed to save partial progress: {e}")
            # Non-fatal - continue anyway

    async def _generate_foundation(
        self,
        context_yaml: str,
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
    ) -> Dict[str, Any]:
        """
        Generate ONLY the foundation (metadata + characters + world), no chapters.

        Args:
            context_yaml: Full premise + treatment as YAML
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
            Dict with metadata, characters, world sections
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
  target_word_count: {total_words}
  chapter_count: {chapter_count}
  glue_fraction: 0.25  # 25% for transitions/exposition
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

        # Iteration-specific instructions for structural flexibility
        word_count_note = ""
        chapter_count_note = ""
        if feedback:
            word_count_note = " # Current target - adjust based on feedback if needed"
            chapter_count_note = " # Current count - adjust based on feedback if needed"

        prompt = f"""# TREATMENT
```yaml
{context_yaml}
```
{unique_context}
# YOUR TASK
Generate foundation (metadata + characters + world) from the treatment above.

Note: Extract and structure what's in the treatment. Elaborate fully but don't invent major plot elements.

# OUTPUT
Return plain YAML (DO NOT wrap in ```yaml or ``` fences):

{metadata_yaml_example}

characters:
  - name: "..."
    role: "protagonist"
    background: |
      ...
    motivation: |
      ...
    character_arc: |
      ...
    personality_traits: ["...", "..."]
    internal_conflict: |
      ...
    relationships:
      - character: "..."
        dynamic: "..."

world:
  setting_overview: |
    ...
  key_locations:
    - name: "..."
      description: "..."
  systems_and_rules:
    - system: "..."
      description: |
        ...
  social_context: ["...", "..."]

IMPORTANT: Return all 3 sections (metadata, characters, world). No chapters section."""

        # Add treatment analysis instruction for initial generation
        if is_initial_generation and min_words and max_words:
            prompt += f"""

TREATMENT ANALYSIS FOR WORD COUNT:

Before setting target_word_count, analyze the treatment to determine the story's natural scope.

Consider these factors from the treatment:
1. STORY COMPLEXITY: How many major plot threads are outlined?
2. CHARACTER COUNT: How many characters have significant roles?
3. WORLD-BUILDING NEEDS: How much setting/system explanation is required?
4. SUBPLOT DENSITY: How many parallel storylines are present?
5. NATURAL PACING: Does the story suggest fast-paced action (fewer words) or deliberate literary exploration (more)?
6. TIMELINE: Do events span days/weeks (shorter) or months/years (longer)?

CONSTRAINTS:
- Genre: {genre or 'general'}
- Length scope: {length_scope} ({min_words:,}-{max_words:,} words)
- Genre baseline: {genre_baseline:,} words (reference only - DO NOT default to this)

CRITICAL: Set target_word_count based on the treatment's ACTUAL COMPLEXITY within the {length_scope} range ({min_words:,}-{max_words:,}).

Examples of organic word count selection:
- Tight thriller with single plot thread, 2-3 main characters, fast pacing → {int(min_words * 1.2):,} words
- Complex mystery with multiple suspects, intricate plotting, moderate pacing → {int((min_words + max_words) / 2):,} words
- Epic with extensive world-building, large cast, multiple subplots → {int(max_words * 0.9):,} words

Your choice should reflect the treatment's inherent scope, not just match the genre default."""

        # Add feedback instruction if iterating
        if feedback:
            prompt += f"\n\nUSER FEEDBACK:\n{feedback}\n\n"
            prompt += f"""CRITICAL INSTRUCTION: Analyze the feedback's structural intent before setting target_word_count and chapter_count.

Current baseline: {total_words:,} words, {chapter_count} chapters

STEP 1: Identify the feedback's overall intent by looking for these indicators:

CONSOLIDATION INDICATORS (→ REDUCE both word count and chapter count):
  Keywords: "consolidate", "combine", "merge", "tighten", "condense", "streamline"
  Problems: "padded", "repetitive", "redundant", "dragging", "slow", "bloated"
  Actions: "remove", "cut", "trim", "reduce", "eliminate"

  If feedback contains these → REDUCE by 15-25%
  Example: {total_words:,} words → {int(total_words * 0.75):,}-{int(total_words * 0.85):,} words
           {chapter_count} chapters → {max(int(chapter_count * 0.75), 1)}-{max(int(chapter_count * 0.85), 1)} chapters

EXPANSION INDICATORS (→ INCREASE both word count and chapter count):
  Keywords: "expand", "develop", "add more", "deepen", "flesh out", "elaborate"
  Problems: "rushed", "underdeveloped", "needs more", "too brief", "shallow"
  Actions: "add", "extend", "grow", "enrich"

  If feedback contains these → INCREASE by 15-25%
  Example: {total_words:,} words → {int(total_words * 1.15):,}-{int(total_words * 1.25):,} words
           {chapter_count} chapters → {int(chapter_count * 1.15)}-{int(chapter_count * 1.25)} chapters

MIXED/REFINEMENT (→ minimal or no adjustment):
  Feedback addresses specific scenes/moments without overall length concerns
  Both consolidation and expansion requested in different areas
  Focus on content changes rather than structural changes

  If mixed signals → Adjust by less than 10% or keep current
  Example: {total_words:,} words → {int(total_words * 0.95):,}-{total_words:,} words
           {chapter_count} chapters → {max(chapter_count - 2, 1)}-{chapter_count} chapters

STEP 2: Set your target_word_count and chapter_count based on your analysis above.

Your values should reflect the feedback's structural intent, not just specific edits.
If feedback clearly indicates consolidation (e.g., mentions "padded", "repetitive", "combine chapters"), you SHOULD reduce both metrics proportionally.

CRITICAL - AVOID DUPLICATE EVENTS IN ITERATION:
When the feedback mentions duplicate or repetitive content:
- This means previous chapter generation created redundant scenes/events
- Your job is to consolidate the structure to PREVENT duplication
- Review the existing chapters carefully and eliminate duplicate plot beats
- Each chapter should cover UNIQUE story events and character moments
- Do NOT create separate chapters for events that should be combined into one"""

        # Generate foundation
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,  # Balanced creativity with adherence to treatment
            stream=True,
            display=True,
            display_label="Generating foundation",
            min_response_tokens=2000
        )

        if not result:
            raise Exception("No response from API for foundation generation")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Strip markdown fences if present (defensive - LLM should not add them)
        response_text = response_text.strip()
        if response_text.startswith('```yaml'):
            response_text = response_text[7:]  # Remove ```yaml
        elif response_text.startswith('```'):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove closing ```
        response_text = response_text.strip()

        # Parse YAML
        try:
            foundation_data = yaml.safe_load(response_text)
        except yaml.YAMLError as e:
            raise Exception(f"Failed to parse foundation YAML: {e}")

        # Validate structure
        if not isinstance(foundation_data, dict):
            raise Exception("Foundation response is not a valid dict structure")

        required_sections = ['metadata', 'characters', 'world']
        missing = [s for s in required_sections if s not in foundation_data]
        if missing:
            found_sections = list(foundation_data.keys())
            # Save failed response for debugging
            debug_file = self.project.path / '.agentic' / 'debug' / f'foundation_failed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml'
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            debug_file.write_text(response_text, encoding='utf-8')

            raise Exception(
                f"Foundation missing required sections: {', '.join(missing)}\n"
                f"Found sections: {', '.join(found_sections)}\n"
                f"Full response saved to: {debug_file.relative_to(self.project.path)}\n"
                f"Response preview (first 500 chars):\n{response_text[:500]}"
            )

        # Make sure chapters section is NOT present
        if 'chapters' in foundation_data:
            if logger:
                logger.warning("Foundation included chapters section - removing it")
            del foundation_data['chapters']

        if logger:
            logger.debug(f"Foundation generated successfully")

        return foundation_data

    # Removed _generate_single_chapter() - sequential generation removed, single-shot only
    # Removed _validate_treatment_fidelity() - per-chapter validation removed, single-shot only

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

        # Serialize foundation for validator
        foundation_yaml = yaml.dump(foundation_data, default_flow_style=False, allow_unicode=True)

        # Build validation prompt
        validation_prompt = f"""You are a treatment fidelity validator. Your job is to detect contradictions between the foundation and treatment.

TREATMENT (SOURCE OF TRUTH):
```
{treatment_text}
```

GENERATED FOUNDATION:
```yaml
{foundation_yaml}
```

TASK:
Analyze the foundation for contradictions with the treatment.

DETECTION CRITERIA:

1. **Character Contradictions**
   - Check: Do character backgrounds, motivations, or roles contradict treatment?
   - Examples: Treatment says character is innocent → Foundation says they're guilty
   - Examples: Treatment has 3 main characters → Foundation lists 5 protagonists

2. **World Contradictions**
   - Check: Do world rules, settings, or systems contradict treatment?
   - Examples: Treatment is realistic → Foundation adds magic system
   - Examples: Treatment set in 2025 → Foundation describes 1950s setting

3. **Metadata Contradictions**
   - Check: Do genre, pacing, themes contradict treatment?
   - Examples: Treatment is fast-paced thriller → Foundation says "slow, contemplative"
   - Examples: Treatment word count is 50k → Foundation target is 120k

4. **Plot Element Inventions**
   - Check: Does foundation introduce major plot elements not in treatment?
   - Examples: "secret organization", "hidden conspiracy", "government program"
   - These should come from treatment, not be invented in foundation

ALLOWED (NOT violations):
- ELABORATIONS: Adding richness to treatment elements (treatment mentions chess → foundation describes chess symbolism system)
- MINOR DETAILS: Specific locations, character appearance details, world atmosphere
- ORGANIZATIONAL: Structuring treatment info into categories

RETURN FORMAT:
Return ONLY valid JSON (no markdown fences):

{{
  "valid": true/false,
  "critical_issues": [
    {{
      "type": "character_contradiction",
      "severity": "critical",
      "element": "Detective Elias Crowe background",
      "reasoning": "Treatment describes Elias as veteran detective. Foundation contradicts this by making him a rookie officer.",
      "recommendation": "Update foundation to match treatment's character description."
    }}
  ],
  "warnings": [
    {{
      "type": "ambiguous_elaboration",
      "severity": "low",
      "element": "City's economic system",
      "reasoning": "Treatment doesn't explicitly describe economy. Foundation adds economic details that may or may not fit."
    }}
  ]
}}

IMPORTANT:
- Be STRICT: If foundation contradicts treatment, flag it
- critical_issues = Direct contradictions that will cause story problems
- warnings = Ambiguous elements that MAY be issues
- If no issues: {{"valid": true, "critical_issues": [], "warnings": []}}
- Temperature is 0.1 for consistency - be thorough and consistent"""

        # Make validation call with LOW temperature for consistency
        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict treatment fidelity validator. You always return valid JSON without additional formatting."},
                    {"role": "user", "content": validation_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent strict evaluation
                stream=False,  # No streaming for validation
                display=False,  # Don't display during validation
                min_response_tokens=200
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

                validation_result = json.loads(response_text)
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

    # Removed _generate_chapter_batch() - replaced by sequential _generate_single_chapter() calls
    # Sequential generation eliminates information loss and enables better resume capability

    # Removed _resume_generation() - sequential generation has built-in resume via generate() loop
    # Resume now happens naturally: check for existing chapter files and ask user to continue/regenerate

    # Removed _merge_yaml() - no longer needed with sequential generation
    # Individual chapter files don't need merging

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
                if 'fantasy_subgenre' in taxonomy_data:
                    genre = 'fantasy'
                elif 'mystery_subgenre' in taxonomy_data:
                    genre = 'mystery'
                elif 'romance_subgenre' in taxonomy_data:
                    genre = 'romance'
                elif 'scifi_subgenre' in taxonomy_data:
                    genre = 'science-fiction'
                elif 'horror_subgenre' in taxonomy_data:
                    genre = 'horror'
                elif 'literary_style' in taxonomy_data:
                    genre = 'literary-fiction'
                elif 'historical_period' in taxonomy_data:
                    genre = 'historical-fiction'
                else:
                    genre = 'general'

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

            # Serialize context to YAML for prompts
            context_yaml = self.context_builder.to_yaml_string(context)

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

                    # Extract metadata from existing foundation to use its values
                    foundation_metadata = foundation.get('metadata', {})
                    stored_word_count = foundation_metadata.get('target_word_count')
                    stored_chapter_count = foundation_metadata.get('chapter_count')

                    if stored_word_count:
                        total_words = int(stored_word_count)
                        if logger:
                            logger.debug(f"Resume: Using foundation's target_word_count: {total_words}")

                    if stored_chapter_count:
                        stored_chapter_count = int(stored_chapter_count)
                        # Validate reasonable range (1-100 chapters)
                        if 1 <= stored_chapter_count <= 100:
                            chapter_count = stored_chapter_count
                            if logger:
                                logger.debug(f"Resume: Using foundation's chapter_count: {chapter_count}")

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
                    context_yaml=context_yaml,
                    taxonomy_data=taxonomy_data,
                    total_words=total_words,
                    chapter_count=chapter_count,
                    original_concept=original_concept,
                    unique_elements=unique_elements,
                    feedback=feedback,
                    genre=genre
                )

                # Save foundation immediately
                self.project.save_foundation(foundation)
                self.console.print(f"[green]✓[/green] Foundation complete")

                # Validate foundation fidelity with interactive iteration loop
                validation_loop_count = 0
                max_validation_iterations = 3

                while validation_loop_count < max_validation_iterations:
                    self.console.print(f"[dim]Validating foundation fidelity...[/dim]")

                    treatment_text = context.get('treatment', {}).get('text', '')
                    is_valid, critical_issues = await self._validate_foundation_fidelity(
                        foundation_data=foundation,
                        treatment_text=treatment_text
                    )

                    if not is_valid and critical_issues:
                        # Show validation issues
                        self.console.print(f"\n[bold yellow]{'='*70}[/bold yellow]")
                        self.console.print(f"[bold yellow]⚠️  FOUNDATION VALIDATION ISSUES[/bold yellow]")
                        self.console.print(f"[bold yellow]{'='*70}[/bold yellow]\n")

                        for i, issue in enumerate(critical_issues, 1):
                            issue_type = issue.get('type', 'unknown').replace('_', ' ').title()
                            element = issue.get('element', 'Unknown')
                            reasoning = issue.get('reasoning', 'No details')
                            recommendation = issue.get('recommendation', '')
                            severity = issue.get('severity', 'medium')

                            severity_color = "red" if severity == "critical" else "yellow"

                            self.console.print(f"[cyan]{i}.[/cyan] [{severity_color}]{issue_type}[/{severity_color}]")
                            self.console.print(f"   Element: {element}")
                            self.console.print(f"   Problem: {reasoning}")
                            if recommendation:
                                self.console.print(f"   Fix: {recommendation}")
                            self.console.print()

                        # Prompt user for action
                        self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
                        self.console.print(f"  [cyan]1.[/cyan] Continue anyway (ignore issues)")
                        self.console.print(f"  [cyan]2.[/cyan] Iterate on selected issues (regenerate foundation)")
                        self.console.print(f"  [cyan]3.[/cyan] Abort generation")

                        try:
                            choice = input("\nEnter choice (1-3): ").strip()
                        except (KeyboardInterrupt, EOFError):
                            self.console.print(f"\n[yellow]Generation cancelled by user[/yellow]")
                            raise KeyboardInterrupt("User cancelled validation")

                        if choice == "1":
                            # Continue anyway
                            self.console.print(f"\n[yellow]⚠️  Continuing with foundation issues...[/yellow]\n")
                            break  # Exit validation loop

                        elif choice == "2":
                            # Iterate - let user select which issues to address
                            selected_issues = self._select_validation_issues(
                                issues=critical_issues,
                                context="foundation"
                            )

                            if not selected_issues:
                                self.console.print(f"[yellow]No issues selected, continuing anyway...[/yellow]\n")
                                break

                            # Format selected issues for iteration prompt
                            formatted_issues = self._format_validation_issues(selected_issues)

                            # Build iteration feedback
                            iteration_feedback = f"""FOUNDATION VALIDATION ISSUES TO FIX:

{formatted_issues}

INSTRUCTIONS:
Regenerate the foundation addressing the issues above.
- Fix the contradictions and inconsistencies
- Ensure alignment with treatment
- Maintain the overall structure and quality"""

                            # Regenerate foundation with validation feedback
                            self.console.print(f"\n[cyan]Regenerating foundation to address {len(selected_issues)} issue(s)...[/cyan]\n")

                            foundation = await self._generate_foundation(
                                context_yaml=context_yaml,
                                taxonomy_data=taxonomy_data,
                                total_words=total_words,
                                chapter_count=chapter_count,
                                original_concept=original_concept,
                                unique_elements=unique_elements,
                                feedback=iteration_feedback,  # Pass validation issues as feedback
                                genre=genre
                            )

                            # Save regenerated foundation
                            self.project.save_foundation(foundation)
                            self.console.print(f"[green]✓[/green] Foundation regenerated\n")

                            # Increment loop counter and continue validation
                            validation_loop_count += 1

                            if validation_loop_count >= max_validation_iterations:
                                self.console.print(f"[yellow]⚠️  Max validation iterations ({max_validation_iterations}) reached.[/yellow]")
                                self.console.print(f"[yellow]Continuing with current foundation...[/yellow]\n")
                                break

                        elif choice == "3":
                            # Abort
                            self.console.print(f"\n[red]Generation aborted due to foundation validation issues[/red]")
                            raise Exception("User aborted generation due to foundation validation issues")

                        else:
                            self.console.print(f"\n[yellow]Invalid choice, treating as abort[/yellow]")
                            raise Exception("Invalid validation choice")

                    else:
                        # Validation passed
                        if logger:
                            logger.debug("Foundation validation passed")
                        self.console.print(f"[green]✓[/green] Foundation validation passed\n")
                        break  # Exit validation loop

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
        output_dir: Optional[Path] = None
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
            # Calculate chapter count from word count
            chapter_count = self._calculate_chapter_count(total_words)
            if logger:
                logger.debug(f"Calculated chapter count: {chapter_count}")

        self.console.print(f"\n[cyan]Generating all {chapter_count} chapters in single call...[/cyan]")
        self.console.print(f"[dim]Target: {total_words:,} words across {chapter_count} chapters[/dim]")
        self.console.print(f"[dim]Using classic key_events format (proven quality)[/dim]\n")

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Serialize foundation to YAML for inclusion in prompt
        foundation_yaml = yaml.dump(foundation, sort_keys=False, allow_unicode=True)

        # Build feedback instruction if present
        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nPlease incorporate the above feedback while generating the chapters."

        # Build comprehensive single-shot chapters generation prompt (OLD STYLE from 4c28f59)
        prompt = f"""Generate a comprehensive chapter structure for a book.

INPUT CONTEXT:
```yaml
{context_yaml}
```

FOUNDATION (already generated):
```yaml
{foundation_yaml}
```

TASK:
Generate {chapter_count} comprehensive chapter outlines for the complete story.
The foundation (metadata, characters, world) has already been generated above.

CRITICAL - PLAN THE COMPLETE ARC:
Since you're generating ALL chapters at once, you have the unique opportunity to:
- Plan the entire story progression before committing to any chapter
- Distribute character development evenly across the arc
- Ensure each chapter has a UNIQUE role in the story
- Avoid duplicating plot beats or character moments
- Create clear causal progression from chapter to chapter

CHAPTER STRUCTURE:
For each chapter provide:
- number, title (evocative, specific)
- pov, act (Act I/Act II/Act III based on position), summary (3-4 sentences)
- key_events: 8-10 specific plot beats (UNIQUE to this chapter, not repeated)
- character_developments: 3-4 internal changes (LINEAR progression, no repeated beats)
- relationship_beats: 2-3 relationship evolutions (UNIQUE dynamics)
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
- word_count_target: distribute {total_words} across chapters proportionally

GUIDELINES:
- Each key_event should be specific and complete (not vague or generic)
- Character developments show PROGRESSIVE internal change (no resets or repeats)
- Relationship beats track EVOLVING dynamics (each interaction builds on previous)
- Be specific with names, places, emotions, concrete details
- Act I: ~25% chapters (setup and introduction)
- Act II: ~50% chapters (rising action and complications)
- Act III: ~25% chapters (climax and resolution){feedback_instruction}

RETURN FORMAT:
Return ONLY valid YAML (no markdown fences):

chapters:
  - number: 1
    title: "..."
    pov: "..."
    act: "Act I"
    summary: "..."
    key_events:
      - "First event description"
      - "Second event description"
      - "Third event description"
      - "Fourth event description"
      - "Fifth event description"
      - "Sixth event description"
      - "Seventh event description"
      - "Eighth event description"
    character_developments:
      - "First development"
      - "Second development"
      - "Third development"
    relationship_beats:
      - "First relationship change"
      - "Second relationship change"
    tension_points:
      - "First tension point"
      - "Second tension point"
    sensory_details:
      - "First sensory detail"
      - "Second sensory detail"
    subplot_threads:
      - "First subplot thread"
    word_count_target: XXXX
  - number: 2
    title: "..."
    # ... continue for all {chapter_count} chapters

YAML SYNTAX RULES:
- ALWAYS wrap ALL list items in double quotes: - "Event text"
- For dialogue in events, use single quotes inside doubles: - "He said: 'Hello'."
- Do NOT wrap in markdown code fences

IMPORTANT:
- Return ONLY the YAML content starting with "chapters:"
- Each chapter must have UNIQUE plot events (no duplication across chapters)
- Character arcs must PROGRESS linearly (no repeated development beats)
- Follow YAML syntax rules above to avoid parsing errors
"""

        # Generate with API
        try:
            # Estimate tokens
            from ..utils.tokens import estimate_messages_tokens
            prompt_tokens = estimate_messages_tokens([{"role": "user", "content": prompt}])

            # Response needs ~600-800 tokens per chapter for rich outlines
            # Plus overhead for structure
            estimated_response_tokens = 2000 + (chapter_count * 700)

            if logger:
                logger.debug(f"Single-shot generation: ~{prompt_tokens} prompt tokens, ~{estimated_response_tokens} response tokens")

            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional story development assistant. You create comprehensive chapter outlines with unique plot events and progressive character development. You always return valid YAML without additional formatting. CRITICAL: All YAML list items MUST be fully quoted strings. Never use unquoted text with colons in list items. Format: - \"Event text here\"."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,  # Use parameter for temperature variation
                display=True,
                display_label=f"Generating all {chapter_count} chapters",
                min_response_tokens=estimated_response_tokens
            )

            if not result:
                raise Exception("No response from API")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Strip markdown fences if present
            response_text = response_text.strip()
            if response_text.startswith('```yaml'):
                response_text = response_text[7:]  # Remove ```yaml
            elif response_text.startswith('```'):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove closing ```
            response_text = response_text.strip()

            # Parse the chapters YAML
            try:
                parsed_data = yaml.safe_load(response_text)
            except yaml.YAMLError as e:
                raise Exception(f"Failed to parse chapters YAML: {e}")

            # Extract chapters list
            if isinstance(parsed_data, dict) and 'chapters' in parsed_data:
                chapters_data = parsed_data['chapters']
            elif isinstance(parsed_data, list):
                # Response might be just the list of chapters
                chapters_data = parsed_data
            else:
                raise Exception(f"Response missing 'chapters' section. Got keys: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'not a dict'}")

            if not chapters_data:
                raise Exception("Empty chapters list in response")

            # Save individual chapter beat files (ONLY format - no chapters.yaml)
            # Use custom output_dir if provided, otherwise use default chapter-beats/
            if output_dir is None:
                beats_dir = self.project.chapter_beats_dir
            else:
                beats_dir = output_dir

            beats_dir.mkdir(parents=True, exist_ok=True)

            # Save foundation if not already saved
            # IMPORTANT: Skip foundation save for variant directories (variant-N/)
            # VariantManager saves foundation once to parent chapter-beats-variants/
            is_variant_dir = 'variant-' in str(beats_dir)
            foundation_path = beats_dir / 'foundation.yaml'

            if not is_variant_dir and not foundation_path.exists():
                foundation_path.write_text(
                    yaml.dump(foundation, sort_keys=False, allow_unicode=True),
                    encoding='utf-8'
                )

            # Save each chapter as individual file
            for chapter in chapters_data:
                chapter_num = chapter.get('number', 0)
                if chapter_num:
                    chapter_path = beats_dir / f'chapter-{chapter_num:02d}.yaml'
                    chapter_path.write_text(
                        yaml.dump(chapter, sort_keys=False, allow_unicode=True),
                        encoding='utf-8'
                    )

            if logger:
                logger.debug(f"Saved {len(chapters_data)} chapters to individual beat files")

            # Basic validation (no ChapterOutline conversion - files are source of truth)
            chapter_count_saved = len([ch for ch in chapters_data if ch.get('number')])
            total_word_target = sum(ch.get('word_count_target', 0) for ch in chapters_data)

            self.console.print(f"\n[green]✓[/green] Generated {chapter_count_saved} chapters successfully")
            self.console.print(f"[dim]Total word target: {total_word_target:,} words[/dim]")

            # Return summary dict (not ChapterOutline objects)
            return {
                'count': len(chapters_data),
                'files_saved': chapter_count_saved,
                'total_words': total_word_target
            }

        except Exception as e:
            if logger:
                logger.error(f"Single-shot generation failed: {e}")
            raise Exception(f"Failed to generate chapters: {e}")