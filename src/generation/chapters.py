"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from typing import Optional, List, Dict, Any

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline
from rich.console import Console
from ..config import get_settings
from .lod_context import LODContextBuilder
from .lod_parser import LODResponseParser
from .depth_calculator import DepthCalculator


# This template is deprecated - using inline prompt generation instead
DEFAULT_CHAPTERS_TEMPLATE = "DEPRECATED"


class ChapterGenerator:
    """
    Generator for chapter outlines (LOD2).

    TOKEN REQUIREMENTS:
    ===================
    The new self-contained chapters format requires significant tokens:

    - Overhead: ~2,000 tokens
      * metadata: ~500 tokens (genre, pacing, tone, themes, etc.)
      * characters: ~1,000 tokens (3-5 full character profiles)
      * world: ~500 tokens (setting, locations, systems)

    - Per chapter: ~600-800 tokens each
      * Rich outlines with 2-4 structured scenes, character developments,
        relationship beats, tension points, sensory details

    TOTAL NEEDED: overhead + (chapter_count * 700)

    Examples:
    - 5 chapters: 2,000 + (5 * 700) = 5,500 tokens
    - 10 chapters: 2,000 + (10 * 700) = 9,000 tokens
    - 20 chapters: 2,000 + (20 * 700) = 16,000 tokens

    MODEL SELECTION:
    - Small models (4k output): Can do ~2-3 chapters maximum
    - Medium models (8k output): Can do ~8-9 chapters
    - Large models (16k+ output): Can do full novels (20+ chapters)

    WORD COUNT vs TOKEN COUNT:
    ===========================
    There's often confusion about these metrics:

    - Word count: Human-readable metric (counted by split())
    - Token count: LLM processing units (~0.75 tokens per English word)

    Why they diverge:
    - YAML structure adds tokens without adding "words"
    - Indentation, colons, quotes are tokens but not words
    - Numbers like "3100" are words but may be multiple tokens

    Example from actual generation:
    - Generated: 5,393 words (from split())
    - Actual tokens: 3,749 tokens
    - Ratio: 0.70 tokens/word (lower due to YAML overhead)

    For chapters.yaml:
    - ~35% of tokens are structural (YAML, keys, formatting)
    - ~65% of tokens are actual content
    - So "5,393 words" is actually ~3,500 content words + YAML structure

    AUTO-RESUME ON TRUNCATION:
    ===========================
    Chapter generation includes automatic resume capability to handle network
    disconnections or silent connection drops during long-running generations.

    How it works:
    1. Detect truncation via YAML parse errors or incomplete chapter counts
    2. Analyze partial generation to find last complete chapter
    3. Generate continuation with custom prompt (only missing chapters)
    4. Merge partial + continuation with validation
    5. Save complete result

    Benefits:
    - Retry wastes ALL tokens and starts over (~15k tokens)
    - Resume keeps partial tokens and only generates missing (~11k tokens)
    - Saves ~25-30% of tokens on truncated generations

    Limitations:
    - Only one level of resume (if resume also truncates, generation fails)
    - Can't resume if truncation happens in metadata/characters/world sections
      (only if truncation is in chapters section with at least 1 complete chapter)
    - Resume request must fit in model's context (partial + context + continuation)
    - TCP keep-alive is limited by OS settings (aiohttp can't control OS-level)

    User experience:
    ```
    ⚠️  Generation truncated: yaml_parse_error_incomplete
    Found 5 complete chapters (of 16 needed)
    Resuming generation for chapters 6-16...
    ✓ Successfully resumed and merged 16 chapters
    ```

    The resume is automatic and transparent - users don't need to take action.
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

    def _find_last_complete_chapter(self, yaml_text: str) -> Dict[str, Any]:
        """
        Parse partial YAML to find last complete chapter.

        Args:
            yaml_text: Potentially truncated YAML text

        Returns:
            Dict with:
            - last_complete_chapter: int - last complete chapter number (0 if none)
            - partial_data: dict - successfully parsed data (may be incomplete)
            - chapters_count: int - number of chapters found
        """
        result = {
            'last_complete_chapter': 0,
            'partial_data': None,
            'chapters_count': 0
        }

        # First attempt: try parsing as-is
        try:
            data = yaml.safe_load(yaml_text)
            if isinstance(data, dict) and 'chapters' in data:
                chapters = data['chapters']
                if isinstance(chapters, list) and len(chapters) > 0:
                    # Check if last chapter has all required fields
                    last_chapter = chapters[-1]
                    # Accept both old (key_events) and new (scenes) formats
                    required_base_fields = ['number', 'title', 'summary', 'word_count_target']
                    has_base = all(f in last_chapter for f in required_base_fields)
                    has_content = ('scenes' in last_chapter or 'key_events' in last_chapter)

                    if has_base and has_content:
                        # Last chapter is complete
                        result['last_complete_chapter'] = len(chapters)
                    else:
                        # Last chapter is incomplete, use second-to-last
                        result['last_complete_chapter'] = max(0, len(chapters) - 1)

                    result['partial_data'] = data
                    result['chapters_count'] = len(chapters)
                    return result
        except yaml.YAMLError as parse_error:
            # YAML parsing failed - try to recover
            from ..utils.logging import get_logger
            logger = get_logger()

            if logger:
                logger.debug(f"Initial YAML parse failed: {parse_error}")
                logger.debug(f"Attempting to fix truncated YAML...")

            # Second attempt: fix unterminated strings and try again
            fixed_yaml = self._fix_truncated_yaml(yaml_text)
            if fixed_yaml:
                try:
                    data = yaml.safe_load(fixed_yaml)
                    if isinstance(data, dict):
                        result['partial_data'] = data

                        if 'chapters' in data and isinstance(data['chapters'], list):
                            chapters = data['chapters']
                            result['chapters_count'] = len(chapters)

                            # Check last chapter completeness
                            if len(chapters) > 0:
                                last_chapter = chapters[-1]
                                # Accept both old (key_events) and new (scenes) formats
                                required_base_fields = ['number', 'title', 'summary', 'word_count_target']
                                has_base = all(f in last_chapter for f in required_base_fields)
                                has_content = ('scenes' in last_chapter or 'key_events' in last_chapter)

                                if has_base and has_content:
                                    result['last_complete_chapter'] = len(chapters)
                                else:
                                    result['last_complete_chapter'] = max(0, len(chapters) - 1)

                        if logger:
                            logger.debug(f"Fixed YAML successfully: {result['chapters_count']} chapters, {result['last_complete_chapter']} complete")

                        return result
                except yaml.YAMLError as e:
                    if logger:
                        logger.debug(f"Fixed YAML still failed to parse: {e}")

            # Third attempt: pattern matching without parsing
            if logger:
                logger.debug("Falling back to pattern matching")

            # Count "- number:" occurrences as chapter markers
            chapter_markers = yaml_text.count('- number:')
            result['chapters_count'] = chapter_markers
            result['last_complete_chapter'] = max(0, chapter_markers - 1)  # Conservative estimate

        return result

    def _fix_truncated_yaml(self, yaml_text: str) -> str:
        """
        Attempt to fix common YAML truncation issues.

        Args:
            yaml_text: Truncated YAML text

        Returns:
            Fixed YAML text, or empty string if unfixable
        """
        # Check for unterminated strings (odd number of quotes)
        lines = yaml_text.split('\n')

        # Find the last line with content
        last_line_idx = len(lines) - 1
        while last_line_idx >= 0 and not lines[last_line_idx].strip():
            last_line_idx -= 1

        if last_line_idx < 0:
            return ""

        # Check if last line has unterminated string
        last_line = lines[last_line_idx]
        quote_count = last_line.count('"')

        if quote_count % 2 != 0:
            # Unterminated string - close it
            lines[last_line_idx] = last_line + '"'

            # Remove any incomplete content after this line
            fixed_lines = lines[:last_line_idx + 1]

            return '\n'.join(fixed_lines)

        # No obvious fix
        return ""

    def _calculate_batch_size(self, chapter_count: int, model_obj) -> int:
        """
        Calculate optimal batch size for chapter generation based on model capacity.

        Args:
            chapter_count: Total number of chapters to generate
            model_obj: Model object with capacity info

        Returns:
            Number of chapters per batch (minimum 1)
        """
        max_output = model_obj.get_max_output_tokens() if model_obj else 8000

        # Conservative estimates:
        # - Foundation overhead in context: ~2,000 tokens
        # - Previous chapter summaries: ~100 tokens each
        # - Output: ~700 tokens per chapter
        # - Safety margin: 20%

        if not max_output or max_output >= 16000:
            # Large models: 8 chapters per batch
            # Needs ~5,600 tokens output
            return min(8, chapter_count)
        elif max_output >= 8000:
            # Medium models: 5 chapters per batch
            # Needs ~3,500 tokens output
            return min(5, chapter_count)
        elif max_output >= 4000:
            # Small models: 3 chapters per batch
            # Needs ~2,100 tokens output
            return min(3, chapter_count)
        else:
            # Very small models: 2 chapters per batch
            # Needs ~1,400 tokens output
            return min(2, chapter_count)

    def _summarize_chapters(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Create compressed summaries of chapters for context passing.

        Args:
            chapters: List of full chapter dicts

        Returns:
            List of summary dicts with just number, title, summary
        """
        summaries = []
        for chapter in chapters:
            summaries.append({
                'number': chapter.get('number'),
                'title': chapter.get('title'),
                'summary': chapter.get('summary')
            })
        return summaries

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
        feedback: Optional[str] = None
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

        prompt = f"""Generate the FOUNDATION for a chapter structure. This is PART 1 of multi-phase generation.

INPUT CONTEXT:
```yaml
{context_yaml}
```
{unique_context}
TASK:
Create ONLY the metadata + characters + world sections. DO NOT generate chapters yet.

SECTION 1: METADATA
Generate high-level story parameters:
- genre, subgenre (if applicable)
- tone (e.g., "dark, tense", "light, humorous")
- pacing (e.g., "fast", "moderate", "slow")
- themes: 2-4 core themes from the story
- story_structure (e.g., "three_act", "hero_journey")
- narrative_style (e.g., "third_person_limited", "first_person")
- target_audience (e.g., "adult", "young adult")
- target_word_count: {total_words}{word_count_note}
- chapter_count: {chapter_count}{chapter_count_note}
- setting_period (e.g., "contemporary", "historical", "future")
- setting_location (e.g., "urban", "rural", "multiple")
- content_warnings: list any if applicable
{"- original_concept: " + json.dumps(original_concept) if original_concept else ""}
{"- core_unique_elements: " + json.dumps(unique_elements) if unique_elements else ""}

SECTION 2: CHARACTERS
Extract ALL major characters from the treatment with COMPLETE profiles.
Include AT MINIMUM: protagonist, main supporting character(s), antagonist.

For each character provide:
- name, role (protagonist/deuteragonist/antagonist/supporting)
- background: 2-3 paragraphs of history, formative experiences, context
- motivation: 1-2 paragraphs on what drives them, their goals
- character_arc: 3-4 sentences on how they change across acts
- personality_traits: 3-5 key traits
- internal_conflict: Their psychological struggle
- relationships: List of relationships with other characters

SECTION 3: WORLD
Extract ALL world-building elements from the treatment.

Provide:
- setting_overview: 2-3 paragraph description of the world
- key_locations: 4-8 important places with name, description, atmosphere, significance
- systems_and_rules: How the world works (magic systems, tech, social structures, etc.)
- social_context: Cultural, political, historical backdrop

RETURN FORMAT:
Return ONLY valid YAML (no markdown fences):

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
    personality_traits:
      - "..."
    internal_conflict: |
      ...
    relationships:
      - character: "..."
        dynamic: "..."
        evolution: "..."

world:
  setting_overview: |
    ...
  key_locations:
    - name: "..."
      description: "..."
      atmosphere: "..."
      significance: "..."
  systems_and_rules:
    - system: "..."
      description: |
        ...
  social_context:
    - "..."

IMPORTANT: Return ONLY these three sections. DO NOT include a 'chapters:' section.
Do NOT wrap in markdown code fences. Return ONLY the YAML content."""

        # Add feedback instruction if iterating
        if feedback:
            prompt += f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: When generating the metadata, you may adjust target_word_count AND chapter_count if the feedback suggests it (e.g., 'consolidate/tighten' → reduce both word count and chapter count, 'expand' → increase both)."

        # Generate foundation
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            stream=True,
            display=True,
            display_label="Generating foundation",
            min_response_tokens=2000
        )

        if not result:
            raise Exception("No response from API for foundation generation")

        response_text = result.get('content', result) if isinstance(result, dict) else result

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
            raise Exception(f"Foundation missing required sections: {', '.join(missing)}")

        # Make sure chapters section is NOT present
        if 'chapters' in foundation_data:
            if logger:
                logger.warning("Foundation included chapters section - removing it")
            del foundation_data['chapters']

        if logger:
            logger.debug(f"Foundation generated successfully")

        return foundation_data

    async def _generate_chapter_batch(
        self,
        context_yaml: str,
        foundation: Dict[str, Any],
        previous_summaries: List[Dict[str, str]],
        start_chapter: int,
        end_chapter: int,
        words_per_chapter: int,
        total_chapters: int,
        form: str,
        pacing: str,
        scenes_per_chapter: List[int],
        feedback: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate a batch of chapters with full context and act-aware word targets.

        Args:
            context_yaml: Full premise + treatment as YAML
            foundation: metadata + characters + world sections
            previous_summaries: Summaries of chapters generated so far
            start_chapter: First chapter number to generate (inclusive)
            end_chapter: Last chapter number to generate (inclusive)
            words_per_chapter: Average words per chapter (for display only)
            total_chapters: Total number of chapters in the complete book
            form: Story form (novella, novel, epic)
            pacing: Pacing taxonomy (fast, moderate, slow)
            scenes_per_chapter: List of scene counts for each chapter in batch

        Returns:
            List of chapter dicts
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        batch_size = end_chapter - start_chapter + 1

        if logger:
            logger.debug(f"Generating chapter batch: {start_chapter}-{end_chapter} ({batch_size} chapters)")

        # Serialize foundation to YAML
        foundation_yaml = yaml.dump(foundation, allow_unicode=True, default_flow_style=False)

        # Serialize previous summaries to YAML
        previous_yaml = ""
        if previous_summaries:
            previous_yaml = yaml.dump({'previous_chapters': previous_summaries}, allow_unicode=True, default_flow_style=False)

        # Determine act for these chapters
        # Simple heuristic: first 25% = Act I, middle 50% = Act II, last 25% = Act III
        act_1_end = total_chapters * 0.25
        act_2_end = total_chapters * 0.75

        if start_chapter <= act_1_end:
            default_act = "Act I"
        elif start_chapter <= act_2_end:
            default_act = "Act II"
        else:
            default_act = "Act III"

        # Build per-chapter scene and word specifications (act-aware)
        chapter_specs = []
        for i, ch_num in enumerate(range(start_chapter, end_chapter + 1)):
            scenes = scenes_per_chapter[i]
            # Calculate act-aware words per scene for this chapter
            act = DepthCalculator.get_act_for_chapter(ch_num, total_chapters)
            act_ws = DepthCalculator.get_act_words_per_scene(form, pacing, act)
            word_target = scenes * act_ws

            # Show which act for context
            act_display = act.replace('act', 'Act ')
            chapter_specs.append(f"Chapter {ch_num} ({act_display}): {scenes} scenes × {act_ws} w/s = {word_target:,} words")

        specs_text = '\n'.join(chapter_specs)

        prompt = f"""Generate chapters {start_chapter}-{end_chapter} for a book. This is part of multi-phase generation.

FULL STORY CONTEXT:
```yaml
{context_yaml}
```

FOUNDATION (metadata + characters + world):
```yaml
{foundation_yaml}
```

PREVIOUS CHAPTERS (summaries only):
```yaml
{previous_yaml if previous_yaml else "# No previous chapters - this is the first batch"}
```

STORY DEPTH ARCHITECTURE (ACT-AWARE):
This story varies depth by act position to create narrative rhythm.
Each chapter's word target is calculated using act-specific words-per-scene:

{specs_text}

Note: Act I (setup) uses slightly lower w/s for efficiency
      Act II (rising action) uses baseline w/s
      Act III (climax) uses HIGHER w/s for emotional depth

TASK:
Generate {batch_size} comprehensive chapter outlines, numbered {start_chapter} through {end_chapter}.

For each chapter, follow the EXACT specifications above:
- number: {start_chapter}, {start_chapter + 1}, ... {end_chapter} (CRITICAL: number sequentially from {start_chapter})
- title: evocative, specific
- pov: character name
- act: "{default_act}" (or adjust based on story flow)
- summary: 3-4 sentences
- scenes: MATCH THE SCENE COUNT specified above for this chapter
  * CRITICAL: Each scene is a COMPLETE DRAMATIC UNIT (1,000-2,000 words when written)
  * NOT bullet point summaries - these are FULL SCENES with structure:
    - scene: Brief scene title (2-4 words)
    - location: Where the scene takes place
    - pov_goal: What the POV character wants in this scene
    - conflict: What prevents them from getting it
    - stakes: What's at risk if they fail
    - outcome: How the scene resolves (success/failure/complication)
    - emotional_beat: Internal character change or realization
    - sensory_focus: 2-3 specific sensory details for atmosphere
    - target_words: Scene word target (use act-specific w/s from above)
  * Act III scenes need MORE depth (higher w/s) even though there are fewer of them
  * This structure signals to prose generation: write FULL dramatic scenes, not summaries
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements (chapter-level)
- subplot_threads: 1-2 if applicable
- word_count_target: USE THE EXACT TARGET from the spec above (already calculated with act-aware w/s)

Guidelines:
- Maintain consistency with the foundation (characters, world, metadata)
- Continue narrative flow from previous chapters
- Be specific with names, places, emotions
- Scene count varies by chapter position in three-act structure (2-4 scenes per chapter)
- Professional novels use 2-4 full scenes per chapter, NOT 6-10 bullet points

RETURN FORMAT:
Return ONLY a YAML list of chapters (no markdown fences):

- number: {start_chapter}
  title: "..."
  pov: "..."
  act: "{default_act}"
  summary: "..."
  scenes:  # {scenes_per_chapter[0]} scenes total for this chapter
    - scene: "Scene Title"
      location: "Specific place"
      pov_goal: "What character wants"
      conflict: "What prevents it"
      stakes: "What's at risk"
      outcome: "How it resolves"
      emotional_beat: "Internal change"
      sensory_focus:
        - "Sensory detail 1"
        - "Sensory detail 2"
      target_words: {act_ws}  # Act-specific target
    - scene: "Next Scene Title"
      location: "..."
      # ... (continue for all {scenes_per_chapter[0]} scenes)
  character_developments:
    - "..."
  relationship_beats:
    - "..."
  tension_points:
    - "..."
  sensory_details:
    - "..."
  subplot_threads:
    - "..."
  word_count_target: {DepthCalculator.get_act_words_per_scene(form, pacing, DepthCalculator.get_act_for_chapter(start_chapter, total_chapters)) * scenes_per_chapter[0]}  # USE EXACT VALUE FROM SPEC ABOVE

[Continue for all chapters {start_chapter} through {end_chapter}]

IMPORTANT: Use "scenes:" (with scene structure), NOT "key_events:" (old format).
Do NOT wrap in markdown code fences. Return ONLY the YAML list."""

        # Add feedback instruction if iterating
        if feedback:
            prompt += f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the above feedback when generating chapters. You may adjust chapter count, scene count, and word targets if the feedback suggests it (e.g., 'consolidate chapters' → fewer chapters with tighter scenes, 'expand' → more chapters/scenes)."

        # Generate batch
        min_tokens = batch_size * 700  # Estimate: 700 tokens per chapter

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            stream=True,
            display=True,
            display_label=f"Generating chapters {start_chapter}-{end_chapter}",
            min_response_tokens=min_tokens
        )

        if not result:
            raise Exception(f"No response from API for chapters {start_chapter}-{end_chapter}")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Parse YAML
        try:
            chapters_list = yaml.safe_load(response_text)
        except yaml.YAMLError as e:
            raise Exception(f"Failed to parse chapters batch YAML: {e}")

        # Validate structure
        if not isinstance(chapters_list, list):
            raise Exception(f"Batch response is not a list (got {type(chapters_list)})")

        # Validate chapter numbers
        for i, chapter in enumerate(chapters_list):
            expected_num = start_chapter + i
            actual_num = chapter.get('number')

            if actual_num != expected_num:
                raise Exception(
                    f"Chapter numbering error in batch: expected {expected_num}, got {actual_num}. "
                    f"Batch should contain chapters {start_chapter}-{end_chapter}."
                )

        # Validate we got the right number of chapters
        if len(chapters_list) != batch_size:
            raise Exception(
                f"Batch size mismatch: requested {batch_size} chapters ({start_chapter}-{end_chapter}), "
                f"but got {len(chapters_list)} chapters"
            )

        if logger:
            logger.debug(f"Batch {start_chapter}-{end_chapter} generated successfully: {len(chapters_list)} chapters")

        return chapters_list

    async def _resume_generation(
        self,
        partial_yaml: str,
        last_complete_chapter: int,
        total_chapters: int,
        context_yaml: str,
        total_words: int
    ) -> str:
        """
        Resume chapter generation from truncation point.

        Args:
            partial_yaml: The partial YAML that was generated before truncation
            last_complete_chapter: Number of last complete chapter (e.g., 5 means we have ch 1-5)
            total_chapters: Total number of chapters needed
            context_yaml: Original context (premise + treatment)
            total_words: Target total word count

        Returns:
            YAML string with ONLY the missing chapters
        """
        remaining_chapters = total_chapters - last_complete_chapter

        if remaining_chapters <= 0:
            return ""  # Nothing to resume

        # Calculate word count for remaining chapters
        words_per_chapter = total_words // total_chapters
        remaining_words = words_per_chapter * remaining_chapters

        prompt = f"""RESUME CHAPTER GENERATION

You previously generated chapters 1-{last_complete_chapter} for a book, but the generation was interrupted.

ORIGINAL CONTEXT:
```yaml
{context_yaml}
```

PARTIAL GENERATION SO FAR:
```yaml
{partial_yaml}
```

TASK:
Continue the chapter generation from where it was interrupted.
Generate chapters {last_complete_chapter + 1}-{total_chapters} ({remaining_chapters} chapters total).

IMPORTANT REQUIREMENTS:
1. Maintain consistency with the chapters already generated
2. Continue the story arc naturally from chapter {last_complete_chapter}
3. Ensure the remaining chapters complete the full story
4. Use the same format and level of detail as the previous chapters

For each chapter ({last_complete_chapter + 1} through {total_chapters}):
- number, title (evocative, specific)
- pov, act, summary (3-4 sentences)
- scenes: 2-4 full dramatic scenes (MATCH FORMAT from previous chapters)
  * If previous chapters use "scenes:" with structure (scene/location/pov_goal/conflict/stakes/outcome/emotional_beat/sensory_focus/target_words), use that format
  * If previous chapters use "key_events:" (old format), use that for consistency
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
- word_count_target: ~{words_per_chapter} words each

RETURN FORMAT:
Return ONLY a YAML list of the missing chapters (no markdown fences, no other content):

- number: {last_complete_chapter + 1}
  title: "..."
  pov: "..."
  act: "..."
  summary: "..."
  scenes:  # Use scenes (new format) or key_events (old format) - match previous chapters
    - scene: "Scene Title"
      location: "..."
      pov_goal: "..."
      conflict: "..."
      stakes: "..."
      outcome: "..."
      emotional_beat: "..."
      sensory_focus:
        - "..."
      target_words: ...
  character_developments:
    - "..."
  relationship_beats:
    - "..."
  tension_points:
    - "..."
  sensory_details:
    - "..."
  subplot_threads:
    - "..."
  word_count_target: {words_per_chapter}

[Continue for all remaining chapters through chapter {total_chapters}]

Return ONLY the YAML list of chapters. Do NOT include any other text."""

        # Generate continuation
        from ..utils.logging import get_logger
        from ..utils.tokens import estimate_messages_tokens
        logger = get_logger()

        if logger:
            logger.debug(f"Resuming chapter generation: chapters {last_complete_chapter + 1}-{total_chapters}")

        # Get model capabilities
        model_obj = await self.client.get_model(self.model)
        if not model_obj:
            raise Exception(f"Failed to fetch model capabilities for {self.model}")

        max_output = model_obj.get_max_output_tokens()
        context_length = model_obj.context_length

        # Estimate tokens for resume request
        # Input: system message + prompt (includes partial_yaml + context_yaml)
        # Output: continuation chapters
        estimated_input_tokens = estimate_messages_tokens([
            {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
            {"role": "user", "content": prompt}
        ])

        tokens_per_chapter = 700
        estimated_output_tokens = remaining_chapters * tokens_per_chapter

        total_tokens_needed = estimated_input_tokens + estimated_output_tokens

        # Check if resume will fit in model's context
        if context_length and total_tokens_needed > context_length:
            raise Exception(
                f"Resume request too large for model context. "
                f"Need ~{total_tokens_needed:,} tokens (input: {estimated_input_tokens:,}, output: {estimated_output_tokens:,}), "
                f"but model context is {context_length:,} tokens. "
                f"The partial generation is too large to resume with this model."
            )

        # Estimate tokens needed for continuation output only
        min_tokens = estimated_output_tokens

        if max_output and max_output < min_tokens:
            min_tokens = int(max_output * 0.8)
            if logger:
                logger.warning(f"Resume output estimate ({estimated_output_tokens}) exceeds model capacity ({max_output}), using {min_tokens}")

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            stream=True,
            display=True,
            display_label=f"Resuming chapters {last_complete_chapter + 1}-{total_chapters}",
            min_response_tokens=min_tokens
        )

        if not result:
            raise Exception("No response from resume generation")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        if logger:
            logger.debug(f"Resume generated {len(response_text)} chars")

        return response_text

    def _merge_yaml(
        self,
        partial_data: Dict[str, Any],
        continuation_yaml: str,
        last_complete_chapter: int
    ) -> Dict[str, Any]:
        """
        Merge partial generation with continuation.

        Args:
            partial_data: Parsed partial YAML data (may have incomplete last chapter)
            continuation_yaml: YAML string with continuation chapters
            last_complete_chapter: Number of last complete chapter in partial

        Returns:
            Complete merged YAML data
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        # Parse continuation
        try:
            continuation_data = yaml.safe_load(continuation_yaml)
        except yaml.YAMLError as e:
            if logger:
                logger.error(f"Failed to parse continuation YAML: {e}")
            raise Exception(f"Failed to parse continuation YAML: {e}")

        # Ensure continuation is a list
        if not isinstance(continuation_data, list):
            if logger:
                logger.error(f"Continuation is not a list: {type(continuation_data)}")
            raise Exception("Continuation must be a list of chapters")

        # Validate continuation chapter numbers
        expected_start = last_complete_chapter + 1
        for i, chapter in enumerate(continuation_data):
            if not isinstance(chapter, dict):
                raise Exception(f"Continuation chapter {i} is not a dict")

            chapter_num = chapter.get('number')
            expected_num = expected_start + i

            if chapter_num != expected_num:
                if logger:
                    logger.error(f"Continuation chapter numbering error: expected {expected_num}, got {chapter_num}")
                raise Exception(
                    f"Continuation chapter numbering is wrong. "
                    f"Expected chapter {expected_num}, got {chapter_num}. "
                    f"Resume should start at chapter {expected_start}."
                )

        # Start with partial data
        merged = partial_data.copy()

        # If partial has chapters, truncate to only complete ones
        if 'chapters' in merged and isinstance(merged['chapters'], list):
            merged['chapters'] = merged['chapters'][:last_complete_chapter]
        else:
            merged['chapters'] = []

        # Append continuation chapters
        merged['chapters'].extend(continuation_data)

        if logger:
            logger.debug(f"Merged {last_complete_chapter} partial + {len(continuation_data)} continued = {len(merged['chapters'])} total chapters")

        # Final validation: check total count and sequential numbering
        final_chapters = merged.get('chapters', [])
        for i, chapter in enumerate(final_chapters):
            expected_num = i + 1
            actual_num = chapter.get('number')
            if actual_num != expected_num:
                if logger:
                    logger.error(f"Final chapter numbering error at index {i}: expected {expected_num}, got {actual_num}")
                raise Exception(f"Merged chapters have numbering gap: chapter {i+1} has number {actual_num}")

        return merged

    async def generate(
        self,
        chapter_count: Optional[int] = None,
        total_words: Optional[int] = None,
        template: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using multi-phase approach for reliability.

        **Multi-Phase Generation:**
        Phase 1: Foundation (metadata + characters + world) ~2,000 tokens, ~30-45s
        Phase 2: Chapter Batches (5-8 chapters per batch) ~3,500-5,600 tokens each, ~30-60s per batch
        Phase 3: Assembly (merge and validate)

        This approach:
        - Reduces network drop risk (short streams)
        - Saves progress incrementally
        - Enables inspection/iteration on partial results
        - Provides better error recovery

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count (auto-calculated if not provided)
            template: Optional custom template (currently unused in multi-phase)
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

            # Calculate story structure (form, chapters, scenes, base_ws)
            if not chapter_count:
                structure = self._calculate_structure(total_words, pacing, length_scope)
                chapter_count = structure['chapter_count']
                form = structure['form']
                base_ws = structure['base_ws']
                total_scenes = structure['total_scenes']

                # Distribute scenes across chapters based on act structure
                scenes_distribution = DepthCalculator.distribute_scenes_across_chapters(
                    total_scenes, chapter_count, form
                )

                if logger:
                    logger.debug(f"Story structure: {form}, {chapter_count} chapters, {total_scenes} scenes, {base_ws} w/s (baseline)")
                    logger.debug(f"Scene distribution: {scenes_distribution}")
            else:
                # User specified chapter count - use it but still calculate structure
                structure = self._calculate_structure(total_words, pacing, length_scope)
                form = structure['form']
                base_ws = structure['base_ws']
                total_scenes = structure['total_scenes']

                # Distribute scenes across user-specified chapter count
                scenes_distribution = DepthCalculator.distribute_scenes_across_chapters(
                    total_scenes, chapter_count, form
                )

                if logger:
                    logger.debug(f"Story structure (user-specified chapters): {form}, {chapter_count} chapters, {total_scenes} scenes, {base_ws} w/s (baseline)")

            # Display comprehensive story structure breakdown
            self.console.print(f"\n[bold cyan]Story Structure Breakdown:[/bold cyan]")
            self.console.print(f"  Form: [green]{form.replace('_', ' ').title()}[/green]")
            self.console.print(f"  Target: [green]{total_words:,}[/green] words")
            self.console.print(f"  Chapters: [green]{chapter_count}[/green]")
            self.console.print(f"  Total Scenes: [green]{total_scenes}[/green]")
            avg_scenes = total_scenes / chapter_count if chapter_count > 0 else 0
            self.console.print(f"  Scenes per Chapter: [green]{avg_scenes:.1f}[/green] avg (clamped to 2-4)")
            self.console.print(f"  Words per Scene: [green]{base_ws:,}[/green] (Act II baseline, varies by act)")

            # Calculate and display expected total
            expected_total = total_scenes * base_ws
            variance_pct = ((expected_total / total_words) - 1) * 100 if total_words > 0 else 0

            if feedback:
                # During iteration, LLM can adjust - show baseline with note
                self.console.print(f"  Baseline Output: [green]{expected_total:,}[/green] words ({variance_pct:+.1f}% from target)")
                self.console.print(f"  [yellow]Note: LLM may adjust word count/chapter count based on feedback[/yellow]")
            else:
                # During generation, show expected output
                self.console.print(f"  Expected Output: [green]{expected_total:,}[/green] words ({variance_pct:+.1f}% from target)")

            # Serialize context to YAML for prompts
            context_yaml = self.context_builder.to_yaml_string(context)

            # Extract original concept and unique elements from premise metadata
            premise_metadata = context.get('premise', {}).get('metadata', {})
            original_concept = premise_metadata.get('original_concept', '')
            unique_elements = premise_metadata.get('unique_elements', [])

            # Get model capabilities
            model_obj = await self.client.get_model(self.model)
            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {self.model}")

            # Calculate batch size based on model capacity
            batch_size = self._calculate_batch_size(chapter_count, model_obj)

            if logger:
                logger.debug(f"Batch size: {batch_size} chapters per batch")

            # ===== PHASE 1: GENERATE FOUNDATION =====
            self.console.print(f"\n[cyan][1/4] Generating foundation (metadata + characters + world)...[/cyan]")

            foundation = await self._generate_foundation(
                context_yaml=context_yaml,
                taxonomy_data=taxonomy_data,
                total_words=total_words,
                chapter_count=chapter_count,
                original_concept=original_concept,
                unique_elements=unique_elements,
                feedback=feedback
            )

            # Save foundation immediately
            self._save_partial(foundation, phase='foundation')
            self.console.print(f"[green]✓[/green] Foundation complete")

            # ===== EXTRACT LLM'S STRUCTURAL CHOICES (ITERATION ONLY) =====
            # During iteration, LLM may adjust word count and chapter count based on feedback
            if feedback:
                foundation_metadata = foundation.get('metadata', {})
                llm_word_count = foundation_metadata.get('target_word_count')
                llm_chapter_count = foundation_metadata.get('chapter_count')

                # Apply LLM's word count (if provided and different)
                if llm_word_count:
                    llm_word_count = int(llm_word_count)
                    if llm_word_count != total_words:
                        self.console.print(
                            f"[yellow]→ LLM adjusted word count:[/yellow] "
                            f"{total_words:,} → {llm_word_count:,} words"
                        )
                        total_words = llm_word_count
                        if logger:
                            logger.info(f"Iteration: LLM adjusted word count to {total_words}")

                # Apply LLM's chapter count (if provided, valid, and different)
                if llm_chapter_count:
                    llm_chapter_count = int(llm_chapter_count)
                    # Validate reasonable range (1-100 chapters)
                    if 1 <= llm_chapter_count <= 100:
                        if llm_chapter_count != chapter_count:
                            self.console.print(
                                f"[yellow]→ LLM adjusted chapter count:[/yellow] "
                                f"{chapter_count} → {llm_chapter_count} chapters"
                            )
                            chapter_count = llm_chapter_count
                            if logger:
                                logger.info(f"Iteration: LLM adjusted chapter count to {chapter_count}")
                    else:
                        if logger:
                            logger.warning(
                                f"Iteration: LLM provided invalid chapter_count {llm_chapter_count}, "
                                f"using calculated value {chapter_count}"
                            )

                # Recalculate structure with LLM's values (if any changed)
                if llm_word_count or llm_chapter_count:
                    structure = self._calculate_structure(total_words, pacing, length_scope)
                    form = structure['form']
                    base_ws = structure['base_ws']
                    total_scenes = structure['total_scenes']

                    # Redistribute scenes across LLM's chosen chapter count
                    scenes_distribution = DepthCalculator.distribute_scenes_across_chapters(
                        total_scenes, chapter_count, form
                    )

                    if logger:
                        logger.debug(
                            f"Recalculated structure with LLM values: {form}, {chapter_count} chapters, "
                            f"{total_scenes} scenes, {base_ws} w/s"
                        )
                        logger.debug(f"Recalculated scene distribution: {scenes_distribution}")

            # ===== PHASE 2: GENERATE CHAPTER BATCHES =====
            all_chapters = []
            words_per_chapter = total_words // chapter_count

            # Calculate batches
            batches = []
            current_chapter = 1
            while current_chapter <= chapter_count:
                batch_end = min(current_chapter + batch_size - 1, chapter_count)
                batches.append((current_chapter, batch_end))
                current_chapter = batch_end + 1

            total_phases = len(batches) + 2  # +2 for foundation and assembly

            for batch_num, (start_ch, end_ch) in enumerate(batches):
                phase_num = batch_num + 2
                self.console.print(f"\n[cyan][{phase_num}/{total_phases}] Generating chapters {start_ch}-{end_ch}...[/cyan]")

                # Create summaries of previous chapters for context
                previous_summaries = self._summarize_chapters(all_chapters)

                # Get scenes for this batch of chapters
                batch_scenes = scenes_distribution[start_ch-1:end_ch]  # 0-indexed to 1-indexed

                # Try batch generation with retry
                batch_chapters = None
                for attempt in range(2):  # Try twice
                    try:
                        batch_chapters = await self._generate_chapter_batch(
                            context_yaml=context_yaml,
                            foundation=foundation,
                            previous_summaries=previous_summaries,
                            start_chapter=start_ch,
                            end_chapter=end_ch,
                            words_per_chapter=words_per_chapter,
                            total_chapters=chapter_count,
                            form=form,
                            pacing=pacing,
                            scenes_per_chapter=batch_scenes,
                            feedback=feedback
                        )
                        break  # Success
                    except Exception as e:
                        if attempt == 0:
                            # First attempt failed, retry
                            self.console.print(f"[yellow]⚠️  Batch failed: {e}[/yellow]")
                            self.console.print(f"[cyan]Retrying batch {start_ch}-{end_ch}...[/cyan]")
                            if logger:
                                logger.warning(f"Batch {start_ch}-{end_ch} failed, retrying: {e}")
                        else:
                            # Second attempt also failed
                            raise Exception(
                                f"Batch {start_ch}-{end_ch} failed after 2 attempts: {e}. "
                                f"You can retry generation or reduce batch size."
                            )

                if not batch_chapters:
                    raise Exception(f"Failed to generate batch {start_ch}-{end_ch}")

                all_chapters.extend(batch_chapters)

                # Save progress after each batch
                progress_data = {
                    **foundation,
                    'chapters': all_chapters
                }
                self._save_partial(progress_data, phase=f'batch_{batch_num + 1}')

                self.console.print(f"[green]✓[/green] Batch {start_ch}-{end_ch} complete ({len(all_chapters)}/{chapter_count} chapters)")

            # ===== PHASE 3: ASSEMBLY AND VALIDATION =====
            self.console.print(f"\n[cyan][{total_phases}/{total_phases}] Assembling final result...[/cyan]")

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

            # Save final result
            self.project.save_chapters_yaml(final_data)

            if logger:
                logger.debug(f"Successfully generated {len(all_chapters)} chapters with full context")

            self.console.print(f"[green]✓[/green] Generation complete! {chapter_count} chapters saved to chapters.yaml")

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
        feedback: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using multi-model competition with unified context.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count (auto-calculated if not provided)
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)

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
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the above feedback while generating the chapters. You may adjust the target word count and chapter count if the feedback suggests it (e.g., 'consolidate' → fewer words/chapters, 'expand' → more words/chapters)."
            word_count_instruction = f"- target_word_count: {total_words} # Current target - adjust based on feedback if needed"
            word_count_distribution = f"- word_count_target: distribute words across chapters (adjust total if feedback requires it)"

        prompt = f"""Generate a comprehensive, self-contained chapter structure for a book.

INPUT CONTEXT:
```yaml
{context_yaml}
```

TASK:
Create a complete chapters.yaml file with 4 sections that contains ALL information needed for prose generation.
This file will be used STANDALONE - prose generation will NOT have access to premise or treatment.

SECTION 1: METADATA
Generate high-level story parameters based on the taxonomy and treatment:
- genre, subgenre (if applicable)
- tone (e.g., "dark, tense", "light, humorous")
- pacing (e.g., "fast", "moderate", "slow")
- themes: 2-4 core themes from the story
- story_structure (e.g., "three_act", "hero_journey")
- narrative_style (e.g., "third_person_limited", "first_person")
- target_audience (e.g., "adult", "young adult")
{word_count_instruction}
- setting_period (e.g., "contemporary", "historical", "future")
- setting_location (e.g., "urban", "rural", "multiple")
- content_warnings: list any if applicable

NOTE: Base this on the taxonomy provided, but YOU MAY ADAPT based on what the actual story requires.

SECTION 2: CHARACTERS
Extract ALL major characters from the treatment with COMPLETE profiles.
Include AT MINIMUM: protagonist, main supporting character(s), antagonist.

For each character provide:
- name, role (protagonist/deuteragonist/antagonist/supporting)
- background: 2-3 paragraphs of history, formative experiences, context
- motivation: 1-2 paragraphs on what drives them, their goals
- character_arc: 3-4 sentences on how they change across acts
- personality_traits: 3-5 key traits
- internal_conflict: Their psychological struggle
- relationships: List of relationships with other characters, including:
  * character name
  * dynamic description
  * evolution across story

CRITICAL: Ensure NO material character information from the treatment is missing.

SECTION 3: WORLD
Extract ALL world-building elements from the treatment.

Provide:
- setting_overview: 2-3 paragraph description of the world
- key_locations: 4-8 important places, each with:
  * name
  * description
  * atmosphere
  * significance to story
- systems_and_rules: How the world works (magic systems, tech, social structures, etc.)
- social_context: Cultural, political, historical backdrop

CRITICAL: Ensure NO material world-building from the treatment is missing.

SECTION 4: CHAPTERS
Generate {chapter_count} comprehensive chapter outlines.

For each chapter:
- number, title (evocative, specific)
- pov, act, summary (3-4 sentences)
- scenes: 2-4 full dramatic scenes with structure
  * CRITICAL: Each scene is a COMPLETE DRAMATIC UNIT (1,000-2,000 words when written)
  * NOT bullet point summaries - use full scene structure:
    - scene: Brief scene title (2-4 words)
    - location: Where the scene takes place
    - pov_goal: What the POV character wants in this scene
    - conflict: What prevents them from getting it
    - stakes: What's at risk if they fail
    - outcome: How the scene resolves
    - emotional_beat: Internal character change
    - sensory_focus: 2-3 specific sensory details
    - target_words: Scene word target (~1,300 words/scene for novels)
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
{word_count_distribution}

Guidelines:
- Each scene should be specific and complete with full structure
- Character developments show internal change
- Relationship beats track evolving dynamics
- Be specific with names, places, emotions
- Act I: ~25% chapters (setup)
- Act II: ~50% chapters (rising action)
- Act III: ~25% chapters (climax, resolution){feedback_instruction}

RETURN FORMAT:
Return ONLY valid YAML (no markdown fences):
```yaml
metadata:
  genre: "..."
  # ... all metadata fields

characters:
  - name: "..."
    role: "protagonist"
    # ... all character fields

world:
  setting_overview: |
    ...
  # ... all world fields

chapters:
  - number: 1
    title: "..."
    # ... all chapter fields
```

Do NOT wrap in markdown code fences.
Return ONLY the YAML content with metadata+characters+world+chapters sections."""

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
                    {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
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