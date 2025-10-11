"""Premise generation (LOD3) for AgenticAuthor."""

import json
from typing import Optional, Dict, Any, List
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

    async def iterate_taxonomy(
        self,
        current_taxonomy: Dict[str, Any],
        feedback: str,
        current_premise: str
    ) -> Dict[str, Any]:
        """
        Modify taxonomy selections based on natural language feedback.

        Args:
            current_taxonomy: Current taxonomy selections
            feedback: Natural language description of desired changes
            current_premise: Current premise text

        Returns:
            Updated taxonomy selections and optionally new premise
        """
        # Get genre from current taxonomy or project
        genre = self.project.metadata.genre if self.project.metadata else 'general'

        # Load full taxonomy to show available options
        full_taxonomy = self.taxonomy_loader.load_merged_taxonomy(genre)
        category_options = self.taxonomy_loader.get_category_options(full_taxonomy)

        prompt = f"""You are updating taxonomy selections for a story premise based on user feedback.

CURRENT PREMISE:
"{current_premise}"

CURRENT TAXONOMY SELECTIONS:
{json.dumps(current_taxonomy, indent=2)}

AVAILABLE OPTIONS BY CATEGORY:
{json.dumps(category_options, indent=2)}

USER FEEDBACK:
"{feedback}"

Based on the feedback, update the taxonomy selections. Keep unchanged categories as-is.

Return a JSON object with:
{{
    "updated_taxonomy": {{
        "category_name": ["selected", "values"],
        ...
    }},
    "changes_made": ["description of what changed"],
    "regenerate_premise": true/false,
    "reasoning": "why these changes were made"
}}

Set regenerate_premise to true if the changes are significant enough to warrant regenerating the premise."""

        try:
            result = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.4,
                display_label="Analyzing taxonomy changes"
            )

            if not result or not isinstance(result, dict):
                raise ValueError("Invalid response from model")

            return result

        except Exception as e:
            raise ValueError(f"Failed to iterate taxonomy: {str(e)}")

    async def regenerate_with_taxonomy(
        self,
        user_input: str,
        taxonomy_selections: Dict[str, Any],
        genre: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Regenerate premise using specific taxonomy selections.

        Args:
            user_input: Original concept/premise
            taxonomy_selections: Specific taxonomy selections to use
            genre: Genre (optional)

        Returns:
            Generated premise with taxonomy
        """
        # Use provided genre or project genre
        if not genre and self.project.metadata:
            genre = self.project.metadata.genre
        if not genre:
            genre = "general"

        # Load taxonomy
        normalized_genre = self.taxonomy_loader.normalize_genre(genre)
        taxonomy = self.taxonomy_loader.load_merged_taxonomy(normalized_genre)

        # Build prompt with enforced taxonomy
        prompt = f"""Generate a compelling fiction premise for the {genre} genre.

Build upon this concept: {user_input}

REQUIRED TAXONOMY SELECTIONS (must incorporate these elements):
{json.dumps(taxonomy_selections, indent=2)}

REQUIREMENTS:
1. 2-3 sentences that capture the core conflict
2. Clear protagonist and stakes
3. Unique hook that sets it apart
4. Must naturally incorporate the specified taxonomy elements
5. Should feel fresh and engaging

Return a JSON object with this structure:
{{
    "premise": "The 2-3 sentence premise text",
    "protagonist": "Brief description of main character",
    "antagonist": "Brief description of opposing force",
    "stakes": "What the protagonist stands to gain/lose",
    "hook": "What makes this story unique",
    "themes": ["theme1", "theme2", "theme3"]
}}"""

        try:
            result = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.7,
                display_label="Regenerating premise with updated taxonomy",
                min_response_tokens=500
            )

            if result and isinstance(result, dict):
                return {
                    'premise': result.get('premise', ''),
                    'metadata': result,
                    'taxonomy': taxonomy_selections
                }

            raise ValueError("Invalid response format")

        except Exception as e:
            raise ValueError(f"Failed to regenerate premise: {str(e)}")

    async def detect_genre(self, concept: str) -> str:
        """
        Detect the most appropriate genre for a given concept.

        Args:
            concept: User's story concept

        Returns:
            Detected genre name
        """
        available_genres = list(self.taxonomy_loader.GENRES.keys())

        prompt = f"""Analyze this story concept and determine the most appropriate genre.

CONCEPT: "{concept}"

AVAILABLE GENRES:
{', '.join(available_genres)}

Return ONLY a JSON object with this structure:
{{
    "genre": "detected_genre_name",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this genre fits"
}}

Choose the single best-fitting genre from the available list. If the concept could fit multiple genres, pick the primary one."""

        try:
            result = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.3,  # Low temperature for consistent detection
                display_label="Detecting genre"
            )

            if result and isinstance(result, dict):
                detected = result.get('genre', 'general')
                # Validate it's a known genre
                normalized = self.taxonomy_loader.normalize_genre(detected)
                return normalized

            return 'general'

        except Exception:
            # Fallback to general on any error
            return 'general'

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
6. Identify 3-5 unique elements that make this story distinctive

Return JSON with this structure:
{{
  "premise": "Your 2-3 sentence premise",
  "protagonist": "Brief protagonist description",
  "antagonist": "Brief antagonist/conflict description",
  "stakes": "What the protagonist stands to gain/lose",
  "hook": "What makes this unique",
  "themes": ["theme1", "theme2", "theme3"],
  "unique_elements": ["element1", "element2", "element3"],
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
                # Add original concept to metadata if user_input was provided
                if user_input:
                    result['original_concept'] = user_input

                self.project.save_premise_metadata(result)

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

Current metadata (including taxonomy selections):
{json.dumps(current_metadata, indent=2)}

User feedback: {feedback}

Please revise the premise based on this feedback. Return the complete JSON structure including all existing fields:
{{
    "premise": "The revised 2-3 sentence premise",
    "protagonist": "Updated protagonist description",
    "antagonist": "Updated antagonist description",
    "stakes": "Updated stakes",
    "hook": "Updated unique hook",
    "themes": ["theme1", "theme2", "theme3"],
    "selections": {{
        // Keep existing taxonomy selections unless feedback specifically asks to change them
        // Include all categories from current metadata
    }}
}}

IMPORTANT: Preserve the existing "selections" taxonomy data unless the feedback specifically requests changes to story parameters."""

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
            min_response_tokens=1200  # Premises + full taxonomy selections need substantial space
        )

        # Save updated premise
        if result and 'premise' in result:
            self.project.save_premise_metadata(result)

            # Git commit (if git manager available)
            # Note: Git integration would be handled by the CLI layer

        return result

    async def generate_batch(
        self,
        count: int,
        user_input: Optional[str] = None,
        genre: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple premise options in a single API call.

        Args:
            count: Number of premises to generate (1-10)
            user_input: Optional user concept to build upon
            genre: Story genre (defaults to project genre)

        Returns:
            List of premise dicts, each containing premise, metadata, and taxonomy selections
        """
        # Validate count
        if count < 1:
            raise ValueError("Count must be at least 1")
        if count > 30:
            raise ValueError("Count cannot exceed 30 (to stay within output token limits)")

        # Use project genre if not specified
        if not genre and self.project.metadata:
            genre = self.project.metadata.genre
        if not genre:
            genre = "general"

        # Normalize and load taxonomy
        normalized_genre = self.taxonomy_loader.normalize_genre(genre)
        taxonomy = self.taxonomy_loader.load_merged_taxonomy(normalized_genre)
        category_options = self.taxonomy_loader.get_category_options(taxonomy)

        # Build guidance context
        guidance_context = ""
        if user_input and user_input.strip():
            guidance_context = f'USER GUIDANCE: "{user_input}"\nIncorporate this concept into each premise.\n\n'

        # Build category JSON example
        json_structure = "{\n"
        for i, category in enumerate(category_options.keys()):
            json_structure += f'    "{category}": ["selected values"]'
            if i < len(category_options) - 1:
                json_structure += ","
            json_structure += "\n"
        json_structure += "  }"

        # Build taxonomy options display
        taxonomy_display = "\n".join([
            f'{cat}: {", ".join(opts[:10])}{"..." if len(opts) > 10 else ""}'
            for cat, opts in category_options.items()
        ])

        prompt = f"""Generate {count} diverse, compelling fiction premises for the {genre} genre.

{guidance_context}REQUIREMENTS FOR EACH PREMISE:
1. 2-3 sentences that capture the core conflict
2. Clear protagonist and stakes
3. Unique hook that sets it apart from the other premises
4. Must be substantially different from the other {count-1} premise{"s" if count > 2 else ""}
5. Ensure variety across all {count} options
6. Identify 3-5 unique elements that make each premise distinctive

TAXONOMY OPTIONS (select appropriate values for each premise):
{taxonomy_display}

Return JSON with this EXACT structure:
{{
  "premises": [
    {{
      "premise": "The 2-3 sentence premise text",
      "protagonist": "Brief protagonist description",
      "antagonist": "Brief antagonist/conflict description",
      "stakes": "What the protagonist stands to gain/lose",
      "hook": "What makes this unique",
      "themes": ["theme1", "theme2", "theme3"],
      "unique_elements": ["element1", "element2", "element3"],
      "selections": {json_structure}
    }}
    // ... {count-1} more unique premises (total of {count})
  ]
}}

CRITICAL: Generate exactly {count} distinct premises. Each must be substantially different from the others in concept, conflict, and hook."""

        try:
            result = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.9,  # High temp for creative diversity
                display_field="premise",  # Stream the "premise" field from first array element
                display_label=f"Generating {count} premise options",
                display_mode="array_first",  # Show first element as it streams
                min_response_tokens=500 * count  # Estimate ~500 tokens per premise
            )

            if not result or 'premises' not in result:
                raise ValueError("Invalid response format - missing 'premises' array")

            premises = result['premises']
            if not isinstance(premises, list):
                raise ValueError("Invalid response format - 'premises' is not an array")

            if len(premises) < count:
                # LLM returned fewer than requested - inform but accept
                from ..utils.logging import get_logger
                logger = get_logger()
                if logger:
                    logger.warning(f"LLM returned {len(premises)} premises instead of requested {count}")

            # Add number field and original_concept to each premise for reference
            for i, premise in enumerate(premises, 1):
                premise['number'] = i
                # Add original concept if user_input was provided
                if user_input:
                    premise['original_concept'] = user_input

            return premises

        except Exception as e:
            raise Exception(f"Failed to generate premise batch: {e}")