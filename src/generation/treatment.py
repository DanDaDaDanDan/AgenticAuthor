"""Treatment generation (LOD2) for AgenticAuthor."""

from typing import Optional, Dict, Any
from pathlib import Path
import json

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from ..config import get_settings
from .lod_context import LODContextBuilder
from .lod_parser import LODResponseParser


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
        self.parser = LODResponseParser()

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
            target_lod='premise',  # Only include premise
            include_downstream=False
        )

        if 'premise' not in context:
            raise Exception("No premise found. Generate premise first with /generate premise")

        # Create unified prompt with YAML context
        context_yaml = self.context_builder.to_yaml_string(context)

        # Extract premise metadata for template if needed
        premise_metadata = context['premise'].get('metadata', {})

        # Build prompt
        prompt = f"""Here is the current book content for context:

```yaml
{context_yaml}
```

Generate a detailed treatment (LOD2) based on the premise above.

Target: {target_words} words

Guidelines:
1. Expand the world and characters
2. Outline the three-act structure clearly
3. Maintain the core premise essence
4. Act I (25%): Setup, ordinary world, inciting incident
5. Act II (50%): Rising action, midpoint turn, complications
6. Act III (25%): Climax, resolution, denouement

Include:
- Character arcs for main characters
- Key plot points and turning moments
- Thematic elements woven throughout
- World-building details relevant to the story

Format as flowing narrative prose, not bullet points.

CRITICAL: Return ONLY the treatment as YAML:
```yaml
treatment:
  text: |
    ### Your Treatment Title

    Your treatment narrative here (Act I, Act II, Act III)...

    Target ~{target_words} words of flowing prose.
```

Do NOT include premise, chapters, or prose sections.
Do NOT wrap in additional markdown code fences.
Return ONLY the treatment section."""

        # Generate with API
        try:
            # Use streaming_completion with dynamic token calculation
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Balanced for coherent narrative
                display=True,  # Show streaming progress
                display_label="Generating treatment",
                min_response_tokens=int(target_words * 1.3)
            )

            if result:
                # Extract content from response
                response_text = result.get('content', result) if isinstance(result, dict) else result

                # Parse and save to files (includes culling downstream)
                parse_result = self.parser.parse_and_save(
                    response=response_text,
                    project=self.project,
                    target_lod='treatment',
                    original_context=context
                )

                # Save metadata
                treatment_metadata = {
                    'word_count': len(self.project.get_treatment().split()),
                    'target_words': target_words,
                    'model': self.model,
                    'updated_files': parse_result['updated_files'],
                    'deleted_files': parse_result['deleted_files']
                }
                metadata_file = self.project.path / "treatment_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(treatment_metadata, f, indent=2)

                # Return treatment text for display
                return self.project.get_treatment()

            return None

        except Exception as e:
            raise Exception(f"Failed to generate treatment: {e}")

    async def generate_with_competition(
        self,
        target_words: int = 2500,
        template: Optional[str] = None
    ) -> str:
        """
        Generate treatment using multi-model competition with unified context.

        Args:
            target_words: Target word count for treatment
            template: Optional custom template

        Returns:
            Winning treatment text
        """
        from .multi_model import MultiModelGenerator

        # Build context (only premise for treatment generation)
        context = self.context_builder.build_context(
            project=self.project,
            target_lod='premise',
            include_downstream=False
        )

        if 'premise' not in context:
            raise Exception("No premise found. Generate premise first with /generate premise")

        premise_metadata = context['premise'].get('metadata', {})
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build prompt (same as generate() method)
        prompt = f"""Here is the current book content for context:

```yaml
{context_yaml}```

Generate a detailed treatment (LOD2) based on the premise above.

Target: {target_words} words

Guidelines:
1. Expand the world and characters
2. Outline the three-act structure clearly
3. Maintain the core premise essence
4. Act I (25%): Setup, ordinary world, inciting incident
5. Act II (50%): Rising action, midpoint turn, complications
6. Act III (25%): Climax, resolution, denouement

Include:
- Character arcs for main characters
- Key plot points and turning moments
- Thematic elements woven throughout
- World-building details relevant to the story

Format as flowing narrative prose, not bullet points.

CRITICAL: Return ONLY the treatment as YAML:
```yaml
treatment:
  text: |
    ### Your Treatment Title

    Your treatment narrative here (Act I, Act II, Act III)...

    Target ~{target_words} words of flowing prose.
```

Do NOT include premise, chapters, or prose sections.
Do NOT wrap in additional markdown code fences.
Return ONLY the treatment section."""

        # Create multi-model generator
        multi_gen = MultiModelGenerator(self.client, self.project)

        # Define generator function that takes model parameter
        async def generate_with_model(model: str) -> str:
            # Generate with this model using dry_run
            result = await self.client.streaming_completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                display=True,
                display_label=f"Generating treatment ({model})",
                min_response_tokens=int(target_words * 1.3)
            )

            if not result:
                raise Exception(f"No response from {model}")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Parse with dry_run to validate but not save
            parse_result = self.parser.parse_and_save(
                response=response_text,
                project=self.project,
                target_lod='treatment',
                original_context=context,
                dry_run=True
            )

            # Return the raw response for comparison
            return response_text

        # Run competition
        competition_result = await multi_gen.generate_parallel(
            generator_func=generate_with_model,
            content_type="treatment",
            file_prefix="treatment",
            context={
                'premise': context['premise']['text'],
                'genre': self.project.metadata.genre if self.project.metadata else None,
                'target_words': target_words
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
            target_lod='treatment',
            original_context=context,
            dry_run=False  # Actually save this time
        )

        # Save metadata
        treatment_metadata = {
            'word_count': len(self.project.get_treatment().split()),
            'target_words': target_words,
            'model': competition_result['winner']['model'],
            'updated_files': parse_result['updated_files'],
            'deleted_files': parse_result['deleted_files'],
            'multi_model': True
        }
        metadata_file = self.project.path / "treatment_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(treatment_metadata, f, indent=2)

        # Return treatment text
        return self.project.get_treatment()