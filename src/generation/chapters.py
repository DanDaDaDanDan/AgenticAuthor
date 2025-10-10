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
      * Rich outlines with 8-10 key_events, character developments,
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

    def _calculate_chapter_count(self, total_words: int) -> int:
        """Calculate recommended chapter count based on word count."""
        avg_chapter_length = 3000  # Typical chapter length
        return max(8, min(30, total_words // avg_chapter_length))

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
                    required_fields = ['number', 'title', 'summary', 'key_events', 'word_count_target']

                    if all(f in last_chapter for f in required_fields):
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
                                required_fields = ['number', 'title', 'summary', 'key_events', 'word_count_target']

                                if all(f in last_chapter for f in required_fields):
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
        chapter_count: int
    ) -> Dict[str, Any]:
        """
        Generate ONLY the foundation (metadata + characters + world), no chapters.

        Args:
            context_yaml: Full premise + treatment as YAML
            taxonomy_data: Taxonomy selections
            total_words: Target total word count
            chapter_count: Number of chapters (for metadata)

        Returns:
            Dict with metadata, characters, world sections
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.debug(f"Generating foundation (metadata + characters + world)")

        prompt = f"""Generate the FOUNDATION for a chapter structure. This is PART 1 of multi-phase generation.

INPUT CONTEXT:
```yaml
{context_yaml}
```

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
- target_word_count: {total_words}
- setting_period (e.g., "contemporary", "historical", "future")
- setting_location (e.g., "urban", "rural", "multiple")
- content_warnings: list any if applicable

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

metadata:
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
  setting_period: "..."
  setting_location: "..."
  content_warnings: []

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
        words_per_chapter: int
    ) -> List[Dict[str, Any]]:
        """
        Generate a batch of chapters with full context.

        Args:
            context_yaml: Full premise + treatment as YAML
            foundation: metadata + characters + world sections
            previous_summaries: Summaries of chapters generated so far
            start_chapter: First chapter number to generate (inclusive)
            end_chapter: Last chapter number to generate (inclusive)
            words_per_chapter: Target words per chapter

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
        total_chapters = end_chapter  # Assume we're generating all chapters eventually
        act_1_end = total_chapters * 0.25
        act_2_end = total_chapters * 0.75

        if start_chapter <= act_1_end:
            default_act = "Act I"
        elif start_chapter <= act_2_end:
            default_act = "Act II"
        else:
            default_act = "Act III"

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

TASK:
Generate {batch_size} comprehensive chapter outlines, numbered {start_chapter} through {end_chapter}.

For each chapter:
- number: {start_chapter}, {start_chapter + 1}, ... {end_chapter} (CRITICAL: number sequentially from {start_chapter})
- title: evocative, specific
- pov: character name
- act: "{default_act}" (or adjust based on story flow)
- summary: 3-4 sentences
- key_events: 8-10 specific plot beats
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
- word_count_target: ~{words_per_chapter} words

Guidelines:
- Maintain consistency with the foundation (characters, world, metadata)
- Continue narrative flow from previous chapters
- Each key_event should be specific and complete
- Be specific with names, places, emotions

RETURN FORMAT:
Return ONLY a YAML list of chapters (no markdown fences):

- number: {start_chapter}
  title: "..."
  pov: "..."
  act: "{default_act}"
  summary: "..."
  key_events:
    - "..."
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

[Continue for all chapters {start_chapter} through {end_chapter}]

Do NOT wrap in markdown code fences. Return ONLY the YAML list."""

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
- key_events: 8-10 specific plot beats
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
  key_events:
    - "..."
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
        total_words: int = 50000,
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
            total_words: Target total word count
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

            # Calculate chapter count if not provided
            if not chapter_count:
                chapter_count = self._calculate_chapter_count(total_words)

            if logger:
                logger.debug(f"Multi-phase generation: {chapter_count} chapters, {total_words} words")

            # Serialize context to YAML for prompts
            context_yaml = self.context_builder.to_yaml_string(context)

            # Get taxonomy
            taxonomy_data = self.project.get_taxonomy() or {}

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
                chapter_count=chapter_count
            )

            # Save foundation immediately
            self._save_partial(foundation, phase='foundation')
            self.console.print(f"[green]✓[/green] Foundation complete")

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
                            words_per_chapter=words_per_chapter
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
        total_words: int = 50000,
        template: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using multi-model competition with unified context.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            List of winning ChapterOutline objects
        """
        from .multi_model import MultiModelGenerator

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

        # Calculate chapter count if not provided
        if not chapter_count:
            chapter_count = self._calculate_chapter_count(total_words)

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build unified prompt (same as generate() method)
        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nPlease incorporate the above feedback while generating the chapters."

        # Use same prompt as normal generate() - self-contained format
        # Get taxonomy from premise_metadata if available
        taxonomy_data = self.project.get_taxonomy() or {}

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
- target_word_count: {total_words}
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
- key_events: 8-10 specific plot beats
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
- word_count_target: distribute {total_words} across chapters

Guidelines:
- Each key_event should be specific and complete
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