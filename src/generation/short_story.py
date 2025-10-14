"""Short-form story generation for AgenticAuthor.

For stories with ≤2 chapters (flash fiction, short stories), generates
complete prose in a single file (story.md) without chapters.yaml overhead.
"""

import json
from typing import Optional
from pathlib import Path

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from ..config import get_settings


SHORT_STORY_TEMPLATE = """You are writing a complete short-form story based on the following:

## Premise:
{{ premise }}

{% if premise_metadata %}
## Story Parameters:
- Genre: {{ premise_metadata.get('genre', 'N/A') }}
- Target Length: {{ target_words }} words
- Themes: {{ premise_metadata.get('themes', []) | join(', ') }}
{% if premise_metadata.get('protagonist') %}
- Protagonist: {{ premise_metadata.get('protagonist') }}
{% endif %}
{% if premise_metadata.get('antagonist') %}
- Antagonist: {{ premise_metadata.get('antagonist') }}
{% endif %}
{% if premise_metadata.get('stakes') %}
- Stakes: {{ premise_metadata.get('stakes') }}
{% endif %}
{% endif %}

## Treatment (Story Outline):
{{ treatment }}

## Task:
Write a complete {{ story_type }} (~{{ target_words }} words) that:

1. **Unity of Effect**: Every sentence serves the core story. Short stories demand tight focus.
2. **Single-Sitting Experience**: Readers should be able to read this in one sitting (15-30 minutes).
3. **Opening Hook**: Start close to the action. No long exposition.
4. **Complete Arc**: Setup → Conflict → Resolution. All three must be present and satisfying.
5. **Character Focus**: Deep dive into protagonist's perspective rather than broad world-building.
6. **Impactful Ending**: Short stories live or die by their endings. Make it memorable.
7. **Precise Language**: Every word counts. No filler, no meandering.
8. **Atmospheric**: Use sensory details to create strong mood and setting quickly.

**Important:**
- This is a COMPLETE story, not a chapter. Give it a satisfying ending.
- Target approximately {{ target_words }} words (can vary by ±20% if story demands it).
- Focus on depth over breadth - explore emotions and character deeply.
- The treatment provides structure, but you can adjust pacing as needed.
- Use scene breaks (marked with ***) if jumping time/location, but sparingly.

Begin the story now:"""


class ShortStoryGenerator:
    """Generator for short-form stories (flash fiction, short stories)."""

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize short story generator.

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

    async def generate(
        self,
        narrative_style: str = "third_person_limited",
        template: Optional[str] = None
    ) -> str:
        """
        Generate complete short-form story from premise and treatment.

        Args:
            narrative_style: Narrative voice/style (not heavily used for short stories)
            template: Optional custom template

        Returns:
            Complete story prose

        Raises:
            Exception: If premise or treatment is missing, or generation fails
        """
        # Check prerequisites
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first with /generate premise")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first with /generate treatment")

        # Load premise metadata (for genre, themes, etc.)
        premise_metadata = {}
        if self.project.premise_metadata_file.exists():
            with open(self.project.premise_metadata_file) as f:
                premise_metadata = json.load(f)

        # Get target word count from taxonomy/stored value
        target_words = self.project.get_target_words()
        if not target_words:
            # Fallback: use default for short story form
            from .depth_calculator import DepthCalculator
            target_words = DepthCalculator.get_default_word_count('short_story', 'general')

        # Determine story type label
        if target_words < 1500:
            story_type = "flash fiction"
        elif target_words < 7500:
            story_type = "short story"
        else:
            story_type = "novelette"

        # Build prompt
        template_obj = Template(template or SHORT_STORY_TEMPLATE)
        prompt = template_obj.render(
            premise=premise,
            premise_metadata=premise_metadata,
            treatment=treatment,
            target_words=target_words,
            story_type=story_type
        )

        # Generate story
        print(f"\n{'='*60}")
        print(f"Generating {story_type} (~{target_words:,} words)")
        print(f"Model: {self.model}")
        print(f"{'='*60}\n")

        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a masterful short story writer, skilled at crafting complete, impactful narratives in {target_words} words or less. You understand the importance of unity of effect, precise language, and memorable endings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Higher creativity for prose
                stream=True,
                display=True,
                display_mode="silent",  # Show stats after completion
                display_label=f"Writing {story_type}"
            )

            if not result:
                raise Exception("LLM returned no response")

            # Extract prose
            story_prose = result.get('content', result) if isinstance(result, dict) else result

            # Save to story.md
            self.project.save_story(story_prose)

            # Update metadata
            if self.project.metadata:
                self.project.metadata.story_type = 'short_form'
                self.project.save_metadata()

            # Display summary
            word_count = len(story_prose.split())
            print(f"\n✅ {story_type.title()} generated successfully")
            print(f"   Word count: {word_count:,} words")
            print(f"   Saved to: story.md")
            print(f"   Target: {target_words:,} words ({word_count / target_words * 100:.1f}% of target)")

            return story_prose

        except Exception as e:
            raise Exception(f"Failed to generate short story: {e}")
