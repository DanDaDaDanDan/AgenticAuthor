"""Unified story analysis - single call analyzing all dimensions."""

from typing import Dict, Any, Optional
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity, PathToAPlus, Recommendation


UNIFIED_ANALYSIS_PROMPT = """You are an expert story editor analyzing this {{ content_type }}.

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

ANALYSIS TASK:

Analyze across ALL story dimensions:
1. **Plot & Structure** - Holes, pacing, cause/effect, foreshadowing, escalation
2. **Character** - Consistency, arcs, motivation, believability
3. **World-Building** - Internal logic, coherence, geography, systems
4. **Dialogue** - Naturalism, character voice, subtext
5. **Prose & Style** - Clarity, engagement, repetition, active voice
6. **Theme** - Coherence, symbols, integration
7. **Narrative Technique** - POV consistency, tense, hooks, distance
8. **Commercial Viability** - Market fit, hook strength, target audience appeal

CRITICAL INSTRUCTIONS:

1. **Focus on CRITICAL issues only** - things that genuinely harm the story
2. **Return 0-7 issues maximum** - quality over quantity
3. **It's OKAY to find 0 issues** if the content is solid
4. **Prioritize by IMPACT** - one major plot hole matters more than five minor word choices
5. **Be specific** - vague feedback like "pacing issues" is useless
6. **Provide actionable fixes** - tell exactly how to improve it
7. **Don't invent problems** - only report real issues that affect reader experience

CONFIDENCE REQUIREMENTS (NEW):

8. **Only report issues with >70% confidence** - be self-critical about your analysis
9. **If uncertain, DON'T include it** - it's better to miss a minor issue than report a false positive
10. **Include confidence percentage (0-100%) for each issue** - be honest about certainty
11. **False positives are worse than false negatives** - when in doubt, leave it out
12. **Ask yourself: "Am I CERTAIN this is a real problem?"** - if the answer is "maybe", skip it

SEVERITY GUIDELINES:
- **CRITICAL**: Story-breaking issues (major plot holes, character contradictions, broken logic)
- **HIGH**: Significant problems that weaken the story (pacing drags, weak character motivation)
- **MEDIUM**: Noticeable issues that could be improved (minor inconsistencies, style quirks)
- **LOW**: Polish items (word choice, minor clarity improvements)

Only include CRITICAL and HIGH severity issues in your response.

Respond with ONLY valid JSON:
{
  "overall_score": 0-10,
  "overall_grade": "A (Excellent) | B+ (Very Good) | B (Good) | C+ (Above Average) | C (Average) | D+ (Below Average) | D (Poor) | F (Needs Major Revision)",
  "summary": "2-3 sentence executive summary of overall quality",

  "priority_fixes": [
    {
      "priority": 1,
      "dimension": "Plot|Character|World-Building|Dialogue|Prose|Theme|Narrative|Commercial",
      "severity": "CRITICAL|HIGH",
      "confidence": 0-100,
      "location": "specific location (Act II, Chapter 3, opening paragraph, etc.)",
      "issue": "concise description of what's wrong",
      "impact": "why this matters - how it affects the reader/story",
      "suggestion": "concrete, actionable fix - be specific"
    }
  ],

  "path_to_a_plus": {
    "current_assessment": "why the current grade was given - what's holding it back from A/A+",
    "recommendations": [
      {
        "description": "specific actionable step to reach A/A+ grade",
        "confidence": 0-100,
        "rationale": "why this would elevate the story to A/A+ level"
      }
    ],
    "unable_to_determine": false,
    "reasoning": "if unable_to_determine is true, explain why you can't identify a clear path to A+"
  },

  "strengths": [
    {
      "dimension": "which aspect shines",
      "description": "specific positive element worth highlighting",
      "location": "where this appears (optional)"
    }
  ],

  "dimension_scores": {
    "plot": 0-10,
    "character": 0-10,
    "worldbuilding": 0-10,
    "dialogue": 0-10,
    "prose": 0-10,
    "theme": 0-10,
    "narrative": 0-10,
    "commercial": 0-10
  },

  "notes": ["any additional high-level observations"]
}

REMEMBER:
- 0-7 issues maximum (it's okay to have fewer or zero)
- Only CRITICAL and HIGH severity
- Be specific with locations and suggestions
- Focus on what genuinely improves the story
- Include confidence percentage for each issue (must be >70%)
- Include confidence percentage for path_to_a_plus recommendations
- It's OKAY to set unable_to_determine=true if you genuinely can't identify improvements
"""


class UnifiedAnalyzer(BaseAnalyzer):
    """Single unified analyzer covering all story dimensions."""

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

        # Create prompt
        prompt = self._create_analysis_prompt(
            UNIFIED_ANALYSIS_PROMPT,
            content,
            content_type,
            ctx,
            max_content_words=8000  # More generous for unified analysis
        )

        # Call LLM with higher token limit for comprehensive analysis
        response = await self._call_llm(
            prompt,
            temperature=0.3,
            max_tokens=4000
        )

        # Parse response
        try:
            data = self._parse_json_response(response)

            # Convert to AnalysisResult
            issues = [
                Issue(
                    category=f"[{i['dimension']}] {i.get('category', i['dimension'])}",
                    severity=Severity(i['severity']),
                    location=i['location'],
                    description=i['issue'],
                    impact=i['impact'],
                    suggestion=i['suggestion'],
                    confidence=i.get('confidence', 100)  # Default to 100 if missing
                )
                for i in data.get('priority_fixes', [])
            ]

            strengths = [
                Strength(
                    category=s['dimension'],
                    description=s['description'],
                    location=s.get('location')
                )
                for s in data.get('strengths', [])
            ]

            # Parse path_to_a_plus section
            path_to_a_plus = None
            if 'path_to_a_plus' in data:
                path_data = data['path_to_a_plus']
                recommendations = [
                    Recommendation(
                        description=r['description'],
                        confidence=r.get('confidence', 0),
                        rationale=r.get('rationale', '')
                    )
                    for r in path_data.get('recommendations', [])
                ]
                path_to_a_plus = PathToAPlus(
                    current_assessment=path_data.get('current_assessment', ''),
                    recommendations=recommendations,
                    unable_to_determine=path_data.get('unable_to_determine', False),
                    reasoning=path_data.get('reasoning')
                )

            return AnalysisResult(
                dimension="Comprehensive Analysis",
                score=data.get('overall_score', 5.0),
                summary=data.get('summary', ''),
                issues=issues,
                strengths=strengths,
                notes=data.get('notes', []),
                path_to_a_plus=path_to_a_plus
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
