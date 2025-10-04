"""Prose and style analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


PROSE_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for prose and style quality.

Content to Analyze:
```
{{ content }}
```

Analyze on these dimensions:

1. **Sentence Variety**: Mix of short/long, simple/complex
2. **Purple Prose Detection**: Flag overwriting, excessive adjectives
3. **Clarity Issues**: Confusing constructions, unclear antecedents
4. **Repetition**: Overused words, phrases, sentence structures
5. **Active vs Passive Voice**: Identify weak passive constructions
6. **Filter Words**: "saw", "felt", "heard" - remove for immediacy
7. **Cliché Detection**: Overused metaphors, tired descriptions
8. **Genre Appropriateness**: Style matches genre expectations

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of prose quality",
  "issues": [
    {
      "category": "CLARITY|REPETITION|PASSIVE|PURPLE_PROSE|CLICHE|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific paragraph/sentence",
      "description": "what's wrong (include example)",
      "impact": "how this affects readability",
      "suggestion": "rewrite suggestion"
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

Include specific text examples when identifying issues.
"""


class ProseAnalyzer(BaseAnalyzer):
    """Analyzer for prose and style."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze prose and style."""
        prompt = self._create_analysis_prompt(
            PROSE_ANALYSIS_PROMPT,
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
                dimension="Prose & Style",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Prose & Style",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
