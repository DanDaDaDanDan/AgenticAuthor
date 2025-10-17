"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline
from rich.console import Console
from ..config import get_settings
from .lod_context import LODContextBuilder
from .lod_parser import LODResponseParser
from .depth_calculator import DepthCalculator


class ChapterGenerator:
    """
    Generator for chapter outlines (LOD2) using sequential generation.

    SEQUENTIAL GENERATION ARCHITECTURE:
    ===================================
    Generates chapters one at a time (not batched) with full context accumulation.

    File Structure:
    - chapter-beats/foundation.yaml     (metadata + characters + world)
    - chapter-beats/chapter-01.yaml     (chapter 1 outline)
    - chapter-beats/chapter-02.yaml     (chapter 2 outline, sees full Ch 1)
    - chapter-beats/chapter-NN.yaml     (chapter N, sees full Ch 1 through N-1)

    Benefits:
    - ZERO information loss (100% of previous chapters passed to each new chapter)
    - Automatic resume capability (check existing files, ask user to continue/regenerate)
    - Incremental saves (inspect partial results anytime)
    - Better error recovery (clear failure point, can resume from there)
    - Prevents duplicate scenes/events (each chapter sees ALL previous detail)

    TOKEN REQUIREMENTS PER GENERATION:
    ==================================
    Foundation generation: ~2,000 tokens output
      - metadata: ~500 tokens
      - characters: ~1,000 tokens
      - world: ~500 tokens

    Per chapter generation: ~700 tokens output + context input
      - Context grows: 8k base + (700 tokens × previous_chapter_count)
      - Example: Chapter 10 sees ~14k tokens context (base + 9 previous chapters)

    Context growth is acceptable because:
    - Each generation is short (~30-60 seconds)
    - Full context prevents duplicates (worth the tokens)
    - Modern models handle 200k+ context easily

    RESUME CAPABILITY:
    ==================
    Built-in resume checks for existing chapter-beats/ files before generation.

    User experience:
    ```
    ⚠️  Found 5 existing chapters

    What would you like to do?
      1. Continue from chapter 6 (resume)
      2. Regenerate all chapters from scratch
      3. Abort generation

    Enter choice (1-3): 1
    Resuming from chapter 6...

    Generating chapter 6/20...
    ✓ Chapter 6/20 complete
    ...
    ```

    Resume is explicit and user-controlled (not automatic).
    User chooses: continue, regenerate, or abort.

    BACKWARD COMPATIBILITY:
    =======================
    Old format (chapters.yaml) still supported for reading.
    New generations always use chapter-beats/ format.
    get_chapters_yaml() aggregates chapter-beats/ transparently.
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
        self.parser = LODResponseParser()

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

    async def _generate_single_chapter(
        self,
        chapter_num: int,
        total_chapters: int,
        context_yaml: str,
        foundation: Dict[str, Any],
        previous_chapters: List[Dict[str, Any]],
        form: str,
        pacing: str,
        chapter_budget: Dict[str, Any],
        feedback: Optional[str] = None,
        auto_fix: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a single chapter with full context of all previous chapters.

        Args:
            chapter_num: Chapter number to generate (1-based)
            total_chapters: Total number of chapters in story
            context_yaml: Full premise + treatment as YAML
            foundation: metadata + characters + world sections
            previous_chapters: FULL chapter dicts for all previous chapters (empty for chapter 1)
            form: Story form (novel, novella, etc.)
            pacing: Story pacing (fast, moderate, slow)
            chapter_budget: Budget dict with role, act, words_total, words_scenes, typical_scenes
            feedback: Optional user feedback (for iteration)
            auto_fix: If True, automatically fix validation issues without prompts

        Returns:
            Dict with chapter data (number, title, pov, act, summary, scenes, etc.)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.debug(f"Generating chapter {chapter_num} with {len(previous_chapters)} previous chapters")

        # Extract budget information
        chapter_role = chapter_budget['role']
        chapter_act = chapter_budget['act']
        words_total = chapter_budget['words_total']
        words_scenes = chapter_budget['words_scenes']
        scene_count = chapter_budget['typical_scenes']

        # chapter_act is already the string "Act I", "Act II", or "Act III"
        default_act = chapter_act

        if logger:
            logger.debug(f"Chapter {chapter_num} budget: role={chapter_role}, act={chapter_act}, "
                        f"total={words_total}, scenes={words_scenes}, scene_count={scene_count}")

        # Serialize foundation to YAML
        foundation_yaml = yaml.dump(foundation, default_flow_style=False, allow_unicode=True)

        # Serialize previous chapters to YAML (FULL detail, not summaries)
        previous_yaml = ""
        if previous_chapters:
            previous_yaml = yaml.dump(previous_chapters, default_flow_style=False, allow_unicode=True)

        # Build prompt with full context
        prompt = f"""# TREATMENT
```
{context_yaml}
```

# STORY FOUNDATION
```yaml
{foundation_yaml}
```

# PREVIOUS CHAPTERS
```yaml
{previous_yaml if previous_yaml else "# Chapter 1 - no previous chapters"}
```

**CRITICAL**: Review previous chapters carefully. Each scene must be NEW events and conflicts. Do NOT duplicate plot beats already covered.

# YOUR TASK
Generate Chapter {chapter_num} of {total_chapters} ({default_act}, {chapter_role} role)

Chapter {chapter_num} role: {chapter_role}
Act: {default_act}
Scenes: {scene_count}
Target: {words_total:,} words (~{words_scenes // scene_count}w per scene)

# OUTPUT
Return plain YAML starting with "number:" (DO NOT wrap in ```yaml or ``` fences):

number: {chapter_num}
title: "Chapter Title"
pov: "Character Name"
act: "{default_act}"
summary: "3-4 sentence summary"
scenes:
  - scene: "Brief Title"
    location: "Where"
    objective: "what character wants (verb phrase)"
    exit_hook: "optional - only if strong"
    beats:
      - "Beat 1: what happens"
      - "Beat 2: what happens"
      - "Beat 3: what happens"
      - "Beat 4: what happens"
      - "Beat 5: what happens"
      - "Beat 6: what happens"
  # {scene_count} scenes total
character_developments: ["...", "..."]
relationship_beats: ["...", "..."]
tension_points: ["...", "..."]
sensory_details: ["...", "..."]
subplot_threads: ["..."]  # if applicable
word_count_target: {words_total}"""

        # Add feedback instruction if iterating
        if feedback:
            # Check if this is a validation fix (contains "FIX ISSUES" or "FIX REMAINING")
            is_validation_fix = "FIX ISSUES" in feedback or "FIX REMAINING" in feedback

            if is_validation_fix:
                # Validation fix: emphasize fixing existing chapter
                prompt += f"\n\n{feedback}"
            else:
                # User feedback: allow more flexibility
                prompt += f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the feedback when generating this chapter. You may adjust scene count, word targets, or content based on the feedback."

        # Generate chapter
        min_tokens = 700  # Estimate: 700 tokens per chapter

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You structure treatments into detailed chapter outlines with scenes and beats. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,  # Balanced creativity with adherence to treatment
            stream=True,
            display=True,
            min_response_tokens=min_tokens
        )

        if not result:
            raise Exception(f"No response from API for chapter {chapter_num}")

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

        # Check finish_reason for early truncation detection
        if isinstance(result, dict) and result.get('finish_reason') == 'connection_error':
            self.console.print(f"[yellow]⚠️  Connection error detected during generation[/yellow]")
            # Will be caught by retry logic below

        # Parse YAML with automatic retry on truncation
        max_yaml_retries = 2
        chapter_data = None

        for yaml_retry in range(max_yaml_retries + 1):
            try:
                chapter_data = yaml.safe_load(response_text)
                break  # Success! Exit retry loop

            except yaml.YAMLError as e:
                is_truncated = self._is_yaml_truncated(e)

                if is_truncated and yaml_retry < max_yaml_retries:
                    # Automatic retry on truncation
                    self.console.print(f"\n[yellow]⚠️  YAML truncated (network error)[/yellow]")
                    self.console.print(f"[yellow]Retrying chapter {chapter_num} generation ({yaml_retry + 1}/{max_yaml_retries})...[/yellow]\n")

                    if logger:
                        logger.warning(f"YAML truncation detected in chapter {chapter_num}, retry {yaml_retry + 1}/{max_yaml_retries}")
                        logger.debug(f"YAML error: {e}")
                        logger.debug(f"Response length: {len(response_text)} chars")

                    # Regenerate from scratch with same parameters
                    result = await self.client.streaming_completion(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a professional story development assistant. You structure treatments into detailed chapter outlines with scenes and beats. You always return valid YAML without additional formatting."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.6,  # Balanced creativity with adherence to treatment
                        stream=True,
                        display=True,
                        min_response_tokens=min_tokens
                    )

                    if not result:
                        raise Exception(f"No response from API for chapter {chapter_num} (retry {yaml_retry + 1})")

                    response_text = result.get('content', result) if isinstance(result, dict) else result
                    continue  # Try parsing again

                else:
                    # Not truncated, or max retries reached
                    if is_truncated:
                        self.console.print(f"\n[red]YAML truncation persists after {max_yaml_retries} retries[/red]")
                        if logger:
                            logger.error(f"YAML truncation in chapter {chapter_num} after {max_yaml_retries} retries")
                    raise Exception(f"Failed to parse chapter {chapter_num} YAML: {e}")

        if not chapter_data:
            raise Exception(f"Failed to generate valid YAML for chapter {chapter_num} after {max_yaml_retries} retries")

        # Validate structure
        if not isinstance(chapter_data, dict):
            raise Exception(f"Chapter {chapter_num} response is not a valid dict structure")

        required_fields = ['number', 'title', 'summary', 'scenes']
        missing = [f for f in required_fields if f not in chapter_data]
        if missing:
            raise Exception(f"Chapter {chapter_num} missing required fields: {', '.join(missing)}")

        # Ensure correct chapter number
        if chapter_data.get('number') != chapter_num:
            if logger:
                logger.warning(f"Chapter number mismatch: expected {chapter_num}, got {chapter_data.get('number')} - correcting")
            chapter_data['number'] = chapter_num

        # Validate scene hygiene (minimal - only required fields)
        scenes = chapter_data.get('scenes', [])
        hygiene_warnings = []

        for i, scene in enumerate(scenes, 1):
            scene_id = scene.get('scene', f'Scene {i}')

            # Check objective (must be verb phrase)
            objective = scene.get('objective', '')
            if not objective:
                hygiene_warnings.append(f"Scene {i} ({scene_id}): Missing 'objective' field")
            elif any(word in objective.lower() for word in ['talk', 'talking', 'discuss', 'discussing']) and 'to' not in objective:
                hygiene_warnings.append(f"Scene {i} ({scene_id}): objective '{objective}' is too vague (use 'convince X to Y' not 'talk to X')")

            # Check beats array
            beats = scene.get('beats', [])
            if not beats:
                hygiene_warnings.append(f"Scene {i} ({scene_id}): Missing 'beats' array")
            elif len(beats) != 6:
                hygiene_warnings.append(f"Scene {i} ({scene_id}): beats array has {len(beats)} beats (expected 6)")

        # Log warnings but don't fail generation
        if hygiene_warnings:
            if logger:
                logger.warning(f"Scene hygiene validation found {len(hygiene_warnings)} issues in chapter {chapter_num}:")
                for warning in hygiene_warnings[:5]:  # Log first 5
                    logger.warning(f"  - {warning}")
                if len(hygiene_warnings) > 5:
                    logger.warning(f"  ... and {len(hygiene_warnings) - 5} more")

        if logger:
            logger.debug(f"Chapter {chapter_num} generated successfully: {len(scenes)} scenes")

        return chapter_data

    async def _validate_treatment_fidelity(
        self,
        chapter_data: Dict[str, Any],
        chapter_num: int,
        treatment_text: str,
        previous_chapters: List[Dict[str, Any]]
    ) -> tuple[bool, List[Dict[str, Any]]]:
        """
        Validate chapter against treatment for fidelity violations (separate LLM call).

        This is a POST-GENERATION validation that detects MAJOR plot inventions not in treatment.
        Uses low temperature (0.1) for consistent, strict evaluation.

        Args:
            chapter_data: Generated chapter dict with scenes
            chapter_num: Chapter number being validated
            treatment_text: Full treatment text (SOURCE OF TRUTH)
            previous_chapters: Previous chapters for context

        Returns:
            Tuple of (is_valid: bool, issues: List[Dict])
            Issues have: type, severity, location, element, reasoning, recommendation
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.debug(f"Validating treatment fidelity for chapter {chapter_num}")

        # Serialize chapter and previous chapters for validator
        chapter_yaml = yaml.dump(chapter_data, default_flow_style=False, allow_unicode=True)

        previous_yaml = ""
        if previous_chapters:
            previous_yaml = yaml.dump(previous_chapters, default_flow_style=False, allow_unicode=True)

        # Build validation prompt
        validation_prompt = f"""You are a treatment fidelity validator. Your job is to detect MAJOR plot inventions that violate the source treatment.

TREATMENT (SOURCE OF TRUTH):
```
{treatment_text}
```

GENERATED CHAPTER {chapter_num}:
```yaml
{chapter_yaml}
```

PREVIOUS CHAPTERS (for context):
```yaml
{previous_yaml if previous_yaml else "# This is chapter 1 - no previous chapters"}
```

TASK:
Analyze chapter {chapter_num} for MAJOR plot inventions NOT in the treatment.

DETECTION CRITERIA:

1. **New Antagonists/Villains**
   - Treatment mentions ONE antagonist → Chapter introduces ADDITIONAL villain
   - Examples: "secret mastermind", "hidden enemy", "surprise antagonist"
   - Check: Is this character in treatment with antagonist role?

2. **New Conspiracies/Organizations**
   - Examples: "secret organization", "government program", "hidden conspiracy", "experiment project"
   - Check: Is this mentioned anywhere in treatment?

3. **Major Backstory Inventions**
   - Examples: "character's traumatic past", "secret identity", "hidden history", "dark secret"
   - Check: Is this character background in treatment?

4. **Plot Threads Not in Treatment**
   - Examples: new subplots, parallel stories, major revelations, plot twists
   - Check: Is this plot element mentioned in treatment?

5. **Character Role Changes**
   - Check: Does chapter change character roles vs treatment?

6. **World-Building Contradictions**
   - Check: Does chapter contradict treatment's world rules?

ALLOWED (NOT violations):
- MINOR elaborations: props, gestures, dialogue specifics, sensory details
- Minor characters: servants, officials, background characters
- Scene-level details: specific actions, internal thoughts, transitions
- Treatment elements with added richness: treatment mentions chess → chapter adds specific chess pieces

RETURN FORMAT:
Return ONLY valid JSON (no markdown fences):

{{
  "valid": true/false,
  "critical_issues": [
    {{
      "type": "major_plot_invention",
      "severity": "critical",
      "location": "Scene 2: The Discovery",
      "element": "Secret government program 'Project Chimera'",
      "reasoning": "Treatment describes ONE antagonist (Dr. Victor Lang). This chapter invents a NEW conspiracy involving government experiments not mentioned in treatment.",
      "recommendation": "Remove this plot thread or verify it exists in treatment."
    }}
  ],
  "warnings": [
    {{
      "type": "ambiguous_elaboration",
      "severity": "low",
      "location": "Scene 3",
      "element": "Character's mysterious locket",
      "reasoning": "Could be MINOR prop or MAJOR plot device. Treatment doesn't mention this."
    }}
  ]
}}

IMPORTANT:
- Be STRICT: If element is not clearly in treatment AND is plot-level (not scene detail), flag it
- critical_issues = MAJOR violations that will cause story drift
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
                    logger.warning(f"Failed to parse validation JSON: {e}")
                # If parsing fails, assume valid (don't block on validator errors)
                return (True, [])

            is_valid = validation_result.get('valid', True)
            critical_issues = validation_result.get('critical_issues', [])
            warnings = validation_result.get('warnings', [])

            if logger:
                logger.debug(f"Validation result: valid={is_valid}, critical={len(critical_issues)}, warnings={len(warnings)}")

            return (is_valid, critical_issues)

        except Exception as e:
            if logger:
                logger.warning(f"Validation call failed: {e}")

            # Validator failed - prompt user for action
            self.console.print(f"\n[bold yellow]{'='*70}[/bold yellow]")
            self.console.print(f"[bold yellow]⚠️  VALIDATOR FAILURE[/bold yellow]")
            self.console.print(f"[bold yellow]{'='*70}[/bold yellow]\n")

            self.console.print(f"[yellow]Problem:[/yellow]")
            self.console.print(f"  The treatment fidelity validator encountered an error: {e}\n")

            self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
            self.console.print(f"  [cyan]1.[/cyan] Retry validation")
            self.console.print(f"  [cyan]2.[/cyan] Continue without validation [bold](NOT recommended)[/bold]")
            self.console.print(f"  [cyan]3.[/cyan] Abort generation")

            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                # Retry validation
                self.console.print(f"\n[cyan]Retrying validation...[/cyan]")
                # Recursive retry - if it fails, user will be prompted again
                return await self._validate_treatment_fidelity(
                    chapter_data=chapter_data,
                    chapter_num=chapter_num,
                    treatment_text=treatment_text,
                    previous_chapters=previous_chapters
                )

            elif choice == "2":
                # Continue without validation
                self.console.print(f"\n[yellow]⚠️  Continuing without validation...[/yellow]")
                self.console.print(f"[yellow]Chapter may contain treatment violations.[/yellow]\n")
                return (True, [])

            elif choice == "3":
                # Abort generation
                self.console.print(f"\n[red]Generation aborted due to validator failure[/red]")
                raise Exception(f"User aborted generation due to validator failure in chapter {chapter_num}")

            else:
                # Invalid choice - treat as abort
                self.console.print(f"\n[red]Invalid choice, aborting generation[/red]")
                raise Exception("Invalid validator failure choice")

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
        feedback: Optional[str] = None,
        auto_fix: bool = False
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using sequential generation with full context.

        **Sequential Generation Architecture:**
        Phase 1: Foundation (metadata + characters + world) ~2,000 tokens, ~30-45s
        Phase 2: Sequential Chapters (one at a time) ~700 tokens each, ~30-60s per chapter
        Phase 3: Assembly (validate and aggregate)

        Each chapter sees 100% of previous chapter detail (not summaries):
        - Chapter 1: foundation only
        - Chapter 2: foundation + full Ch 1
        - Chapter 3: foundation + full Ch 1 + full Ch 2
        - Chapter N: foundation + full Ch 1 through N-1

        Benefits:
        - Zero information loss (prevents duplicate scenes/events)
        - Built-in resume (checks for existing chapter-beats/, asks user)
        - Incremental saves (can inspect/debug partial results)
        - Better error recovery (clear failure point, easy resume)
        - Auto-fix mode: Automatically iterates with all validation issues (when enabled)

        File structure:
        - chapter-beats/foundation.yaml (saved once)
        - chapter-beats/chapter-01.yaml through chapter-NN.yaml (saved incrementally)

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count (auto-calculated if not provided)
            template: Optional custom template (currently unused)
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            List of ChapterOutline objects
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

            # Track whether this is initial generation (no stored value) vs iteration/regeneration
            is_initial_generation = False
            min_words = None
            max_words = None
            genre_baseline = None

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

                        # Validate stored target against current length_scope from taxonomy
                        if length_scope:
                            normalized_scope = length_scope.lower().replace(' ', '_')
                            form_ranges = DepthCalculator.FORM_RANGES.get(normalized_scope)
                            if form_ranges:
                                min_words, max_words = form_ranges
                                # If stored target is outside form range, recalculate with warning
                                if total_words < min_words or total_words > max_words:
                                    if logger:
                                        logger.warning(
                                            f"Stored target {total_words:,} words is outside range for {length_scope} "
                                            f"({min_words:,}-{max_words:,}). Recalculating to match taxonomy..."
                                        )
                                    self.console.print(
                                        f"[yellow]Note:[/yellow] Stored target ({total_words:,} words) doesn't match "
                                        f"{length_scope} range. Recalculating..."
                                    )
                                    total_words = None  # Force recalculation

                # Calculate intelligent default if no stored value (or if invalidated)
                # For initial generation, we'll let LLM analyze treatment and choose
                if total_words is None:
                    is_initial_generation = True  # No stored value means first-time generation

                    # Get the range constraints from taxonomy
                    if length_scope:
                        normalized_scope = length_scope.lower().replace(' ', '_')
                        form_ranges = DepthCalculator.FORM_RANGES.get(normalized_scope)
                        if form_ranges:
                            min_words, max_words = form_ranges
                        else:
                            # Fallback to novel range
                            min_words, max_words = DepthCalculator.FORM_RANGES.get('novel', (50000, 120000))

                        # Get genre baseline for reference
                        genre_baseline = DepthCalculator.get_default_word_count(length_scope, genre)

                        if logger:
                            logger.debug(
                                f"Initial generation: Will use LLM treatment analysis for word count. "
                                f"Range: {min_words:,}-{max_words:,}, Genre baseline: {genre_baseline:,}"
                            )

                        # Use genre baseline as starting point (will be replaced by LLM's analysis)
                        total_words = genre_baseline
                    else:
                        # Fallback: use 'novel' baseline
                        total_words = DepthCalculator.get_default_word_count('novel', genre)
                        min_words, max_words = DepthCalculator.FORM_RANGES.get('novel', (50000, 120000))
                        if logger:
                            logger.debug(f"Using fallback default for novel/{genre}: {total_words} words")

            # Calculate story structure using top-down budgeting
            if not chapter_count:
                structure = self._calculate_structure(total_words, pacing, length_scope)
                chapter_count = structure['chapter_count']
                form = structure['form']
            else:
                # User specified chapter count - use it
                structure = self._calculate_structure(total_words, pacing, length_scope)
                form = structure['form']

            # Calculate top-down budget (Book → Acts → Chapters → Scenes → Beats)
            budget = DepthCalculator.calculate_top_down_budget(
                total_words=total_words,
                chapter_count=chapter_count,
                form=form,
                glue_fraction=0.25  # 25% for transitions/exposition
            )

            if logger:
                logger.debug(f"Top-down budget calculated: {form}, {chapter_count} chapters")
                logger.debug(f"Act budgets: {budget['act_budgets']}")
                logger.debug(f"Chapter budgets: {len(budget['chapter_budgets'])} chapters with roles/targets")

            # Display comprehensive story structure breakdown
            self.console.print(f"\n[bold cyan]Story Structure Breakdown:[/bold cyan]")
            self.console.print(f"  Form: [green]{form.replace('_', ' ').title()}[/green]")
            self.console.print(f"  Target: [green]{total_words:,}[/green] words")
            self.console.print(f"  Chapters: [green]{chapter_count}[/green]")

            # Display act breakdown
            act_budgets = budget['act_budgets']
            self.console.print(f"  Act Budgets: [green]Act I: {act_budgets[0]:,}w[/green] | [green]Act II: {act_budgets[1]:,}w[/green] | [green]Act III: {act_budgets[2]:,}w[/green]")
            self.console.print(f"  Glue Fraction: [green]25%[/green] (transitions/exposition)")

            # Count peak chapters
            peak_chapters = [ch for ch in budget['chapter_budgets'] if ch['role'] in ['inciting_setup', 'midpoint', 'crisis', 'climax']]
            self.console.print(f"  Peak Chapters: [green]{len(peak_chapters)}[/green] (inciting, midpoint, crisis, climax)")

            if feedback:
                # During iteration, LLM can adjust - show baseline with note
                self.console.print(f"\n[bold yellow]📝 Iteration Mode:[/bold yellow] LLM will analyze feedback and may adjust:")
                self.console.print(f"   • Word count (currently {total_words:,})")
                self.console.print(f"   • Chapter count (currently {chapter_count})")
                self.console.print(f"   Changes will be shown after foundation generation")

            # Serialize context to YAML for prompts
            context_yaml = self.context_builder.to_yaml_string(context)

            # Extract original concept and unique elements from premise metadata
            premise_metadata = context.get('premise', {}).get('metadata', {})
            original_concept = premise_metadata.get('original_concept', '')
            unique_elements = premise_metadata.get('unique_elements', [])

            # Get model capabilities (for display/validation only - no batching)
            model_obj = await self.client.get_model(self.model)
            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {self.model}")

            # ===== PHASE 1: GENERATE OR LOAD FOUNDATION =====
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
                    self.console.print(f"\n[cyan][1/3] Loading existing foundation...[/cyan]")
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

                            # Recalculate structure AND budget with foundation's values
                            structure = self._calculate_structure(total_words, pacing, length_scope)
                            form = structure['form']

                            # Recalculate budget with foundation's values
                            budget = DepthCalculator.calculate_top_down_budget(
                                total_words=total_words,
                                chapter_count=chapter_count,
                                form=form,
                                glue_fraction=0.25
                            )
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
                    self.console.print(f"\n[cyan][1/3] Regenerating foundation (iteration mode)...[/cyan]")
                else:
                    self.console.print(f"\n[cyan][1/3] Generating foundation (metadata + characters + world)...[/cyan]")

                foundation = await self._generate_foundation(
                context_yaml=context_yaml,
                taxonomy_data=taxonomy_data,
                total_words=total_words,
                chapter_count=chapter_count,
                original_concept=original_concept,
                unique_elements=unique_elements,
                feedback=feedback,
                is_initial_generation=is_initial_generation,
                min_words=min_words,
                max_words=max_words,
                genre_baseline=genre_baseline,
                length_scope=length_scope,
                genre=genre
            )

                # Save foundation immediately to both locations
                self._save_partial(foundation, phase='foundation')  # Backup/debug
                self.project.save_foundation(foundation)  # Proper location for resume
                self.console.print(f"[green]✓[/green] Foundation complete")

                # Validate foundation fidelity (separate LLM call)
                # NOTE: Validation happens AFTER saving to aid debugging
                self.console.print(f"[dim]Validating foundation fidelity...[/dim]")

                treatment_text = context.get('treatment', {}).get('text', '')
                is_valid, critical_issues = await self._validate_foundation_fidelity(
                    foundation_data=foundation,
                    treatment_text=treatment_text
                )

                if not is_valid and critical_issues:
                    # Display critical issues
                    self.console.print(f"\n[bold red]{'='*70}[/bold red]")
                    self.console.print(f"[bold red]✗ CRITICAL ISSUE DETECTED in Foundation[/bold red]")
                    self.console.print(f"[bold red]{'='*70}[/bold red]\n")

                    for issue in critical_issues:
                        self.console.print(f"[bold yellow]Issue Type:[/bold yellow] {issue.get('type', 'Unknown')}")
                        self.console.print(f"[bold yellow]Element:[/bold yellow] {issue.get('element', 'Unknown')}\n")

                        self.console.print(f"[yellow]Problem:[/yellow]")
                        self.console.print(f"  {issue.get('reasoning', 'No details provided')}\n")

                        self.console.print(f"[cyan]Recommendation:[/cyan]")
                        self.console.print(f"  {issue.get('recommendation', 'Review and fix')}\n")
                        self.console.print(f"[dim]{'-'*70}[/dim]\n")

                    self.console.print(f"[bold yellow]⚠️  Foundation contradicts the treatment.[/bold yellow]")
                    self.console.print(f"[yellow]Continuing may cause story drift and compound errors in chapters.[/yellow]\n")

                    self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
                    self.console.print(f"  [cyan]1.[/cyan] Abort generation [bold](recommended)[/bold] - fix treatment or regenerate foundation")
                    self.console.print(f"  [cyan]2.[/cyan] Iterate on foundation to fix specific issues")
                    self.console.print(f"  [cyan]3.[/cyan] Ignore and continue [bold](NOT recommended)[/bold] - may cause story drift")

                    foundation_choice = input("\nEnter choice (1-3): ").strip()

                    if foundation_choice == "1":
                        # Abort generation
                        self.console.print(f"\n[red]Generation aborted due to foundation fidelity issues[/red]")
                        self.console.print(f"[dim]Review foundation at: chapter-beats/foundation.yaml[/dim]")
                        raise Exception("Foundation validation failed - user aborted generation")

                    elif foundation_choice == "2":
                        # Iterate on foundation with specific feedback from validation
                        self.console.print(f"\n[yellow]Iterating on foundation to fix specific issues...[/yellow]")
                        self.console.print(f"[yellow]Previous foundation saved to .agentic/debug/ for reference[/yellow]\n")

                        # Save previous foundation for reference
                        debug_dir = self.project.path / ".agentic" / "debug"
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        debug_file = debug_dir / f"foundation_failed_{timestamp}.yaml"
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            yaml.dump(foundation, f, default_flow_style=False, allow_unicode=True)

                        # Let user select which issues to incorporate
                        selected_issues = self._select_validation_issues(critical_issues, context="foundation")

                        # Build iteration prompt with previous foundation and selected issues
                        foundation_yaml = yaml.dump(foundation, default_flow_style=False, allow_unicode=True)
                        issues_formatted = self._format_validation_issues(selected_issues)

                        iteration_feedback = f"""FOUNDATION ITERATION - FIX VALIDATION ISSUES:

The foundation below contradicts the treatment in specific ways.
Fix ONLY the flagged issues while preserving correct elements.

YOUR PREVIOUS FOUNDATION:
```yaml
{foundation_yaml}
```

VALIDATION ISSUES TO FIX:

{issues_formatted}

INSTRUCTIONS:
1. Review each issue carefully
2. Cross-reference the treatment (provided in context above)
3. Update ONLY the problematic elements
4. Keep everything else that was correct
5. Do NOT add new major plot elements
6. Elaborate on treatment elements, don't contradict them

Return the corrected foundation as complete YAML."""

                        # Combine with any existing feedback
                        if feedback:
                            iteration_feedback = f"{feedback}\n\n{iteration_feedback}"

                        # Generate corrected foundation
                        foundation = await self._generate_foundation(
                            context_yaml=context_yaml,
                            taxonomy_data=taxonomy_data,
                            total_words=total_words,
                            chapter_count=chapter_count,
                            original_concept=original_concept,
                            unique_elements=unique_elements,
                            feedback=iteration_feedback,
                            is_initial_generation=is_initial_generation,
                            min_words=min_words,
                            max_words=max_words,
                            genre_baseline=genre_baseline,
                            length_scope=length_scope,
                            genre=genre
                        )

                        # Save iterated foundation
                        self._save_partial(foundation, phase='foundation')
                        self.project.save_foundation(foundation)
                        self.console.print(f"[green]✓[/green] Foundation iteration complete")

                        # Validate again
                        self.console.print(f"[dim]Validating corrected foundation...[/dim]")
                        is_valid, new_issues = await self._validate_foundation_fidelity(
                            foundation_data=foundation,
                            treatment_text=treatment_text
                        )

                        # Show results
                        if not is_valid and new_issues:
                            self.console.print(f"\n[yellow]⚠️  Foundation still has issues:[/yellow]")
                            for issue in new_issues:
                                self.console.print(f"  • {issue.get('element', 'Unknown')}: {issue.get('reasoning', '')}")
                            self.console.print(f"\n[yellow]Continuing anyway (iteration attempted)...[/yellow]\n")
                        else:
                            self.console.print(f"[green]✓[/green] Foundation validation passed!\n")

                    elif foundation_choice == "3":
                        # Ignore and continue
                        self.console.print(f"\n[yellow]⚠️  Ignoring foundation fidelity issues...[/yellow]")
                        self.console.print(f"[yellow]Future chapters may drift from treatment.[/yellow]\n")

                    else:
                        # Invalid choice - treat as abort
                        self.console.print(f"\n[red]Invalid choice, aborting generation[/red]")
                        raise Exception("Invalid foundation validation choice")
                else:
                    if logger:
                        logger.debug("Foundation validation passed")
                    self.console.print(f"[green]✓[/green] Foundation validation passed\n")

            # ===== EXTRACT LLM'S STRUCTURAL CHOICES =====
            # During iteration: LLM adjusts based on feedback
            # During initial generation: LLM chooses based on treatment analysis
            if feedback or is_initial_generation:
                foundation_metadata = foundation.get('metadata', {})
                llm_word_count = foundation_metadata.get('target_word_count')
                llm_chapter_count = foundation_metadata.get('chapter_count')

                # Track what changed
                original_total_words = total_words
                original_chapter_count = chapter_count
                word_count_changed = False
                chapter_count_changed = False

                # Apply LLM's word count (if provided and different)
                if llm_word_count:
                    llm_word_count = int(llm_word_count)
                    if llm_word_count != total_words:
                        total_words = llm_word_count
                        word_count_changed = True
                        if logger:
                            if feedback:
                                logger.info(f"Iteration: LLM adjusted word count to {total_words}")
                            else:
                                logger.info(f"Initial generation: LLM chose word count {total_words} based on treatment")

                # Apply LLM's chapter count (if provided, valid, and different)
                if llm_chapter_count:
                    llm_chapter_count = int(llm_chapter_count)
                    # Validate reasonable range (1-100 chapters)
                    if 1 <= llm_chapter_count <= 100:
                        if llm_chapter_count != chapter_count:
                            chapter_count = llm_chapter_count
                            chapter_count_changed = True
                            if logger:
                                if feedback:
                                    logger.info(f"Iteration: LLM adjusted chapter count to {chapter_count}")
                                else:
                                    logger.info(f"Initial generation: LLM chose chapter count {chapter_count} based on treatment")
                    else:
                        if logger:
                            logger.warning(
                                f"LLM provided invalid chapter_count {llm_chapter_count}, "
                                f"using calculated value {chapter_count}"
                            )

                # Display adjustments (if any)
                if word_count_changed or chapter_count_changed:
                    self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
                    if feedback:
                        self.console.print(f"[bold cyan]📊 LLM Structural Adjustments Based on Feedback[/bold cyan]")
                    else:
                        self.console.print(f"[bold cyan]📊 Treatment Analysis Results[/bold cyan]")
                    self.console.print(f"[bold cyan]{'='*60}[/bold cyan]")

                    if word_count_changed:
                        word_diff = total_words - original_total_words
                        word_pct = (word_diff / original_total_words * 100) if original_total_words > 0 else 0
                        direction = "↗" if word_diff > 0 else "↘"
                        color = "green" if word_diff > 0 else "yellow"
                        self.console.print(
                            f"  [bold]Word Count:[/bold] [{color}]{original_total_words:,} → {total_words:,}[/{color}] "
                            f"[{color}]{direction} {abs(word_pct):.1f}% ({word_diff:+,} words)[/{color}]"
                        )

                    if chapter_count_changed:
                        chapter_diff = chapter_count - original_chapter_count
                        direction = "↗" if chapter_diff > 0 else "↘"
                        color = "green" if chapter_diff > 0 else "yellow"
                        self.console.print(
                            f"  [bold]Chapters:[/bold] [{color}]{original_chapter_count} → {chapter_count}[/{color}] "
                            f"[{color}]{direction} {abs(chapter_diff)} chapters[/{color}]"
                        )

                    # Show impact summary
                    if word_count_changed and chapter_count_changed:
                        avg_before = original_total_words // original_chapter_count if original_chapter_count > 0 else 0
                        avg_after = total_words // chapter_count if chapter_count > 0 else 0
                        self.console.print(
                            f"\n  [dim]Average chapter length: {avg_before:,} → {avg_after:,} words[/dim]"
                        )

                    self.console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")
                else:
                    # No changes made - LLM kept existing structure
                    if feedback:
                        # Only show this message during iteration
                        self.console.print(f"\n[dim]→ LLM analysis: Current structure appropriate for feedback[/dim]\n")

                # Recalculate structure AND budget with LLM's values (if any changed)
                if llm_word_count or llm_chapter_count:
                    structure = self._calculate_structure(total_words, pacing, length_scope)
                    form = structure['form']

                    # Recalculate top-down budget with LLM's values
                    budget = DepthCalculator.calculate_top_down_budget(
                        total_words=total_words,
                        chapter_count=chapter_count,
                        form=form,
                        glue_fraction=0.25
                    )

                    if logger:
                        logger.debug(
                            f"Recalculated structure with LLM values: {form}, {chapter_count} chapters"
                        )
                        logger.debug(f"Recalculated budget: act_budgets={budget['act_budgets']}")

            # ===== CHECK FOR EXISTING CHAPTERS (RESUME CAPABILITY) =====
            existing_chapters = self.project.list_chapter_beats()
            start_chapter = 1

            if existing_chapters and not feedback:
                # We have existing chapters and this is NOT an iteration
                existing_count = len(existing_chapters)

                self.console.print(f"\n[yellow]⚠️  Found {existing_count} existing chapters[/yellow]")
                self.console.print(f"\nWhat would you like to do?")
                self.console.print(f"  [cyan]1.[/cyan] Continue from chapter {existing_count + 1} (resume)")
                self.console.print(f"  [cyan]2.[/cyan] Regenerate all chapters from scratch")
                self.console.print(f"  [cyan]3.[/cyan] Abort generation")

                choice = input("\nEnter choice (1-3): ").strip()

                if choice == "1":
                    # Resume: start from next chapter
                    start_chapter = existing_count + 1
                    self.console.print(f"[cyan]Resuming from chapter {start_chapter}...[/cyan]")

                    if start_chapter > chapter_count:
                        self.console.print(f"[green]✓[/green] All chapters already complete!")
                        # Load existing and return
                        existing_data = self.project.get_chapters()
                        if existing_data:
                            chapters = []
                            for chapter_dict in existing_data:
                                chapter = ChapterOutline.from_api_response(chapter_dict)
                                chapters.append(chapter)
                            return chapters
                        else:
                            raise Exception("Found chapter files but failed to load them")
                elif choice == "2":
                    # Regenerate: delete existing chapters, keep foundation
                    self.console.print(f"[yellow]Deleting {existing_count} existing chapters...[/yellow]")

                    # Delete all chapter files only (keep foundation - it's the stable story structure)
                    for chapter_file in existing_chapters:
                        chapter_file.unlink()

                    start_chapter = 1
                    self.console.print(f"[cyan]Regenerating all chapters from scratch...[/cyan]")
                    self.console.print(f"[dim](keeping existing foundation - use /iterate to change story structure)[/dim]")
                elif choice == "3":
                    # Abort
                    self.console.print(f"[yellow]Generation aborted[/yellow]")
                    raise Exception("User aborted generation")
                else:
                    self.console.print(f"[yellow]Invalid choice, aborting[/yellow]")
                    raise Exception("Invalid resume choice")

            # ===== PHASE 2: GENERATE CHAPTERS SEQUENTIALLY =====
            self.console.print(f"\n[cyan][2/3] Generating chapters sequentially...[/cyan]")

            # Generate each chapter one at a time with full context
            for chapter_num in range(start_chapter, chapter_count + 1):
                self.console.print(f"\n[cyan]Generating chapter {chapter_num}/{chapter_count}...[/cyan]")

                # Load ALL previous chapters for full context
                previous_chapters = []
                for prev_num in range(1, chapter_num):
                    prev_chapter_data = self.project.get_chapter_beat(prev_num)
                    if prev_chapter_data:
                        previous_chapters.append(prev_chapter_data)

                if logger:
                    logger.debug(f"Loaded {len(previous_chapters)} previous chapters for context")

                # Get chapter budget for this chapter
                chapter_budget = budget['chapter_budgets'][chapter_num - 1]

                # Generate this chapter with full context
                try:
                    chapter_data = await self._generate_single_chapter(
                        chapter_num=chapter_num,
                        total_chapters=chapter_count,
                        context_yaml=context_yaml,
                        foundation=foundation,
                        previous_chapters=previous_chapters,
                        form=form,
                        pacing=pacing,
                        chapter_budget=chapter_budget,
                        feedback=feedback,
                        auto_fix=auto_fix
                    )
                except Exception as e:
                    # Save error context for debugging
                    if logger:
                        logger.error(f"Chapter {chapter_num} generation failed: {e}")

                    self.console.print(f"[red]✗[/red] Failed to generate chapter {chapter_num}: {e}")

                    # Add truncation hint if it's a YAML error indicating truncation
                    error_str = str(e).lower()
                    if any(indicator in error_str for indicator in [
                        "while scanning", "unexpected end", "unclosed", "truncation", "retries"
                    ]):
                        self.console.print(f"\n[yellow]This looks like a network truncation (automatic retries exhausted).[/yellow]")
                        self.console.print(f"[yellow]This can happen with unstable connections or slow models.[/yellow]")

                    self.console.print(f"\n[yellow]Generation stopped at chapter {chapter_num}[/yellow]")
                    self.console.print(f"[dim]Completed chapters saved to chapter-beats/[/dim]")
                    self.console.print(f"[dim]You can resume by running /generate chapters again[/dim]")
                    raise Exception(f"Failed to generate chapter {chapter_num}: {e}")

                # Save chapter immediately (enables resume and debugging)
                # IMPORTANT: Save BEFORE validation so chapter is preserved even if issues detected
                self.project.save_chapter_beat(chapter_num, chapter_data)

                if logger:
                    logger.debug(f"Saved chapter {chapter_num} to chapter-beats/chapter-{chapter_num:02d}.yaml")
                    # Log details for debugging
                    logger.info(f"=== SAVING INITIAL CHAPTER {chapter_num} (pre-validation) ===")
                    initial_yaml = yaml.dump(chapter_data, default_flow_style=False, allow_unicode=True)
                    has_parkinson = "parkinson" in initial_yaml.lower()
                    logger.info(f"Parkinson mentioned in initial chapter: {has_parkinson}")

                # Validate treatment fidelity (separate LLM call)
                self.console.print(f"[dim]Validating treatment fidelity...[/dim]")

                treatment_text = context.get('treatment', {}).get('text', '')
                is_valid, critical_issues = await self._validate_treatment_fidelity(
                    chapter_data=chapter_data,
                    chapter_num=chapter_num,
                    treatment_text=treatment_text,
                    previous_chapters=previous_chapters
                )

                if not is_valid and critical_issues:
                    # Display critical issues
                    self.console.print(f"\n[bold red]{'='*70}[/bold red]")
                    self.console.print(f"[bold red]✗ CRITICAL ISSUE DETECTED in Chapter {chapter_num}[/bold red]")
                    self.console.print(f"[bold red]{'='*70}[/bold red]\n")

                    for issue in critical_issues:
                        self.console.print(f"[bold yellow]Issue Type:[/bold yellow] {issue.get('type', 'Unknown')}")
                        self.console.print(f"[bold yellow]Location:[/bold yellow] {issue.get('location', 'Unknown')}")
                        self.console.print(f"[bold yellow]Element:[/bold yellow] {issue.get('element', 'Unknown')}\n")

                        self.console.print(f"[yellow]Problem:[/yellow]")
                        self.console.print(f"  {issue.get('reasoning', 'No details provided')}\n")

                        self.console.print(f"[cyan]Recommendation:[/cyan]")
                        self.console.print(f"  {issue.get('recommendation', 'Review and fix')}\n")
                        self.console.print(f"[dim]{'-'*70}[/dim]\n")

                    self.console.print(f"[bold yellow]⚠️  This chapter invents major plot elements not in the treatment.[/bold yellow]")
                    self.console.print(f"[yellow]Continuing may cause story drift and compound errors in future chapters.[/yellow]\n")

                    # Check if auto-fix is enabled
                    if auto_fix:
                        # Auto-fix: automatically iterate with ALL issues (no prompts)
                        choice = "2"
                        self.console.print(f"[cyan]Auto-fix enabled: Automatically iterating with all {len(critical_issues)} issues...[/cyan]\n")
                    else:
                        # Normal mode: show choices and prompt user
                        self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
                        self.console.print(f"  [cyan]1.[/cyan] Abort generation - fix treatment or modify chapter manually")
                        self.console.print(f"  [cyan]2.[/cyan] Iterate on chapter {chapter_num} to fix specific issues [bold](recommended)[/bold]")
                        self.console.print(f"  [cyan]3.[/cyan] Ignore and continue [bold](NOT recommended)[/bold] - may cause story drift")

                        try:
                            choice = input("\nEnter choice (1-3): ").strip()
                        except (KeyboardInterrupt, EOFError):
                            # User cancelled - treat as abort
                            self.console.print(f"\n[yellow]Cancelled by user. Aborting generation...[/yellow]")
                            raise KeyboardInterrupt(f"User cancelled validation choice for chapter {chapter_num}")

                    if choice == "1":
                        # Abort generation
                        self.console.print(f"\n[red]Generation aborted at chapter {chapter_num}[/red]")
                        self.console.print(f"[dim]Completed chapters (1-{chapter_num - 1}) saved to chapter-beats/[/dim]")
                        self.console.print(f"[dim]Fix treatment or modify feedback, then run /generate chapters to resume[/dim]")
                        raise Exception(f"User aborted generation due to treatment fidelity violation in chapter {chapter_num}")

                    elif choice == "2":
                        # Iterate on chapter with specific feedback from validation
                        self.console.print(f"\n[yellow]Iterating on chapter {chapter_num} to fix specific issues...[/yellow]")
                        self.console.print(f"[yellow]Previous chapter saved to .agentic/debug/ for reference[/yellow]\n")

                        # Save previous chapter for reference
                        debug_dir = self.project.path / ".agentic" / "debug"
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        debug_file = debug_dir / f"chapter_{chapter_num}_failed_{timestamp}.yaml"
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            yaml.dump(chapter_data, f, default_flow_style=False, allow_unicode=True)

                        # Select issues: auto-fix uses ALL, normal mode prompts user
                        if auto_fix:
                            # Auto-fix: include ALL issues without prompting
                            selected_issues = critical_issues
                            self.console.print(f"[green]✓[/green] Auto-fix: Including all {len(critical_issues)} issues\n")
                        else:
                            # Normal mode: let user select which issues to incorporate
                            selected_issues = self._select_validation_issues(critical_issues, context=f"chapter {chapter_num}")

                        # Build iteration prompt with previous chapter and selected issues
                        chapter_yaml = yaml.dump(chapter_data, default_flow_style=False, allow_unicode=True)
                        issues_formatted = self._format_validation_issues(selected_issues)

                        iteration_feedback = f"""APPLY MINIMAL FIXES TO CHAPTER {chapter_num}:

The chapter below has specific validation issues that need surgical fixes.
Your task is to make the ABSOLUTE MINIMUM changes needed to fix ONLY these issues.

EXISTING CHAPTER {chapter_num} (99% correct - needs minimal fixes):
```yaml
{chapter_yaml}
```

SPECIFIC ISSUES TO FIX (and NOTHING else):

{issues_formatted}

CRITICAL INSTRUCTIONS - MINIMAL CHANGES ONLY:
1. FIX ONLY the specific elements mentioned in the issues above
2. PRESERVE everything else EXACTLY as-is (even imperfect but non-violating content)
3. Do NOT improve, enhance, or rewrite any scenes that aren't mentioned in issues
4. Do NOT add new plot elements, scenes, or character moments
5. Do NOT reorganize or restructure the chapter
6. Do NOT fix things that aren't explicitly listed as issues
7. If a scene has no issues mentioned, copy it VERBATIM

Think of this as a surgical edit - change ONLY what's broken, leave everything else untouched.
The goal is the SMALLEST possible diff that fixes the violations.

Example:
- Issue says "Remove Parkinson subplot from scene 3" → Delete those specific lines from scene 3 ONLY
- Issue says "Dr. Lang not in treatment" → Change Dr. Lang to a character from treatment
- Everything else → COPY EXACTLY AS-IS

Return the fixed chapter as complete YAML with same structure."""

                        # Retry up to 5 times
                        max_retries = 5
                        for retry_attempt in range(1, max_retries + 1):
                            self.console.print(f"[dim]Attempt {retry_attempt}/{max_retries}...[/dim]")

                            try:
                                # Do NOT include the failed chapter in previous_chapters
                                # The failed chapter is already shown in the iteration_feedback
                                # Including it in previous_chapters can cause LLM to preserve elements that should be removed

                                iterated_chapter = await self._generate_single_chapter(
                                    chapter_num=chapter_num,
                                    total_chapters=chapter_count,
                                    context_yaml=context_yaml,
                                    foundation=foundation,
                                    previous_chapters=previous_chapters,
                                    form=form,
                                    pacing=pacing,
                                    chapter_budget=chapter_budget,
                                    feedback=iteration_feedback,
                                    auto_fix=auto_fix
                                )

                                # Save iterated chapter (overwrite previous)
                                self.project.save_chapter_beat(chapter_num, iterated_chapter)
                                chapter_data = iterated_chapter  # Use iterated version

                                if logger:
                                    logger.debug(f"Iterated chapter {chapter_num} (attempt {retry_attempt})")
                                    # Log details about what we're saving to help debug Parkinson issue
                                    logger.info(f"=== SAVING ITERATED CHAPTER {chapter_num} ===")
                                    logger.info(f"Iteration attempt: {retry_attempt}")
                                    # Check if Parkinson is mentioned in the iterated content
                                    iterated_yaml = yaml.dump(iterated_chapter, default_flow_style=False, allow_unicode=True)
                                    has_parkinson = "parkinson" in iterated_yaml.lower()
                                    logger.info(f"Parkinson mentioned in iterated chapter: {has_parkinson}")
                                    if has_parkinson:
                                        logger.warning("WARNING: Parkinson still present after iteration!")
                                    logger.info(f"Chapter saved to: chapter-beats/chapter-{chapter_num:02d}.yaml")

                                    # Verify save by reading back
                                    readback = self.project.get_chapter_beat(chapter_num)
                                    if readback:
                                        readback_yaml = yaml.dump(readback, default_flow_style=False, allow_unicode=True)
                                        readback_has_parkinson = "parkinson" in readback_yaml.lower()
                                        logger.info(f"Verification: Parkinson in saved file: {readback_has_parkinson}")
                                        if readback_has_parkinson != has_parkinson:
                                            logger.error(f"MISMATCH: Memory has parkinson={has_parkinson}, disk has parkinson={readback_has_parkinson}")
                                    else:
                                        logger.error(f"Failed to read back saved chapter {chapter_num}")

                                # Validate iterated chapter
                                self.console.print(f"[dim]Validating corrected chapter...[/dim]")
                                iter_valid, iter_issues = await self._validate_treatment_fidelity(
                                    chapter_data=iterated_chapter,
                                    chapter_num=chapter_num,
                                    treatment_text=treatment_text,
                                    previous_chapters=previous_chapters
                                )

                                if iter_valid or not iter_issues:
                                    # Success! Iterated chapter passed validation
                                    self.console.print(f"\n[green]✓[/green] Chapter {chapter_num} iteration complete - validation passed!\n")
                                    break
                                else:
                                    # Still has issues
                                    if retry_attempt < max_retries:
                                        self.console.print(f"[yellow]Chapter still has issues. Retrying iteration...[/yellow]")

                                        # Select issues for retry: auto-fix uses ALL, normal mode prompts user
                                        if auto_fix:
                                            # Auto-fix: include ALL issues without prompting
                                            retry_selected_issues = iter_issues
                                            self.console.print(f"[green]✓[/green] Auto-fix: Including all {len(iter_issues)} issues for retry\n")
                                        else:
                                            # Normal mode: let user select which new issues to incorporate for retry
                                            retry_selected_issues = self._select_validation_issues(iter_issues, context=f"chapter {chapter_num} retry")

                                        # Update iteration_feedback with selected new issues for next attempt
                                        issues_formatted = self._format_validation_issues(retry_selected_issues)
                                        iteration_feedback = f"""APPLY MINIMAL FIXES - RETRY (Attempt {retry_attempt + 1}/{max_retries}):

Previous fix still has a few remaining issues. Apply MINIMAL fixes to address ONLY these.

CURRENT CHAPTER {chapter_num} (mostly fixed - needs tiny adjustments):
```yaml
{yaml.dump(iterated_chapter, default_flow_style=False, allow_unicode=True)}
```

REMAINING ISSUES TO FIX (and NOTHING else):

{issues_formatted}

CRITICAL - MINIMAL CHANGES ONLY:
1. FIX ONLY the specific elements mentioned above
2. PRESERVE everything else EXACTLY as-is
3. Do NOT improve or rewrite unrelated content
4. Do NOT add any new content
5. Copy everything that isn't mentioned in the issues VERBATIM

This is a surgical fix - change ONLY what's listed as an issue, nothing more.

Return the fixed chapter as complete YAML with same structure."""
                                        # Update chapter_data for next iteration's context
                                        chapter_data = iterated_chapter
                                    else:
                                        # Max retries reached
                                        self.console.print(f"\n[yellow]Max retries reached. Chapter {chapter_num} still has issues:[/yellow]")
                                        for issue in iter_issues:
                                            self.console.print(f"  • {issue.get('element', 'Unknown')}: {issue.get('reasoning', 'No details')}")

                                        # In auto mode, just abort at max retries
                                        if auto_fix:
                                            self.console.print(f"\n[red]Auto-fix: Max retries reached, aborting generation[/red]")
                                            raise Exception(f"Auto-fix failed after {max_retries} attempts for chapter {chapter_num}")

                                        self.console.print(f"\n[yellow]Options:[/yellow]")
                                        self.console.print(f"  [cyan]1.[/cyan] Abort generation [bold](recommended)[/bold]")
                                        self.console.print(f"  [cyan]2.[/cyan] Ignore and continue [bold](NOT recommended)[/bold]")

                                        try:
                                            final_choice = input("\nEnter choice (1-2): ").strip()
                                        except (KeyboardInterrupt, EOFError):
                                            # User cancelled - treat as abort
                                            self.console.print(f"\n[yellow]Cancelled by user. Aborting generation...[/yellow]")
                                            raise KeyboardInterrupt(f"User cancelled max retries choice for chapter {chapter_num}")

                                        if final_choice == "1":
                                            self.console.print(f"\n[red]Generation aborted at chapter {chapter_num}[/red]")
                                            raise Exception(f"User aborted after failed iteration attempts for chapter {chapter_num}")
                                        else:
                                            self.console.print(f"\n[yellow]⚠️  Continuing with iterated chapter despite issues...[/yellow]\n")
                                            break

                            except KeyboardInterrupt:
                                # User aborted (Ctrl+C) - propagate immediately
                                self.console.print(f"\n[red]Iteration aborted by user[/red]")
                                raise

                            except Exception as iter_e:
                                if logger:
                                    logger.error(f"Iteration attempt {retry_attempt} failed: {iter_e}")

                                if retry_attempt < max_retries:
                                    self.console.print(f"[red]Iteration failed: {iter_e}[/red]")
                                    self.console.print(f"[yellow]Retrying...[/yellow]")
                                else:
                                    self.console.print(f"[red]All iteration attempts failed: {iter_e}[/red]")

                                    # In auto mode, abort on failure
                                    if auto_fix:
                                        self.console.print(f"[red]Auto-fix: Max retries exhausted, aborting generation[/red]")
                                        raise Exception(f"Auto-fix failed after {max_retries} iteration attempts for chapter {chapter_num}: {iter_e}")

                                    self.console.print(f"[yellow]Continuing with original chapter...[/yellow]\n")
                                    break

                    elif choice == "3":
                        # Ignore and continue
                        self.console.print(f"\n[yellow]⚠️  Continuing with chapter {chapter_num} despite issues...[/yellow]")
                        self.console.print(f"[yellow]This may cause compound errors in future chapters.[/yellow]\n")

                    else:
                        # Invalid choice - treat as abort
                        self.console.print(f"\n[red]Invalid choice, aborting generation[/red]")
                        raise Exception("Invalid validation choice")

                # Save chapter immediately (enables resume)
                # This final save ensures the correct version is persisted after all validation/iteration
                self.project.save_chapter_beat(chapter_num, chapter_data)

                # Show progress
                self.console.print(f"[green]✓[/green] Chapter {chapter_num}/{chapter_count} complete")

                if logger:
                    logger.debug(f"Saved chapter {chapter_num} to chapter-beats/chapter-{chapter_num:02d}.yaml")
                    # Log details for debugging
                    logger.info(f"=== SAVING FINAL CHAPTER {chapter_num} (post-validation) ===")
                    final_yaml = yaml.dump(chapter_data, default_flow_style=False, allow_unicode=True)
                    has_parkinson = "parkinson" in final_yaml.lower()
                    logger.info(f"Parkinson mentioned in final chapter: {has_parkinson}")
                    if has_parkinson:
                        logger.warning("WARNING: Parkinson present in final saved version!")

            # Load all chapters for assembly
            all_chapters = []
            for chapter_num in range(1, chapter_count + 1):
                chapter_data = self.project.get_chapter_beat(chapter_num)
                if not chapter_data:
                    raise Exception(f"Missing chapter {chapter_num} after generation")
                all_chapters.append(chapter_data)

            # ===== PHASE 3: ASSEMBLY AND VALIDATION =====
            self.console.print(f"\n[cyan][3/3] Assembling final result...[/cyan]")

            # Combine foundation + all chapters
            final_data = {
                **foundation,
                'chapters': all_chapters
            }

            # Final validation
            required_sections = ['metadata', 'characters', 'world', 'chapters']
            missing = [s for s in required_sections if s not in final_data]
            if missing:
                raise Exception(f"Missing required sections: {', '.join(missing)}")

            # Validate chapter count
            if len(all_chapters) != chapter_count:
                raise Exception(
                    f"Chapter count mismatch: generated {len(all_chapters)}, expected {chapter_count}"
                )

            # Validate sequential numbering
            for i, chapter in enumerate(all_chapters):
                expected_num = i + 1
                actual_num = chapter.get('number')
                if actual_num != expected_num:
                    raise Exception(
                        f"Chapter numbering error: chapter at index {i} has number {actual_num}, expected {expected_num}"
                    )

            # Validate pacing anchors
            if logger:
                logger.debug("Validating pacing anchors...")

            anchor_results = DepthCalculator.validate_pacing_anchors(
                chapter_budgets=budget['chapter_budgets'],
                total_words=total_words
            )

            # Display pacing validation results
            self.console.print(f"\n[bold cyan]Pacing Validation:[/bold cyan]")
            all_ok = True
            for anchor in ['inciting_incident', 'midpoint', 'crisis', 'climax']:
                result = anchor_results.get('anchors', {}).get(anchor)
                if result:
                    in_range = result['in_range']
                    actual_pct = result['actual_pct']
                    expected_min, expected_max = result['expected_range']

                    if in_range:
                        self.console.print(f"  ✓ {anchor.replace('_', ' ').title()}: [green]{actual_pct:.1f}%[/green] (expected {expected_min:.0f}-{expected_max:.0f}%)")
                    else:
                        all_ok = False
                        # Generate suggestion based on position
                        if actual_pct < expected_min:
                            suggestion = f"appears too early, consider moving later"
                        else:
                            suggestion = f"appears too late, consider moving earlier"
                        self.console.print(f"  ✗ {anchor.replace('_', ' ').title()}: [yellow]{actual_pct:.1f}%[/yellow] (expected {expected_min:.0f}-{expected_max:.0f}%) - {suggestion}")

            if all_ok:
                self.console.print(f"[green]All pacing anchors within expected ranges![/green]")
            else:
                self.console.print(f"[yellow]Some anchors outside expected ranges - consider adjusting chapter structure[/yellow]")

            # NOTE: We do NOT save chapters.yaml - chapter-beats/ is the only format
            # Individual chapter files (chapter-beats/chapter-NN.yaml) are already saved
            # No need for aggregated chapters.yaml file

            if logger:
                logger.debug(f"Successfully generated {len(all_chapters)} chapters with full context")

            # Display completion message with summary
            self.console.print(f"[green]✓[/green] Generation complete!")

            if feedback:
                # Show iteration summary
                self.console.print(f"\n[bold green]{'='*60}[/bold green]")
                self.console.print(f"[bold green]✨ Iteration Complete![/bold green]")
                self.console.print(f"[bold green]{'='*60}[/bold green]")

                # Get final metadata for summary
                final_metadata = final_data.get('metadata', {})
                final_word_count = final_metadata.get('target_word_count', total_words)

                self.console.print(f"  [bold]Final Structure:[/bold]")
                self.console.print(f"    • Chapters: [cyan]{chapter_count}[/cyan]")
                self.console.print(f"    • Target words: [cyan]{final_word_count:,}[/cyan]")
                self.console.print(f"    • Saved to: [cyan]chapters.yaml[/cyan]")
                self.console.print(f"\n  [dim]Your feedback has been incorporated into the structure[/dim]")
                self.console.print(f"[bold green]{'='*60}[/bold green]")
            else:
                # Regular generation message
                self.console.print(f"  [cyan]{chapter_count} chapters[/cyan] saved to [cyan]chapters.yaml[/cyan]")

            # Convert to ChapterOutline objects for backward compatibility
            chapters = []
            for chapter_dict in all_chapters:
                chapter = ChapterOutline.from_api_response(chapter_dict)
                chapters.append(chapter)

            return chapters

        except Exception as e:
            raise Exception(f"Failed to generate chapters: {e}")

    async def generate_with_competition(
        self,
        chapter_count: Optional[int] = None,
        total_words: Optional[int] = None,
        template: Optional[str] = None,
        feedback: Optional[str] = None,
        auto_fix: bool = False
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using multi-model competition with unified context.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count (auto-calculated if not provided)
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)
            auto_fix: If True, automatically fix validation issues without prompts (not yet implemented for competition mode)

        Returns:
            List of winning ChapterOutline objects
        """
        from .multi_model import MultiModelGenerator
        from ..utils.logging import get_logger
        logger = get_logger()

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

        # Extract length_scope (handle list format from taxonomy)
        length_scope_value = taxonomy_data.get('length_scope')
        if isinstance(length_scope_value, list) and length_scope_value:
            length_scope = length_scope_value[0]
        else:
            length_scope = length_scope_value if isinstance(length_scope_value, str) else None

        # Calculate total_words if not provided (same logic as generate())
        if total_words is None:
            # Try stored value first
            chapters_yaml = self.project.get_chapters_yaml()
            if chapters_yaml and isinstance(chapters_yaml, dict):
                metadata = chapters_yaml.get('metadata', {})
                stored_target = metadata.get('target_word_count')
                if stored_target:
                    total_words = int(stored_target)
                    if logger:
                        logger.debug(f"Using stored target_word_count: {total_words}")

            # Calculate intelligent default if no stored value
            if total_words is None:
                if length_scope:
                    total_words = DepthCalculator.get_default_word_count(length_scope, genre)
                    if logger:
                        logger.debug(f"Calculated default for {length_scope}/{genre}: {total_words} words")
                else:
                    # Fallback: use 'novel' baseline
                    total_words = DepthCalculator.get_default_word_count('novel', genre)
                    if logger:
                        logger.debug(f"Using fallback default for novel/{genre}: {total_words} words")

        # Calculate chapter count if not provided
        if not chapter_count:
            chapter_count = self._calculate_chapter_count(total_words)

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build unified prompt with iteration-specific instructions
        feedback_instruction = ""
        word_count_instruction = f"- target_word_count: {total_words}"
        word_count_distribution = f"- word_count_target: distribute {total_words} across chapters"

        if feedback:
            # For iteration: give LLM freedom to adjust word count based on feedback
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the above feedback while generating the chapters. You may adjust the target word count and chapter count if the feedback suggests it (e.g., 'consolidate' → fewer words/chapters, 'expand' → more words/chapters).\n\nCRITICAL - AVOID DUPLICATE EVENTS:\n- Review ALL existing chapters and scenes before creating new structure\n- Do NOT repeat plot beats, events, or character moments already covered\n- Each chapter must advance the story with UNIQUE events and conflicts\n- If feedback mentions 'duplicate' or 'repetitive', consolidate those events into single chapters"
            word_count_instruction = f"- target_word_count: {total_words} # Current target - adjust based on feedback if needed"
            word_count_distribution = f"- word_count_target: distribute words across chapters (adjust total if feedback requires it)"

        prompt = f"""# TREATMENT
```yaml
{context_yaml}
```

# YOUR TASK
Generate complete chapter structure (metadata + characters + world + chapters) from the treatment above.

# OUTPUT
Return plain YAML (DO NOT wrap in ```yaml or ``` fences):

metadata:
  genre: "..."
  tone: "..."
  pacing: "..."
  themes: ["...", "..."]
  narrative_style: "..."
  {word_count_instruction}

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

chapters:
  - number: 1
    title: "..."
    pov: "..."
    act: "Act I"
    summary: "..."
    scenes:
      - scene: "Brief Title"
        location: "Where"
        objective: "what character wants (verb phrase)"
        exit_hook: "optional"
        beats:
          - "Beat 1: what happens"
          - "Beat 2: what happens"
          - "Beat 3: what happens"
          - "Beat 4: what happens"
          - "Beat 5: what happens"
          - "Beat 6: what happens"
    character_developments: ["...", "..."]
    relationship_beats: ["...", "..."]
    tension_points: ["...", "..."]
    sensory_details: ["...", "..."]
    subplot_threads: ["..."]
    {word_count_distribution}
  # {chapter_count} chapters total
{feedback_instruction}"""

        # Create multi-model generator
        multi_gen = MultiModelGenerator(self.client, self.project)

        # Define generator function that takes model parameter
        async def generate_with_model(model: str) -> str:
            # Get model capabilities
            model_obj = await self.client.get_model(model)
            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {model}")

            max_output = model_obj.get_max_output_tokens()
            min_tokens = 5000  # Default for rich outlines

            if max_output and max_output < min_tokens:
                min_tokens = int(max_output * 0.8)

            # Generate with this model using dry_run
            result = await self.client.streaming_completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional story development assistant. You structure treatments into detailed chapter outlines with scenes and beats. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,  # Balanced creativity with adherence to treatment
                stream=True,
                display=True,
                display_label=f"Generating chapters ({model})",
                min_response_tokens=min_tokens
            )

            if not result:
                raise Exception(f"No response from {model}")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Parse with dry_run to validate but not save
            parse_result = self.parser.parse_and_save(
                response=response_text,
                project=self.project,
                target_lod='chapters',
                original_context=context,
                dry_run=True
            )

            # Return the raw response for comparison
            return response_text

        # Run competition
        competition_result = await multi_gen.generate_parallel(
            generator_func=generate_with_model,
            content_type="chapters",
            file_prefix="chapters",
            context={
                'premise': context['premise']['text'],
                'treatment': context['treatment']['text'],
                'genre': self.project.metadata.genre if self.project.metadata else None,
                'chapter_count': chapter_count,
                'total_words': total_words
            }
        )

        if not competition_result:
            raise Exception("Multi-model competition failed or was cancelled")

        # Get winning response
        winning_response = competition_result['winner']['content']

        # Now save the winner for real
        parse_result = self.parser.parse_and_save(
            response=winning_response,
            project=self.project,
            target_lod='chapters',
            original_context=context,
            dry_run=False  # Actually save this time
        )

        # Load the saved chapters and return as ChapterOutline objects
        chapters_data = self.project.get_chapters()
        if not chapters_data:
            raise Exception("No chapters found after saving winner")

        chapters = []
        for chapter_dict in chapters_data:
            chapter = ChapterOutline.from_api_response(chapter_dict)
            chapters.append(chapter)

        return chapters