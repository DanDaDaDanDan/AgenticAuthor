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

    def cull_chapters(self) -> Dict[str, Any]:
        """
        Delete chapter-beats/ directory (foundation + all chapters) and cascade to prose.

        Also deletes chapter-beats-variants/ directory if present (multi-variant generation artifacts).

        Returns:
            Dict with deleted_files list
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        deleted_files = []

        # Helper to recursively collect and delete a directory tree
        def _rmtree_collect(root: Path) -> List[str]:
            collected: List[str] = []
            if not root.exists():
                return collected
            for p in root.rglob('*'):
                if p.is_file():
                    collected.append(str(p.relative_to(self.project.path)))
            shutil.rmtree(root, ignore_errors=True)
            return collected

        # Delete entire chapter-beats/ directory (finalized chapters)
        beats_dir = self.project.chapter_beats_dir

        if logger:
            logger.debug(f"Cull chapters: checking directory {beats_dir}")
            logger.debug(f"Directory exists: {beats_dir.exists()}")

        if beats_dir.exists():
            if logger:
                logger.debug(f"Deep deleting directory: {beats_dir}")
            deleted_files.extend(_rmtree_collect(beats_dir))

        # NEW: Delete chapter-beats-variants/ directory (multi-variant artifacts)
        variants_dir = self.project.path / 'chapter-beats-variants'

        if logger:
            logger.debug(f"Cull chapters: checking variants directory {variants_dir}")
            logger.debug(f"Variants directory exists: {variants_dir.exists()}")

        if variants_dir.exists():
            if logger:
                logger.debug(f"Deep deleting variants directory: {variants_dir}")
            deleted_files.extend(_rmtree_collect(variants_dir))

            # Delete shared foundation (both .md and .yaml for backward compatibility)
            for foundation_ext in ['.md', '.yaml']:
                foundation_file = variants_dir / f'foundation{foundation_ext}'
                if foundation_file.exists():
                    if logger:
                        logger.debug(f"Deleting variants foundation: {foundation_file}")
                    foundation_file.unlink()
                    deleted_files.append(str(foundation_file.relative_to(self.project.path)))

            # Delete decision.json if present
            decision_file = variants_dir / 'decision.json'
            if decision_file.exists():
                if logger:
                    logger.debug(f"Deleting decision file: {decision_file}")
                decision_file.unlink()
                deleted_files.append(str(decision_file.relative_to(self.project.path)))

            # Delete combined.md if present
            combined_file = variants_dir / 'combined.md'
            if combined_file.exists():
                if logger:
                    logger.debug(f"Deleting combined file: {combined_file}")
                combined_file.unlink()
                deleted_files.append(str(combined_file.relative_to(self.project.path)))

            # Try to remove variants directory
            try:
                variants_dir.rmdir()
                if logger:
                    logger.debug(f"Removed variants directory: {variants_dir}")
            except OSError as e:
                if logger:
                    logger.debug(f"Could not remove variants directory: {e}")

        # Also delete legacy chapters.yaml if it exists
        legacy_chapters_file = self.project.path / "chapters.yaml"
        if legacy_chapters_file.exists():
            if logger:
                logger.debug(f"Deleting legacy chapters.yaml")
            legacy_chapters_file.unlink()
            deleted_files.append("chapters.yaml")

        # Cascade: delete all prose
        prose_result = self.cull_prose()
        deleted_files.extend(prose_result['deleted_files'])

        if logger:
            logger.debug(f"Cull chapters complete: deleted {len(deleted_files)} files")

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
            deleted_files.extend(_rmtree_collect(self.project.treatment_dir))

        # Also delete legacy treatment.md if it exists at root
        legacy_treatment_file = self.project.path / "treatment.md"
        if legacy_treatment_file.exists():
            legacy_treatment_file.unlink()
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
        Delete premise/ directory and cascade all downstream.

        Returns:
            Dict with deleted_files list
        """
        deleted_files = []

        # Delete entire premise/ directory (deep)
        if self.project.premise_dir.exists():
            deleted_files.extend(_rmtree_collect(self.project.premise_dir))

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

        Returns:
            Dict with deleted_files list
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        deleted_files = []

        # .agentic directory path
        agentic_dir = self.project.path / '.agentic'

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

        # Recursively delete all files and subdirectories in .agentic/
        # Keep the .agentic directory itself
        def delete_recursively(directory: Path):
            """Helper to recursively delete all contents of a directory."""
            for item in directory.iterdir():
                if item.is_file():
                    if logger:
                        logger.debug(f"Deleting file: {item}")
                    item.unlink()
                    deleted_files.append(str(item.relative_to(self.project.path)))
                elif item.is_dir():
                    # Recursively delete subdirectory contents
                    delete_recursively(item)
                    # Remove the now-empty subdirectory
                    try:
                        item.rmdir()
                        if logger:
                            logger.debug(f"Removed directory: {item}")
                    except OSError as e:
                        if logger:
                            logger.debug(f"Could not remove directory {item}: {e}")

        delete_recursively(agentic_dir)

        if logger:
            logger.debug(f"Cull debug complete: deleted {len(deleted_files)} files")

        return {
            'deleted_files': deleted_files,
            'updated_files': [],
            'count': len(deleted_files)
        }
