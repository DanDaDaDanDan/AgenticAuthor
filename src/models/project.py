"""Project data models."""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
import json
import yaml


class ProjectMetadata(BaseModel):
    """Project metadata and configuration."""

    name: str = Field(description="Project name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    story_type: Optional[str] = Field(None, description="Story type: short_form or long_form")
    book_metadata: Dict[str, Any] = Field(default_factory=dict, description="Book metadata (title, author, copyright_year)")
    genre: Optional[str] = Field(None, description="Genre from premise taxonomy")

    def update_timestamp(self):
        """Update the last modified timestamp."""
        self.updated_at = datetime.now(timezone.utc)


class Project:
    """Represents a book project with all its files and metadata."""

    def __init__(self, path: Path):
        """
        Initialize a project from a directory path.

        Args:
            path: Path to the project directory
        """
        self.path = Path(path).resolve()
        self.name = self.path.name
        self.metadata: Optional[ProjectMetadata] = None
        self._load_metadata()
        self._migrate_legacy_files()

    @property
    def project_file(self) -> Path:
        """Get path to project.yaml file."""
        return self.path / "project.yaml"

    @property
    def premise_dir(self) -> Path:
        """Get path to premise directory."""
        return self.path / "premise"

    @property
    def premise_file(self) -> Path:
        """Get path to premise.md file (legacy - for backward compatibility)."""
        return self.path / "premise.md"

    @property
    def premise_metadata_file(self) -> Path:
        """Get path to premise_metadata.json file."""
        return self.premise_dir / "premise_metadata.json"

    @property
    def premises_file(self) -> Path:
        """Get path to premises_candidates.json file (for batch generation)."""
        return self.premise_dir / "premises_candidates.json"

    @property
    def treatment_dir(self) -> Path:
        """Get path to treatment directory."""
        return self.path / "treatment"

    @property
    def treatment_file(self) -> Path:
        """Get path to treatment.md file."""
        return self.treatment_dir / "treatment.md"

    @property
    def structure_plan_file(self) -> Path:
        """Get path to structure-plan.md file."""
        return self.path / "structure-plan.md"

    @property
    def chapters_dir(self) -> Path:
        """Get path to chapters directory (original prose files)."""
        return self.path / "chapters"

    @property
    def chapters_edited_dir(self) -> Path:
        """Get path to chapters-edited directory (copy-edited prose files)."""
        return self.path / "chapters-edited"

    @property
    def story_file(self) -> Path:
        """Get path to story.md file (for short-form stories)."""
        return self.path / "story.md"

    @property
    def analysis_dir(self) -> Path:
        """Get path to analysis directory."""
        return self.path / "analysis"

    @property
    def exports_dir(self) -> Path:
        """Get path to exports directory."""
        return self.path / "exports"

    @property
    def frontmatter_file(self) -> Path:
        """Get path to frontmatter.md file."""
        return self.exports_dir / "frontmatter.md"

    @property
    def dedication_file(self) -> Path:
        """Get path to dedication.md file."""
        return self.exports_dir / "dedication.md"

    @property
    def publishing_metadata_file(self) -> Path:
        """Get path to publishing-metadata.md file (KDP metadata)."""
        return self.exports_dir / "publishing-metadata.md"

    @property
    def config_file(self) -> Path:
        """
        DEPRECATED: config.yaml is now merged into project.yaml.

        This property is kept for backward compatibility during migration.
        """
        return self.path / "config.yaml"

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid project directory."""
        return self.path.exists() and self.project_file.exists()

    def _sync_genre_from_premise(self):
        """
        Sync genre from premise_metadata into project metadata.

        Genre is stored in premise_metadata.json as part of taxonomy selections.
        This method extracts it and populates project.metadata.genre for convenience.
        """
        if not self.metadata:
            return

        premise_metadata = self.get_premise_metadata()
        if not premise_metadata:
            return

        # Try to get genre from premise_metadata
        genre = premise_metadata.get('genre')

        # If not directly specified, try to infer from taxonomy selections
        if not genre:
            selections = premise_metadata.get('selections', {})
            if selections:
                from ..generation.taxonomies import TaxonomyLoader
                genre = TaxonomyLoader.infer_genre_from_selections(selections)

        # Update project metadata if genre found
        if genre and genre != self.metadata.genre:
            self.metadata.genre = genre

    def _load_metadata(self):
        """
        Load project metadata from project.yaml.

        Automatically migrates from old split structure (config.yaml + project.yaml)
        to new merged structure (single project.yaml with book_metadata).
        """
        if self.project_file.exists():
            with open(self.project_file) as f:
                data = yaml.safe_load(f)

                # Migration: Remove deprecated fields
                deprecated_fields = ['model', 'status', 'word_count',
                                   'chapter_count', 'tags', 'iteration_target', 'custom_data']
                for field in deprecated_fields:
                    data.pop(field, None)

                # Migration: Merge config.yaml into project.yaml if config exists
                if self.config_file.exists() and 'book_metadata' not in data:
                    config = self._load_config()
                    if 'book_metadata' in config:
                        data['book_metadata'] = config['book_metadata']

                self.metadata = ProjectMetadata(**data)

                # Sync genre from premise_metadata if available
                self._sync_genre_from_premise()

                # Save migrated data if any changes were made
                if any(field in yaml.safe_load(self.project_file.read_text()) for field in deprecated_fields):
                    self.save_metadata()

    def _migrate_legacy_files(self):
        """
        Migrate legacy file structure to new folder-based structure.

        Old structure:
        - config.yaml (book metadata) + project.yaml (project metadata) - SEPARATE FILES
        - premise_metadata.json (root)
        - premises_candidates.json (root)
        - treatment.md (root)
        - frontmatter.md (root)
        - dedication.md (root)
        - publishing-metadata.md (root)

        New structure:
        - project.yaml (merged: project metadata + book metadata) - SINGLE FILE
        - premise/premise_metadata.json
        - premise/premises_candidates.json
        - treatment/treatment.md
        - exports/frontmatter.md
        - exports/dedication.md
        - exports/publishing-metadata.md

        This migration is idempotent and safe to run multiple times.
        """
        # Migrate premise_metadata.json
        old_premise_metadata = self.path / "premise_metadata.json"
        if old_premise_metadata.exists() and not self.premise_metadata_file.exists():
            self.premise_dir.mkdir(exist_ok=True)
            old_premise_metadata.rename(self.premise_metadata_file)

        # Migrate premises_candidates.json
        old_premises = self.path / "premises_candidates.json"
        if old_premises.exists() and not self.premises_file.exists():
            self.premise_dir.mkdir(exist_ok=True)
            old_premises.rename(self.premises_file)

        # Migrate treatment.md
        old_treatment = self.path / "treatment.md"
        if old_treatment.exists() and not self.treatment_file.exists():
            self.treatment_dir.mkdir(exist_ok=True)
            old_treatment.rename(self.treatment_file)

        # Migrate frontmatter.md
        old_frontmatter = self.path / "frontmatter.md"
        if old_frontmatter.exists() and not self.frontmatter_file.exists():
            self.exports_dir.mkdir(exist_ok=True)
            old_frontmatter.rename(self.frontmatter_file)

        # Migrate dedication.md
        old_dedication = self.path / "dedication.md"
        if old_dedication.exists() and not self.dedication_file.exists():
            self.exports_dir.mkdir(exist_ok=True)
            old_dedication.rename(self.dedication_file)

        # Migrate publishing-metadata.md
        old_publishing_metadata = self.path / "publishing-metadata.md"
        if old_publishing_metadata.exists() and not self.publishing_metadata_file.exists():
            self.exports_dir.mkdir(exist_ok=True)
            old_publishing_metadata.rename(self.publishing_metadata_file)

        # Migrate config.yaml into project.yaml (book_metadata merge)
        # This is handled by _load_metadata(), but we delete config.yaml here after migration
        if self.config_file.exists() and self.metadata and self.metadata.book_metadata:
            # config.yaml has been merged into project.yaml, safe to delete
            self.config_file.unlink()


    def save_metadata(self):
        """Save project metadata to project.yaml."""
        if not self.metadata:
            self.metadata = ProjectMetadata(name=self.name)

        self.metadata.update_timestamp()

        # Ensure directory exists
        self.path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        with open(self.project_file, 'w') as f:
            yaml.dump(
                self.metadata.model_dump(exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False
            )

    def get_premise(self) -> Optional[str]:
        """
        Load premise content.

        Reads from premise_metadata.json (single source of truth).
        Falls back to premise.md for backward compatibility with old projects.
        """
        # Try new format first (JSON only)
        metadata = self.get_premise_metadata()
        if metadata and 'premise' in metadata:
            return metadata['premise']

        # Fall back to old format (premise.md) for backward compatibility
        if self.premise_file.exists():
            return self.premise_file.read_text(encoding='utf-8')

        return None

    def get_premise_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Load full premise metadata including taxonomy selections.

        Returns dict with: premise, protagonist, antagonist, stakes, hook, themes, selections
        Returns None if file doesn't exist.
        """
        if self.premise_metadata_file.exists():
            with open(self.premise_metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_premise(self, content: str):
        """
        DEPRECATED: Use save_premise_metadata() instead.

        This method is kept for backward compatibility but should not be used.
        It only saves premise.md which creates duplication and inconsistency.
        """
        # For backward compatibility, still write premise.md
        # But warn that this is deprecated
        import warnings
        warnings.warn(
            "save_premise() is deprecated. Use save_premise_metadata() to save premise with full metadata.",
            DeprecationWarning,
            stacklevel=2
        )
        self.premise_file.write_text(content, encoding='utf-8')
        if self.metadata:
            self.metadata.update_timestamp()

    def save_premise_metadata(self, metadata: Dict[str, Any]):
        """
        Save premise metadata (single source of truth).

        Args:
            metadata: Dict with premise, protagonist, antagonist, stakes, hook, themes, selections

        Writes only to premise_metadata.json. Does NOT write premise.md.
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== PROJECT: save_premise_metadata START ===")
            logger.info(f"PROJECT: Writing to: {self.premise_metadata_file}")
            logger.debug(f"PROJECT: Metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'NOT A DICT'}")
            if isinstance(metadata, dict) and 'premise' in metadata:
                logger.debug(f"PROJECT: Premise length: {len(metadata['premise'])} chars")
                logger.debug(f"PROJECT: Premise preview: {metadata['premise'][:100]}...")

        try:
            # Ensure premise directory exists
            self.premise_dir.mkdir(exist_ok=True)

            with open(self.premise_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            if logger:
                logger.info(f"PROJECT: Successfully wrote premise_metadata.json")

            # Sync genre from premise metadata
            if self.metadata:
                self._sync_genre_from_premise()
                self.metadata.update_timestamp()
                self.save_metadata()

                if logger:
                    logger.info(f"PROJECT: Updated project metadata timestamp and synced genre")

        except Exception as e:
            if logger:
                logger.error(f"PROJECT: Exception while saving: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"PROJECT: Traceback: {traceback.format_exc()}")
            raise

        if logger:
            logger.info(f"=== PROJECT: save_premise_metadata END ===")
            # Verify file was written
            if self.premise_metadata_file.exists():
                file_size = self.premise_metadata_file.stat().st_size
                logger.info(f"PROJECT: File verified on disk: {file_size} bytes")
            else:
                logger.error(f"PROJECT: FILE NOT FOUND after write - this is a BUG!")

    def get_treatment(self) -> Optional[str]:
        """Load treatment content."""
        if self.treatment_file.exists():
            return self.treatment_file.read_text(encoding='utf-8')
        return None

    def save_treatment(self, content: str):
        """Save treatment content."""
        # Ensure treatment directory exists
        self.treatment_dir.mkdir(exist_ok=True)

        self.treatment_file.write_text(content, encoding='utf-8')
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_structure_plan(self) -> Optional[str]:
        """Load structure plan content."""
        if self.structure_plan_file.exists():
            return self.structure_plan_file.read_text(encoding='utf-8')
        return None

    def save_structure_plan(self, content: str):
        """Save structure plan content."""
        self.structure_plan_file.write_text(content, encoding='utf-8')
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_taxonomy(self) -> Optional[Dict[str, Any]]:
        """Load taxonomy selections from premise metadata."""
        if self.premise_metadata_file.exists():
            with open(self.premise_metadata_file) as f:
                data = json.load(f)
                if data and isinstance(data, dict):
                    return data.get('selections')
        return None

    def get_chapter(self, chapter_num: int) -> Optional[str]:
        """
        Load a specific chapter's content.

        Args:
            chapter_num: Chapter number (1-based)

        Returns:
            Chapter content or None if not found
        """
        chapter_file = self.chapters_dir / f"chapter-{chapter_num:02d}.md"
        if chapter_file.exists():
            return chapter_file.read_text(encoding='utf-8')
        return None

    def save_chapter(self, chapter_num: int, content: str):
        """
        Save a chapter's content.

        Args:
            chapter_num: Chapter number (1-based)
            content: Chapter content
        """
        # Ensure chapters directory exists
        self.chapters_dir.mkdir(exist_ok=True)

        chapter_file = self.chapters_dir / f"chapter-{chapter_num:02d}.md"
        chapter_file.write_text(content, encoding='utf-8')

        # Update timestamp
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def list_chapters(self) -> List[Path]:
        """List all chapter files (original prose)."""
        if not self.chapters_dir.exists():
            return []
        return sorted(self.chapters_dir.glob("chapter-*.md"))

    def get_edited_chapter(self, chapter_num: int) -> Optional[str]:
        """
        Load a specific edited chapter's content.

        Args:
            chapter_num: Chapter number (1-based)

        Returns:
            Edited chapter content or None if not found
        """
        chapter_file = self.chapters_edited_dir / f"chapter-{chapter_num:02d}.md"
        if chapter_file.exists():
            return chapter_file.read_text(encoding='utf-8')
        return None

    def save_edited_chapter(self, chapter_num: int, content: str):
        """
        Save an edited chapter's content to chapters-edited/ folder.

        Args:
            chapter_num: Chapter number (1-based)
            content: Edited chapter content
        """
        # Ensure chapters-edited directory exists
        self.chapters_edited_dir.mkdir(exist_ok=True)

        chapter_file = self.chapters_edited_dir / f"chapter-{chapter_num:02d}.md"
        chapter_file.write_text(content, encoding='utf-8')

        # Update timestamp
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def list_edited_chapters(self) -> List[Path]:
        """List all edited chapter files."""
        if not self.chapters_edited_dir.exists():
            return []
        return sorted(self.chapters_edited_dir.glob("chapter-*.md"))

    def get_story(self) -> Optional[str]:
        """
        Load short-form story content from story.md.

        Returns:
            Story content or None if not found
        """
        if self.story_file.exists():
            return self.story_file.read_text(encoding='utf-8')
        return None

    def save_story(self, content: str):
        """
        Save short-form story content to story.md.

        Args:
            content: Story prose content
        """
        self.story_file.write_text(content, encoding='utf-8')

        # Update timestamp
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_target_words(self) -> Optional[int]:
        """
        Get target word count using intelligent defaults based on taxonomy.

        Priority:
        1. Calculate from taxonomy (length_scope + genre)
        2. None (caller should handle)

        Returns:
            Target word count or None if cannot be determined
        """
        # Calculate from taxonomy if available
        if self.premise_metadata_file.exists():
            with open(self.premise_metadata_file) as f:
                data = json.load(f)

                # Get selections (taxonomy)
                selections = data.get('selections', {})
                if selections:
                    # Extract length_scope
                    length_scope = selections.get('length_scope')
                    if isinstance(length_scope, list) and length_scope:
                        length_scope = length_scope[0]

                    # Extract genre (with fallback detection from taxonomy)
                    genre = data.get('genre')
                    if not genre and self.metadata:
                        genre = self.metadata.genre

                    # Infer genre from taxonomy selections if not explicitly set
                    if not genre:
                        from ..generation.taxonomies import TaxonomyLoader
                        genre = TaxonomyLoader.infer_genre_from_selections(selections)

                    if length_scope:
                        # Use DepthCalculator to get intelligent default
                        from ..generation.depth_calculator import DepthCalculator
                        return DepthCalculator.get_default_word_count(length_scope, genre)

        # No information available
        return None

    def is_short_form(self) -> bool:
        """
        Detect if this is a short-form story.

        Short-form stories (flash fiction, short story) use story.md.
        Long-form stories use chapters/ directory with chapter-NN.md files.

        Returns:
            True if short-form, False otherwise
        """
        # Check cached story_type in metadata
        if self.metadata and self.metadata.story_type:
            return self.metadata.story_type == 'short_form'

        # Detect from files (for backward compatibility)
        # If story.md exists, it's short-form
        if self.story_file.exists():
            return True

        # If chapters/ directory exists with files, it's long-form
        if self.chapters_dir.exists() and list(self.chapters_dir.glob('chapter-*.md')):
            return False

        # Detect from target word count
        target_words = self.get_target_words()
        if target_words:
            # Short-form: ≤7,500 words (flash fiction + short story)
            # Long-form: >7,500 words (novelette + novella + novel)
            # This matches the taxonomy boundary between short_story and novelette
            is_short = target_words <= 7500

            # Cache the result in metadata
            if self.metadata:
                self.metadata.story_type = 'short_form' if is_short else 'long_form'
                self.save_metadata()

            return is_short

        # Default: if no information, assume long-form for safety
        return False

    def get_analysis(self, analysis_type: str) -> Optional[str]:
        """
        Load analysis content.

        Args:
            analysis_type: Type of analysis (e.g., 'commercial', 'plot')

        Returns:
            Analysis content or None if not found
        """
        analysis_file = self.analysis_dir / f"{analysis_type}.md"
        if analysis_file.exists():
            return analysis_file.read_text(encoding='utf-8')
        return None

    def save_analysis(self, analysis_type: str, content: str):
        """
        Save analysis content.

        Args:
            analysis_type: Type of analysis
            content: Analysis content
        """
        # Ensure analysis directory exists
        self.analysis_dir.mkdir(exist_ok=True)

        analysis_file = self.analysis_dir / f"{analysis_type}.md"
        analysis_file.write_text(content, encoding='utf-8')

    @classmethod
    def create(
        cls,
        path: Path,
        name: Optional[str] = None,
        **metadata_kwargs
    ) -> "Project":
        """
        Create a new project.

        Args:
            path: Path where project should be created
            name: Project name (uses directory name if not provided)
            **metadata_kwargs: Additional metadata fields

        Returns:
            New Project instance
        """
        path = Path(path).resolve()
        path.mkdir(parents=True, exist_ok=True)

        # Create project metadata
        project_name = name or path.name
        metadata = ProjectMetadata(name=project_name, **metadata_kwargs)

        # Save metadata
        project = cls(path)
        project.metadata = metadata
        project.save_metadata()

        # Create subdirectories
        project.premise_dir.mkdir(exist_ok=True)
        project.treatment_dir.mkdir(exist_ok=True)
        project.chapters_dir.mkdir(exist_ok=True)
        project.analysis_dir.mkdir(exist_ok=True)
        project.exports_dir.mkdir(exist_ok=True)

        return project

    def clone(self, new_path: Path, new_name: Optional[str] = None) -> "Project":
        """
        Clone this project to a new location.

        Args:
            new_path: Path where cloned project should be created
            new_name: Name for the cloned project (uses directory name if not provided)

        Returns:
            New Project instance

        Raises:
            FileExistsError: If destination already exists
        """
        import shutil

        new_path = Path(new_path).resolve()

        # Check if destination exists
        if new_path.exists():
            raise FileExistsError(f"Destination already exists: {new_path}")

        # Copy entire project directory
        shutil.copytree(self.path, new_path)

        # Load the cloned project
        cloned_project = Project(new_path)

        # Update metadata with new name and timestamp
        if cloned_project.metadata:
            cloned_project.metadata.name = new_name or new_path.name
            cloned_project.metadata.created_at = datetime.now(timezone.utc)
            cloned_project.metadata.updated_at = datetime.now(timezone.utc)
            cloned_project.save_metadata()

        return cloned_project

    # --- Book Metadata Methods ---

    def _load_config(self) -> Dict[str, Any]:
        """
        DEPRECATED: Load config.yaml file (for backward compatibility).

        New code should use self.metadata.book_metadata instead.
        """
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_config(self, config: Dict[str, Any]):
        """
        DEPRECATED: Save config.yaml file (for backward compatibility).

        New code should use self.metadata.book_metadata and self.save_metadata() instead.
        """
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def get_book_metadata(self, key: Optional[str] = None, default=None):
        """
        Get book metadata from project.yaml (merged structure).

        Args:
            key: Specific metadata key, or None for all metadata
            default: Default value if key not found

        Returns:
            Single value if key specified, dict if key is None
        """
        if not self.metadata:
            return default if key else {}

        book_meta = self.metadata.book_metadata

        if key is None:
            return book_meta
        return book_meta.get(key, default)

    def set_book_metadata(self, key: str, value):
        """
        Set book metadata value in project.yaml (merged structure).

        Args:
            key: Metadata key
            value: Metadata value
        """
        if not self.metadata:
            self.metadata = ProjectMetadata(name=self.name)

        self.metadata.book_metadata[key] = value
        self.save_metadata()

    def has_required_metadata(self) -> bool:
        """
        Check if required metadata (title, author) is set.

        Returns:
            True if title and author are non-empty
        """
        title = self.get_book_metadata('title', '')
        author = self.get_book_metadata('author', '')
        return bool(title and author)

    def init_default_book_metadata(self):
        """Initialize book metadata with default values if not exists."""
        from datetime import datetime
        if not self.metadata:
            self.metadata = ProjectMetadata(name=self.name)

        if not self.metadata.book_metadata:
            self.metadata.book_metadata = {
                'title': '',
                'author': '',
                'copyright_year': datetime.now().year
            }
            self.save_metadata()

    # --- Frontmatter Methods ---

    def get_frontmatter(self) -> Optional[str]:
        """
        Get frontmatter content.

        Returns:
            Frontmatter text, or None if not exists
        """
        if self.frontmatter_file.exists():
            return self.frontmatter_file.read_text(encoding='utf-8')
        return None

    def save_frontmatter(self, content: str):
        """
        Save frontmatter content.

        Args:
            content: Frontmatter markdown text
        """
        # Ensure exports directory exists
        self.exports_dir.mkdir(exist_ok=True)
        self.frontmatter_file.write_text(content, encoding='utf-8')

    def get_dedication(self) -> Optional[str]:
        """
        Get dedication content.

        Returns:
            Dedication text, or None if not exists
        """
        if self.dedication_file.exists():
            return self.dedication_file.read_text(encoding='utf-8')
        return None

    def save_dedication(self, content: str):
        """
        Save dedication content.

        Args:
            content: Dedication text
        """
        # Ensure exports directory exists
        self.exports_dir.mkdir(exist_ok=True)
        self.dedication_file.write_text(content, encoding='utf-8')

    # --- Combined Context ---
    def write_combined_markdown(self, target: str, include_prose: bool = False) -> Path:
        """Write a combined.md for a specific folder target.

        Args:
            target: One of: 'treatment', 'chapters'
            include_prose: When target='chapters', include chapter prose

        Returns:
            Path written
        """
        lines: list[str] = []
        lines.append(f"# Combined Context — {self.name} — {target}")
        lines.append("")

        # Premise
        premise = self.get_premise()
        if premise:
            lines.append("## Premise")
            lines.append("")
            lines.append(premise.strip())
            lines.append("")

        # Taxonomy selections
        selections = self.get_taxonomy() or {}
        if selections:
            try:
                import yaml as _yaml
                taxo_yaml = _yaml.dump({'selections': selections}, sort_keys=False, allow_unicode=True)
            except Exception:
                taxo_yaml = str(selections)
            lines.append("## Taxonomy Selections")
            lines.append("")
            lines.append("```yaml")
            lines.append(taxo_yaml.strip())
            lines.append("```")
            lines.append("")

        # Treatment
        treatment = self.get_treatment()
        if treatment:
            lines.append("## Treatment")
            lines.append("")
            lines.append(treatment.strip())
            lines.append("")

        # Structure Plan
        structure_plan = self.get_structure_plan()
        if structure_plan:
            lines.append("## Structure Plan")
            lines.append("")
            lines.append(structure_plan.strip())
            lines.append("")

        # Prose (optional)
        if include_prose and self.chapters_dir.exists():
            prose_files = sorted(self.chapters_dir.glob("chapter-*.md"))
            if prose_files:
                lines.append("## Prose (Generated Chapters)")
                lines.append("")
                for pf in prose_files:
                    try:
                        lines.append(f"---\n\n{pf.read_text(encoding='utf-8').strip()}\n")
                    except Exception:
                        continue
                lines.append("")

        # Determine output folder by target
        if target == 'treatment':
            out_dir = self.treatment_dir
        elif target == 'chapters':
            out_dir = self.chapters_dir
        else:
            raise ValueError(f"Unknown combined target: {target}")

        out_dir.mkdir(exist_ok=True)
        combined_path = out_dir / "combined.md"
        combined_path.write_text("\n".join(lines).strip() + "\n", encoding='utf-8')
        return combined_path

    def split_combined_markdown(self, target: str) -> tuple[int, int, int]:
        """
        Split combined.md back into individual chapter files.

        Parses combined.md and writes chapter-*.md files for prose.

        IMPORTANT: Deletes existing chapter-*.md files before writing new ones
        to handle cases where the new version has fewer chapters.

        Args:
            target: Must be 'prose'

        Returns:
            Tuple of (files_written, chapters_written, files_deleted)

        Raises:
            FileNotFoundError: If combined.md doesn't exist
            ValueError: If target is invalid or content can't be parsed
        """
        if target != 'prose':
            raise ValueError(f"Invalid target for split: {target}. Use 'prose'")

        source_dir = self.chapters_dir
        combined_path = source_dir / "combined.md"
        if not combined_path.exists():
            raise FileNotFoundError(f"No combined.md found in {source_dir}")

        # Read combined.md
        content = combined_path.read_text(encoding='utf-8')

        # Delete existing chapter-*.md files before writing new ones
        files_deleted = 0
        for old_chapter_file in source_dir.glob('chapter-*.md'):
            old_chapter_file.unlink()
            files_deleted += 1

        files_written = 0
        chapters_written = 0

        # Find ## Prose section and split chapters
        section_marker = "## Prose (Generated Chapters)"
        if section_marker not in content:
            raise ValueError(f"Could not find '{section_marker}' section in combined.md")

        section_start = content.index(section_marker) + len(section_marker)
        section_content = content[section_start:].strip()

        # Remove leading --- if present
        if section_content.startswith('---'):
            section_content = section_content[3:].strip()

        # Split by \n---\n pattern
        chapter_sections = [s.strip() for s in section_content.split('\n---\n') if s.strip()]

        if not chapter_sections:
            raise ValueError("No prose chapters found")

        # Write chapter files
        for i, chapter_content in enumerate(chapter_sections, 1):
            chapter_file = source_dir / f"chapter-{i:02d}.md"
            chapter_file.write_text(chapter_content + "\n", encoding='utf-8')
            files_written += 1
            chapters_written += 1

        return (files_written, chapters_written, files_deleted)

    def init_default_frontmatter(self):
        """Initialize frontmatter with default template if not exists."""
        if not self.frontmatter_file.exists():
            template = self._get_default_frontmatter_template()
            self.save_frontmatter(template)

    def _get_default_frontmatter_template(self) -> str:
        """Get default frontmatter template with placeholders."""
        return """---
# Frontmatter Template for {{title}}
# Edit sections as needed. Delete sections you don't want.
# Variables: {{title}}, {{author}}, {{copyright_year}}
---

## Title Page

{{title}}

by {{author}}

---

## Copyright

Copyright © {{copyright_year}} by {{author}}

All rights reserved. No part of this book may be reproduced in any form or by any electronic or mechanical means, including information storage and retrieval systems, without permission in writing from the author, except by a reviewer who may quote brief passages in a review.

This is a work of fiction. Names, characters, places, and incidents are either the product of the author's imagination or are used fictitiously. Any resemblance to actual persons, living or dead, events, or locales is entirely coincidental.

---

## Dedication

[Your dedication here, or delete this section]

---

## Acknowledgments

[Your acknowledgments here, or delete this section]
"""

    # --- Export Methods ---

    def ensure_exports_dir(self):
        """Ensure exports directory exists."""
        self.exports_dir.mkdir(exist_ok=True)

    def get_export_path(self, format_name: str) -> Path:
        """
        Get default export file path for given format with timestamp.

        Args:
            format_name: Format extension (rtf, md, html, etc.)

        Returns:
            Path to export file in exports/ directory with timestamp
        """
        from datetime import datetime

        self.ensure_exports_dir()
        title = self.get_book_metadata('title', self.name)
        # Create safe filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))
        safe_title = safe_title.replace(' ', '-').lower()
        if not safe_title:
            safe_title = self.name

        # Add timestamp to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.exports_dir / f"{safe_title}_{timestamp}.{format_name}"
