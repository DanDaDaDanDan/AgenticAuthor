"""Markdown exporter for book projects."""

from pathlib import Path
from typing import Optional


class MarkdownExporter:
    """Export project to combined markdown file."""

    def __init__(self, project, client=None, model: str = None):
        """
        Initialize markdown exporter.

        Args:
            project: Project to export
            client: Optional OpenRouter client (for dedication generation)
            model: Optional model name (for dedication generation)
        """
        self.project = project
        self.metadata = project.get_book_metadata()
        self.client = client
        self.model = model

    async def export(self, output_path: Optional[Path] = None) -> Path:
        """
        Export project to combined markdown file.

        Args:
            output_path: Optional custom output path

        Returns:
            Path to generated markdown file

        Raises:
            ValueError: If required metadata missing
        """
        if not self.project.has_required_metadata():
            raise ValueError(
                "Missing required metadata (title and author). "
                "Set with /metadata title and /metadata author"
            )

        # Determine output path
        if output_path is None:
            output_path = self.project.get_export_path('md')

        # Ensure dedication exists (generate if needed)
        await self._ensure_dedication()

        # Build markdown content
        markdown = await self._build_markdown()

        # Write to file
        output_path.write_text(markdown, encoding='utf-8')

        return output_path

    async def _build_markdown(self) -> str:
        """Build complete markdown document."""
        from datetime import datetime
        parts = []

        # Title page
        title = self.metadata.get('title', 'Untitled')
        author = self.metadata.get('author', 'Unknown Author')

        parts.append(f"# {title}\n\n")
        parts.append(f"by {author}\n\n")
        parts.append("---\n\n")

        # Copyright
        year = self.metadata.get('copyright_year', datetime.now().year)

        parts.append(f"Copyright © {year} by {author}\n\n")
        parts.append("All rights reserved. No part of this book may be reproduced in any form or by any electronic or mechanical means, including information storage and retrieval systems, without permission in writing from the author, except by a reviewer who may quote brief passages in a review.\n\n")
        parts.append("This is a work of fiction. Names, characters, places, and incidents are either the product of the author's imagination or are used fictitiously. Any resemblance to actual persons, living or dead, events, or locales is entirely coincidental.\n\n")
        parts.append("---\n\n")

        # Dedication (if exists)
        dedication = self.project.get_dedication()
        if dedication:
            parts.append("## Dedication\n\n")
            parts.append(f"{dedication}\n\n")
            parts.append("---\n\n")

        # Frontmatter sections (if any)
        frontmatter = self.project.get_frontmatter()
        if frontmatter:
            # Replace variables
            frontmatter = self._replace_variables(frontmatter)

            # Extract sections after title/copyright
            import re
            frontmatter_parts = re.split(r'^---+\s*$', frontmatter, flags=re.MULTILINE)

            # Skip first section (template comments) and title/copyright sections
            # Include remaining sections (dedication, acknowledgments, etc.)
            for i, section in enumerate(frontmatter_parts):
                section = section.strip()

                # Skip empty or template sections
                if not section or section.startswith('#'):
                    continue

                # Skip title page and copyright (already added above)
                if '## Title Page' in section or '## Copyright' in section:
                    continue

                # Check for placeholder text
                if section.startswith('[') and section.endswith(']'):
                    continue

                # Add section
                parts.append(section)
                parts.append("\n\n---\n\n")

        # Chapters (or short story)
        if self.project.is_short_form():
            # Export single story.md file (no chapter structure)
            story_text = self.project.get_story()
            if not story_text:
                raise ValueError("No story content found in story.md")

            # Add story content directly (no chapter headings)
            parts.append(story_text)
            parts.append("\n\n")
        else:
            # Long-form: iterate over chapter files
            chapters_yaml = self.project.get_chapters_yaml()
            if chapters_yaml:
                chapters = chapters_yaml.get('chapters', [])
            else:
                chapters = self.project.get_chapters() or []

            for chapter_file in sorted(self.project.list_chapters()):
                chapter_num = self._extract_chapter_number(chapter_file)
                chapter_text = chapter_file.read_text(encoding='utf-8')

                # Find chapter title
                chapter_info = next((c for c in chapters if c.get('number') == chapter_num), None)
                chapter_title = chapter_info.get('title', '') if chapter_info else ''

                # Chapter heading
                parts.append(f"# Chapter {chapter_num}")
                if chapter_title:
                    parts.append(f": {chapter_title}")
                parts.append("\n\n")

                # Strip markdown heading from chapter text if present
                # Chapter files often start with "# Chapter X: Title" which we don't want to duplicate
                import re
                chapter_text = re.sub(r'^#\s+Chapter\s+\d+[:\s].*?$', '', chapter_text, flags=re.MULTILINE | re.IGNORECASE).strip()

                # Chapter content
                parts.append(chapter_text)
                parts.append("\n\n")

        # Backmatter (if author is Sloane Grey)
        backmatter = await self._get_backmatter()
        if backmatter:
            parts.append("---\n\n")
            parts.append(backmatter)
            parts.append("\n\n")

        return ''.join(parts)

    def _replace_variables(self, text: str) -> str:
        """Replace {{variable}} placeholders in text."""
        from datetime import datetime
        replacements = {
            'title': self.metadata.get('title', ''),
            'author': self.metadata.get('author', ''),
            'copyright_year': str(self.metadata.get('copyright_year', datetime.now().year)),
        }

        for key, value in replacements.items():
            text = text.replace('{{' + key + '}}', value)

        return text

    def _extract_chapter_number(self, chapter_file: Path) -> int:
        """Extract chapter number from filename."""
        import re
        match = re.search(r'chapter-(\d+)', chapter_file.name)
        if match:
            return int(match.group(1))
        return 0

    async def _ensure_dedication(self):
        """Ensure dedication exists, generate if needed."""
        # Check if dedication already exists
        if self.project.get_dedication():
            return  # Already have it

        # Need client and model to generate
        if not self.client or not self.model:
            return  # Can't generate without these

        # Generate dedication
        from .dedication_generator import DedicationGenerator
        generator = DedicationGenerator(self.client, self.project, self.model)

        try:
            dedication = await generator.generate_dedication()
            self.project.save_dedication(dedication)
        except Exception as e:
            # Log error but don't fail export
            print(f"Warning: Could not generate dedication: {e}")

    async def _get_backmatter(self) -> Optional[str]:
        """Get backmatter if author matches Sloane Grey."""
        author = self.metadata.get('author', '').lower()

        # Check if author is Sloane Grey (case-insensitive)
        if 'sloane grey' not in author and 'sloane-grey' not in author:
            return None

        # Load Sloane Grey backmatter
        backmatter_path = Path(__file__).parent.parent.parent / "misc" / "backmatter-sloane-grey.md"
        if not backmatter_path.exists():
            return None

        # Read backmatter markdown
        backmatter_md = backmatter_path.read_text(encoding='utf-8')

        # For markdown export, we can include it as-is (it's already markdown)
        return backmatter_md
