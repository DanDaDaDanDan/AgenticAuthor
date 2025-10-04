"""Plot and structure analysis."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity


PLOT_ANALYSIS_PROMPT = """Analyze the following {{ content_type }} for plot and structure quality.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

Analyze on these dimensions:

1. **Three-Act Structure**: Setup, rising action, climax, resolution balance
2. **Plot Holes**: Logical inconsistencies, unexplained events, abandoned threads
3. **Cause & Effect**: Events follow logical progression
4. **Foreshadowing & Payoff**: Setups have payoffs
5. **Pacing**: Identify sections that drag or rush
6. **Scene Purpose**: Every scene advances plot, reveals character, or builds world
7. **Conflict Escalation**: Stakes increase throughout
8. **Structural Coherence**: Story flows logically from beginning to end

Respond with ONLY valid JSON:
{
  "score": 0-10,
  "summary": "brief overview of plot quality",
  "issues": [
    {
      "category": "PLOT HOLE|PACING|CAUSE_EFFECT|STRUCTURE|etc",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "specific location (Act, chapter, scene description)",
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

Be specific with locations. Identify real issues, don't invent them. Highlight genuine strengths.
"""


class PlotAnalyzer(BaseAnalyzer):
    """Analyzer for plot and structure."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze plot and structure.

        Args:
            content: Content to analyze
            content_type: Type (premise, treatment, chapter, prose)
            context: Additional context (premise, etc.)

        Returns:
            AnalysisResult with plot analysis
        """
        # Build context
        ctx = context or {}
        ctx['premise'] = ctx.get('premise', '')

        # Create prompt
        prompt = self._create_analysis_prompt(
            PLOT_ANALYSIS_PROMPT,
            content,
            content_type,
            ctx
        )

        # Call LLM
        response = await self._call_llm(prompt, temperature=0.3, max_tokens=3000)

        # Parse response
        try:
            data = self._parse_json_response(response)

            # Convert to AnalysisResult
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
                dimension="Plot & Structure",
                score=data.get('score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', [])
            )

        except Exception as e:
            # Return error result
            return AnalysisResult(
                dimension="Plot & Structure",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
