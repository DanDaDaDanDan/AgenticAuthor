"""
Resume state management for tracking in-progress generation operations.

Enables resuming failed or interrupted generations with /resume command.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ResumeStateManager:
    """Manages resume state for in-progress generation operations."""

    def __init__(self, project_path: Path):
        """
        Initialize resume state manager.

        Args:
            project_path: Path to project directory
        """
        self.project_path = project_path
        self.state_file = project_path / '.agentic' / 'resume_state.json'
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def save_state(
        self,
        operation: str,
        parameters: Dict[str, Any],
        progress: Dict[str, Any]
    ):
        """
        Save current generation state for resume capability.

        Args:
            operation: Operation type (generate_chapters, generate_prose, iterate_chapters, etc.)
            parameters: Generation parameters (model, chapter_count, total_words, feedback, etc.)
            progress: Progress tracking (chapters_complete, last_chapter_attempted, etc.)
        """
        state = {
            'operation': operation,
            'started_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'parameters': parameters,
            'progress': progress,
            'resumable': True
        }

        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def update_progress(self, progress_updates: Dict[str, Any]):
        """
        Update progress portion of state without rewriting everything.

        Args:
            progress_updates: Dictionary of progress fields to update
        """
        state = self.load_state()
        if state:
            state['progress'].update(progress_updates)
            state['updated_at'] = datetime.now().isoformat()

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)

    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Load resume state if available.

        Returns:
            State dictionary or None if no state exists
        """
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def clear_state(self):
        """Clear resume state (called after successful completion)."""
        if self.state_file.exists():
            self.state_file.unlink()

    def validate_state(self) -> tuple[bool, Optional[str]]:
        """
        Validate that current state is actually resumable.

        Returns:
            Tuple of (is_valid, error_message)
        """
        state = self.load_state()
        if not state:
            return False, "No resume state found. Nothing to resume."

        operation = state.get('operation')
        progress = state.get('progress', {})

        # Validate based on operation type
        if operation == 'generate_chapters':
            return self._validate_chapter_generation_state(state, progress)
        elif operation == 'generate_prose':
            return self._validate_prose_generation_state(state, progress)
        elif operation == 'iterate_chapters':
            return self._validate_iteration_state(state, progress)
        else:
            return False, f"Unknown operation type: {operation}"

    def _validate_chapter_generation_state(
        self,
        state: Dict[str, Any],
        progress: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate chapter generation can be resumed."""
        # Check foundation exists
        foundation_file = self.project_path / 'chapter-beats' / 'foundation.yaml'
        if not foundation_file.exists():
            return False, "Foundation file missing. Cannot resume chapter generation."

        # Check if already complete
        chapters_complete = progress.get('chapters_complete', [])
        total_chapters = progress.get('total_chapters', 0)

        if len(chapters_complete) >= total_chapters:
            return False, "Chapter generation already complete. Nothing to resume."

        # Check that completed chapters exist
        for ch_num in chapters_complete:
            chapter_file = self.project_path / 'chapter-beats' / f'chapter-{ch_num:02d}.yaml'
            if not chapter_file.exists():
                return False, f"Chapter {ch_num} marked complete but file missing. State corrupted."

        return True, None

    def _validate_prose_generation_state(
        self,
        state: Dict[str, Any],
        progress: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate prose generation can be resumed."""
        # Check chapters.yaml exists
        chapters_file = self.project_path / 'chapters.yaml'
        if not chapters_file.exists():
            return False, "chapters.yaml missing. Cannot resume prose generation."

        # Check if already complete
        chapters_complete = progress.get('chapters_complete', [])
        total_chapters = progress.get('total_chapters', 0)

        if len(chapters_complete) >= total_chapters:
            return False, "Prose generation already complete. Nothing to resume."

        # Check that completed prose files exist
        chapters_dir = self.project_path / 'chapters'
        for ch_num in chapters_complete:
            prose_file = chapters_dir / f'chapter-{ch_num:02d}.md'
            if not prose_file.exists():
                return False, f"Chapter {ch_num} prose marked complete but file missing. State corrupted."

        return True, None

    def _validate_iteration_state(
        self,
        state: Dict[str, Any],
        progress: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate iteration can be resumed."""
        # Iterations are typically atomic (all-or-nothing)
        # If we have state, it means iteration failed midway
        # This is trickier to resume - for now, don't support it
        return False, "Iteration resume not yet supported. Please run /iterate again."

    def get_resume_info(self) -> Optional[str]:
        """
        Get human-readable resume information.

        Returns:
            Formatted string describing what can be resumed, or None
        """
        state = self.load_state()
        if not state:
            return None

        is_valid, error = self.validate_state()
        if not is_valid:
            return None

        operation = state.get('operation')
        parameters = state.get('parameters', {})
        progress = state.get('progress', {})

        if operation == 'generate_chapters':
            chapters_complete = progress.get('chapters_complete', [])
            total_chapters = progress.get('total_chapters', 0)
            next_chapter = len(chapters_complete) + 1

            model = parameters.get('model', 'unknown')
            return (
                f"Resume: Chapter generation ({next_chapter}/{total_chapters})\n"
                f"  Model: {model}\n"
                f"  Completed: {len(chapters_complete)} chapters\n"
                f"  Next: Chapter {next_chapter}"
            )

        elif operation == 'generate_prose':
            chapters_complete = progress.get('chapters_complete', [])
            total_chapters = progress.get('total_chapters', 0)
            next_chapter = len(chapters_complete) + 1

            model = parameters.get('model', 'unknown')
            return (
                f"Resume: Prose generation ({next_chapter}/{total_chapters})\n"
                f"  Model: {model}\n"
                f"  Completed: {len(chapters_complete)} chapters\n"
                f"  Next: Chapter {next_chapter}"
            )

        return None
