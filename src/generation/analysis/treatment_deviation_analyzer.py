"""Treatment deviation analysis - checks how well chapters follow the treatment."""

from typing import Dict, Any, Optional, List
from .base import BaseAnalyzer, AnalysisResult, Issue, Strength, Severity
from ...prompts import get_prompt_loader


class TreatmentDeviationAnalyzer(BaseAnalyzer):
    """Analyzes how well chapters follow the treatment."""

    def __init__(self, client, model: str):
        """Initialize analyzer with prompt loader."""
        super().__init__(client, model)
        self.prompt_loader = get_prompt_loader()

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

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "analysis/treatment_deviation",
            treatment=ctx.get('treatment', ''),
            content=content,
            foundation=ctx.get('foundation', ''),
            chapters_index=ctx.get('chapters_index', '')
        )

        # Get configuration from config
        config = self.prompt_loader.get_metadata("analysis/treatment_deviation")
        temperature = config.get('temperature', 0.1)
        reserve_tokens = config.get('reserve_tokens', 3000)
        use_structured_output = config.get('structured_output', False)

        # Make direct API call with system + user prompts
        response_data = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False,
            reserve_tokens=reserve_tokens,
            response_format={"type": "json_object"} if use_structured_output else None
        )

        response = response_data.get('content', '').strip()

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
