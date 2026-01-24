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

    async def check_structure_gate(self) -> QualityGate:
        """
        STRUCTURE_GATE: Validate chapter structure after outline generation.

        Checks:
        - Arc coherence (beginning, middle, end)
        - No duplicate events across chapters
        - Balanced pacing (no chapter too short/long)
        - Character arcs have setup and payoff
        """
        # Load chapter outlines
        chapters_yaml = self.project.get_chapters_yaml()
        if not chapters_yaml:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning="No chapter outlines found",
                issues=["chapters.yaml or chapter-beats/ not found"],
                suggestions=["Generate chapters with /generate chapters"]
            )

        chapters = chapters_yaml.get('chapters', [])
        if not chapters:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning="Empty chapter list",
                issues=["No chapters defined in outline"],
                suggestions=["Regenerate chapters"]
            )

        # Build context for judge
        foundation = chapters_yaml.get('metadata', {})
        characters = chapters_yaml.get('characters', [])

        context = {
            'total_chapters': len(chapters),
            'foundation': foundation,
            'character_count': len(characters),
            'chapters': chapters,
        }

        # Use prompt template for structure validation
        prompts = self.prompt_loader.render(
            "validation/structure_gate",
            chapters=chapters,
            foundation=foundation,
            characters=characters,
            total_chapters=len(chapters),
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("validation/structure_gate", default=0.1)

        # Call LLM judge
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

    async def check_continuity_gate(self, chapter_num: int) -> QualityGate:
        """
        CONTINUITY_GATE: Validate prose chapter against prior chapters.

        Checks:
        - Character consistency (traits, speech patterns)
        - Plot coherence with previous chapters
        - No contradictions with established facts
        - Setting continuity
        """
        # Load current chapter prose
        prose = self.project.get_chapter(chapter_num)
        if not prose:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning=f"Chapter {chapter_num} prose not found",
                issues=[f"No prose file for chapter {chapter_num}"],
                suggestions=["Generate prose first"]
            )

        # Load prior chapters
        prior_prose = []
        for i in range(1, chapter_num):
            ch_prose = self.project.get_chapter(i)
            if ch_prose:
                prior_prose.append({
                    'number': i,
                    'content': ch_prose[:5000]  # Truncate for context
                })

        # Load chapter outline for reference
        chapters_yaml = self.project.get_chapters_yaml()
        current_outline = None
        if chapters_yaml:
            for ch in chapters_yaml.get('chapters', []):
                if ch.get('number') == chapter_num:
                    current_outline = ch
                    break

        # Use prompt template
        prompts = self.prompt_loader.render(
            "validation/continuity_gate",
            chapter_num=chapter_num,
            current_prose=prose,
            current_outline=current_outline,
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
        # Load all prose chapters
        chapters_list = self.project.list_chapters()
        if not chapters_list:
            return QualityGate(
                result=QualityGateResult.BLOCKED,
                reasoning="No prose chapters found",
                issues=["No prose generated"],
                suggestions=["Generate prose with /generate prose all"]
            )

        # Build summary of all chapters (abbreviated for context)
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

        # Load foundation for reference
        chapters_yaml = self.project.get_chapters_yaml()
        foundation = chapters_yaml.get('metadata', {}) if chapters_yaml else {}
        characters = chapters_yaml.get('characters', []) if chapters_yaml else []

        # Use prompt template
        prompts = self.prompt_loader.render(
            "validation/completion_gate",
            chapter_summaries=chapter_summaries,
            total_chapters=len(chapters_list),
            total_words=total_words,
            foundation=foundation,
            characters=characters,
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
