"""Intent analysis for natural language feedback."""

import json
from typing import Dict, Any, Optional
from jinja2 import Template

from ...api import OpenRouterClient
from ...models import Project


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
  "scale": "patch|regenerate|unclear",
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

- scale: Should this be a patch or regenerate
  * patch: Small change, can use unified diff
  * regenerate: Large change, need full regeneration
  * unclear: Not sure, need further analysis

- reasoning: Brief explanation of your classification

Be specific and confident. If unclear, set confidence < 0.8 and intent_type = "clarify".
"""


class IntentAnalyzer:
    """Analyze user feedback to determine intent."""

    def __init__(self, client: OpenRouterClient, model: Optional[str] = None):
        """
        Initialize intent analyzer.

        Args:
            client: OpenRouter API client
            model: Model to use (defaults to fast/cheap model for intent analysis)
        """
        self.client = client
        # Use fast, cheap model for intent analysis (Claude Haiku or GPT-3.5-turbo)
        self.model = model or "anthropic/claude-3-haiku:beta"

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
        if not feedback or not feedback.strip():
            raise ValueError("Feedback cannot be empty")

        # Build context
        project_context = self._build_project_context(project)

        # Render prompt
        template = Template(INTENT_ANALYSIS_TEMPLATE)
        prompt = template.render(
            project_name=project.name,
            genre=project_context['genre'],
            status=project_context['status'],
            has_premise="Yes" if project_context['has_premise'] else "No",
            has_treatment="Yes" if project_context['has_treatment'] else "No",
            chapter_count=project_context['chapter_count'],
            prose_chapters=project_context['prose_chapters'],
            feedback=feedback
        )

        # Call LLM for intent analysis
        messages = [
            {"role": "system", "content": "You are an expert at analyzing user intent. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.client.streaming_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Low temperature for consistent structured output
                stream=False,
                display=False,
                max_tokens=500
            )

            content = response.get('content', '').strip()

            # Try to extract JSON from response
            intent = self._parse_json_response(content)

            # Validate intent structure
            self._validate_intent(intent)

            # Add original feedback
            intent['original_feedback'] = feedback

            return intent

        except Exception as e:
            raise ValueError(f"Failed to analyze intent: {str(e)}")

    def _build_project_context(self, project: Project) -> Dict[str, Any]:
        """Build context about project state."""
        context = {
            'genre': project.metadata.genre if project.metadata else 'unknown',
            'status': project.metadata.status if project.metadata else 'draft',
            'has_premise': project.premise_file.exists(),
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
            'scope', 'action', 'description', 'scale', 'reasoning'
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

        valid_scales = ['patch', 'regenerate', 'unclear']
        if intent['scale'] not in valid_scales:
            raise ValueError(f"Invalid scale: {intent['scale']}")
