"""Dialogue quality analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


DIALOGUE_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for dialogue quality.

Content to Analyze:
```
{{ content }}
```

Analyze on these dimensions:

1. **Naturalistic Flow**: Sounds like real speech (with intentional stylization)
2. **Character Differentiation**: Each character has distinct voice
3. **Subtext vs On-the-Nose**: Avoid explaining everything explicitly
4. **Purpose**: Advances plot, reveals character, or builds tension
5. **Pacing**: Balance dialogue with action/description
6. **Exposition Handling**: Info revealed organically, not info-dumped
7. **Conflict in Conversation**: Dialogue has tension/disagreement

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of dialogue quality",
  "issues": [
    {
      "category": "NATURALISM|VOICE|SUBTEXT|PURPOSE|EXPOSITION|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific scene/exchange",
      "description": "what's wrong",
      "impact": "how this affects the story",
      "suggestion": "concrete fix or example"
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

Include specific dialogue examples when identifying issues.
"""


class DialogueAnalyzer(BaseAnalyzer):
    """Analyzer for dialogue quality."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze dialogue quality."""
        prompt = self._create_analysis_prompt(
            DIALOGUE_ANALYSIS_PROMPT,
            content,
            content_type,
            context or {}
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
                dimension="Dialogue Quality",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Dialogue Quality",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
