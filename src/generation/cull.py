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

        Also deletes chapter-beats-variants/ directory if present (multi-variant generation artifacts).

        Returns:
            Dict with deleted_files list
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        deleted_files = []

        # Delete entire chapter-beats/ directory (finalized chapters)
        beats_dir = self.project.chapter_beats_dir

        if logger:
            logger.debug(f"Cull chapters: checking directory {beats_dir}")
            logger.debug(f"Directory exists: {beats_dir.exists()}")

        if beats_dir.exists():
            # Explicitly delete foundation.yaml first
            foundation_file = beats_dir / "foundation.yaml"
            if foundation_file.exists():
                if logger:
                    logger.debug(f"Deleting foundation: {foundation_file}")
                foundation_file.unlink()
                deleted_files.append(str(foundation_file.relative_to(self.project.path)))

            # Delete all chapter-NN.yaml files
            chapter_files = sorted(beats_dir.glob("chapter-*.yaml"))
            if logger:
                logger.debug(f"Found {len(chapter_files)} chapter files")

            for chapter_file in chapter_files:
                if logger:
                    logger.debug(f"Deleting: {chapter_file}")
                chapter_file.unlink()
                deleted_files.append(str(chapter_file.relative_to(self.project.path)))

            # Delete any other .yaml files (catch-all)
            other_yaml = [f for f in beats_dir.glob("*.yaml") if f.exists()]
            for yaml_file in other_yaml:
                if logger:
                    logger.debug(f"Deleting other yaml: {yaml_file}")
                yaml_file.unlink()
                deleted_files.append(str(yaml_file.relative_to(self.project.path)))

            # Try to remove directory if empty
            try:
                beats_dir.rmdir()
                if logger:
                    logger.debug(f"Removed empty directory: {beats_dir}")
            except OSError as e:
                if logger:
                    logger.debug(f"Could not remove directory (not empty or error): {e}")

        # NEW: Delete chapter-beats-variants/ directory (multi-variant artifacts)
        variants_dir = self.project.path / 'chapter-beats-variants'

        if logger:
            logger.debug(f"Cull chapters: checking variants directory {variants_dir}")
            logger.debug(f"Variants directory exists: {variants_dir.exists()}")

        if variants_dir.exists():
            # Delete all variant-N/ subdirectories
            for variant_dir in variants_dir.glob('variant-*'):
                if variant_dir.is_dir():
                    # Delete all chapter files in this variant
                    for chapter_file in variant_dir.glob('*.yaml'):
                        if logger:
                            logger.debug(f"Deleting variant file: {chapter_file}")
                        chapter_file.unlink()
                        deleted_files.append(str(chapter_file.relative_to(self.project.path)))

                    # Remove variant directory
                    try:
                        variant_dir.rmdir()
                        if logger:
                            logger.debug(f"Removed variant directory: {variant_dir}")
                    except OSError as e:
                        if logger:
                            logger.debug(f"Could not remove variant directory: {e}")

            # Delete shared foundation.yaml
            foundation_file = variants_dir / 'foundation.yaml'
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
