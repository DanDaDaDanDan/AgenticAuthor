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
    """Generator for chapter outlines (LOD2)."""

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

    async def generate(
        self,
        chapter_count: Optional[int] = None,
        total_words: int = 50000,
        template: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines from treatment using unified LOD context.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            List of ChapterOutline objects
        """
        # Build context (premise + treatment for chapter generation)
        context = self.context_builder.build_context(
            project=self.project,
            target_lod='treatment',  # Include up to treatment
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

        # Get taxonomy from premise_metadata if available
        taxonomy_data = self.project.get_taxonomy() or {}

        # Build comprehensive self-contained chapters generation prompt
        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"\n\nUSER FEEDBACK: {feedback}\n\nPlease incorporate the above feedback while generating."

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

chapters:
  - number: 1
    title: "..."
    pov: "..."
    act: "Act I"
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
    word_count_target: 3000
```

Do NOT wrap in markdown code fences.
Return ONLY the YAML content."""

        # Generate with API
        try:
            # Get model from project settings or default
            from ..utils.logging import get_logger
            logger = get_logger()

            if logger:
                logger.debug(f"Starting chapter generation: model={self.model}, chapter_count={chapter_count}, total_words={total_words}")
                logger.debug(f"Context size: {len(context_yaml)} chars")
                logger.debug(f"Prompt length: {len(prompt)} chars")

            # Get model capabilities to determine appropriate token allocation
            min_tokens = 5000  # Default for rich outlines
            model_obj = await self.client.get_model(self.model)

            if logger:
                if model_obj:
                    logger.debug(f"Model fetched: {model_obj.id}, context={model_obj.context_length}, max_output={model_obj.get_max_output_tokens()}")
                else:
                    logger.error(f"Failed to fetch model object for {self.model}")

            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {self.model}")

            max_output = model_obj.get_max_output_tokens()

            # Adjust based on actual model capabilities
            if max_output and max_output < min_tokens:
                # Use 80% of available output capacity to avoid hitting limits
                min_tokens = int(max_output * 0.8)

                self.console.print(f"\n[yellow]⚠️  Model output capacity: {max_output} tokens[/yellow]")
                self.console.print(f"[dim]Adjusting generation to use {min_tokens} tokens[/dim]")
                self.console.print(f"[dim]Consider:[/dim]")
                self.console.print(f"[dim]  • Generating fewer chapters at once[/dim]")
                self.console.print(f"[dim]  • Using a model with higher output capacity[/dim]")

                # Suggest alternatives if output is very limited
                if max_output < 3000:
                    models_list = await self.client.discover_models()
                    alternative = models_list.select_by_requirements(
                        min_output_tokens=5000,
                        exclude_models=[self.model]
                    )
                    if alternative:
                        self.console.print(f"[dim]  • Try: {alternative.id} (supports {alternative.get_max_output_tokens() or 'unlimited'} tokens)[/dim]")
                self.console.print()

            if logger:
                logger.debug(f"Calling streaming_completion with min_response_tokens={min_tokens}")

            # Use streaming_completion with YAML response
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Slightly higher for more creative variety
                stream=True,
                display=True,
                display_label="Generating chapter outlines",
                min_response_tokens=min_tokens
            )

            if not result:
                raise Exception("No response from API")

            # Extract response text
            response_text = result.get('content', result) if isinstance(result, dict) else result

            if logger:
                logger.debug(f"Received response, length: {len(response_text)} chars")

            # Parse YAML response directly
            try:
                chapters_yaml_data = yaml.safe_load(response_text)
            except yaml.YAMLError as e:
                raise Exception(f"Failed to parse YAML response: {e}")

            # Validate structure
            if not isinstance(chapters_yaml_data, dict):
                raise Exception("Response is not a valid dict structure")

            required_sections = ['metadata', 'characters', 'world', 'chapters']
            missing = [s for s in required_sections if s not in chapters_yaml_data]
            if missing:
                raise Exception(f"Missing required sections: {', '.join(missing)}")

            # Save using new self-contained format
            self.project.save_chapters_yaml(chapters_yaml_data)

            if logger:
                chapters_list = chapters_yaml_data.get('chapters', [])
                logger.debug(f"Successfully generated {len(chapters_list)} chapters with full context")

            # Return chapter outlines for backward compatibility
            chapters = []
            for chapter_dict in chapters_yaml_data.get('chapters', []):
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
            target_lod='treatment',
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

        prompt = f"""Here is the current book content in YAML format:

```yaml
{context_yaml}
```

Generate {chapter_count} detailed chapter outlines based on the treatment above.

Target: {total_words} total words distributed across chapters

IMPORTANT: Create comprehensive, professional-quality outlines with 15-20 total beats per chapter.

For each chapter, provide:
1. Chapter number
2. Title (evocative, specific, not generic)
3. POV character (whose perspective we follow)
4. Summary (3-4 sentences capturing the essence)
5. Key events (8-10 specific plot beats showing what happens)
6. Character developments (3-4 internal changes/realizations)
7. Relationship beats (2-3 how relationships evolve)
8. Tension points (2-3 what raises stakes/urgency)
9. Sensory details (2-3 atmospheric/sensory elements)
10. Subplot threads (1-2 if applicable)
11. Word count target (distribute {total_words} words across chapters)
12. Act designation (Act I, Act II, or Act III)

Guidelines for rich outlines:
- Each key_event should be a complete story beat, not just "Clara talks to Amos"
- Character developments show internal change, not just actions
- Relationship beats track evolving dynamics between specific characters
- Tension points identify what creates urgency or raises stakes
- Be specific: names, places, emotions, not generic descriptions

Pacing structure:
- Act I: ~25% of chapters (setup, inciting incident, establishing stakes)
- Act II: ~50% of chapters (rising action, complications, midpoint shift)
- Act III: ~25% of chapters (climax, resolution, denouement)
- Each chapter ends with momentum (cliffhanger, revelation, or decision)
- Vary chapter lengths between 2500-4000 words for rhythm{feedback_instruction}

CRITICAL: Return your response as YAML with this structure:
```yaml
premise:
  text: |
    ... (keep existing premise unchanged)
  metadata:
    ... (keep existing metadata unchanged)

treatment:
  text: |
    ... (keep existing treatment unchanged)

chapters:
  - number: 1
    title: "Specific Evocative Title"
    pov: "Character Name"
    act: "Act I"
    summary: "3-4 sentences describing what happens..."
    key_events:
      - "Opening hook/scene that draws reader in"
      - "Inciting incident or triggering event"
      - ...
    character_developments:
      - "Internal conflict or desire revealed"
      - ...
    relationship_beats:
      - "How protagonist relates to another character"
      - ...
    tension_points:
      - "What deadline or threat looms"
      - ...
    sensory_details:
      - "Key visual or atmospheric element"
      - ...
    subplot_threads:
      - "Secondary storyline progression"
    word_count_target: 3000
  - number: 2
    # ... (continue for all {chapter_count} chapters)
```

Do NOT wrap your response in additional markdown code fences (```).
Return ONLY the YAML content with premise + treatment + chapters sections."""

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