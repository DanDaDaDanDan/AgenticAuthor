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


DEFAULT_CHAPTERS_TEMPLATE = """Based on this treatment:
{{ treatment }}

Generate detailed chapter outlines that break down the story into {{ chapter_count }} chapters.

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
11. Word count target (distribute {{ total_words }} words across chapters)
12. Act designation

Return as JSON array with this structure:
[
  {
    "number": 1,
    "title": "Specific Evocative Title",
    "pov": "Character Name",
    "act": "Act I",
    "summary": "3-4 sentences describing what happens, the emotional journey, and why it matters to the story.",
    "key_events": [
      "Opening hook/scene that draws reader in",
      "Inciting incident or triggering event",
      "First obstacle or complication",
      "Discovery or revelation moment",
      "Conflict escalation or confrontation",
      "Attempt that succeeds or fails",
      "New information that changes things",
      "Climactic moment of the scene",
      "Consequence or transition to next scene"
    ],
    "character_developments": [
      "Internal conflict or desire revealed",
      "Key realization or decision point",
      "Emotional shift or growth moment",
      "Change in beliefs or perspective"
    ],
    "relationship_beats": [
      "How protagonist relates to another character",
      "Shift in power dynamic or trust",
      "Bond strengthened or tested"
    ],
    "tension_points": [
      "What deadline or threat looms",
      "Stakes raised or consequences revealed"
    ],
    "sensory_details": [
      "Key visual or atmospheric element",
      "Sound, smell, or texture that matters"
    ],
    "subplot_threads": ["Secondary storyline progression"],
    "word_count_target": 3000
  },
  ...
]

Guidelines for rich outlines:
- Each key_event should be a complete story beat, not just "Clara talks to Amos"
- Character developments show internal change, not just actions
- Relationship beats track evolving dynamics between specific characters
- Tension points identify what creates urgency or raises stakes
- Sensory details ground the reader in the scene
- Be specific: names, places, emotions, not generic descriptions

Pacing structure:
- Act I: ~25% of chapters (setup, inciting incident, establishing stakes)
- Act II: ~50% of chapters (rising action, complications, midpoint shift)
- Act III: ~25% of chapters (climax, resolution, denouement)
- Each chapter ends with momentum (cliffhanger, revelation, or decision)
- Vary chapter lengths between 2500-4000 words for rhythm"""


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

        # Build unified prompt
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

            # Parse and save to files (includes culling downstream)
            parse_result = self.parser.parse_and_save(
                response=response_text,
                project=self.project,
                target_lod='chapters',
                original_context=context
            )

            if logger:
                logger.debug(f"Parse result: updated_files={parse_result['updated_files']}, deleted_files={parse_result['deleted_files']}")

            # Load the saved chapters and return as ChapterOutline objects
            chapters_data = self.project.get_chapters()
            if not chapters_data:
                raise Exception("No chapters found after generation")

            chapters = []
            for chapter_dict in chapters_data:
                chapter = ChapterOutline.from_api_response(chapter_dict)
                chapters.append(chapter)

            if logger:
                logger.debug(f"Successfully generated {len(chapters)} chapters")

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