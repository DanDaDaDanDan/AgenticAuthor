"""Thematic coherence analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


THEME_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for thematic coherence.

Content to Analyze:
```
{{ content }}
```

Analyze on these dimensions:

1. **Theme Clarity**: Central themes identified and tracked
2. **Symbolic Consistency**: Recurring symbols/motifs used effectively
3. **Thematic Integration**: Theme woven through plot, not tacked on
4. **Subtlety vs Heavy-Handed**: Theme explored, not preached
5. **Character-Theme Alignment**: Arcs reinforce themes
6. **Ending Resonance**: Resolution reflects/answers thematic questions

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of thematic quality",
  "identified_themes": ["list of identified themes"],
  "issues": [
    {
      "category": "CLARITY|SUBTLETY|INTEGRATION|SYMBOLS|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific location",
      "description": "what's wrong",
      "impact": "how this affects thematic depth",
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

Identify actual themes, not surface-level topics.
"""


class ThemeAnalyzer(BaseAnalyzer):
    """Analyzer for thematic coherence."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze thematic coherence."""
        prompt = self._create_analysis_prompt(
            THEME_ANALYSIS_PROMPT,
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

            # Add identified themes to notes
            notes = data.get('notes', [])
            if 'identified_themes' in data:
                notes.insert(0, f"Identified themes: {', '.join(data['identified_themes'])}")

            return AnalysisResult(
                dimension="Thematic Coherence",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=notes
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Thematic Coherence",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
