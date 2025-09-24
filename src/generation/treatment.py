"""Treatment generation (LOD2) for AgenticAuthor."""

from typing import Optional, Dict, Any
from pathlib import Path
import json

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project


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

    def __init__(self, client: OpenRouterClient, project: Project):
        """
        Initialize treatment generator.

        Args:
            client: OpenRouter API client
            project: Current project
        """
        self.client = client
        self.project = project

    async def generate(
        self,
        target_words: int = 2500,
        template: Optional[str] = None
    ) -> str:
        """
        Generate a story treatment from premise.

        Args:
            target_words: Target word count for treatment
            template: Optional custom template

        Returns:
            Treatment text
        """
        # Load premise
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first with /generate premise")

        # Load premise metadata if exists
        premise_metadata = None
        metadata_path = self.project.path / "premise_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                premise_metadata = json.load(f)

        # Prepare template
        template_str = template or DEFAULT_TREATMENT_TEMPLATE
        jinja_template = Template(template_str)

        # Render prompt
        prompt = jinja_template.render(
            premise=premise,
            premise_metadata=premise_metadata,
            target_words=target_words
        )

        # Generate with API
        try:
            # Get model from project settings or default
            model = None
            if self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            # Use streaming_completion with dynamic token calculation
            result = await self.client.streaming_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Balanced for coherent narrative
                display=True,  # Show streaming progress
                # No max_tokens - let it use full available context
                # Estimate we need roughly 1.3 tokens per word for English prose
                min_response_tokens=int(target_words * 1.3)
            )

            if result:
                # Extract content from response
                content = result.get('content', result) if isinstance(result, dict) else result

                # Save treatment
                self.project.save_treatment(content)

                # Save metadata
                treatment_metadata = {
                    'word_count': len(content.split()),
                    'target_words': target_words,
                    'model': model
                }
                metadata_file = self.project.path / "treatment_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(treatment_metadata, f, indent=2)

                # Git commit handled by caller if needed

                return content

            return None

        except Exception as e:
            raise Exception(f"Failed to generate treatment: {e}")

    async def iterate(self, feedback: str) -> str:
        """
        Iterate on existing treatment with feedback.

        Args:
            feedback: Natural language feedback

        Returns:
            Updated treatment text
        """
        # Load current treatment
        current_treatment = self.project.get_treatment()
        if not current_treatment:
            raise Exception("No treatment found to iterate on")

        # Create iteration prompt
        prompt = f"""Current treatment:
{current_treatment}

User feedback: {feedback}

Please revise the treatment based on this feedback. Maintain the same overall structure and length.
Return the complete revised treatment as flowing narrative prose."""

        # Get current word count
        current_words = len(current_treatment.split())

        # Get model from project settings or default
        model = None
        if self.project.metadata and self.project.metadata.model:
            model = self.project.metadata.model
        if not model:
            from ..config import get_settings
            settings = get_settings()
            model = settings.active_model

        # Generate revision with dynamic token calculation
        result = await self.client.streaming_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # Lower temp for controlled iteration
            display=True,  # Show streaming progress
            # No max_tokens - let it use full available context
            # Estimate we need roughly same token count as current treatment
            min_response_tokens=int(current_words * 1.3)
        )

        if result:
            # Extract content from response
            content = result.get('content', result) if isinstance(result, dict) else result

            # Save updated treatment
            self.project.save_treatment(content)

            # Update metadata
            metadata_file = self.project.path / "treatment_metadata.json"
            treatment_metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    treatment_metadata = json.load(f)

            treatment_metadata['word_count'] = len(result.split())
            treatment_metadata['last_iteration'] = feedback[:100]

            with open(metadata_file, 'w') as f:
                json.dump(treatment_metadata, f, indent=2)

            # Git commit
            if self.project.git:
                self.project.git.add()
                self.project.git.commit(f"Iterate treatment: {feedback[:50]}")

        return result