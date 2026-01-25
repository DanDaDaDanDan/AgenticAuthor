"""Quality gates for generation validation."""

import json
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from ..models import Project
from ..prompts import get_prompt_loader


class QualityGateResult(str, Enum):
    """Possible quality gate outcomes."""

    PASS = "pass"              # Continue to next phase
    NEEDS_WORK = "needs_work"  # Auto-iterate (max 2 attempts)
    BLOCKED = "blocked"        # Requires human review


@dataclass
class QualityGate:
    """Result of a quality gate check."""

    result: QualityGateResult
    reasoning: str
    issues: List[str]
    suggestions: List[str]

    @property
    def passed(self) -> bool:
        """Check if gate passed."""
        return self.result == QualityGateResult.PASS

    @property
    def can_auto_fix(self) -> bool:
        """Check if issues can be auto-fixed."""
        return self.result == QualityGateResult.NEEDS_WORK

    def to_dict(self) -> Dict[str, Any]:
        return {
            'result': self.result.value,
            'reasoning': self.reasoning,
            'issues': self.issues,
            'suggestions': self.suggestions,
        }


class QualityGateManager:
    """Manages quality gate validation using LLM judges."""

    def __init__(self, client, model: str, project: Project):
        """
        Initialize quality gate manager.

        Args:
            client: OpenRouter API client
            model: Model to use for judging
            project: Current project
        """
        self.client = client
        self.model = model
        self.project = project
        self.prompt_loader = get_prompt_loader()

    async def check_continuity_gate(self, unit_num: int) -> QualityGate:
        """
        CONTINUITY_GATE: Validate prose unit against prior units.

        Checks:
        - Character consistency (traits, speech patterns)
        - Plot coherence with previous units
        - No contradictions with established facts
        - Setting continuity
        """
        # Load current unit prose
        prose = self.project.get_chapter(unit_num)
        if not prose:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning=f"Unit {unit_num} prose not found",
                issues=[f"No prose file for unit {unit_num}"],
                suggestions=["Generate prose first"]
            )

        # Load prior units (full content - Context is King)
        prior_prose = []
        for i in range(1, unit_num):
            unit_prose = self.project.get_chapter(i)
            if unit_prose:
                prior_prose.append({
                    'number': i,
                    'content': unit_prose
                })

        # Load structure plan for reference
        structure_plan = None
        plan_file = self.project.path / "structure-plan.md"
        if plan_file.exists():
            structure_plan = plan_file.read_text(encoding='utf-8')

        # Use prompt template
        prompts = self.prompt_loader.render(
            "validation/continuity_gate",
            chapter_num=unit_num,
            current_prose=prose,
            current_outline=structure_plan,
            prior_chapters=prior_prose,
        )

        temperature = self.prompt_loader.get_temperature("validation/continuity_gate", default=0.1)

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False,
            response_format={"type": "json_object"}
        )

        return self._parse_gate_response(result)

    async def check_completion_gate(self) -> QualityGate:
        """
        COMPLETION_GATE: Final quality check after all prose generated.

        Checks:
        - Overall narrative coherence
        - Major plot holes
        - Unresolved character arcs
        - Thematic consistency
        - Satisfying conclusion
        """
        # Check for story.md (short stories) or chapters/ (novels)
        story_file = self.project.story_file
        chapters_list = self.project.list_chapters()

        if story_file.exists():
            # Short story - single file
            content = story_file.read_text(encoding='utf-8')
            total_words = len(content.split())
            chapter_summaries = [{
                'number': 1,
                'word_count': total_words,
                'opening': content[:1000],
                'closing': content[-1000:] if len(content) > 1000 else content,
            }]
            total_chapters = 1
        elif chapters_list:
            # Novel - multiple chapters
            chapter_summaries = []
            total_words = 0

            for ch_path in chapters_list:
                content = ch_path.read_text(encoding='utf-8')
                words = len(content.split())
                total_words += words

                # Take first and last paragraphs for summary
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                summary = {
                    'number': int(ch_path.stem.split('-')[1]),
                    'word_count': words,
                    'opening': paragraphs[0][:500] if paragraphs else "",
                    'closing': paragraphs[-1][:500] if len(paragraphs) > 1 else "",
                }
                chapter_summaries.append(summary)
            total_chapters = len(chapters_list)
        else:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning="No prose found",
                issues=["No story.md or chapter files found"],
                suggestions=["Generate prose first"]
            )

        # Load premise and treatment for reference
        premise = self.project.get_premise() or ""
        treatment = self.project.get_treatment() or ""

        # Use prompt template
        prompts = self.prompt_loader.render(
            "validation/completion_gate",
            chapter_summaries=chapter_summaries,
            total_chapters=total_chapters,
            total_words=total_words,
            foundation={'premise': premise, 'treatment': treatment},
            characters=[],
        )

        temperature = self.prompt_loader.get_temperature("validation/completion_gate", default=0.1)

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False,
            response_format={"type": "json_object"}
        )

        return self._parse_gate_response(result)

    def _parse_gate_response(self, result: Dict[str, Any]) -> QualityGate:
        """Parse LLM response into QualityGate."""
        if not result:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning="No response from judge",
                issues=["LLM returned empty response"],
                suggestions=["Retry the quality check"]
            )

        response_text = result.get('content', result) if isinstance(result, dict) else result

        try:
            # Strip markdown fences if present
            response_text = response_text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)

            # Parse JSON
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try with non-strict parsing for control characters
                data = json.loads(response_text, strict=False)

            # Map verdict to result
            verdict = data.get('verdict', 'blocked').lower()
            if verdict in ('pass', 'approved'):
                gate_result = QualityGateResult.PASS
            elif verdict in ('needs_work', 'needs_revision'):
                gate_result = QualityGateResult.NEEDS_WORK
            else:
                gate_result = QualityGateResult.BLOCKED

            return QualityGate(
                result=gate_result,
                reasoning=data.get('reasoning', ''),
                issues=data.get('issues', data.get('specific_issues', [])),
                suggestions=data.get('suggestions', []),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning=f"Failed to parse judge response: {e}",
                issues=["Invalid JSON response from judge"],
                suggestions=["Retry the quality check"]
            )
