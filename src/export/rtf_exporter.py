"""RTF exporter for book projects."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import will be resolved at runtime
# from ..models.project import Project


class RTFExporter:
    """Export project to RTF format suitable for Kindle/ebook."""

    # RTF header with font table
    HEADER = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0\froman Times New Roman;}}
{\colortbl;\red0\green0\blue0;}
\f0\fs24
"""

    FOOTER = "}\n"

    def __init__(self, project):
        """
        Initialize RTF exporter.

        Args:
            project: Project to export
        """
        self.project = project
        self.metadata = project.get_book_metadata()

    def export(self, output_path: Optional[Path] = None) -> Path:
        """
        Export project to RTF file.

        Args:
            output_path: Optional custom output path

        Returns:
            Path to generated RTF file

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
            output_path = self.project.get_export_path('rtf')

        # Build RTF content
        rtf = self._build_rtf()

        # Write to file
        output_path.write_text(rtf, encoding='utf-8')

        return output_path

    def _build_rtf(self) -> str:
        """Build complete RTF document."""
        parts = []

        # Header
        parts.append(self.HEADER)

        # Frontmatter
        parts.append(self._build_title_page())
        parts.append(self._page_break())
        parts.append(self._build_copyright_page())
        parts.append(self._page_break())

        # Optional frontmatter sections
        frontmatter_sections = self._parse_frontmatter()
        for section_name, section_content in frontmatter_sections.items():
            if section_name not in ['title page', 'copyright']:
                parts.append(section_content)
                parts.append(self._page_break())

        # Chapters
        parts.append(self._build_all_chapters())

        # Footer
        parts.append(self.FOOTER)

        return ''.join(parts)

    def _build_title_page(self) -> str:
        """Build RTF title page."""
        title = self.metadata.get('title', 'Untitled')
        subtitle = self.metadata.get('subtitle', '')
        author = self.metadata.get('author', 'Unknown Author')

        parts = []

        # Title (large, bold, centered)
        parts.append(r"{\pard\qc\fs48\b ")
        parts.append(self._escape_rtf(title))
        parts.append(r"\b0\fs24\par}")
        parts.append("\n")

        # Subtitle (if present)
        if subtitle:
            parts.append(r"{\pard\qc\fs32 ")
            parts.append(self._escape_rtf(subtitle))
            parts.append(r"\fs24\par}")
            parts.append("\n")

        # Spacing
        parts.append(r"{\pard\qc\par}")
        parts.append("\n")

        # Author (medium, centered)
        parts.append(r"{\pard\qc\fs32 by\par}")
        parts.append("\n")
        parts.append(r"{\pard\qc\fs32 ")
        parts.append(self._escape_rtf(author))
        parts.append(r"\fs24\par}")
        parts.append("\n")

        return ''.join(parts)

    def _build_copyright_page(self) -> str:
        """Build RTF copyright page."""
        author = self.metadata.get('author', 'Unknown Author')
        year = self.metadata.get('copyright_year', 2025)
        isbn = self.metadata.get('isbn', '')
        edition = self.metadata.get('edition', 'First Edition')

        parts = []

        # Copyright symbol and year
        parts.append(r"{\pard ")
        parts.append(f"Copyright \\u169  {year} by {self._escape_rtf(author)}")
        parts.append(r"\par}")
        parts.append("\n")

        # Blank line
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Rights statement
        parts.append(r"{\pard ")
        parts.append("All rights reserved. No part of this book may be reproduced in any form or by any electronic or mechanical means, including information storage and retrieval systems, without permission in writing from the author, except by a reviewer who may quote brief passages in a review.")
        parts.append(r"\par}")
        parts.append("\n")

        # Blank line
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Fiction disclaimer
        parts.append(r"{\pard ")
        parts.append("This is a work of fiction. Names, characters, places, and incidents are either the product of the author's imagination or are used fictitiously. Any resemblance to actual persons, living or dead, events, or locales is entirely coincidental.")
        parts.append(r"\par}")
        parts.append("\n")

        # ISBN if present
        if isbn:
            parts.append(r"{\pard\par}")
            parts.append("\n")
            parts.append(r"{\pard ")
            parts.append(f"ISBN: {self._escape_rtf(isbn)}")
            parts.append(r"\par}")
            parts.append("\n")

        # Edition
        parts.append(r"{\pard\par}")
        parts.append("\n")
        parts.append(r"{\pard ")
        parts.append(self._escape_rtf(edition))
        parts.append(r"\par}")
        parts.append("\n")

        return ''.join(parts)

    def _build_all_chapters(self) -> str:
        """Build RTF for all chapters."""
        parts = []

        # Get chapters list for titles
        chapters_yaml = self.project.get_chapters_yaml()
        if chapters_yaml:
            chapters = chapters_yaml.get('chapters', [])
        else:
            chapters = self.project.get_chapters() or []

        # Process each chapter file
        for chapter_file in sorted(self.project.list_chapters()):
            chapter_num = self._extract_chapter_number(chapter_file)
            chapter_text = chapter_file.read_text(encoding='utf-8')

            # Find chapter info
            chapter_info = next((c for c in chapters if c.get('number') == chapter_num), None)
            chapter_title = chapter_info.get('title', '') if chapter_info else ''

            # Build chapter RTF
            parts.append(self._build_chapter(chapter_num, chapter_title, chapter_text))
            parts.append(self._page_break())

        return ''.join(parts)

    def _build_chapter(self, number: int, title: str, text: str) -> str:
        """
        Build RTF for a single chapter.

        Args:
            number: Chapter number
            title: Chapter title
            text: Chapter prose (markdown)

        Returns:
            RTF string for chapter
        """
        parts = []

        # Chapter number (centered, large, bold)
        parts.append(r"{\pard\qc\fs36\b ")
        parts.append(f"Chapter {number}")
        parts.append(r"\b0\fs24\par}")
        parts.append("\n")

        # Chapter title if present (centered, bold)
        if title:
            parts.append(r"{\pard\qc\b ")
            parts.append(self._escape_rtf(title))
            parts.append(r"\b0\par}")
            parts.append("\n")

        # Blank line after heading
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Convert markdown prose to RTF paragraphs
        paragraphs = self._markdown_to_paragraphs(text)

        # Apply professional formatting: no indent on first paragraph and after scene breaks
        is_first = True
        for para in paragraphs:
            # Check if this is a scene break (centered * * *, not just any occurrence)
            if r"\qc * * *" in para:
                parts.append(para)
                parts.append("\n")
                is_first = True  # Next paragraph after scene break has no indent
                continue

            # Remove indent from first paragraph or paragraph after scene break
            if is_first and '\\fi360' in para:
                para = para.replace('\\fi360', '\\fi0')
                is_first = False

            parts.append(para)
            parts.append("\n")

        return ''.join(parts)

    def _markdown_to_paragraphs(self, text: str) -> List[str]:
        """
        Convert markdown text to RTF paragraphs.

        Handles:
        - Bold: **text** → \\b text\\b0
        - Italic: *text* → \\i text\\i0
        - Scene breaks: *** or * * * → centered
        - Paragraphs: separated by blank lines

        Args:
            text: Markdown text

        Returns:
            List of RTF paragraph strings
        """
        paragraphs = []

        # Split on blank lines (two or more newlines)
        sections = re.split(r'\n\s*\n', text.strip())

        for section in sections:
            section = section.strip()

            if not section:
                continue

            # Check if scene break
            if re.match(r'^\*\s*\*\s*\*$', section) or section == '***':
                # Scene break: centered asterisks
                paragraphs.append(r"{\pard\qc * * *\par}")
                continue

            # Regular paragraph: merge lines, convert markdown
            para_text = section.replace('\n', ' ')  # Single newlines become spaces

            # CRITICAL: Escape RTF special characters FIRST, before adding RTF codes
            # This escapes \, {, } in the user's text but not * or —
            para_text = self._escape_rtf(para_text)

            # Now convert markdown to RTF (asterisks are not escaped, so patterns still work)
            # Convert markdown bold: **text** → \b text\b0
            para_text = re.sub(r'\*\*(.*?)\*\*', r'\\b \1\\b0 ', para_text)

            # Convert markdown italic: *text* → \i text\i0 (but not **)
            para_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\\i \1\\i0 ', para_text)

            # Convert em dashes (after escaping user text, we add RTF control codes)
            para_text = para_text.replace('—', '\\emdash ')
            para_text = para_text.replace('–', '\\endash ')

            # Build paragraph with first-line indent and justification
            rtf_para = r"{\pard\fi360\qj " + para_text + r"\par}"

            paragraphs.append(rtf_para)

        return paragraphs

    def _parse_frontmatter(self) -> Dict[str, str]:
        """
        Parse frontmatter.md into sections.

        Returns:
            Dict mapping section names to RTF content
        """
        frontmatter = self.project.get_frontmatter()
        if not frontmatter:
            return {}

        # Replace variables
        frontmatter = self._replace_variables(frontmatter)

        sections = {}

        # Split by ## headings
        parts = re.split(r'^##\s+(.+?)$', frontmatter, flags=re.MULTILINE)

        # parts[0] is content before first heading (ignore)
        # parts[1], parts[2], parts[3], parts[4], ... are heading, content, heading, content, ...

        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                heading = parts[i].strip().lower()
                content = parts[i + 1].strip()

                # Skip if placeholder text
                if content.startswith('[') and content.endswith(']'):
                    continue

                # Convert to RTF
                rtf_content = self._markdown_section_to_rtf(heading, content)
                sections[heading] = rtf_content

        return sections

    def _replace_variables(self, text: str) -> str:
        """Replace {{variable}} placeholders in text."""
        replacements = {
            'title': self.metadata.get('title', ''),
            'subtitle': self.metadata.get('subtitle', ''),
            'author': self.metadata.get('author', ''),
            'copyright_year': str(self.metadata.get('copyright_year', 2025)),
            'isbn': self.metadata.get('isbn', ''),
            'edition': self.metadata.get('edition', ''),
            'publisher': self.metadata.get('publisher', ''),
        }

        for key, value in replacements.items():
            text = text.replace('{{' + key + '}}', value)

        return text

    def _markdown_section_to_rtf(self, heading: str, content: str) -> str:
        """Convert a frontmatter section to RTF."""
        parts = []

        # Section heading (centered, bold)
        parts.append(r"{\pard\qc\b ")
        parts.append(self._escape_rtf(heading.title()))
        parts.append(r"\b0\par}")
        parts.append("\n")

        # Blank line
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Content paragraphs
        paragraphs = self._markdown_to_paragraphs(content)
        for para in paragraphs:
            parts.append(para)
            parts.append("\n")

        return ''.join(parts)

    def _escape_rtf(self, text: str) -> str:
        """
        Escape special RTF characters.

        Args:
            text: Plain text

        Returns:
            RTF-escaped text
        """
        # Escape backslash first (to avoid double-escaping)
        text = text.replace('\\', '\\\\')
        # Escape braces
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')

        return text

    def _page_break(self) -> str:
        """Return RTF page break."""
        return r"\page" + "\n"

    def _extract_chapter_number(self, chapter_file: Path) -> int:
        """Extract chapter number from filename."""
        match = re.search(r'chapter-(\d+)', chapter_file.name)
        if match:
            return int(match.group(1))
        return 0
