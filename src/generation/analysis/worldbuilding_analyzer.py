"""World-building coherence analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


WORLDBUILDING_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for world-building coherence.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

Analyze on these dimensions:

1. **Internal Logic**: Rules of world remain consistent
2. **Geography/Setting Consistency**: Locations don't contradict
3. **Timeline Coherence**: Events happen in logical sequence
4. **Technology/Magic Systems**: Rules established and followed
5. **Cultural Elements**: Social norms, language, customs stay consistent
6. **Sensory Details**: World feels immersive and grounded
7. **Show vs Tell Balance**: World revealed through action, not exposition dumps

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of world-building quality",
  "issues": [
    {
      "category": "LOGIC|GEOGRAPHY|TIMELINE|SYSTEM|CULTURE|EXPOSITION|etc",
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

Track world details and check for contradictions.
"""


class WorldBuildingAnalyzer(BaseAnalyzer):
    """Analyzer for world-building coherence."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze world-building coherence."""
        ctx = context or {}
        ctx['premise'] = ctx.get('premise', '')

        prompt = self._create_analysis_prompt(
            WORLDBUILDING_ANALYSIS_PROMPT,
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
                dimension="World-Building Coherence",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            return AnalysisResult(
                dimension="World-Building Coherence",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
