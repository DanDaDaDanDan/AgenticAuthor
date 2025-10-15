"""Convert story-export JSON format to AgenticAuthor format."""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from html2text import html2text


class StoryExportConverter:
    """Converts story-export JSON files to AgenticAuthor project structure."""

    def __init__(self, export_file: Path):
        """Initialize converter with export file path."""
        self.export_file = export_file
        with open(export_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)['data']

    def convert_to_project(self, project_dir: Path, use_edited: bool = True) -> None:
        """
        Convert export data to AgenticAuthor project structure.

        Args:
            project_dir: Destination directory for the project
            use_edited: If True, use editedChapters (copy-edited). If False, use proseChapters.
        """
        project_dir = Path(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create premise.md
        self._write_premise(project_dir)

        # Create premise_metadata.json
        self._write_taxonomy(project_dir)

        # Create treatment.md
        self._write_treatment(project_dir)

        # Create chapters.yaml
        self._write_chapters_yaml(project_dir)

        # Create chapters/ directory with prose
        self._write_prose_chapters(project_dir, use_edited)

        # Create project.yaml
        self._write_project_metadata(project_dir)

    def _write_premise(self, project_dir: Path) -> None:
        """Write premise_metadata.json file with premise text and taxonomy."""
        premise = self.data['premise']['formData']['premise']
        taxonomy = self.data['premise']['formData']['taxonomySelections']

        # Build unified metadata structure
        metadata = {
            'premise': premise,
            **taxonomy  # Merge taxonomy selections
        }

        metadata_file = project_dir / 'premise_metadata.json'
        metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def _write_taxonomy(self, project_dir: Path) -> None:
        """Deprecated: Taxonomy is now written with premise in _write_premise()."""
        # No-op: taxonomy is now part of premise_metadata.json
        pass

    def _write_treatment(self, project_dir: Path) -> None:
        """Write treatment.md file from overview/stories."""
        # The treatment is in overview.stories[0].content
        stories = self.data.get('overview', {}).get('stories', [])
        if stories:
            treatment = stories[0]['content']
            treatment_file = project_dir / 'treatment.md'
            treatment_file.write_text(treatment, encoding='utf-8')

    def _write_chapters_yaml(self, project_dir: Path) -> None:
        """Write chapters.yaml file from chapter metadata."""
        chapters_data = self.data.get('chapters', {}).get('chapters', [])

        # Convert to YAML format
        chapters_yaml = []
        for chapter in chapters_data:
            chapters_yaml.append({
                'number': chapter['number'],
                'title': chapter['title'],
                'id': chapter['id']
            })

        chapters_file = project_dir / 'chapters.yaml'
        chapters_file.write_text(
            yaml.dump(chapters_yaml, default_flow_style=False, allow_unicode=True),
            encoding='utf-8'
        )

    def _write_prose_chapters(self, project_dir: Path, use_edited: bool) -> None:
        """Write individual chapter files."""
        chapters_dir = project_dir / 'chapters'
        chapters_dir.mkdir(exist_ok=True)

        if use_edited and 'editedBook' in self.data:
            # Use copy-edited chapters
            chapters = self.data['editedBook'].get('editedChapters', [])
            for chapter in chapters:
                if not chapter:  # Skip null entries
                    continue

                # Convert HTML to markdown
                html_content = chapter.get('htmlContent', '')
                if html_content:
                    markdown_content = self._html_to_markdown(html_content)

                    # Add chapter title as header
                    chapter_title = chapter.get('title', f"Chapter {chapter.get('number', '?')}")
                    full_content = f"# {chapter_title}\n\n{markdown_content}"

                    # Write to file
                    chapter_num = chapter.get('number', 0)
                    chapter_file = chapters_dir / f"chapter-{chapter_num:02d}.md"
                    chapter_file.write_text(full_content, encoding='utf-8')
        else:
            # Use original prose chapters
            chapters = self.data.get('fullBook', {}).get('proseChapters', [])
            for chapter in chapters:
                if not chapter:  # Skip null entries
                    continue

                prose_content = chapter.get('proseContent', '')
                if prose_content:
                    # Write to file (already in markdown format)
                    chapter_num = chapter.get('number', 0)
                    chapter_file = chapters_dir / f"chapter-{chapter_num:02d}.md"
                    chapter_file.write_text(prose_content, encoding='utf-8')

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        # Use html2text library for conversion
        markdown = html2text(html)
        # Clean up extra whitespace
        markdown = markdown.strip()
        return markdown

    def _write_project_metadata(self, project_dir: Path) -> None:
        """Write project.yaml file with metadata."""
        # Extract relevant metadata
        premise_data = self.data['premise']['formData']

        metadata = {
            'name': project_dir.name,
            'created': self.data.get('timestamp', ''),
            'author': premise_data.get('authorName', ''),
            'genre': ', '.join(premise_data['taxonomySelections'].get('genres', [])),
            'version': self.data.get('version', ''),
            'export_type': self.data.get('exportType', '')
        }

        project_file = project_dir / 'project.yaml'
        project_file.write_text(
            yaml.dump(metadata, default_flow_style=False, allow_unicode=True),
            encoding='utf-8'
        )


def convert_story_export(
    export_file: str | Path,
    output_dir: str | Path,
    project_name: Optional[str] = None,
    use_edited: bool = True
) -> Path:
    """
    Convert a story-export JSON file to AgenticAuthor project format.

    Args:
        export_file: Path to the story-export JSON file
        output_dir: Base directory where project will be created (e.g., 'books/')
        project_name: Name for the project directory. If None, derives from filename.
        use_edited: If True, use copy-edited chapters. If False, use original prose.

    Returns:
        Path to the created project directory

    Example:
        >>> convert_story_export(
        ...     'story-export-edited-book-2025-09-17.json',
        ...     'books/',
        ...     'legal-magic-novel'
        ... )
        Path('books/legal-magic-novel')
    """
    export_file = Path(export_file)
    output_dir = Path(output_dir)

    # Derive project name from filename if not provided
    if project_name is None:
        # Remove 'story-export-' prefix and '.json' suffix
        project_name = export_file.stem.replace('story-export-', '')

    # Create project directory
    project_dir = output_dir / project_name

    # Convert
    converter = StoryExportConverter(export_file)
    converter.convert_to_project(project_dir, use_edited=use_edited)

    return project_dir


if __name__ == '__main__':
    # CLI usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python import_converter.py <export-file.json> [output-dir] [project-name]")
        sys.exit(1)

    export_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'books'
    project_name = sys.argv[3] if len(sys.argv) > 3 else None

    result = convert_story_export(export_file, output_dir, project_name)
    print(f"Project created at: {result}")
