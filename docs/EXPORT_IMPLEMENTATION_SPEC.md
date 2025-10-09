# Export System Implementation Specification

## Overview

This document specifies the implementation of book export functionality for AgenticAuthor, including metadata management, frontmatter, and RTF export.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User Commands                            │
│  /metadata title "Book"  │  /export rtf  │  /frontmatter    │
└──────────────┬──────────────────┬──────────────┬────────────┘
               │                  │              │
               ▼                  ▼              ▼
       ┌───────────────┐  ┌──────────────┐  ┌──────────────┐
       │   Metadata    │  │   Exporter   │  │  Frontmatter │
       │   Manager     │  │   Factory    │  │   Editor     │
       └───────┬───────┘  └──────┬───────┘  └──────────────┘
               │                  │
               ▼                  ▼
       ┌───────────────────────────────────┐
       │       Project Model               │
       │  - config.yaml                    │
       │  - frontmatter.md                 │
       │  - chapters/*.md                  │
       │  - chapters.yaml                  │
       └───────────────┬───────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────┐
       │      Export Modules               │
       │  - RTFExporter                    │
       │  - MarkdownExporter               │
       │  - HTMLExporter (future)          │
       └───────────────────────────────────┘
```

## 1. Metadata Structure

### config.yaml Extension

```yaml
name: my-novel
created_at: 2025-01-15T10:30:00Z
model: anthropic/claude-sonnet-4
default_target: prose

# NEW: Book metadata section
book_metadata:
  title: "The Shadow Protocol"
  subtitle: "A Thriller"
  author: "Jane Doe"
  series: "Shadow Series"
  series_number: 1
  isbn: ""
  copyright_year: 2025
  publisher: "Self-Published"
  edition: "First Edition"
```

### Default Values

When project is created, initialize with:
```yaml
book_metadata:
  title: ""  # Empty, user must set
  subtitle: ""
  author: ""  # Empty, user must set
  series: ""
  series_number: null
  isbn: ""
  copyright_year: 2025  # Current year
  publisher: "Self-Published"
  edition: "First Edition"
```

## 2. Project Model Updates

### New Methods

```python
class Project:
    """Extended with book metadata support."""

    def __init__(self, path: Path):
        self.path = path
        self.config_file = path / "config.yaml"
        self.frontmatter_file = path / "frontmatter.md"
        self.exports_dir = path / "exports"
        # ... existing init code ...

    # --- Book Metadata Methods ---

    def get_book_metadata(self, key: str = None, default=None):
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
# Variables: {{title}}, {{author}}, {{subtitle}}, {{copyright_year}}, {{isbn}}
---

## Title Page

{{title}}
{{subtitle}}

by {{author}}

---

## Copyright

Copyright © {{copyright_year}} by {{author}}

All rights reserved. No part of this book may be reproduced in any form or by any electronic or mechanical means, including information storage and retrieval systems, without permission in writing from the author, except by a reviewer who may quote brief passages in a review.

This is a work of fiction. Names, characters, places, and incidents are either the product of the author's imagination or are used fictitiously. Any resemblance to actual persons, living or dead, events, or locales is entirely coincidental.

ISBN: {{isbn}}
Edition: {{edition}}

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
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))
        safe_title = safe_title.replace(' ', '-').lower()
        return self.exports_dir / f"{safe_title}.{format_name}"
```

## 3. /metadata Command

### Command Syntax

```bash
# View all metadata
/metadata

# Set specific fields
/metadata title <value>
/metadata author <value>
/metadata subtitle <value>
/metadata series <value>
/metadata series_number <number>
/metadata isbn <value>
/metadata copyright <year>
/metadata publisher <value>
/metadata edition <value>
```

### Implementation

```python
# In src/cli/interactive.py

async def cmd_metadata(self, args: str):
    """
    Set or view book metadata.

    Usage:
        /metadata                    # View all metadata
        /metadata title "Book Title" # Set title
        /metadata author "Author"    # Set author
        /metadata copyright 2025     # Set copyright year
    """
    if not self.project:
        console.print("[red]No project open. Use /open <project> first.[/red]")
        return

    args = args.strip()

    if not args:
        # Display all metadata
        self._display_book_metadata()
        return

    # Parse key-value
    parts = args.split(None, 1)
    key = parts[0].lower()

    if len(parts) < 2:
        # Show single key
        self._display_single_metadata(key)
        return

    value = parts[1].strip().strip('"\'')

    # Set metadata
    self._set_metadata(key, value)

def _display_book_metadata(self):
    """Display all book metadata in a table."""
    from rich.table import Table

    metadata = self.project.get_book_metadata()

    table = Table(title="Book Metadata", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="yellow")

    fields = [
        ('title', 'Title'),
        ('subtitle', 'Subtitle'),
        ('author', 'Author'),
        ('series', 'Series'),
        ('series_number', 'Series #'),
        ('isbn', 'ISBN'),
        ('copyright_year', 'Copyright Year'),
        ('publisher', 'Publisher'),
        ('edition', 'Edition')
    ]

    for key, label in fields:
        value = metadata.get(key, '')
        if value is None or value == '':
            value = '[dim]Not set[/dim]'
        table.add_row(label, str(value))

    console.print(table)

    # Warn if required fields missing
    if not self.project.has_required_metadata():
        console.print("\n[yellow]⚠ Required fields missing: title and author[/yellow]")
        console.print("Set with: [cyan]/metadata title \"Your Title\"[/cyan]")
        console.print("          [cyan]/metadata author \"Your Name\"[/cyan]")

def _display_single_metadata(self, key: str):
    """Display single metadata field."""
    valid_keys = ['title', 'subtitle', 'author', 'series', 'series_number',
                  'isbn', 'copyright', 'publisher', 'edition']

    if key == 'copyright':
        key = 'copyright_year'

    if key not in valid_keys and key != 'copyright_year':
        console.print(f"[red]Unknown metadata key: {key}[/red]")
        console.print(f"Valid keys: {', '.join(valid_keys)}")
        return

    value = self.project.get_book_metadata(key, '')
    label = key.replace('_', ' ').title()

    if value:
        console.print(f"{label}: [yellow]{value}[/yellow]")
    else:
        console.print(f"{label}: [dim]Not set[/dim]")

def _set_metadata(self, key: str, value: str):
    """Set metadata value with validation."""
    # Normalize key
    if key == 'copyright':
        key = 'copyright_year'

    valid_keys = ['title', 'subtitle', 'author', 'series', 'series_number',
                  'isbn', 'copyright_year', 'publisher', 'edition']

    if key not in valid_keys:
        console.print(f"[red]Unknown metadata key: {key}[/red]")
        console.print(f"Valid keys: {', '.join(valid_keys)}")
        return

    # Validate specific types
    if key == 'series_number':
        try:
            value = int(value) if value else None
        except ValueError:
            console.print("[red]Series number must be an integer[/red]")
            return

    if key == 'copyright_year':
        try:
            year = int(value)
            if year < 1900 or year > 2100:
                console.print("[red]Copyright year must be between 1900 and 2100[/red]")
                return
            value = year
        except ValueError:
            console.print("[red]Copyright year must be a number (e.g., 2025)[/red]")
            return

    # Set value
    self.project.set_book_metadata(key, value)

    label = key.replace('_', ' ').title()
    console.print(f"[green]✓[/green] {label} set to: [yellow]{value}[/yellow]")

    # Auto-create frontmatter if this is first metadata
    if not self.project.frontmatter_file.exists():
        self.project.init_default_frontmatter()
        console.print("[dim]Created default frontmatter template[/dim]")
```

### Tab Completion

```python
# In src/cli/command_completer.py

def _complete_metadata(self, document, complete_event):
    """Complete metadata command."""
    text = document.text_before_cursor
    parts = text.split()

    if len(parts) == 1:
        # After /metadata, suggest keys
        keys = ['title', 'author', 'subtitle', 'series', 'series_number',
                'isbn', 'copyright', 'publisher', 'edition']
        return [Completion(k) for k in keys]

    return []
```

## 4. Frontmatter Template

### Default Template Location

- File: `frontmatter.md` in project root
- Created automatically when first metadata is set
- User can edit manually

### Template Processing

Variables that will be replaced:
- `{{title}}` - Book title
- `{{subtitle}}` - Book subtitle
- `{{author}}` - Author name
- `{{copyright_year}}` - Copyright year
- `{{isbn}}` - ISBN if set
- `{{edition}}` - Edition info
- `{{publisher}}` - Publisher name

### Section Detection

Frontmatter is divided by `---` separators:
```markdown
## Title Page
content here
---
## Copyright
content here
---
## Dedication
content here
```

Parser extracts each section by heading.

## 5. RTF Exporter

### Module Structure

```
src/export/
├── __init__.py
├── base.py          # BaseExporter abstract class
├── rtf_exporter.py  # RTF implementation
├── md_exporter.py   # Markdown implementation
└── utils.py         # Shared utilities
```

### RTF Exporter Class

```python
# src/export/rtf_exporter.py

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from ..models import Project


class RTFExporter:
    """Export project to RTF format suitable for Kindle/ebook."""

    # RTF control words
    HEADER = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0\froman Times New Roman;}}
{\colortbl;\red0\green0\blue0;}
\f0\fs24
"""

    FOOTER = "}\n"

    def __init__(self, project: Project):
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

        for para in paragraphs:
            parts.append(para)
            parts.append("\n")

        return ''.join(parts)

    def _markdown_to_paragraphs(self, text: str) -> List[str]:
        """
        Convert markdown text to RTF paragraphs.

        Handles:
        - Bold: **text** → \b text\b0
        - Italic: *text* → \i text\i0
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

            # Convert markdown bold: **text** → \b text\b0
            para_text = re.sub(r'\*\*(.*?)\*\*', r'\\b \1\\b0 ', para_text)

            # Convert markdown italic: *text* → \i text\i0 (but not **)
            para_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\\i \1\\i0 ', para_text)

            # Convert em dashes
            para_text = para_text.replace('—', '\\emdash ')
            para_text = para_text.replace('–', '\\endash ')

            # Escape RTF special characters
            para_text = self._escape_rtf(para_text)

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
        # Escape backslash, braces
        text = text.replace('\\', '\\\\')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')

        return text

    def _page_break(self) -> str:
        """Return RTF page break."""
        return r"\page" + "\n"

    def _extract_chapter_number(self, chapter_file: Path) -> int:
        """Extract chapter number from filename."""
        import re
        match = re.search(r'chapter-(\d+)', chapter_file.name)
        if match:
            return int(match.group(1))
        return 0
```

## 6. /export Command

### Command Syntax

```bash
/export rtf              # Export to RTF with default filename
/export rtf my-book.rtf  # Export to RTF with custom filename
/export markdown         # Export to combined markdown
```

### Implementation

```python
# In src/cli/interactive.py

async def cmd_export(self, args: str):
    """
    Export book to various formats.

    Usage:
        /export rtf [filename]       # Export to RTF format
        /export markdown [filename]  # Export to combined markdown
    """
    if not self.project:
        console.print("[red]No project open. Use /open <project> first.[/red]")
        return

    parts = args.strip().split(None, 1)

    if not parts:
        console.print("[yellow]Usage: /export <format> [filename][/yellow]")
        console.print("Formats: rtf, markdown")
        return

    format_type = parts[0].lower()
    custom_path = parts[1] if len(parts) > 1 else None

    # Check required metadata
    if not self.project.has_required_metadata():
        console.print("[red]Missing required metadata (title and author).[/red]")
        console.print("Set with: [cyan]/metadata title \"Your Title\"[/cyan]")
        console.print("          [cyan]/metadata author \"Your Name\"[/cyan]")
        return

    try:
        if format_type == 'rtf':
            await self._export_rtf(custom_path)
        elif format_type == 'markdown':
            await self._export_markdown(custom_path)
        else:
            console.print(f"[red]Unknown export format: {format_type}[/red]")
            console.print("Supported formats: rtf, markdown")

    except Exception as e:
        console.print(f"[red]Export failed: {str(e)}[/red]")
        self.logger.exception("Export error")

async def _export_rtf(self, custom_path: Optional[str] = None):
    """Export to RTF format."""
    from ..export.rtf_exporter import RTFExporter

    exporter = RTFExporter(self.project)

    # Determine output path
    if custom_path:
        output_path = Path(custom_path)
        if not output_path.is_absolute():
            output_path = self.project.path / output_path
    else:
        output_path = None  # Use default

    # Export
    with console.status("[yellow]Generating RTF...[/yellow]"):
        result_path = exporter.export(output_path)

    console.print(f"[green]✓[/green] Exported to: [cyan]{result_path}[/cyan]")

    # Show file info
    size_kb = result_path.stat().st_size / 1024
    console.print(f"  File size: {size_kb:.1f} KB")

    # Count chapters
    chapters = len(list(self.project.list_chapters()))
    console.print(f"  Chapters: {chapters}")

async def _export_markdown(self, custom_path: Optional[str] = None):
    """Export to combined markdown."""
    from ..export.md_exporter import MarkdownExporter

    exporter = MarkdownExporter(self.project)

    # Determine output path
    if custom_path:
        output_path = Path(custom_path)
        if not output_path.is_absolute():
            output_path = self.project.path / output_path
    else:
        output_path = None  # Use default

    # Export
    with console.status("[yellow]Combining markdown files...[/yellow]"):
        result_path = exporter.export(output_path)

    console.print(f"[green]✓[/green] Exported to: [cyan]{result_path}[/cyan]")
```

## 7. Testing Strategy

### Test Files to Create

1. `tests/test_rtf_exporter.py` - RTF exporter tests
2. `tests/test_metadata.py` - Metadata management tests
3. `tests/fixtures/test-book/` - Test project with sample content

### Manual Testing Checklist

- [ ] Set metadata with /metadata
- [ ] View metadata with /metadata (no args)
- [ ] Edit frontmatter.md manually
- [ ] Export to RTF
- [ ] Open RTF in Microsoft Word
- [ ] Open RTF in LibreOffice Writer
- [ ] Convert RTF to EPUB with Calibre
- [ ] Test in Kindle Previewer
- [ ] Verify formatting: indents, scene breaks, chapters
- [ ] Verify special characters: em dashes, quotes
- [ ] Verify front matter: title page, copyright
- [ ] Test with empty frontmatter sections

## 8. File Structure After Implementation

```
books/my-novel/
├── config.yaml                # Enhanced with book_metadata
├── premise.md
├── treatment.md
├── chapters.yaml
├── frontmatter.md             # NEW: Front matter template
├── chapters/
│   ├── chapter-01.md
│   ├── chapter-02.md
│   └── ...
└── exports/                   # NEW: Export outputs
    ├── my-novel.rtf          # RTF export
    └── my-novel.md           # Markdown export
```

## 9. Implementation Order

1. ✅ Research (DONE - see KINDLE_FORMATTING_RESEARCH.md)
2. Update Project model with metadata methods
3. Implement /metadata command with tab completion
4. Create default frontmatter template
5. Implement RTF exporter module
6. Implement /export command
7. Test with sample book
8. Document in USER_GUIDE.md

## 10. Future Enhancements

- HTML export with embedded CSS
- EPUB export via Pandoc integration
- PDF export
- Custom formatting presets
- Cover image integration
- Table of Contents auto-generation
- Back matter support (About Author, Other Books)
- Multiple frontmatter templates (fiction vs. non-fiction)
- Live preview in browser
