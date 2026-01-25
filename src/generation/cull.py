"""Content culling (deletion) system for AgenticAuthor."""

from typing import Dict, Any, List
from pathlib import Path

from ..models import Project
import shutil


class CullManager:
    """Manage culling (deletion) of generated content at various LOD levels."""

    def __init__(self, project: Project):
        """
        Initialize cull manager.

        Args:
            project: Current project
        """
        self.project = project

    # === Shared helpers ===
    def _rmtree(self, root: Path, preserve_root: bool = False) -> List[str]:
        """Recursively delete a directory tree and collect deleted files.

        Args:
            root: Directory to delete (or whose contents to delete)
            preserve_root: If True, delete only contents and keep root dir

        Returns:
            List of file paths (relative to project root) that were deleted
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        deleted: List[str] = []
        if not root.exists():
            return deleted

        if preserve_root:
            # Delete children recursively, keep root
            for item in root.iterdir():
                if item.is_file():
                    if logger:
                        logger.debug(f"Deleting file: {item}")
                    item.unlink(missing_ok=True)
                    deleted.append(str(item.relative_to(self.project.path)))
                elif item.is_dir():
                    deleted.extend(self._rmtree(item, preserve_root=False))
            return deleted

        # Delete entire tree and collect files via rglob before removal
        for p in root.rglob('*'):
            if p.is_file():
                deleted.append(str(p.relative_to(self.project.path)))
        shutil.rmtree(root, ignore_errors=True)
        return deleted

    def cull_prose(self) -> Dict[str, Any]:
        """
        Deep-delete the chapters/ directory (all prose files and subfolders).

        Returns:
            Dict with deleted_files list
        """
        deleted_files: List[str] = []

        chapters_dir = self.project.chapters_dir
        if chapters_dir.exists():
            # Collect all files for reporting, then remove the tree
            for p in chapters_dir.rglob('*'):
                if p.is_file():
                    deleted_files.append(str(p.relative_to(self.project.path)))
            shutil.rmtree(chapters_dir, ignore_errors=True)

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }

    def cull_plan(self) -> Dict[str, Any]:
        """
        Delete structure-plan.md and cascade to prose.

        Returns:
            Dict with deleted_files list
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        deleted_files = []

        # Delete structure-plan.md
        plan_file = self.project.structure_plan_file
        if plan_file.exists():
            if logger:
                logger.debug(f"Deleting structure plan: {plan_file}")
            plan_file.unlink()
            deleted_files.append("structure-plan.md")

        # Cascade: delete all prose
        prose_result = self.cull_prose()
        deleted_files.extend(prose_result['deleted_files'])

        if logger:
            logger.debug(f"Cull plan complete: deleted {len(deleted_files)} files")

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

        # Delete entire treatment/ directory (deep)
        if self.project.treatment_dir.exists():
            deleted_files.extend(self._rmtree(self.project.treatment_dir))

        # Also delete legacy treatment.md if it exists at root
        legacy_treatment_file = self.project.path / "treatment.md"
        if legacy_treatment_file.exists():
            legacy_treatment_file.unlink()
            deleted_files.append("treatment.md")

        # Cascade: delete plan and prose
        plan_result = self.cull_plan()
        deleted_files.extend(plan_result['deleted_files'])

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

        # Delete entire premise/ directory (deep)
        if self.project.premise_dir.exists():
            deleted_files.extend(self._rmtree(self.project.premise_dir))

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

    def cull_debug(self) -> Dict[str, Any]:
        """
        Delete all files in .agentic/ directory (logs, debug files, history, etc.).

        This cleans up all debug artifacts, session logs, and temporary files
        without affecting generated content (premise, treatment, chapters, prose).

        NOTE: .agentic is centralized at the repository root (NOT inside books/project-name/).

        Returns:
            Dict with deleted_files list
        """
        from ..utils.logging import get_logger
        from pathlib import Path
        logger = get_logger()

        deleted_files = []

        # .agentic directory is at repository root (centralized for all projects)
        # Use relative path from current working directory (repository root)
        agentic_dir = Path('.agentic')

        if logger:
            logger.debug(f"Cull debug: checking directory {agentic_dir}")
            logger.debug(f"Directory exists: {agentic_dir.exists()}")

        if not agentic_dir.exists():
            if logger:
                logger.debug("Cull debug: .agentic directory does not exist, nothing to delete")
            return {
                'deleted_files': deleted_files,
                'updated_files': [],
                'count': 0
            }

        # Delete contents of .agentic/ but keep the folder
        deleted_files.extend(self._rmtree(agentic_dir, preserve_root=True))

        if logger:
            logger.debug(f"Cull debug complete: deleted {len(deleted_files)} files")

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }
