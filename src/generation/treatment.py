"""Treatment generation (LOD2) for AgenticAuthor."""

from typing import Optional, Dict, Any
from pathlib import Path
import json
import yaml

from ..api import OpenRouterClient
from ..models import Project
from .lod_context import LODContextBuilder
from .cull import CullManager
from ..prompts import get_prompt_loader


DEFAULT_TREATMENT_TEMPLATE = """Based on this premise:
{{ premise }}

{% if premise_metadata %}
Additional context:
- Protagonist: {{ premise_metadata.protagonist }}
- Antagonist: {{ premise_metadata.antagonist }}
- Stakes: {{ premise_metadata.stakes }}
- Themes: {{ premise_metadata.themes | join(', ') }}
{% endif %}

Generate a detailed story treatment that:
1. Expands the world and characters
2. Outlines the three-act structure
3. Maintains the core premise essence
4. Target length: {{ target_words }} words

Include:
- Act I (25%): Setup, ordinary world, inciting incident
- Act II (50%): Rising action, midpoint turn, complications
- Act III (25%): Climax, resolution, denouement

Also include:
- Character arcs for main characters
- Key plot points and turning moments
- Thematic elements woven throughout
- World-building details relevant to the story

Format as flowing narrative prose, not bullet points."""


class TreatmentGenerator:
    """Generator for story treatments (LOD2)."""

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize treatment generator.

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
        self.context_builder = LODContextBuilder()
        self.prompt_loader = get_prompt_loader()

    async def generate(
        self,
        target_words: int = 2500,
        template: Optional[str] = None
    ) -> str:
        """
        Generate a story treatment from premise using unified LOD context.

        Args:
            target_words: Target word count for treatment
            template: Optional custom template

        Returns:
            Treatment text
        """
        # Build context (only premise for treatment generation)
        context = self.context_builder.build_context(
            project=self.project,
            context_level='premise',  # Only include premise as input context
            include_downstream=False
        )

        if 'premise' not in context:
            raise Exception("No premise found. Generate premise first with /generate premise")

        # Create unified prompt with markdown context
        context_markdown = self.context_builder.build_markdown_context(
            project=self.project,
            context_level='premise'
        )

        # Extract premise metadata for template if needed
        premise_metadata = context['premise'].get('metadata', {})

        # Extract original concept and unique elements if available
        original_concept = premise_metadata.get('original_concept', '')
        unique_elements = premise_metadata.get('unique_elements', [])

        # Build unique elements context
        unique_context = ""
        if original_concept or unique_elements:
            unique_context = "\n\nORIGINAL CONCEPT & UNIQUE ELEMENTS:\n"
            if original_concept:
                unique_context += f'Original Concept: "{original_concept}"\n'
                unique_context += "This reference should inform the scale, tone, and epic scope of the treatment.\n"
            if unique_elements:
                unique_context += f"Unique Elements: {', '.join(unique_elements)}\n"
                unique_context += "Ensure these elements are woven throughout and expanded upon in the treatment.\n"

        # Render treatment prompt from template
        prompts = self.prompt_loader.render(
            "generation/treatment_generation",
            context_markdown=context_markdown,
            unique_context=unique_context,
            target_words=target_words
        )

        # Generate with API
        try:
            # Use streaming_completion with dynamic token calculation
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompts['user']}
                ],
                temperature=0.7,  # Balanced for coherent narrative
                display=True,  # Show streaming progress
                display_label="Generating treatment",
                reserve_tokens=int(target_words * 1.3)
            )

            if result:
                # Extract content from response (plain markdown text)
                treatment_text = result.get('content', result) if isinstance(result, dict) else result

                # Strip markdown code fences if present (in case LLM ignored instructions)
                treatment_text = treatment_text.strip()
                if treatment_text.startswith('```markdown') or treatment_text.startswith('```md'):
                    # Remove opening fence with language
                    treatment_text = '\n'.join(treatment_text.split('\n')[1:])
                elif treatment_text.startswith('```'):
                    # Remove opening fence
                    treatment_text = treatment_text[3:]
                if treatment_text.endswith('```'):
                    # Remove closing fence
                    treatment_text = treatment_text[:-3]
                treatment_text = treatment_text.strip()

                # Validate we got some content
                if not treatment_text or len(treatment_text.split()) < 100:
                    raise ValueError(f"Treatment text too short ({len(treatment_text.split())} words). Expected ~{target_words} words.")

                # Save treatment directly (no YAML parsing needed)
                self.project.save_treatment(treatment_text)

                # Cull downstream content
                CullManager(self.project).cull_treatment()

                # Return treatment text directly
                return treatment_text

            return None

        except Exception as e:
            raise Exception(f"Failed to generate treatment: {e}")