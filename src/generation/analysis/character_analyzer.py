"""Character consistency analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


CHARACTER_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for character quality and consistency.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

Analyze on these dimensions:

1. **Character Voice**: Dialogue and actions match established personality
2. **Motivation Tracking**: Actions align with stated goals
3. **Arc Progression**: Character grows/changes throughout
4. **Relationship Dynamics**: Interactions remain consistent
5. **Knowledge Consistency**: Characters can't know what they haven't learned
6. **Physical/Temporal Tracking**: Character location/timeline coherence
7. **Emotional Authenticity**: Reactions match circumstances
8. **Character Differentiation**: Distinct, memorable characters

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of character quality",
  "issues": [
    {
      "category": "VOICE|MOTIVATION|KNOWLEDGE|CONSISTENCY|ARC|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific location",
      "description": "what's wrong",
      "impact": "how this affects the story",
      "suggestion": "concrete fix"
    }
  ],
  "strengths": [
    {
      "category": "strength type",
      "description": "specific positive element",
      "location": "where this appears (optional)"
    }
  ],
  "notes": ["additional observations"]
}

Be specific. Track character names and their consistency throughout.
"""


class CharacterAnalyzer(BaseAnalyzer):
    """Analyzer for character consistency."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze character consistency."""
        ctx = context or {}
        ctx['premise'] = ctx.get('premise', '')

        prompt = self._create_analysis_prompt(
            CHARACTER_ANALYSIS_PROMPT,
            content,
            content_type,
            ctx
        )

        response = await self._call_llm(prompt, temperature=0.3, max_tokens=3000)

        try:
            data = self._parse_json_response(response)

            issues = [
                Issue(
                    category=i['category'],
                    severity=Severity(i['severity']),
                    location=i['location'],
                    description=i['description'],
                    impact=i['impact'],
                    suggestion=i['suggestion']
                )
                for i in data.get('issues', [])
            ]

            strengths = [
                Strength(
                    category=s['category'],
                    description=s['description'],
                    location=s.get('location')
                )
                for s in data.get('strengths', [])
            ]

            return AnalysisResult(
                dimension="Character Consistency",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Character Consistency",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
