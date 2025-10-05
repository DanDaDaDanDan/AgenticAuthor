"""Premise generation (LOD3) for AgenticAuthor."""

import json
from typing import Optional, Dict, Any
from pathlib import Path

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from .taxonomies import TaxonomyLoader, PremiseHistory


DEFAULT_PREMISE_TEMPLATE = """Generate a compelling fiction premise for the {{ genre }} genre.

{% if user_input %}
Build upon this concept: {{ user_input }}
{% endif %}

REQUIREMENTS:
1. 2-3 sentences that capture the core conflict
2. Clear protagonist and stakes
3. Unique hook that sets it apart
4. Should feel fresh and engaging

{% if taxonomy %}
GENRE ELEMENTS TO CONSIDER:
{{ taxonomy | tojson(indent=2) }}
{% endif %}

Return a JSON object with this structure:
{
    "premise": "The 2-3 sentence premise text",
    "protagonist": "Brief description of main character",
    "antagonist": "Brief description of opposing force",
    "stakes": "What the protagonist stands to gain/lose",
    "hook": "What makes this story unique",
    "themes": ["theme1", "theme2", "theme3"]
}"""


class PremiseGenerator:
    """Generator for story premises (LOD3)."""

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize premise generator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation (required)
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.project = project
        self.taxonomy_loader = TaxonomyLoader()
        self.model = model

    async def generate(
        self,
        user_input: Optional[str] = None,
        genre: Optional[str] = None,
        template: Optional[str] = None,
        premise_history: Optional[PremiseHistory] = None
    ) -> Dict[str, Any]:
        """
        Generate a story premise with taxonomy selections.

        Args:
            user_input: Optional user concept to build upon
            genre: Story genre (defaults to project genre)
            template: Optional custom template (uses default if not provided)
            premise_history: History tracker for avoiding repetition

        Returns:
            Dict containing premise, metadata, and taxonomy selections
        """
        # Use project genre if not specified
        if not genre and self.project.metadata:
            genre = self.project.metadata.genre
        if not genre:
            genre = "general"

        # Normalize and load taxonomy
        normalized_genre = self.taxonomy_loader.normalize_genre(genre)
        taxonomy = self.taxonomy_loader.load_merged_taxonomy(normalized_genre)
        category_options = self.taxonomy_loader.get_category_options(taxonomy)

        # Build enhanced prompt with taxonomy
        history_context = ""
        if premise_history:
            history_context = premise_history.format_for_prompt()

        guidance_context = ""
        if user_input and user_input.strip():
            guidance_context = f'USER GUIDANCE: "{user_input}"\nIncorporate this concept into the premise.\n\n'

        # Build category JSON example
        json_structure = "{\n"
        for i, category in enumerate(category_options.keys()):
            json_structure += f'    "{category}": ["selected values"]'
            if i < len(category_options) - 1:
                json_structure += ","
            json_structure += "\n"
        json_structure += "  }"

        prompt = f"""Generate a compelling fiction premise for the {genre} genre.

{guidance_context}{history_context}

AVAILABLE TAXONOMY OPTIONS:
{chr(10).join([f'{cat}: {", ".join(opts[:10])}{"..." if len(opts) > 10 else ""}'
               for cat, opts in category_options.items()])}

REQUIREMENTS:
1. Create a 2-3 sentence premise that captures the core conflict
2. Include clear protagonist and stakes
3. Select appropriate values from EACH category above
4. Ensure all selections work cohesively together
5. You may create custom values if needed for the story

Return JSON with this structure:
{{
  "premise": "Your 2-3 sentence premise",
  "protagonist": "Brief protagonist description",
  "antagonist": "Brief antagonist/conflict description",
  "stakes": "What the protagonist stands to gain/lose",
  "hook": "What makes this unique",
  "themes": ["theme1", "theme2", "theme3"],
  "selections": {json_structure}
}}"""

        # Generate with API
        try:
            # Get model from project or use default
            model = self.model
            if not model and self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            result = await self.client.json_completion(
                model=model,
                prompt=prompt,
                temperature=0.9,  # Higher temp for creativity
                display_field="premise",
                display_label="Generating premise",
                # No max_tokens - let it use full available context
                min_response_tokens=800  # Premises need substantial space
            )

            # Save to project
            if result and 'premise' in result:
                self.project.save_premise(result['premise'])

                # Save full metadata
                metadata_path = self.project.path / "premise_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(result, f, indent=2)

                # Git commit (if git manager available)
                # Note: Git integration would be handled by the CLI layer

            return result

        except Exception as e:
            raise Exception(f"Failed to generate premise: {e}")

    async def generate_taxonomy_only(self, treatment: str, genre: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate only taxonomy selections for an existing treatment.

        Args:
            treatment: The full treatment text
            genre: Genre for taxonomy loading

        Returns:
            Dict containing taxonomy selections
        """
        if not genre and self.project.metadata:
            genre = self.project.metadata.genre
        if not genre:
            genre = "general"

        # Load taxonomy
        normalized_genre = self.taxonomy_loader.normalize_genre(genre)
        taxonomy = self.taxonomy_loader.load_merged_taxonomy(normalized_genre)
        category_options = self.taxonomy_loader.get_category_options(taxonomy)

        prompt = f"""Analyze this story treatment and extract appropriate taxonomy parameters.

TREATMENT:
{treatment}

AVAILABLE TAXONOMY OPTIONS:
{chr(10).join([f'{cat}: {", ".join(opts[:10])}{"..." if len(opts) > 10 else ""}'
               for cat, opts in category_options.items()])}

TASK:
Based on the treatment above, select the most appropriate values from each category.
Choose values that best match the story's themes, tone, and style.

Return JSON with only the selections:
{{
  "selections": {{
    {chr(10).join([f'    "{cat}": ["selected values"]{"," if i < len(category_options) - 1 else ""}'
                   for i, cat in enumerate(category_options.keys())])}
  }}
}}"""

        try:
            # Get model from project or use default
            model = self.model
            if not model and self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            result = await self.client.json_completion(
                model=model,
                prompt=prompt,
                temperature=0.5,  # Lower temp for analysis
                display_field="selections",
                display_label="Analyzing taxonomy",
                # No max_tokens - let it use full available context
                min_response_tokens=500  # Taxonomy analysis needs moderate space
            )

            # Save metadata
            if result and 'selections' in result:
                metadata_path = self.project.path / "premise_metadata.json"

                # Load existing metadata if it exists
                existing_metadata = {}
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        existing_metadata = json.load(f)

                # Merge with new selections
                existing_metadata['selections'] = result['selections']
                existing_metadata['genre'] = genre
                existing_metadata['treatment_analyzed'] = True

                with open(metadata_path, 'w') as f:
                    json.dump(existing_metadata, f, indent=2)

                # Git commit (if git manager available)
                # Note: Git integration would be handled by the CLI layer

            return result

        except Exception as e:
            raise Exception(f"Failed to generate taxonomy selections: {e}")

    async def iterate(self, feedback: str) -> Dict[str, Any]:
        """
        Iterate on existing premise with feedback.

        Args:
            feedback: Natural language feedback

        Returns:
            Updated premise dict
        """
        # Load current premise
        current_premise = self.project.get_premise()
        if not current_premise:
            raise Exception("No premise found to iterate on")

        # Load metadata if exists
        metadata_path = self.project.path / "premise_metadata.json"
        current_metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                current_metadata = json.load(f)

        # Create iteration prompt
        prompt = f"""Current premise:
{current_premise}

Current metadata:
{json.dumps(current_metadata, indent=2)}

User feedback: {feedback}

Please revise the premise based on this feedback. Maintain the same JSON structure as before:
{{
    "premise": "The revised 2-3 sentence premise",
    "protagonist": "Updated protagonist description",
    "antagonist": "Updated antagonist description",
    "stakes": "Updated stakes",
    "hook": "Updated unique hook",
    "themes": ["theme1", "theme2", "theme3"]
}}"""

        # Generate revision
        # Get model from project or use default
        model = self.model
        if not model and self.project.metadata and self.project.metadata.model:
            model = self.project.metadata.model
        if not model:
            from ..config import get_settings
            settings = get_settings()
            model = settings.active_model

        result = await self.client.json_completion(
            model=model,
            prompt=prompt,
            temperature=0.5,  # Lower temp for controlled iteration
            display_field="premise",
            display_label="Revising premise",
            # No max_tokens - let it use full available context
            min_response_tokens=800  # Premises need substantial space
        )

        # Save updated premise
        if result and 'premise' in result:
            self.project.save_premise(result['premise'])

            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump(result, f, indent=2)

            # Git commit (if git manager available)
            # Note: Git integration would be handled by the CLI layer

        return result