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
        Delete chapters.yaml and cascade to prose.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete chapters.yaml
        chapters_file = self.project.path / "chapters.yaml"
        if chapters_file.exists():
            chapters_file.unlink()
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
        Delete treatment.md and cascade to chapters + prose.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete treatment.md
        treatment_file = self.project.path / "treatment.md"
        if treatment_file.exists():
            treatment_file.unlink()
            deleted_files.append("treatment.md")

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
        Delete premise.md, premise_metadata.json, and cascade all downstream.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete premise.md
        premise_file = self.project.path / "premise.md"
        if premise_file.exists():
            premise_file.unlink()
            deleted_files.append("premise.md")

        # Delete premise_metadata.json
        metadata_file = self.project.premise_metadata_file
        if metadata_file.exists():
            metadata_file.unlink()
            deleted_files.append(str(metadata_file.relative_to(self.project.path)))

        # Cascade: delete treatment, chapters, prose
        treatment_result = self.cull_treatment()
        deleted_files.extend(treatment_result['deleted_files'])

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }
