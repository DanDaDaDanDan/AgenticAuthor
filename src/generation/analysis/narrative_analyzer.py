"""Narrative technique analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


NARRATIVE_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for narrative technique quality.

Content to Analyze:
```
{{ content }}
```

Analyze on these dimensions:

1. **POV Consistency**: No head-hopping or POV violations
2. **Tense Consistency**: Past/present tense maintained
3. **Narrative Distance**: Psychic distance appropriate and consistent
4. **Scene vs Summary Balance**: Right mix of dramatized vs told
5. **Opening Hooks**: Chapters/scenes start with engagement
6. **Transitions**: Smooth movement between scenes/chapters
7. **Ending Impact**: Chapters end with hooks/resolution

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of narrative technique",
  "issues": [
    {
      "category": "POV|TENSE|DISTANCE|PACING|HOOKS|TRANSITIONS|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific location",
      "description": "what's wrong",
      "impact": "how this affects reading experience",
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

Check for technical consistency throughout.
"""


class NarrativeAnalyzer(BaseAnalyzer):
    """Analyzer for narrative technique."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze narrative technique."""
        prompt = self._create_analysis_prompt(
            NARRATIVE_ANALYSIS_PROMPT,
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
                dimension="Narrative Technique",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Narrative Technique",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
