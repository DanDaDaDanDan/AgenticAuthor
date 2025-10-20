"""Intent analysis for natural language feedback."""

import json
from typing import Dict, Any, Optional

from ...api import OpenRouterClient
from ...models import Project
from ...prompts import get_prompt_loader


INTENT_ANALYSIS_TEMPLATE = """You are analyzing user feedback for a book generation system.

Project Context:
- Project: {{ project_name }}
- Genre: {{ genre }}
- Current Status: {{ status }}

Available Content:
- Premise: {{ has_premise }}
- Treatment: {{ has_treatment }}
- Chapters: {{ chapter_count }} chapters
- Prose: {{ prose_chapters }} chapters with prose

{% if default_target %}
Default Iteration Target: {{ default_target }}
(User has set this as their focus area - if feedback doesn't specify a different target, assume this one)
{% endif %}

User Feedback: "{{ feedback }}"

Analyze the intent and respond with ONLY valid JSON (no other text):

{
  "intent_type": "modify|add|remove|regenerate|analyze|clarify",
  "confidence": 0.0-1.0,
  "target_type": "premise|treatment|chapter|chapters|prose|taxonomy|project",
  "target_id": "specific identifier or null",
  "scope": "specific|section|multiple|entire",
  "action": "add_dialogue|fix_plot|enhance_description|change_tone|add_chapter|etc",
  "description": "clear description of what user wants",
  "reasoning": "why you classified it this way"
}

Guidelines:
- intent_type: What kind of change is requested
  * modify: Change existing content
  * add: Add new content
  * remove: Remove content
  * regenerate: Complete regeneration with new direction
  * analyze: Request analysis (not iteration)
  * clarify: Need more information

- confidence: How confident you are (0.0 to 1.0)
  * >0.8: High confidence, can execute
  * <0.8: Need clarification

- target_type: What part of the project
  * premise: Story premise
  * treatment: Treatment document
  * chapter: Specific chapter (set target_id)
  * chapters: Multiple chapters (set target_id like "3-5")
  * prose: Prose content
  * taxonomy: Genre/style metadata
  * project: Project-wide changes

- target_id: Specific identifier (chapter number, range, etc.) or null

- scope: How broad is the change
  * specific: Single, localized change
  * section: Part of a chapter/document
  * multiple: Multiple chapters/sections
  * entire: Whole document/project

- action: What action to take (use underscores, be specific)

- reasoning: Brief explanation of your classification

Be specific and confident. If unclear, set confidence < 0.8 and intent_type = "clarify".
"""


class IntentAnalyzer:
    """Analyze user feedback to determine intent."""

    def __init__(
        self,
        client: OpenRouterClient,
        model: str,
        default_target: Optional[str] = None
    ):
        """
        Initialize intent analyzer.

        Args:
            client: OpenRouter API client
            model: Model to use for intent analysis (required)
            default_target: Default target for iterations when not specified
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.model = model
        self.default_target = default_target
        self.prompt_loader = get_prompt_loader()

    async def analyze(
        self,
        feedback: str,
        project: Project,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze feedback and return structured intent.

        Args:
            feedback: User's natural language feedback
            project: Current project
            context: Additional context (optional)

        Returns:
            Structured intent dict with confidence score

        Raises:
            ValueError: If feedback is empty or intent cannot be parsed
        """
        from ...utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info("=== INTENT ANALYZER: analyze START ===")
            logger.info(f"Feedback: {feedback}")
            logger.info(f"Model: {self.model}")

        if not feedback or not feedback.strip():
            raise ValueError("Feedback cannot be empty")

        # Build context
        if logger:
            logger.info("INTENT: Building project context...")

        project_context = self._build_project_context(project)

        if logger:
            logger.debug(f"INTENT: Project context: {project_context}")

        # Render prompt
        if logger:
            logger.info("INTENT: Rendering prompt template...")

        prompts = self.prompt_loader.render(
            "analysis/intent_check",
            project_name=project.name,
            genre=project_context['genre'],
            status=project_context['status'],
            has_premise="Yes" if project_context['has_premise'] else "No",
            has_treatment="Yes" if project_context['has_treatment'] else "No",
            chapter_count=project_context['chapter_count'],
            prose_chapters=project_context['prose_chapters'],
            default_target=self.default_target or "",
            feedback=feedback
        )

        if logger:
            logger.debug(f"INTENT: Prompt length: {len(prompts['user'])} chars")

        # Call LLM for intent analysis
        messages = [
            {"role": "system", "content": prompts['system']},
            {"role": "user", "content": prompts['user']}
        ]

        try:
            if logger:
                logger.info("INTENT: Calling streaming_completion API...")

            response = await self.client.streaming_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Low temperature for consistent structured output
                stream=True,
                display=True,
                display_label="Analyzing intent",
                max_tokens=500,
                response_format={"type": "json_object"}  # Use structured JSON output
            )

            if logger:
                logger.info("INTENT: API call returned successfully")
                logger.debug(f"INTENT: Response type: {type(response)}")

            content = response.get('content', '').strip()

            if logger:
                logger.debug(f"INTENT: Content length: {len(content)} chars")
                logger.debug(f"INTENT: Content preview: {content[:200]}")

            # Try to extract JSON from response
            if logger:
                logger.info("INTENT: Parsing JSON response...")

            intent = self._parse_json_response(content)

            if logger:
                logger.info("INTENT: JSON parsed successfully")
                logger.debug(f"INTENT: Intent keys: {list(intent.keys())}")

            # Validate intent structure
            if logger:
                logger.info("INTENT: Validating intent structure...")

            self._validate_intent(intent)

            if logger:
                logger.info("INTENT: Validation passed")

            # Post-processing: map chapter references to prose for short stories
            if project.is_short_form() and intent['target_type'] in ['chapter', 'chapters']:
                if logger:
                    logger.info("INTENT: Short-form project, mapping chapter -> prose")
                # Short stories don't have chapters, map to prose
                intent['target_type'] = 'prose'
                # Clear chapter-specific target_id if present
                if intent.get('target_id'):
                    intent['target_id'] = None

            # Add original feedback
            intent['original_feedback'] = feedback

            if logger:
                logger.info(f"INTENT: Final intent type={intent['intent_type']}, target={intent['target_type']}, confidence={intent['confidence']}")
                logger.info("=== INTENT ANALYZER: analyze END (SUCCESS) ===")

            return intent

        except Exception as e:
            if logger:
                logger.error(f"INTENT: Exception during analysis: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"INTENT: Traceback: {traceback.format_exc()}")
                logger.info("=== INTENT ANALYZER: analyze END (ERROR) ===")
            raise ValueError(f"Failed to analyze intent: {str(e)}")

    def _build_project_context(self, project: Project) -> Dict[str, Any]:
        """Build context about project state."""
        context = {
            'genre': project.metadata.genre if project.metadata else 'unknown',
            'status': project.metadata.status if project.metadata else 'draft',
            # Check premise_metadata.json (new format), fallback to premise.md (old format)
            'has_premise': project.premise_metadata_file.exists() or project.premise_file.exists(),
            'has_treatment': project.treatment_file.exists(),
            'chapter_count': 0,
            'prose_chapters': 0
        }

        # Count chapters
        if project.chapters_file.exists():
            try:
                import yaml
                chapters_data = yaml.safe_load(project.chapters_file.read_text())
                if chapters_data and 'chapters' in chapters_data:
                    context['chapter_count'] = len(chapters_data['chapters'])
            except:
                pass

        # Count prose chapters
        if project.chapters_dir.exists():
            prose_files = list(project.chapters_dir.glob('chapter-*.md'))
            context['prose_chapters'] = len(prose_files)

        return context

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        # Remove markdown code blocks if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        # Try to parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Try to find JSON object in text
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end+1])
                except:
                    pass
            raise ValueError(f"Failed to parse JSON from response: {str(e)}\nContent: {content}")

    def _validate_intent(self, intent: Dict[str, Any]) -> None:
        """Validate intent structure."""
        required_fields = [
            'intent_type', 'confidence', 'target_type',
            'scope', 'action', 'description', 'reasoning'
        ]

        for field in required_fields:
            if field not in intent:
                raise ValueError(f"Missing required field in intent: {field}")

        # Validate types
        if not isinstance(intent['confidence'], (int, float)):
            raise ValueError(f"Confidence must be a number, got: {type(intent['confidence'])}")

        if not 0.0 <= intent['confidence'] <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got: {intent['confidence']}")

        # Validate enums
        valid_intent_types = ['modify', 'add', 'remove', 'regenerate', 'analyze', 'clarify']
        if intent['intent_type'] not in valid_intent_types:
            raise ValueError(f"Invalid intent_type: {intent['intent_type']}")

        valid_target_types = ['premise', 'treatment', 'chapter', 'chapters', 'prose', 'taxonomy', 'project']
        if intent['target_type'] not in valid_target_types:
            raise ValueError(f"Invalid target_type: {intent['target_type']}")

        valid_scopes = ['specific', 'section', 'multiple', 'entire']
        if intent['scope'] not in valid_scopes:
            raise ValueError(f"Invalid scope: {intent['scope']}")
