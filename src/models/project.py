"""Project data models."""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
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
    status: str = Field("draft", description="Project status")
    tags: List[str] = Field(default_factory=list, description="Project tags")
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
    def analysis_dir(self) -> Path:
        """Get path to analysis directory."""
        return self.path / "analysis"

    @property
    def exports_dir(self) -> Path:
        """Get path to exports directory."""
        return self.path / "exports"

    @property
    def git_dir(self) -> Path:
        """Get path to .git directory."""
        return self.path / ".git"

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid project directory."""
        return self.path.exists() and self.project_file.exists()

    @property
    def is_git_repo(self) -> bool:
        """Check if project is a git repository."""
        return self.git_dir.exists()

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
        """Load premise content."""
        if self.premise_file.exists():
            return self.premise_file.read_text(encoding='utf-8')
        return None

    def save_premise(self, content: str):
        """Save premise content."""
        self.premise_file.write_text(content, encoding='utf-8')
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

    def save_chapter_outlines(self, outlines: Dict[str, Any]):
        """Save chapter outlines to YAML."""
        with open(self.chapters_file, 'w') as f:
            yaml.dump(outlines, f, default_flow_style=False, sort_keys=False)
        if self.metadata:
            self.metadata.update_timestamp()
            self.metadata.chapter_count = len(outlines.get('chapters', []))
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