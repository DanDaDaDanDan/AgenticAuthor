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

CRITICAL REQUIREMENTS:
1. You MUST return ALL THREE sections: metadata, characters, AND world
2. The 'world:' section is REQUIRED - do not omit it
3. DO NOT include a 'chapters:' section
4. Do NOT wrap in markdown code fences
5. Return ONLY valid YAML content

If you omit any of the three required sections (metadata, characters, world), the response will be rejected."""

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
        feedback: Optional[str] = None
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
            feedback: Optional user feedback (for iteration)

        Returns:
            Dict with chapter data (number, title, pov, act, summary, scenes, etc.)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.debug(f"Generating chapter {chapter_num} with {len(previous_chapters)} previous chapters")

        # Calculate act and scene count for this chapter
        act = DepthCalculator.get_act_for_chapter(chapter_num, total_chapters)
        act_ws = DepthCalculator.get_act_words_per_scene(form, pacing, act)

        # Get scene count for this chapter
        structure = self._calculate_structure(
            total_words=foundation['metadata']['target_word_count'],
            pacing=pacing
        )
        scenes_per_chapter = structure['scenes_per_chapter']
        chapter_index = chapter_num - 1
        scene_count = scenes_per_chapter[chapter_index] if chapter_index < len(scenes_per_chapter) else 3

        word_target = scene_count * act_ws

        # Determine default act label
        act_1_end = total_chapters * 0.25
        act_2_end = total_chapters * 0.75
        if chapter_num <= act_1_end:
            default_act = "Act I"
        elif chapter_num <= act_2_end:
            default_act = "Act II"
        else:
            default_act = "Act III"

        # Serialize foundation to YAML
        foundation_yaml = yaml.dump(foundation, default_flow_style=False, allow_unicode=True)

        # Serialize previous chapters to YAML (FULL detail, not summaries)
        previous_yaml = ""
        if previous_chapters:
            previous_yaml = yaml.dump(previous_chapters, default_flow_style=False, allow_unicode=True)

        # Build prompt
        prompt = f"""Generate chapter {chapter_num} of {total_chapters} for a book.

FULL STORY CONTEXT:
```yaml
{context_yaml}
```

FOUNDATION (metadata + characters + world):
```yaml
{foundation_yaml}
```

PREVIOUS CHAPTERS (full details with all scenes):
```yaml
{previous_yaml if previous_yaml else "# This is chapter 1 - no previous chapters"}
```

STORY DEPTH ARCHITECTURE:
This is chapter {chapter_num} in {act} ({default_act}).
- Scene count: {scene_count} scenes
- Words per scene: {act_ws} w/s
- Target word count: {word_target:,} words

TASK:
Generate chapter {chapter_num} with the EXACT specifications:
- number: {chapter_num}
- title: evocative, specific (2-6 words)
- pov: character name
- act: "{default_act}" (or adjust based on story flow)
- summary: 3-4 sentences describing this chapter
- scenes: {scene_count} complete scenes with structure:
  * scene: Brief scene title (2-4 words)
  * location: Where the scene takes place
  * pov_goal: What the POV character wants in this scene
  * conflict: What prevents them from getting it
  * stakes: What's at risk if they fail
  * outcome: How the scene resolves
  * emotional_beat: Internal character change
  * sensory_focus: 2-3 specific sensory details
  * target_words: {act_ws}
- character_developments: 3-4 internal changes
- relationship_beats: 2-3 relationship evolutions
- tension_points: 2-3 stakes/urgency moments
- sensory_details: 2-3 atmospheric elements
- subplot_threads: 1-2 if applicable
- word_count_target: {word_target}

Guidelines:
- Maintain consistency with foundation (characters, world, metadata)
- Continue narrative flow from previous chapters
- Review previous chapters' scenes CAREFULLY to avoid duplication
- Each scene must advance the story with NEW events and conflicts
- Do NOT repeat plot beats, events, or character moments already covered
- Be specific with names, places, emotions
- {scene_count} scenes = {scene_count} complete dramatic units (not bullet points)

RETURN FORMAT:
Return ONLY valid YAML for this ONE chapter (no markdown fences):

number: {chapter_num}
title: "..."
pov: "..."
act: "{default_act}"
summary: "..."
scenes:
  - scene: "Scene Title"
    location: "..."
    pov_goal: "..."
    conflict: "..."
    stakes: "..."
    outcome: "..."
    emotional_beat: "..."
    sensory_focus:
      - "..."
      - "..."
    target_words: {act_ws}
  # ... continue for all {scene_count} scenes
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
word_count_target: {word_target}

IMPORTANT: Return ONLY the YAML for chapter {chapter_num}. Do NOT wrap in markdown code fences."""

        # Add feedback instruction if iterating
        if feedback:
            prompt += f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the feedback when generating this chapter. You may adjust scene count, word targets, or content based on the feedback."

        # Generate chapter
        min_tokens = 700  # Estimate: 700 tokens per chapter

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            stream=True,
            display=True,
            min_response_tokens=min_tokens
        )

        if not result:
            raise Exception(f"No response from API for chapter {chapter_num}")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Parse YAML
        try:
            chapter_data = yaml.safe_load(response_text)
        except yaml.YAMLError as e:
            raise Exception(f"Failed to parse chapter {chapter_num} YAML: {e}")

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

        if logger:
            logger.debug(f"Chapter {chapter_num} generated successfully: {len(chapter_data.get('scenes', []))} scenes")

        return chapter_data

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
                self.console.print(f"\n[bold yellow]📝 Iteration Mode:[/bold yellow] LLM will analyze feedback and may adjust:")
                self.console.print(f"   • Word count (currently {total_words:,})")
                self.console.print(f"   • Chapter count (currently {chapter_count})")
                self.console.print(f"   Changes will be shown after foundation generation")
            else:
                # During generation, show expected output
                self.console.print(f"  Expected Output: [green]{expected_total:,}[/green] words ({variance_pct:+.1f}% from target)")

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
            # Check for existing foundation (skip generation on resume if no feedback)
            existing_foundation = self.project.get_foundation()

            if existing_foundation and not feedback:
                # Resume mode: use existing foundation
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

                        # Recalculate structure with foundation's values
                        structure = self._calculate_structure(total_words, pacing, length_scope)
                        form = structure['form']
                        base_ws = structure['base_ws']
                        total_scenes = structure['total_scenes']

                        # Redistribute scenes across foundation's chapter count
                        scenes_distribution = DepthCalculator.distribute_scenes_across_chapters(
                            total_scenes, chapter_count, form
                        )
            else:
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
                        feedback=feedback
                    )
                except Exception as e:
                    # Save error context for debugging
                    if logger:
                        logger.error(f"Chapter {chapter_num} generation failed: {e}")

                    self.console.print(f"[red]✗[/red] Failed to generate chapter {chapter_num}: {e}")
                    self.console.print(f"\n[yellow]Generation stopped at chapter {chapter_num}[/yellow]")
                    self.console.print(f"[dim]Completed chapters saved to chapter-beats/[/dim]")
                    self.console.print(f"[dim]You can resume by running /generate chapters again[/dim]")
                    raise Exception(f"Failed to generate chapter {chapter_num}: {e}")

                # Save chapter immediately (enables resume)
                self.project.save_chapter_beat(chapter_num, chapter_data)

                # Show progress
                self.console.print(f"[green]✓[/green] Chapter {chapter_num}/{chapter_count} complete")

                if logger:
                    logger.debug(f"Saved chapter {chapter_num} to chapter-beats/chapter-{chapter_num:02d}.yaml")

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

            # Save final result
            self.project.save_chapters_yaml(final_data)

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
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nIMPORTANT: Incorporate the above feedback while generating the chapters. You may adjust the target word count and chapter count if the feedback suggests it (e.g., 'consolidate' → fewer words/chapters, 'expand' → more words/chapters).\n\nCRITICAL - AVOID DUPLICATE EVENTS:\n- Review ALL existing chapters and scenes before creating new structure\n- Do NOT repeat plot beats, events, or character moments already covered\n- Each chapter must advance the story with UNIQUE events and conflicts\n- If feedback mentions 'duplicate' or 'repetitive', consolidate those events into single chapters"
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