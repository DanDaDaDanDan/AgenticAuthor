"""Unified story analysis - single call analyzing all dimensions."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity, PathToAPlus, Recommendation
from ...prompts import get_prompt_loader


# Legacy inline prompt - kept for reference but replaced by template
OLD_UNIFIED_ANALYSIS_PROMPT = """You are an expert story editor. Read this {{ content_type }} and provide honest feedback.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

{% if genre %}
Genre: {{ genre }}
{% endif %}

{% if treatment %}
Treatment Context:
{{ treatment }}
{% endif %}

{% if chapter_outline %}
Chapter Outline:
{{ chapter_outline }}
{% endif %}

Rate the quality and provide constructive criticism. Focus on what matters most to making this better.

⚠️ IMPORTANT: Check for duplicate plot elements:
- Duplicate events across different chapters (e.g., "alliance formed" in Ch 6 AND Ch 10)
- Repeated character moments or developments
- Redundant scenes covering the same story beats
- Structural repetition (two chapters doing essentially the same thing)
If you find duplicates, note them SPECIFICALLY in feedback (e.g., "Ch 6 'Alliance of Thieves' and Ch 10 'Manchester Accord' both cover the same alliance formation event - consolidate into one chapter")

Respond with ONLY valid JSON:
{
  "grade": "A+ (Exceptional) | A (Excellent) | B+ (Very Good) | B (Good) | C+ (Above Average) | C (Average) | D+ (Below Average) | D (Poor) | F (Needs Major Revision)",
  "grade_justification": "one sentence explaining the grade",
  "overall_assessment": "2-3 sentences on overall quality",
  "feedback": [
    "Specific observation with concrete suggestion (e.g., 'Act II drags - consolidate chapters 9-11 to maintain momentum')",
    "Another point...",
    ...
  ],
  "strengths": [
    "What works well in this story",
    ...
  ],
  "next_steps": "Single most impactful change to improve this {{ content_type }}"
}

Be honest, specific, and constructive. Focus on impact, not minutiae.
"""


class UnifiedAnalyzer(BaseAnalyzer):
    """Single unified analyzer covering all story dimensions."""

    def __init__(self, client, model: str):
        """Initialize analyzer with prompt loader."""
        super().__init__(client, model)
        self.prompt_loader = get_prompt_loader()

    def _grade_to_score(self, grade_str: str) -> float:
        """Convert letter grade to numeric score (0-10)."""
        grade_map = {
            'A+': 10.0,
            'A': 9.5,
            'B+': 8.5,
            'B': 8.0,
            'C+': 7.0,
            'C': 6.0,
            'D+': 5.0,
            'D': 4.0,
            'F': 2.0
        }
        # Extract just the grade letter (e.g., "A+ (Exceptional)" -> "A+")
        grade = grade_str.split('(')[0].strip()
        return grade_map.get(grade, 6.0)

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze content across all dimensions in a single call.

        Args:
            content: Content to analyze
            content_type: Type (premise, treatment, chapter, prose)
            context: Additional context (premise, genre, treatment, etc.)

        Returns:
            AnalysisResult with comprehensive analysis
        """
        # Build context
        ctx = context or {}

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "analysis/unified_analysis",
            content=content,
            content_type=content_type,
            premise=ctx.get('premise', ''),
            genre=ctx.get('genre', ''),
            treatment=ctx.get('treatment', ''),
            chapter_outline=ctx.get('chapter_outline', '')
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("analysis/unified_analysis", default=0.3)

        # Call LLM with higher token limit for comprehensive analysis
        # Make direct API call with system + user prompts
        response_data = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False,
            reserve_tokens=4000
        )

        response = response_data.get('content', '').strip()

        # Parse response
        try:
            data = self._parse_json_response(response)

            # Extract grade and convert to numeric score
            grade_str = data.get('grade', 'C')
            score = self._grade_to_score(grade_str)

            # Build summary from grade + justification + assessment
            grade_justification = data.get('grade_justification', '')
            overall_assessment = data.get('overall_assessment', '')
            summary = f"{grade_str}\n{grade_justification}\n\n{overall_assessment}"

            # Convert feedback points to issues (no severity/impact needed for simplified format)
            feedback_points = data.get('feedback', [])
            issues = [
                Issue(
                    category="Feedback",
                    severity=Severity.MEDIUM,
                    location="General",
                    description=point,
                    impact="",
                    suggestion="",
                    confidence=100
                )
                for point in feedback_points
            ]

            # Convert strengths (simple strings to Strength objects)
            strength_points = data.get('strengths', [])
            strengths = [
                Strength(
                    category="Strength",
                    description=s,
                    location=None
                )
                for s in strength_points
            ]

            # Next steps as notes
            next_steps = data.get('next_steps', '')
            notes = [f"Next steps: {next_steps}"] if next_steps else []

            return AnalysisResult(
                dimension="Comprehensive Analysis",
                score=score,
                summary=summary,
                issues=issues,
                strengths=strengths,
                notes=notes,
                path_to_a_plus=None  # Removed - redundant with next_steps
            )

        except Exception as e:
            # Return error result
            return AnalysisResult(
                dimension="Comprehensive Analysis",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
