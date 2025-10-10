"""Scale detection for determining patch vs regenerate."""

import json
from typing import Dict, Any, Optional
from jinja2 import Template

from ...api import OpenRouterClient


SCALE_DETECTION_TEMPLATE = """You are determining if a content change should be a small patch or full regeneration.

User Request: "{{ feedback }}"

Current Content Summary:
- Type: {{ content_type }}
- Length: {{ content_length }} words
- Has Structure: {{ has_structure }}

Intent Analysis:
- Intent: {{ intent_description }}
- Action: {{ action }}
- Scope: {{ scope }}

Classify as:
- "patch": Small, localized change (<30% of content affected, preserves structure)
- "regenerate": Large structural change (>30% affected, changes fundamental structure)

Examples of PATCH changes:
- Adding/removing dialogue in a specific scene
- Tweaking descriptions or word choices
- Minor plot adjustments
- Character detail changes
- Fixing inconsistencies
- Style refinements

Examples of REGENERATE changes:
- Major plot revisions
- Character arc changes
- Structural rewrites
- Genre/tone shifts
- Adding/removing entire scenes
- Premise modifications
- "Rewrite this completely"

Respond with ONLY valid JSON:
{
  "scale": "patch|regenerate",
  "estimated_change_percentage": 0-100,
  "reasoning": "why this scale is appropriate",
  "confidence": 0.0-1.0
}
"""


class ScaleDetector:
    """Detect if change should be patch or regenerate."""

    # Keywords that strongly indicate regeneration
    REGEN_KEYWORDS = [
        'rewrite', 'completely change', 'start over',
        'different approach', 'major revision',
        'restructure', 'rethink', 'total rewrite',
        'from scratch', 'redo', 'overhaul'
    ]

    # Structural actions that require regeneration
    STRUCTURAL_ACTIONS = [
        'add_chapter', 'remove_chapter', 'merge_chapters',
        'change_structure', 'reorder', 'split',
        'change_genre', 'change_tone', 'change_premise'
    ]

    def __init__(self, client: Optional[OpenRouterClient] = None, model: Optional[str] = None):
        """
        Initialize scale detector.

        Args:
            client: OpenRouter API client (optional, for LLM-based detection)
            model: Model to use for unclear cases (required if client provided)
        """
        self.client = client
        if client and not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.model = model

    def detect_scale(
        self,
        intent: Dict[str, Any],
        content: Optional[str] = None
    ) -> str:
        """
        Determine if change should be patch or regenerate.

        Args:
            intent: Parsed intent structure
            content: Current content being modified (optional)

        Returns:
            "patch" or "regenerate"
        """
        # If intent already has clear scale determination, use it
        if intent.get('scale') == 'patch':
            # Check for override conditions
            if not self._has_override_conditions(intent):
                return "patch"

        if intent.get('scale') == 'regenerate':
            return "regenerate"

        # Apply heuristic rules
        scale = self._apply_heuristics(intent, content)

        if scale != "unclear":
            return scale

        # If still unclear and we have LLM client, ask the model
        if self.client and content:
            return "ask_model"  # Coordinator will call ask_model_for_scale

        # Default to patch for safety (less destructive)
        return "patch"

    def _has_override_conditions(self, intent: Dict[str, Any]) -> bool:
        """
        Check if there are conditions that override the scale.

        Uses lines-based estimation, not structural scope.
        """
        # Check for regeneration keywords in feedback
        feedback = intent.get('original_feedback', '').lower()
        if any(kw in feedback for kw in self.REGEN_KEYWORDS):
            return True

        # Check for structural actions
        if intent.get('action') in self.STRUCTURAL_ACTIONS:
            return True

        # Estimate lines changed - if > 300 lines, override to regenerate
        estimated_lines = self._estimate_lines_changed(intent)
        if estimated_lines > 300:
            return True

        return False

    def _apply_heuristics(
        self,
        intent: Dict[str, Any],
        content: Optional[str] = None
    ) -> str:
        """
        Apply rule-based heuristics to determine scale based on estimated lines changed.

        KEY: Focus on estimated lines changed, not structural scope.
        E.g., adjusting 20 pieces of dialog across 10 chapters = patch (localized changes)
        vs. rewriting chapter structure = regenerate (fundamental change)

        NOTE: Premise iteration is handled at coordinator level and always uses regenerate.
        This method should not be called for premise, but if it is, treat as regenerate.

        Returns:
            "patch", "regenerate", or "unclear"
        """
        # Premise should always regenerate (handled in coordinator, but adding here for safety)
        if intent.get('target_type') == 'premise':
            return "regenerate"

        # Explicit keywords indicate regeneration
        feedback = intent.get('original_feedback', '').lower()
        if any(kw in feedback for kw in self.REGEN_KEYWORDS):
            return "regenerate"

        # Structural changes require regeneration
        if intent.get('action') in self.STRUCTURAL_ACTIONS:
            return "regenerate"

        # Estimate lines changed based on intent
        estimated_lines = self._estimate_lines_changed(intent, content)

        # Decision based on estimated lines:
        # < 100 lines: patch (localized changes, e.g., 20-30 dialog tweaks)
        # 100-300 lines: ask model (unclear, moderate changes)
        # > 300 lines: regenerate (major changes)
        if estimated_lines < 100:
            return "patch"
        elif estimated_lines > 300:
            return "regenerate"
        else:
            # Unclear, need LLM analysis
            return "unclear"

    def _estimate_lines_changed(self, intent: Dict[str, Any], content: Optional[str] = None) -> int:
        """
        Estimate how many lines will be changed based on intent.

        Args:
            intent: Parsed intent structure
            content: Current content being modified

        Returns:
            Estimated number of lines that will change
        """
        feedback = intent.get('original_feedback', '').lower()
        action = intent.get('action', '').lower()
        scope = intent.get('scope', '').lower()

        # Analyze feedback for quantitative hints
        # Look for numbers like "20 pieces of dialog", "5 scenes", etc.
        import re
        numbers = re.findall(r'\d+', feedback)
        if numbers:
            # Take the largest number mentioned as a hint
            max_num = max(int(n) for n in numbers)
        else:
            max_num = 0

        # Base estimate on action type
        if 'dialogue' in action or 'dialog' in feedback:
            # Dialog changes: typically 2-5 lines per occurrence
            if max_num > 0:
                return max_num * 3  # ~3 lines per dialog change
            return 10  # Default: small dialog tweak

        if 'description' in action or 'describe' in feedback:
            # Description changes: typically 3-10 lines per description
            if max_num > 0:
                return max_num * 5
            return 15  # Default: small description enhancement

        if 'scene' in feedback or 'scenes' in feedback:
            # Scene changes: large, 50-200 lines per scene
            if max_num > 0:
                return max_num * 100
            return 100

        if 'character' in feedback and ('arc' in feedback or 'motivation' in feedback):
            # Character arc changes: affects many lines throughout
            return 150

        if 'pacing' in action or 'tone' in action:
            # Style/pacing changes: typically affects many lines but localized
            return 30

        if 'fix' in action or 'typo' in action or 'grammar' in action:
            # Fixes: very small
            return 5

        # Scope-based estimation
        if scope == 'entire':
            # Entire content - assume 50% of lines change
            if content:
                return len(content.splitlines()) // 2
            return 250  # Default to large change

        if scope == 'multiple':
            # Multiple sections - estimate based on content size
            if content:
                # Assume 30% of lines across multiple sections
                return len(content.splitlines()) // 3
            return 100

        if scope == 'specific':
            # Specific location - small change
            return 20

        # Default: medium estimate
        return 50

    async def ask_model_for_scale(
        self,
        intent: Dict[str, Any],
        content: str,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Ask LLM to classify scale when unclear.

        Args:
            intent: Parsed intent structure
            content: Current content to be modified
            content_type: Type of content (premise, treatment, chapter, etc.)

        Returns:
            Scale classification dict with scale, percentage, reasoning, confidence
        """
        if not self.client:
            raise ValueError("Cannot ask model without OpenRouter client")

        # Analyze content
        content_length = len(content.split())
        has_structure = '\n\n' in content or '\n#' in content

        # Render prompt
        template = Template(SCALE_DETECTION_TEMPLATE)
        prompt = template.render(
            feedback=intent.get('original_feedback', ''),
            content_type=content_type,
            content_length=content_length,
            has_structure=has_structure,
            intent_description=intent.get('description', ''),
            action=intent.get('action', ''),
            scope=intent.get('scope', '')
        )

        messages = [
            {"role": "system", "content": "You are an expert at analyzing change magnitude. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.client.streaming_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                stream=False,
                display=False,
                max_tokens=300
            )

            content_response = response.get('content', '').strip()

            # Parse JSON
            scale_data = self._parse_json_response(content_response)

            # Validate
            if 'scale' not in scale_data:
                raise ValueError("Missing 'scale' in response")

            if scale_data['scale'] not in ['patch', 'regenerate']:
                raise ValueError(f"Invalid scale: {scale_data['scale']}")

            return scale_data

        except Exception as e:
            # Fallback to heuristics
            return {
                'scale': 'patch',
                'estimated_change_percentage': 15,
                'reasoning': f'Defaulted to patch due to error: {str(e)}',
                'confidence': 0.5
            }

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        # Remove markdown code blocks if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                return json.loads(content[start:end+1])
            raise
