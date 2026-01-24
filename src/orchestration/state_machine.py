"""State machine for tracking generation progress."""

import json
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List


class GenerationPhase(str, Enum):
    """Generation phases in order of progression."""

    IDLE = "idle"            # No generation in progress
    PREMISE = "premise"      # Generating premise
    TREATMENT = "treatment"  # Generating treatment
    PLAN = "plan"            # Model-driven structure planning (novels only)
    PROSE = "prose"          # Generating prose
    COMPLETE = "complete"    # All generation done

    @classmethod
    def from_string(cls, value: str) -> 'GenerationPhase':
        """Convert string to phase enum."""
        try:
            return cls(value.lower())
        except ValueError:
            # Handle legacy 'chapters' phase -> map to PLAN
            if value.lower() == 'chapters':
                return cls.PLAN
            return cls.IDLE

    def next_phase(self, is_short_form: bool = False) -> Optional['GenerationPhase']:
        """
        Get the next phase in the progression.

        Args:
            is_short_form: If True, skip PLAN phase (short stories go direct to PROSE)
        """
        if self == GenerationPhase.IDLE:
            return GenerationPhase.PREMISE
        elif self == GenerationPhase.PREMISE:
            return GenerationPhase.TREATMENT
        elif self == GenerationPhase.TREATMENT:
            # Short stories skip planning, go direct to prose
            return GenerationPhase.PROSE if is_short_form else GenerationPhase.PLAN
        elif self == GenerationPhase.PLAN:
            return GenerationPhase.PROSE
        elif self == GenerationPhase.PROSE:
            return GenerationPhase.COMPLETE
        return None

    @property
    def display_name(self) -> str:
        """Human-readable phase name."""
        return self.value.upper()


@dataclass
class QualityGateStatus:
    """Status of a single quality gate."""

    name: str
    passed: Optional[bool] = None
    message: str = ""
    checked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityGateStatus':
        return cls(**data)


@dataclass
class GenerationState:
    """Persistent state for generation progress."""

    phase: GenerationPhase = GenerationPhase.IDLE
    current_chapter: int = 0
    total_chapters: int = 0
    word_count: int = 0
    target_word_count: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None

    # Quality gate statuses
    structure_gate: Optional[QualityGateStatus] = None
    continuity_gates: List[QualityGateStatus] = field(default_factory=list)
    completion_gate: Optional[QualityGateStatus] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        data = {
            'phase': self.phase.value,
            'current_chapter': self.current_chapter,
            'total_chapters': self.total_chapters,
            'word_count': self.word_count,
            'target_word_count': self.target_word_count,
            'started_at': self.started_at,
            'updated_at': self.updated_at,
            'error': self.error,
        }

        if self.structure_gate:
            data['structure_gate'] = self.structure_gate.to_dict()
        if self.continuity_gates:
            data['continuity_gates'] = [g.to_dict() for g in self.continuity_gates]
        if self.completion_gate:
            data['completion_gate'] = self.completion_gate.to_dict()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationState':
        """Create from dict."""
        state = cls(
            phase=GenerationPhase.from_string(data.get('phase', 'idle')),
            current_chapter=data.get('current_chapter', 0),
            total_chapters=data.get('total_chapters', 0),
            word_count=data.get('word_count', 0),
            target_word_count=data.get('target_word_count', 0),
            started_at=data.get('started_at'),
            updated_at=data.get('updated_at'),
            error=data.get('error'),
        )

        if 'structure_gate' in data and data['structure_gate']:
            state.structure_gate = QualityGateStatus.from_dict(data['structure_gate'])
        if 'continuity_gates' in data:
            state.continuity_gates = [
                QualityGateStatus.from_dict(g) for g in data['continuity_gates']
            ]
        if 'completion_gate' in data and data['completion_gate']:
            state.completion_gate = QualityGateStatus.from_dict(data['completion_gate'])

        return state

    @property
    def is_in_progress(self) -> bool:
        """Check if generation is in progress."""
        return self.phase not in (GenerationPhase.IDLE, GenerationPhase.COMPLETE)

    @property
    def has_error(self) -> bool:
        """Check if there's an error blocking progress."""
        return self.error is not None

    @property
    def progress_percent(self) -> int:
        """Calculate overall progress percentage."""
        if self.phase == GenerationPhase.COMPLETE:
            return 100
        if self.phase == GenerationPhase.IDLE:
            return 0

        # Weight: premise=10%, treatment=20%, chapters=20%, prose=50%
        base_progress = {
            GenerationPhase.PREMISE: 0,
            GenerationPhase.TREATMENT: 10,
            GenerationPhase.CHAPTERS: 30,
            GenerationPhase.PROSE: 50,
        }

        base = base_progress.get(self.phase, 0)

        if self.phase == GenerationPhase.PROSE and self.total_chapters > 0:
            # Add prose progress (50% total allocated to prose)
            chapter_progress = (self.current_chapter / self.total_chapters) * 50
            return int(base + chapter_progress)

        return base

    def get_quality_gates_summary(self) -> Dict[str, Any]:
        """Get summary of all quality gates."""
        summary = {
            'structure': 'pending',
            'continuity': '0/0',
            'completion': 'pending',
        }

        if self.structure_gate:
            if self.structure_gate.passed is True:
                summary['structure'] = 'PASS'
            elif self.structure_gate.passed is False:
                summary['structure'] = 'FAIL'

        if self.continuity_gates:
            passed = sum(1 for g in self.continuity_gates if g.passed is True)
            total = len(self.continuity_gates)
            summary['continuity'] = f'{passed}/{total}'

        if self.completion_gate:
            if self.completion_gate.passed is True:
                summary['completion'] = 'PASS'
            elif self.completion_gate.passed is False:
                summary['completion'] = 'FAIL'

        return summary


class StateManager:
    """Manages generation state persistence."""

    STATE_FILE = "state.json"

    def __init__(self, project_path: Path):
        """
        Initialize state manager.

        Args:
            project_path: Path to project directory
        """
        self.project_path = Path(project_path)
        self.state_file = self.project_path / self.STATE_FILE
        self._state: Optional[GenerationState] = None

    def load(self) -> GenerationState:
        """Load state from file or create new."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._state = GenerationState.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Corrupted state file - start fresh
                self._state = GenerationState()
        else:
            self._state = GenerationState()

        return self._state

    def save(self) -> None:
        """Save current state to file."""
        if self._state is None:
            self._state = GenerationState()

        self._state.updated_at = datetime.now(timezone.utc).isoformat()

        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self._state.to_dict(), f, indent=2)

    def get_state(self) -> GenerationState:
        """Get current state, loading if necessary."""
        if self._state is None:
            self.load()
        return self._state

    def update_phase(self, phase: GenerationPhase) -> None:
        """Update generation phase."""
        state = self.get_state()
        state.phase = phase

        if phase != GenerationPhase.IDLE and not state.started_at:
            state.started_at = datetime.now(timezone.utc).isoformat()

        state.error = None  # Clear error on phase change
        self.save()

    def update_progress(
        self,
        current_chapter: Optional[int] = None,
        total_chapters: Optional[int] = None,
        word_count: Optional[int] = None,
        target_word_count: Optional[int] = None,
    ) -> None:
        """Update progress metrics."""
        state = self.get_state()

        if current_chapter is not None:
            state.current_chapter = current_chapter
        if total_chapters is not None:
            state.total_chapters = total_chapters
        if word_count is not None:
            state.word_count = word_count
        if target_word_count is not None:
            state.target_word_count = target_word_count

        self.save()

    def set_error(self, error: str) -> None:
        """Set error state."""
        state = self.get_state()
        state.error = error
        self.save()

    def clear_error(self) -> None:
        """Clear error state."""
        state = self.get_state()
        state.error = None
        self.save()

    def update_quality_gate(
        self,
        gate_type: str,
        passed: bool,
        message: str = "",
        chapter_num: Optional[int] = None
    ) -> None:
        """
        Update a quality gate status.

        Args:
            gate_type: 'structure', 'continuity', or 'completion'
            passed: Whether the gate passed
            message: Optional message/reason
            chapter_num: For continuity gates, which chapter
        """
        state = self.get_state()
        now = datetime.now(timezone.utc).isoformat()

        if gate_type == 'structure':
            state.structure_gate = QualityGateStatus(
                name='STRUCTURE_GATE',
                passed=passed,
                message=message,
                checked_at=now
            )
        elif gate_type == 'continuity':
            gate = QualityGateStatus(
                name=f'CONTINUITY_GATE_CH{chapter_num}' if chapter_num else 'CONTINUITY_GATE',
                passed=passed,
                message=message,
                checked_at=now
            )
            # Update or append
            if chapter_num:
                # Replace existing gate for this chapter
                state.continuity_gates = [
                    g for g in state.continuity_gates
                    if not g.name.endswith(f'_CH{chapter_num}')
                ]
            state.continuity_gates.append(gate)
        elif gate_type == 'completion':
            state.completion_gate = QualityGateStatus(
                name='COMPLETION_GATE',
                passed=passed,
                message=message,
                checked_at=now
            )

        self.save()

    def reset(self) -> None:
        """Reset state to initial."""
        self._state = GenerationState()
        if self.state_file.exists():
            self.state_file.unlink()

    def detect_phase_from_files(self, project) -> GenerationPhase:
        """
        Detect current phase by examining project files.

        Handles both new structure plan system and legacy chapter beats.

        Args:
            project: Project instance

        Returns:
            Detected generation phase
        """
        # Check for prose - either chapters/ or story.md
        prose_chapters = list(project.chapters_dir.glob("chapter-*.md")) if project.chapters_dir.exists() else []
        has_story = project.story_file.exists() if hasattr(project, 'story_file') else False

        if prose_chapters or has_story:
            # For short stories, having story.md means complete
            if has_story and project.is_short_form():
                return GenerationPhase.COMPLETE
            # For novels, check if we have prose
            if prose_chapters:
                return GenerationPhase.PROSE

        # Check for structure plan (new system)
        structure_plan = project.path / "structure-plan.md"
        if structure_plan.exists():
            return GenerationPhase.PLAN

        # Check for legacy chapter beats (backward compatibility)
        chapter_beats = list(project.chapter_beats_dir.glob("chapter-*.md")) if project.chapter_beats_dir.exists() else []
        if chapter_beats:
            foundation = project.chapter_beats_dir / "foundation.md"
            if foundation.exists() or chapter_beats:
                return GenerationPhase.PLAN  # Map legacy chapters to PLAN phase

        if project.treatment_file.exists():
            return GenerationPhase.TREATMENT

        if project.premise_metadata_file.exists() or project.premise_file.exists():
            return GenerationPhase.PREMISE

        return GenerationPhase.IDLE
