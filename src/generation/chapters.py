"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from typing import Optional, List, Dict, Any

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline
from rich.console import Console
from ..config import get_settings


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
        Generate chapter outlines from treatment.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            List of ChapterOutline objects
        """
        # Load treatment
        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first with /generate treatment")

        # Calculate chapter count if not provided
        if not chapter_count:
            chapter_count = self._calculate_chapter_count(total_words)

        # Load existing chapters if feedback is provided (iteration mode)
        existing_chapters_yaml = None
        if feedback:
            chapters_file = self.project.path / "chapters.yaml"
            if chapters_file.exists():
                with open(chapters_file, 'r') as f:
                    existing_chapters_data = yaml.safe_load(f)
                    existing_chapters_yaml = yaml.dump(existing_chapters_data, default_flow_style=False, sort_keys=False)

        # Prepare template
        template_str = template or DEFAULT_CHAPTERS_TEMPLATE
        jinja_template = Template(template_str)

        # Render prompt
        prompt = jinja_template.render(
            treatment=treatment,
            chapter_count=chapter_count,
            total_words=total_words
        )

        # Append existing chapters and feedback if provided (for iteration)
        if feedback:
            if existing_chapters_yaml:
                prompt = f"""Here are the current chapter outlines:

```yaml
{existing_chapters_yaml}
```

User feedback: {feedback}

Please modify the existing chapters based on the user's feedback. Preserve what works well and change what needs improvement. Return the updated chapters in the same JSON format as specified below.

{prompt}"""
            else:
                prompt += f"\n\nADDITIONAL USER GUIDANCE:\n{feedback}\n\nPlease incorporate the above feedback into the chapter outlines."

        # Generate with API
        try:
            # Get model from project settings or default
            from ..utils.logging import get_logger
            logger = get_logger()

            if logger:
                logger.debug(f"Starting chapter generation: model={self.model}, chapter_count={chapter_count}, total_words={total_words}")
                logger.debug(f"Treatment length: {len(treatment)} chars")
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

            if model_obj:
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
                            exclude_models=[model]
                        )
                        if alternative:
                            self.console.print(f"[dim]  • Try: {alternative.id} (supports {alternative.get_max_output_tokens() or 'unlimited'} tokens)[/dim]")
                    self.console.print()

            if logger:
                logger.debug(f"Calling json_completion with display_field='summary', display_mode='array_first', min_response_tokens={min_tokens}")

            result = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.7,  # Slightly higher for more creative variety
                display_field="summary",  # Display summaries as they complete
                display_label="Generating chapter outlines",
                display_mode="array_progressive",  # Show all chapter summaries as they complete
                # No max_tokens - let it use full available context
                min_response_tokens=min_tokens
            )

            if logger:
                logger.debug(f"json_completion returned: type={type(result)}, is_list={isinstance(result, list)}, length={len(result) if isinstance(result, list) else 'N/A'}")

            if result and isinstance(result, list):
                # Convert to ChapterOutline objects using robust from_api_response method
                chapters = []
                for chapter_data in result:
                    # Use the model's from_api_response method which handles missing/extra fields
                    chapter = ChapterOutline.from_api_response(chapter_data)
                    chapters.append(chapter)

                # Save to project
                chapters_file = self.project.path / "chapters.yaml"
                chapters_data = []
                for chapter in chapters:
                    # Use Pydantic's model_dump to get all fields, excluding None values
                    chapter_dict = chapter.model_dump(exclude_none=True)
                    chapters_data.append(chapter_dict)

                with open(chapters_file, 'w') as f:
                    yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False)

                # Git commit handled by caller if needed

                return chapters

            raise Exception("Invalid response format from API")

        except Exception as e:
            raise Exception(f"Failed to generate chapters: {e}")

    async def iterate_chapter(self, chapter_number: int, feedback: str) -> ChapterOutline:
        """
        Iterate on a specific chapter outline.

        Args:
            chapter_number: Chapter to iterate on
            feedback: Natural language feedback

        Returns:
            Updated ChapterOutline
        """
        # Load current chapters
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            raise Exception("No chapter outlines found. Generate chapters first with /generate chapters")

        with open(chapters_file, 'r') as f:
            chapters_data = yaml.safe_load(f)

        # Find the chapter
        chapter_data = None
        chapter_index = None
        for i, ch in enumerate(chapters_data):
            if ch['number'] == chapter_number:
                chapter_data = ch
                chapter_index = i
                break

        if not chapter_data:
            raise Exception(f"Chapter {chapter_number} not found")

        # Create iteration prompt
        prompt = f"""Current chapter outline:
{json.dumps(chapter_data, indent=2)}

User feedback: {feedback}

Please revise this chapter outline based on the feedback. Return the updated chapter in the same JSON format."""

        # Generate revision
        result = await self.client.json_completion(
            model=self.model,
            prompt=prompt,
            temperature=0.5,
            display_field="summary",  # Display the updated summary
            display_label=f"Revising chapter {chapter_number}",
            # No max_tokens - let it use full available context
            min_response_tokens=800  # Single chapter outline needs moderate space
        )

        if result:
            # Update the chapter
            chapters_data[chapter_index] = result

            # Save updated chapters
            with open(chapters_file, 'w') as f:
                yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False)

            # Return as ChapterOutline using robust from_api_response method
            return ChapterOutline.from_api_response(result)

        raise Exception("Failed to iterate chapter")

    async def generate_with_competition(
        self,
        chapter_count: Optional[int] = None,
        total_words: int = 50000,
        template: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines using multi-model competition.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count
            template: Optional custom template
            feedback: Optional user feedback to incorporate (for iteration)

        Returns:
            List of winning ChapterOutline objects
        """
        from .multi_model import MultiModelGenerator

        # Get context
        premise = self.project.get_premise()
        treatment = self.project.get_treatment()
        genre = self.project.metadata.genre if self.project.metadata else None

        # Calculate chapter count if needed
        if not chapter_count:
            chapter_count = self._calculate_chapter_count(total_words)

        # Create multi-model generator
        multi_gen = MultiModelGenerator(self.client, self.project)

        # Define generator function that takes model parameter
        async def generate_with_model(model: str) -> str:
            # Temporarily override self.model
            original_model = self.model
            self.model = model
            try:
                chapters = await self.generate(
                    chapter_count=chapter_count,
                    total_words=total_words,
                    template=template,
                    feedback=feedback
                )
                # Convert chapters to YAML for comparison
                chapters_data = []
                for chapter in chapters:
                    chapter_dict = chapter.model_dump(exclude_none=True)
                    chapters_data.append(chapter_dict)
                return yaml.dump(chapters_data, default_flow_style=False, sort_keys=False)
            finally:
                self.model = original_model

        # Run competition
        result = await multi_gen.generate_parallel(
            generator_func=generate_with_model,
            content_type="chapters",
            file_prefix="chapters",
            context={
                'premise': premise,
                'treatment': treatment,
                'genre': genre,
                'chapter_count': chapter_count,
                'total_words': total_words
            }
        )

        if not result:
            raise Exception("Multi-model competition failed or was cancelled")

        if result.get('fallback'):
            yaml_content = result['winner']['content']
        else:
            yaml_content = result['winner']['content']

        # Parse YAML back to chapter objects
        chapters_data = yaml.safe_load(yaml_content)
        chapters = []
        for chapter_data in chapters_data:
            chapter = ChapterOutline.from_api_response(chapter_data)
            chapters.append(chapter)

        # Save to project (the normal generate() already saved, but we need to save winner)
        chapters_file = self.project.path / "chapters.yaml"
        with open(chapters_file, 'w') as f:
            yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False)

        return chapters