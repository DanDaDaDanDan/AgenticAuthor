"""Treatment deviation analysis - checks how well chapters follow the treatment."""

from typing import Dict, Any, Optional, List
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity

TREATMENT_DEVIATION_PROMPT = """You are a story editor checking how well chapters follow the treatment.

TREATMENT (SOURCE OF TRUTH):
```
{{ treatment }}
```

CHAPTER OUTLINES TO ANALYZE:
```
{{ content }}
```

Your task is to identify:
1. **MISSING ELEMENTS**: Plot points from treatment not covered in chapters
2. **ADDED ELEMENTS**: New plot points/characters not in treatment
3. **DUPLICATION**: Same events/character arcs repeated across multiple chapters
4. **MISALIGNMENT**: Events happening in different order than treatment suggests

⚠️ IMPORTANT FOCUS ON DUPLICATION:
- Same character development beat repeated (e.g., "learns to trust" in Ch 1, 4, 7, 9)
- Same plot event covered multiple times (e.g., "alliance formed" in Ch 6 AND Ch 10)
- Redundant scenes/chapters covering identical story beats
- Character arcs reset or repeated instead of progressing

Respond with ONLY valid JSON:
{
  "fidelity_score": 0-10,
  "deviations": [
    {
      "type": "missing|added|duplicated|misaligned",
      "severity": "critical|high|medium|low",
      "element": "specific plot point or character beat",
      "treatment_reference": "where in treatment this appears (if applicable)",
      "chapter_references": ["Chapter X", "Chapter Y"],
      "description": "detailed explanation of the deviation",
      "impact": "how this affects the story",
      "recommendation": "specific fix"
    }
  ],
  "duplication_analysis": {
    "character_development_duplicates": [
      {
        "character": "character name",
        "development": "what development is repeated",
        "chapters": [1, 4, 7, 9],
        "recommendation": "consolidate into chapters X and Y"
      }
    ],
    "plot_event_duplicates": [
      {
        "event": "what event is repeated",
        "chapters": [6, 10],
        "recommendation": "keep in chapter X, remove from chapter Y"
      }
    ],
    "redundant_chapters": [
      {
        "chapters": "10-17",
        "issue": "all covering same subplot without progression",
        "recommendation": "consolidate into 2-3 chapters"
      }
    ]
  },
  "alignment_summary": "2-3 sentences on overall treatment fidelity",
  "critical_fixes": [
    "Most important deviation to fix",
    "Second priority",
    "Third priority"
  ]
}
"""


class TreatmentDeviationAnalyzer(BaseAnalyzer):
    """Analyzes how well chapters follow the treatment."""

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze chapters for treatment deviations.

        Args:
            content: Chapter outlines to analyze
            content_type: Should be 'chapters'
            context: Must contain 'treatment'

        Returns:
            AnalysisResult with deviation analysis
        """
        ctx = context or {}

        # Must have treatment for comparison
        if 'treatment' not in ctx:
            return AnalysisResult(
                dimension="Treatment Fidelity",
                score=0.0,
                summary="Cannot analyze treatment deviations without treatment context",
                issues=[],
                strengths=[],
                notes=["Treatment text required for deviation analysis"]
            )

        # Create prompt
        prompt = self._create_analysis_prompt(
            TREATMENT_DEVIATION_PROMPT,
            content,
            content_type,
            ctx,
            max_content_words=10000  # Need full chapters and treatment
        )

        # Call LLM
        # FIXED: Changed min_response_tokens to reserve_tokens
        response = await self._call_llm(
            prompt,
            temperature=0.1,  # Low temp for accurate comparison
            reserve_tokens=3000
        )

        # Parse response
        try:
            data = self._parse_json_response(response)

            score = float(data.get('fidelity_score', 5.0))
            summary = data.get('alignment_summary', 'No summary provided')

            # Convert deviations to issues
            issues = []
            deviations = data.get('deviations', [])
            for dev in deviations:
                severity_map = {
                    'critical': Severity.CRITICAL,
                    'high': Severity.HIGH,
                    'medium': Severity.MEDIUM,
                    'low': Severity.LOW
                }

                # Build location string
                chapters_str = ', '.join(dev.get('chapter_references', []))
                location = chapters_str if chapters_str else 'General'

                issue = Issue(
                    category=f"Treatment {dev.get('type', 'deviation').title()}",
                    severity=severity_map.get(dev.get('severity', 'medium'), Severity.MEDIUM),
                    location=location,
                    description=dev.get('description', 'Deviation from treatment'),
                    impact=dev.get('impact', ''),
                    suggestion=dev.get('recommendation', ''),
                    confidence=95
                )
                issues.append(issue)

            # Process duplication analysis
            dup_analysis = data.get('duplication_analysis', {})

            # Character development duplicates
            char_dups = dup_analysis.get('character_development_duplicates', [])
            for dup in char_dups:
                chapters = dup.get('chapters', [])
                chapters_str = f"Chapters {', '.join(map(str, chapters))}"

                issue = Issue(
                    category="Character Development Duplication",
                    severity=Severity.HIGH,
                    location=chapters_str,
                    description=f"{dup.get('character', 'Character')}: {dup.get('development', 'development')} repeated {len(chapters)} times",
                    impact="Stalls character progression and wastes narrative space",
                    suggestion=dup.get('recommendation', 'Consolidate development beats'),
                    confidence=100
                )
                issues.append(issue)

            # Plot event duplicates
            plot_dups = dup_analysis.get('plot_event_duplicates', [])
            for dup in plot_dups:
                chapters = dup.get('chapters', [])
                chapters_str = f"Chapters {', '.join(map(str, chapters))}"

                issue = Issue(
                    category="Plot Event Duplication",
                    severity=Severity.HIGH,
                    location=chapters_str,
                    description=f"Event '{dup.get('event', 'unknown')}' repeated in multiple chapters",
                    impact="Confuses timeline and reduces narrative impact",
                    suggestion=dup.get('recommendation', 'Remove duplicate'),
                    confidence=100
                )
                issues.append(issue)

            # Redundant chapters
            redundant = dup_analysis.get('redundant_chapters', [])
            for red in redundant:
                issue = Issue(
                    category="Redundant Chapters",
                    severity=Severity.CRITICAL,
                    location=f"Chapters {red.get('chapters', 'unknown')}",
                    description=red.get('issue', 'Multiple chapters covering same content'),
                    impact="Severe pacing problems and reader fatigue",
                    suggestion=red.get('recommendation', 'Consolidate chapters'),
                    confidence=100
                )
                issues.append(issue)

            # Build strengths (chapters that follow treatment well)
            strengths = []
            if score >= 8.0:
                strengths.append(Strength(
                    category="Treatment Fidelity",
                    description="Chapters closely follow the treatment structure",
                    location=None
                ))
            if not char_dups and not plot_dups:
                strengths.append(Strength(
                    category="No Duplication",
                    description="Each chapter advances the story without repetition",
                    location=None
                ))

            # Critical fixes as notes
            notes = []
            critical_fixes = data.get('critical_fixes', [])
            if critical_fixes:
                notes.append("Priority fixes:")
                for i, fix in enumerate(critical_fixes[:3], 1):
                    notes.append(f"{i}. {fix}")

            return AnalysisResult(
                dimension="Treatment Fidelity",
                score=score,
                summary=summary,
                issues=issues,
                strengths=strengths,
                notes=notes
            )

        except Exception as e:
            return AnalysisResult(
                dimension="Treatment Fidelity",
                score=0.0,
                summary=f"Analysis failed: {str(e)}",
                issues=[],
                strengths=[],
                notes=[f"Error: {str(e)}"]
            )
