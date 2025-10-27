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

    def __init__(self, project, client=None, model: str = None):
        """
        Initialize RTF exporter.

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

        # Choose between original and edited chapters
        use_edited = self._choose_chapter_source()

        # Ensure dedication exists (generate if needed)
        await self._ensure_dedication()

        # Build RTF content
        rtf = await self._build_rtf(use_edited=use_edited)

        # Write to file
        output_path.write_text(rtf, encoding='utf-8')

        return output_path

    def _choose_chapter_source(self) -> bool:
        """
        Choose between original and edited chapters for export.

        Only prompts if original chapters are newer than edited chapters
        (suggesting modifications after copy editing).

        Returns:
            True to use edited chapters, False to use original
        """
        from rich.console import Console
        console = Console()

        original_files = self.project.list_chapters()
        edited_files = self.project.list_edited_chapters()

        # Only original exists
        if original_files and not edited_files:
            return False

        # Only edited exists
        if edited_files and not original_files:
            console.print("[dim]Using copy-edited chapters from chapters-edited/[/dim]")
            return True

        # Both exist - check timestamps
        if original_files and edited_files:
            # Get newest modification time from each folder
            newest_original = max(f.stat().st_mtime for f in original_files)
            newest_edited = max(f.stat().st_mtime for f in edited_files)

            # If original chapters are newer, warn and prompt
            if newest_original > newest_edited:
                from datetime import datetime
                orig_time = datetime.fromtimestamp(newest_original).strftime('%Y-%m-%d %H:%M:%S')
                edit_time = datetime.fromtimestamp(newest_edited).strftime('%Y-%m-%d %H:%M:%S')

                console.print("\n[yellow]⚠ Warning: Original chapters have been modified after copy editing[/yellow]")
                console.print(f"  Original chapters: last modified {orig_time}")
                console.print(f"  Edited chapters:   last modified {edit_time}")
                console.print("\n[bold]Which version do you want to export?[/bold]")
                console.print("  [cyan]1[/cyan] - Export from [bold]chapters/[/bold] (newer originals)")
                console.print("  [cyan]2[/cyan] - Export from [bold]chapters-edited/[/bold] (copy-edited)")

                while True:
                    choice = input("\nChoice (1/2): ").strip()
                    if choice == '1':
                        console.print("[dim]Using original chapters[/dim]\n")
                        return False
                    elif choice == '2':
                        console.print("[dim]Using edited chapters (ignoring newer originals)[/dim]\n")
                        return True
                    else:
                        console.print("[red]Invalid choice. Please enter 1 or 2.[/red]")
            else:
                # Edited is newer or same age - auto-use edited
                console.print("[dim]Using copy-edited chapters from chapters-edited/[/dim]")
                return True

        # No chapters at all
        return False

    async def _build_rtf(self, use_edited: bool = False) -> str:
        """
        Build complete RTF document.

        Args:
            use_edited: If True, use chapters-edited/, otherwise use chapters/
        """
        parts = []

        # Header
        parts.append(self.HEADER)

        # Frontmatter
        parts.append(self._build_title_page())
        parts.append(self._page_break())
        parts.append(self._build_copyright_page())
        parts.append(self._page_break())

        # Dedication (if exists)
        dedication = self.project.get_dedication()
        if dedication:
            parts.append(self._build_dedication(dedication))
            parts.append(self._page_break())

        # Optional frontmatter sections
        frontmatter_sections = self._parse_frontmatter()
        for section_name, section_content in frontmatter_sections.items():
            if section_name not in ['title page', 'copyright', 'dedication']:
                parts.append(section_content)
                parts.append(self._page_break())

        # Chapters
        parts.append(self._build_all_chapters())

        # Backmatter (if author is Sloane Grey)
        backmatter = await self._get_backmatter()
        if backmatter:
            parts.append(self._page_break())
            parts.append(backmatter)

        # Footer
        parts.append(self.FOOTER)

        return ''.join(parts)

    def _build_title_page(self) -> str:
        """Build RTF title page."""
        title = self.metadata.get('title', 'Untitled')
        author = self.metadata.get('author', 'Unknown Author')

        parts = []

        # Title (large, bold, centered)
        parts.append(r"{\pard\qc\fs48\b ")
        title_text = self._escape_rtf(title)
        title_text = self._encode_special_characters(title_text)
        parts.append(title_text)
        parts.append(r"\b0\fs24\par}")
        parts.append("\n")

        # Spacing
        parts.append(r"{\pard\qc\par}")
        parts.append("\n")

        # Author (medium, centered)
        parts.append(r"{\pard\qc\fs32 by\par}")
        parts.append("\n")
        parts.append(r"{\pard\qc\fs32 ")
        author_text = self._escape_rtf(author)
        author_text = self._encode_special_characters(author_text)
        parts.append(author_text)
        parts.append(r"\fs24\par}")
        parts.append("\n")

        return ''.join(parts)

    def _build_copyright_page(self) -> str:
        """Build RTF copyright page."""
        from datetime import datetime
        author = self.metadata.get('author', 'Unknown Author')
        year = self.metadata.get('copyright_year', datetime.now().year)

        parts = []

        # Copyright symbol and year
        parts.append(r"{\pard ")
        author_text = self._escape_rtf(author)
        author_text = self._encode_special_characters(author_text)
        parts.append(f"Copyright \\u169  {year} by {author_text}")
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

        return ''.join(parts)

    def _build_all_chapters(self) -> str:
        """Build RTF for all chapters (or short story)."""
        parts = []

        # Check if short-form story
        if self.project.is_short_form():
            # Export single story.md file (no chapter structure)
            story_text = self.project.get_story()
            if not story_text:
                raise ValueError("No story content found in story.md")

            # Convert markdown to RTF (no chapter number/title)
            paragraphs = self._markdown_to_paragraphs(story_text)

            # Apply professional formatting
            is_first = True
            for para in paragraphs:
                # Check if this is a scene break
                if r"\qc * * *" in para:
                    parts.append(para)
                    parts.append("\n")
                    is_first = True
                    continue

                # Remove indent from first paragraph or after scene break
                if is_first and '\\fi360' in para:
                    para = para.replace('\\fi360', '\\fi0')
                    is_first = False

                parts.append(para)
                parts.append("\n")

            return ''.join(parts)
        else:
            # Long-form: iterate over chapter files
            # Get chapters list for titles
            chapters_yaml = self.project.get_chapters_yaml()
            if chapters_yaml:
                chapters = chapters_yaml.get('chapters', [])
            else:
                chapters = self.project.get_chapters() or []

            # Choose chapter source based on use_edited flag
            chapter_files = sorted(self.project.list_edited_chapters() if use_edited else self.project.list_chapters())

            # Process each chapter file
            for chapter_file in chapter_files:
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
            title_text = self._escape_rtf(title)
            title_text = self._encode_special_characters(title_text)
            parts.append(title_text)
            parts.append(r"\b0\par}")
            parts.append("\n")

        # Blank line after heading
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Strip markdown heading from chapter text if present
        # Chapter files often start with "# Chapter X: Title" which we don't want to duplicate
        import re
        text = re.sub(r'^#\s+Chapter\s+\d+[:\s].*?$', '', text, flags=re.MULTILINE | re.IGNORECASE).strip()

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

            # Convert special Unicode characters to RTF ANSI hex codes
            para_text = self._encode_special_characters(para_text)

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
        from datetime import datetime
        replacements = {
            'title': self.metadata.get('title', ''),
            'author': self.metadata.get('author', ''),
            'copyright_year': str(self.metadata.get('copyright_year', datetime.now().year)),
        }

        for key, value in replacements.items():
            text = text.replace('{{' + key + '}}', value)

        return text

    def _markdown_section_to_rtf(self, heading: str, content: str) -> str:
        """Convert a frontmatter section to RTF."""
        parts = []

        # Section heading (centered, bold)
        parts.append(r"{\pard\qc\b ")
        heading_text = self._escape_rtf(heading.title())
        heading_text = self._encode_special_characters(heading_text)
        parts.append(heading_text)
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

    def _build_dedication(self, dedication: str) -> str:
        """Build RTF dedication section."""
        parts = []

        # Dedication heading (centered, italic)
        parts.append(r"{\pard\qc\i Dedication\i0\par}")
        parts.append("\n")

        # Blank line
        parts.append(r"{\pard\par}")
        parts.append("\n")

        # Escape RTF special characters first, then encode Unicode characters
        dedication_text = self._escape_rtf(dedication)
        dedication_text = self._encode_special_characters(dedication_text)

        # Dedication text (centered)
        parts.append(r"{\pard\qc ")
        parts.append(dedication_text)
        parts.append(r"\par}")
        parts.append("\n")

        return ''.join(parts)

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

        backmatter_md = backmatter_path.read_text(encoding='utf-8')

        # Convert markdown to RTF
        return self._backmatter_to_rtf(backmatter_md)

    def _backmatter_to_rtf(self, markdown: str) -> str:
        """Convert backmatter markdown to RTF."""
        parts = []

        # Split into sections by ## headings
        sections = re.split(r'^## (.+?)$', markdown, flags=re.MULTILINE)

        # First part is intro (before any ## headings)
        if sections and sections[0].strip():
            intro = sections[0].strip()
            # Remove "# A Note from the Author" if present
            intro = re.sub(r'^# A Note from the Author\s*', '', intro, flags=re.MULTILINE)
            if intro:
                paragraphs = self._markdown_to_paragraphs(intro)
                for para in paragraphs:
                    parts.append(para)
                    parts.append("\n")
                # Blank line
                parts.append(r"{\pard\par}")
                parts.append("\n")

        # Process remaining sections (heading, content, heading, content, ...)
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                heading = sections[i].strip()
                content = sections[i + 1].strip()

                # Section heading (bold, left-aligned)
                parts.append(r"{\pard\b ")
                heading_text = self._escape_rtf(heading)
                heading_text = self._encode_special_characters(heading_text)
                parts.append(heading_text)
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

                # Blank line after section
                parts.append(r"{\pard\par}")
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

    def _encode_special_characters(self, text: str) -> str:
        """
        Convert special Unicode characters to RTF ANSI hex codes.

        Use this after _escape_rtf() to convert Unicode characters
        that need special encoding in RTF (em/en dashes, smart quotes, etc.)

        Handles all Windows-1252 (ANSI) characters including:
        - Smart quotes and dashes (0x80-0x9F)
        - Latin-1 extended characters (0xA0-0xFF) like é, ç, ñ, etc.

        Args:
            text: RTF-escaped text

        Returns:
            Text with Unicode characters converted to ANSI hex codes
        """
        # Process character by character for comprehensive encoding
        result = []
        for char in text:
            # ASCII characters (0x00-0x7F) pass through unchanged
            if ord(char) < 0x80:
                result.append(char)
                continue

            # For characters >= 0x80, try to encode to Windows-1252
            try:
                # Encode character to Windows-1252 (cp1252)
                byte_value = char.encode('cp1252')

                # If it's a single byte, convert to RTF hex format
                if len(byte_value) == 1:
                    hex_code = byte_value[0]
                    result.append(f"\\'{hex_code:02x}")
                else:
                    # Multi-byte or unmappable - use Unicode escape
                    result.append(f"\\u{ord(char)}?")

            except UnicodeEncodeError:
                # Character not in Windows-1252, use Unicode escape
                # RTF format: \uN? where N is the Unicode code point
                result.append(f"\\u{ord(char)}?")

        return ''.join(result)

    def _page_break(self) -> str:
        """Return RTF page break."""
        return r"\page" + "\n"

    def _extract_chapter_number(self, chapter_file: Path) -> int:
        """Extract chapter number from filename."""
        match = re.search(r'chapter-(\d+)', chapter_file.name)
        if match:
            return int(match.group(1))
        return 0
