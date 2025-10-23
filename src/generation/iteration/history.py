"""Iteration history management."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class IterationHistory:
    """Manages iteration history for a specific LOD level."""

    def __init__(self, history_file: Path):
        """
        Initialize iteration history.

        Args:
            history_file: Path to iteration_history.json file
        """
        self.history_file = history_file
        self.iterations: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load iteration history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.iterations = data.get('iterations', [])
            except Exception:
                # If file is corrupted, start fresh
                self.iterations = []

    def save(self):
        """Save iteration history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump({'iterations': self.iterations}, f, indent=2)

    def add_iteration(
        self,
        feedback: str,
        judge_attempts: int,
        judge_verdict: str,
        judge_reasoning: str,
        semantic_summary: str,
        commit_sha: str,
        files_changed: int,
        lines_changed: int
    ):
        """
        Add a new iteration to history.

        Args:
            feedback: User feedback text
            judge_attempts: Number of judge validation attempts
            judge_verdict: Final judge verdict (approved/rejected)
            judge_reasoning: Judge's reasoning
            semantic_summary: LLM-generated semantic diff summary
            commit_sha: Git commit SHA
            files_changed: Number of files changed
            lines_changed: Total lines changed (±)
        """
        iteration = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'feedback': feedback,
            'judge_attempts': judge_attempts,
            'judge_verdict': judge_verdict,
            'judge_reasoning': judge_reasoning,
            'semantic_summary': semantic_summary,
            'commit_sha': commit_sha,
            'files_changed': files_changed,
            'lines_changed': lines_changed
        }

        self.iterations.append(iteration)
        self.save()

    def get_context_for_llm(self) -> List[Dict[str, str]]:
        """
        Get iteration history formatted for LLM context.

        Returns:
            List of dicts with feedback and semantic_summary
        """
        return [
            {
                'feedback': it['feedback'],
                'semantic_summary': it['semantic_summary']
            }
            for it in self.iterations
        ]

    def get_summary(self) -> str:
        """
        Get a human-readable summary of iteration history.

        Returns:
            Formatted string summary
        """
        if not self.iterations:
            return "No previous iterations"

        lines = []
        for i, it in enumerate(self.iterations, 1):
            timestamp = it['timestamp'][:19]  # Remove microseconds
            feedback = it['feedback']
            if len(feedback) > 60:
                feedback = feedback[:57] + "..."
            lines.append(f"{i}. ({timestamp}) {feedback}")

        return "\n".join(lines)

    def count(self) -> int:
        """Get number of iterations."""
        return len(self.iterations)
