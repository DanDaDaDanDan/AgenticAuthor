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
    author: Optional[str] = Field(None, description="Author name")
    genre: Optional[str] = Field(None, description="Story genre")
    taxonomy: Optional[str] = Field(None, description="Taxonomy file used")
    model: Optional[str] = Field(None, description="Primary model used")
    word_count: int = Field(0, description="Total word count")
    chapter_count: int = Field(0, description="Number of chapters")
    story_type: Optional[str] = Field(None, description="Story type: short_form or long_form")
    status: str = Field("draft", description="Project status")
    tags: List[str] = Field(default_factory=list, description="Project tags")
    iteration_target: Optional[str] = Field(None, description="Current iteration target (premise/treatment/chapters/prose)")
    custom_data: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

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

    @property
    def project_file(self) -> Path:
        """Get path to project.yaml file."""
        return self.path / "project.yaml"

    @property
    def premise_file(self) -> Path:
        """Get path to premise.md file."""
        return self.path / "premise.md"

    @property
    def premise_metadata_file(self) -> Path:
        """Get path to premise_metadata.json file."""
        return self.path / "premise_metadata.json"

    @property
    def premises_file(self) -> Path:
        """Get path to premises_candidates.json file (for batch generation)."""
        return self.path / "premises_candidates.json"

    @property
    def treatment_file(self) -> Path:
        """Get path to treatment.md file."""
        return self.path / "treatment.md"

    @property
    def chapters_file(self) -> Path:
        """Get path to chapters.yaml file."""
        return self.path / "chapters.yaml"

    @property
    def chapters_dir(self) -> Path:
        """Get path to chapters directory."""
        return self.path / "chapters"

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
        return self.path / "frontmatter.md"

    @property
    def config_file(self) -> Path:
        """Get path to config.yaml file (for book metadata)."""
        return self.path / "config.yaml"

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid project directory."""
        return self.path.exists() and self.project_file.exists()

    def _load_metadata(self):
        """Load project metadata from project.yaml."""
        if self.project_file.exists():
            with open(self.project_file) as f:
                data = yaml.safe_load(f)
                self.metadata = ProjectMetadata(**data)

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
        with open(self.premise_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_treatment(self) -> Optional[str]:
        """Load treatment content."""
        if self.treatment_file.exists():
            return self.treatment_file.read_text(encoding='utf-8')
        return None

    def save_treatment(self, content: str):
        """Save treatment content."""
        self.treatment_file.write_text(content, encoding='utf-8')
        if self.metadata:
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_chapter_outlines(self) -> Optional[Dict[str, Any]]:
        """Load chapter outlines from YAML."""
        if self.chapters_file.exists():
            with open(self.chapters_file) as f:
                return yaml.safe_load(f)
        return None

    def get_chapters(self) -> Optional[List[Dict[str, Any]]]:
        """Load chapters list from chapter outlines."""
        outlines = self.get_chapter_outlines()
        # chapters.yaml contains a direct list of chapter dicts
        if outlines and isinstance(outlines, list):
            return outlines
        return None

    def get_taxonomy(self) -> Optional[Dict[str, Any]]:
        """Load taxonomy from premise metadata."""
        if self.premise_metadata_file.exists():
            with open(self.premise_metadata_file) as f:
                data = json.load(f)
                return data.get('taxonomy')
        return None

    def save_chapter_outlines(self, outlines: Dict[str, Any]):
        """Save chapter outlines to YAML."""
        with open(self.chapters_file, 'w') as f:
            yaml.dump(outlines, f, default_flow_style=False, sort_keys=False)
        if self.metadata:
            self.metadata.update_timestamp()
            self.metadata.chapter_count = len(outlines.get('chapters', []))
            self.save_metadata()

    def get_chapters_yaml(self) -> Optional[Dict[str, Any]]:
        """
        Load complete chapters.yaml structure (self-contained format).

        Returns full structure with metadata, characters, world, chapters sections.
        Returns None if file doesn't exist or for legacy format.
        """
        if self.chapters_file.exists():
            with open(self.chapters_file) as f:
                data = yaml.safe_load(f)
                # Check if it's the new self-contained format
                if isinstance(data, dict) and 'metadata' in data:
                    return data
                # Legacy format (list or old dict) - return None
                return None
        return None

    def save_chapters_yaml(self, data: Dict[str, Any]):
        """
        Save complete chapters.yaml structure (self-contained format).

        Args:
            data: Dict with metadata, characters, world, chapters sections
        """
        with open(self.chapters_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        if self.metadata:
            self.metadata.update_timestamp()
            # Extract chapter count from new structure
            chapters = data.get('chapters', [])
            self.metadata.chapter_count = len(chapters)
            self.save_metadata()

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

        # Update word count
        if self.metadata:
            self._update_word_count()
            self.metadata.update_timestamp()
            self.save_metadata()

    def list_chapters(self) -> List[Path]:
        """List all chapter files."""
        if not self.chapters_dir.exists():
            return []
        return sorted(self.chapters_dir.glob("chapter-*.md"))

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

        # Update word count and timestamp
        if self.metadata:
            self.metadata.word_count = len(content.split())
            self.metadata.update_timestamp()
            self.save_metadata()

    def get_target_words(self) -> Optional[int]:
        """
        Extract target word count from premise metadata or treatment.

        Returns:
            Target word count or None if not found
        """
        # Try premise metadata first
        if self.premise_metadata_file.exists():
            with open(self.premise_metadata_file) as f:
                data = json.load(f)
                # Check for target_word_count in taxonomy selections
                taxonomy = data.get('taxonomy', {})
                if isinstance(taxonomy, dict):
                    length_scope = taxonomy.get('length_scope', {})
                    if isinstance(length_scope, dict):
                        word_range = length_scope.get('word_range', '')
                        # Parse word range like "1,500-7,500"
                        if word_range:
                            parts = word_range.replace(',', '').split('-')
                            if len(parts) == 2:
                                try:
                                    # Use midpoint of range
                                    low = int(parts[0])
                                    high = int(parts[1])
                                    return (low + high) // 2
                                except ValueError:
                                    pass

        # Try chapters.yaml metadata
        chapters_yaml = self.get_chapters_yaml()
        if chapters_yaml:
            metadata = chapters_yaml.get('metadata', {})
            target = metadata.get('target_word_count')
            if target:
                return int(target)

        # Fallback: estimate from treatment length
        treatment = self.get_treatment()
        if treatment:
            # Typical treatment is ~2-5% of final length
            treatment_words = len(treatment.split())
            return treatment_words * 20  # Rough 5% estimate

        return None

    def is_short_form(self) -> bool:
        """
        Detect if this is a short-form story (≤2 chapters).

        Short-form stories (flash fiction, short story) should use story.md
        instead of chapters.yaml structure.

        Returns:
            True if short-form (≤2 chapters), False otherwise
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

    def _update_word_count(self):
        """Update the total word count from all chapters."""
        total_words = 0
        for chapter_file in self.list_chapters():
            content = chapter_file.read_text(encoding='utf-8')
            # Simple word count (can be improved)
            total_words += len(content.split())

        if self.metadata:
            self.metadata.word_count = total_words

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
        """Load config.yaml file."""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_config(self, config: Dict[str, Any]):
        """Save config.yaml file."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def get_book_metadata(self, key: Optional[str] = None, default=None):
        """
        Get book metadata.

        Args:
            key: Specific metadata key, or None for all metadata
            default: Default value if key not found

        Returns:
            Single value if key specified, dict if key is None
        """
        config = self._load_config()
        book_meta = config.get('book_metadata', {})

        if key is None:
            return book_meta
        return book_meta.get(key, default)

    def set_book_metadata(self, key: str, value):
        """
        Set book metadata value.

        Args:
            key: Metadata key
            value: Metadata value
        """
        config = self._load_config()
        if 'book_metadata' not in config:
            config['book_metadata'] = {}
        config['book_metadata'][key] = value
        self._save_config(config)

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
        config = self._load_config()
        if 'book_metadata' not in config:
            config['book_metadata'] = {
                'title': '',
                'author': '',
                'copyright_year': datetime.now().year
            }
            self._save_config(config)

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
        self.frontmatter_file.write_text(content, encoding='utf-8')

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
        Get default export file path for given format.

        Args:
            format_name: Format extension (rtf, md, html, etc.)

        Returns:
            Path to export file in exports/ directory
        """
        self.ensure_exports_dir()
        title = self.get_book_metadata('title', self.name)
        # Create safe filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))
        safe_title = safe_title.replace(' ', '-').lower()
        if not safe_title:
            safe_title = self.name
        return self.exports_dir / f"{safe_title}.{format_name}"