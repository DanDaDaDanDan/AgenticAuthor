"""Commercial viability analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


COMMERCIAL_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for commercial viability.

Content to Analyze:
```
{{ content }}
```

{% if genre %}
Genre: {{ genre }}
{% endif %}

Analyze on these dimensions:

1. **Market Fit**: Genre expectations met/subverted appropriately
2. **Target Audience Appeal**: Content matches intended readers
3. **Hook Strength**: Premise compelling and marketable
4. **Word Count Appropriateness**: Length matches genre norms
5. **Trope Usage**: Fresh take on familiar elements
6. **Query Potential**: Story can be pitched in 1-2 sentences
7. **Comparable Titles**: Fits alongside similar successful works

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of commercial viability",
  "target_audience": "identified target audience",
  "comparable_titles": ["list of similar successful books (if identifiable)"],
  "issues": [
    {
      "category": "MARKET_FIT|HOOK|LENGTH|TROPES|PITCH|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific aspect",
      "description": "what's wrong",
      "impact": "how this affects marketability",
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
  "notes": ["additional observations about market positioning"]
}

Be realistic about market fit. Consider genre conventions.
"""


class CommercialAnalyzer(BaseAnalyzer):
    """Analyzer for commercial viability."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze commercial viability."""
        ctx = context or {}

        prompt = self._create_analysis_prompt(
            COMMERCIAL_ANALYSIS_PROMPT,
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

            # Add market info to notes
            notes = data.get('notes', [])
            if 'target_audience' in data:
                notes.insert(0, f"Target Audience: {data['target_audience']}")
            if 'comparable_titles' in data and data['comparable_titles']:
                notes.insert(1, f"Comparable Titles: {', '.join(data['comparable_titles'])}")

            return AnalysisResult(
                dimension="Commercial Viability",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=notes
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Commercial Viability",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
