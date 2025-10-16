"""Content culling (deletion) system for AgenticAuthor."""

from typing import Dict, Any, List
from pathlib import Path

from ..models import Project


class CullManager:
    """Manage culling (deletion) of generated content at various LOD levels."""

    def __init__(self, project: Project):
        """
        Initialize cull manager.

        Args:
            project: Current project
        """
        self.project = project

    def cull_prose(self) -> Dict[str, Any]:
        """
        Remove all prose files.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Find all chapter prose files
        if self.project.chapters_dir.exists():
            for prose_file in self.project.chapters_dir.glob("chapter-*.md"):
                prose_file.unlink()
                deleted_files.append(str(prose_file.relative_to(self.project.path)))

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }

    def cull_chapters(self) -> Dict[str, Any]:
        """
        Delete chapter-beats/ directory (foundation + all chapters) and cascade to prose.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete entire chapter-beats/ directory
        if self.project.chapter_beats_dir.exists():
            for beat_file in self.project.chapter_beats_dir.glob("*.yaml"):
                beat_file.unlink()
                deleted_files.append(str(beat_file.relative_to(self.project.path)))

            # Try to remove directory if empty
            try:
                self.project.chapter_beats_dir.rmdir()
            except OSError:
                pass  # Directory not empty, that's fine

        # Also delete legacy chapters.yaml if it exists
        legacy_chapters_file = self.project.path / "chapters.yaml"
        if legacy_chapters_file.exists():
            legacy_chapters_file.unlink()
            deleted_files.append("chapters.yaml")

        # Cascade: delete all prose
        prose_result = self.cull_prose()
        deleted_files.extend(prose_result['deleted_files'])

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }

    def cull_treatment(self) -> Dict[str, Any]:
        """
        Delete treatment/ directory and cascade to chapters + prose.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete entire treatment/ directory
        if self.project.treatment_dir.exists():
            for file in self.project.treatment_dir.glob("*"):
                file.unlink()
                deleted_files.append(str(file.relative_to(self.project.path)))

            # Try to remove directory if empty
            try:
                self.project.treatment_dir.rmdir()
            except OSError:
                pass  # Directory not empty, that's fine

        # Also delete legacy treatment.md if it exists at root
        legacy_treatment_file = self.project.path / "treatment.md"
        if legacy_treatment_file.exists():
            legacy_treatment_file.unlink()
            deleted_files.append("treatment.md")

        # Also delete legacy treatment_metadata.json if it exists at root
        legacy_treatment_metadata = self.project.path / "treatment_metadata.json"
        if legacy_treatment_metadata.exists():
            legacy_treatment_metadata.unlink()
            deleted_files.append("treatment_metadata.json")

        # Cascade: delete chapters and prose
        chapters_result = self.cull_chapters()
        deleted_files.extend(chapters_result['deleted_files'])

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }

    def cull_premise(self) -> Dict[str, Any]:
        """
        Delete premise/ directory and cascade all downstream.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete entire premise/ directory
        if self.project.premise_dir.exists():
            for file in self.project.premise_dir.glob("*"):
                file.unlink()
                deleted_files.append(str(file.relative_to(self.project.path)))

            # Try to remove directory if empty
            try:
                self.project.premise_dir.rmdir()
            except OSError:
                pass  # Directory not empty, that's fine

        # Also delete legacy files if they exist at root
        legacy_premise_file = self.project.path / "premise.md"
        if legacy_premise_file.exists():
            legacy_premise_file.unlink()
            deleted_files.append("premise.md")

        legacy_premise_metadata = self.project.path / "premise_metadata.json"
        if legacy_premise_metadata.exists():
            legacy_premise_metadata.unlink()
            deleted_files.append("premise_metadata.json")

        # Cascade: delete treatment, chapters, prose
        treatment_result = self.cull_treatment()
        deleted_files.extend(treatment_result['deleted_files'])

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }
