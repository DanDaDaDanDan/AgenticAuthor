# Kindle Book Formatting Research

## Executive Summary

This document contains comprehensive research on professional ebook formatting for Kindle/KDP, RTF structure, and implementation plan for AgenticAuthor's export functionality.

## 1. Professional Ebook Structure

### Standard Ebook Components (in order)

1. **Title Page** - Book title, subtitle, author name
2. **Copyright Page** - Copyright notice, ISBN, disclaimers, edition info
3. **Dedication** (optional) - Personal dedication
4. **Acknowledgments** (optional) - Thank yous
5. **Table of Contents** (optional for fiction, recommended for non-fiction)
6. **Foreword/Preface** (optional)
7. **Main Content** - Chapters
8. **Epilogue** (optional)
9. **About the Author** - Author bio
10. **Also by Author** - Other books

### Kindle-Specific Best Practices

- **Skip half-title page** - Wastes digital space
- **Simple title page** - Title, subtitle (if any), author
- **Copyright immediately after title** - Standard position
- **Interactive TOC** - Use hyperlinks, auto-generated from headings
- **First chapter preview** - Many readers check "Look Inside"
- **Back matter at end** - About author, other books, mailing list

## 2. Paragraph Formatting Standards

### Traditional Print Fiction Standard

```
No indent after chapter heading or scene break
First line indent: 0.5em (about 0.18 inches with 12pt font)
No blank lines between paragraphs
Justified text
```

### Modern Ebook Practice

**Fiction (most professional):**
- First-line indent: 0.25-0.5 inches
- No blank lines between paragraphs
- No indent on first paragraph after heading/break
- Justified or left-aligned text

**Non-Fiction:**
- Block paragraphs (no indent)
- Blank line between paragraphs
- Left-aligned text
- Section headings

### Scene Break Formatting

Standard options (in order of preference):

1. `* * *` (three asterisks with spaces) - Most common
2. `***` (three asterisks together)
3. `# # #` (three hashtags)
4. Ornamental break (special character/dingbat)
5. ~~Extra blank line~~ - NOT RECOMMENDED (can disappear at page breaks)

## 3. Chapter Formatting

### Common Chapter Heading Styles

**Style 1 - Numbered with title (two lines):**
```
Chapter One
The Beginning
```

**Style 2 - Just number:**
```
Chapter 1
```

**Style 3 - Just title:**
```
The Beginning
```

**Style 4 - Number and title (one line):**
```
Chapter 1: The Beginning
```

### Chapter Formatting Rules

- Each chapter starts on new page (page break before)
- Chapter number: larger font, bold, centered or left-aligned
- Chapter title: medium-large font, may be bold, centered or left-aligned
- First paragraph: traditionally no indent, modern often has indent
- Subsequent paragraphs: first-line indent (fiction) or block (non-fiction)

## 4. RTF Format Deep Dive

### RTF Structure Overview

RTF (Rich Text Format) is a text-based format with embedded formatting codes.

**Basic RTF Document:**
```rtf
{\rtf1\ansi\deff0
{\fonttbl{\f0\froman Times New Roman;}}
\f0\fs24

Content here with \b bold\b0 and \i italic\i0.

\par
}
```

### Essential RTF Control Words

| Code | Meaning | Example |
|------|---------|---------|
| `\rtf1` | RTF version 1 | Required |
| `\ansi` | ANSI character set | Required |
| `\deff0` | Default font = font 0 | Required |
| `\f0` | Use font 0 | Switch font |
| `\fs24` | Font size 12pt (24 half-points) | 24 = 12pt, 32 = 16pt, 48 = 24pt |
| `\b` | Bold on | `\b text\b0` |
| `\b0` | Bold off | After bold text |
| `\i` | Italic on | `\i text\i0` |
| `\i0` | Italic off | After italic text |
| `\ul` | Underline on | `\ul text\ul0` |
| `\ul0` | Underline off | After underline |
| `\qc` | Center align | Paragraph alignment |
| `\ql` | Left align | Default |
| `\qr` | Right align | Rarely used |
| `\qj` | Justify | Professional look |
| `\fi360` | First line indent 0.25" | 360 twips = 0.25" |
| `\fi720` | First line indent 0.5" | 720 twips = 0.5" |
| `\li720` | Left indent 0.5" | For all lines |
| `\par` | Paragraph break | End of paragraph |
| `\page` | Page break | Start new page |
| `\line` | Line break | Soft return |

### Twips Conversion

RTF uses "twips" (twentieth of a point, 1/1440 inch):
- 0.25 inch = 360 twips
- 0.5 inch = 720 twips
- 1 inch = 1440 twips

### Font Table

```rtf
{\fonttbl
{\f0\froman Times New Roman;}
{\f1\fswiss Arial;}
{\f2\fmodern Courier New;}
}
```

Font families:
- `\froman` - Serif (Times New Roman, Georgia)
- `\fswiss` - Sans-serif (Arial, Helvetica)
- `\fmodern` - Monospace (Courier)

### Color Table (optional)

```rtf
{\colortbl
;\red0\green0\blue0;
\red255\green255\blue255;
}
```

## 5. Complete RTF Example for Kindle

```rtf
{\rtf1\ansi\deff0
{\fonttbl{\f0\froman Times New Roman;}}
\f0\fs24

{\pard\qc\fs48\b THE SHADOW PROTOCOL\b0\fs24\par}
{\pard\qc\fs32 A Thriller\fs24\par}
{\pard\qc\par}
{\pard\qc\fs32 by\par}
{\pard\qc\fs32 Jane Doe\b0\fs24\par}
\page

{\pard\qc\b Copyright Page\b0\par}
{\pard\par}
{\pard Copyright \u169 2025 by Jane Doe\par}
{\pard\par}
{\pard All rights reserved. No part of this book may be reproduced in any form or by any electronic or mechanical means, including information storage and retrieval systems, without permission in writing from the author, except by a reviewer who may quote brief passages in a review.\par}
{\pard\par}
{\pard This is a work of fiction. Names, characters, places, and incidents are either the product of the author's imagination or are used fictitiously. Any resemblance to actual persons, living or dead, events, or locales is entirely coincidental.\par}
{\pard\par}
{\pard ISBN: 978-1-234567-89-0\par}
{\pard\par}
{\pard First Edition: 2025\par}
\page

{\pard\qc\fs36\b Chapter 1\b0\fs24\par}
{\pard\qc\b The Discovery\b0\par}
{\pard\par}
{\pard\fi360\qj Sarah Chen stared at the encrypted file on her screen, her heart pounding. This wasn't supposed to be here. The file had been deleted three years ago\emdash she had watched it burn in the incinerator herself.\par}
{\pard\par}
{\pard\fi360\qj Yet here it was, reconstructed from fragments scattered across a dozen compromised servers. Someone had been very careful, very patient.\par}
{\pard\par}
{\pard\qc * * *\par}
{\pard\par}
{\pard\fi360\qj The phone rang at 3 AM. Sarah knew who it was before she picked up.\par}
{\pard\par}
{\pard\fi360\qj "You found it," Director Martinez said. Not a question.\par}
\page

{\pard\qc\fs36\b Chapter 2\b0\fs24\par}
{\pard\qc\b The Protocol\b0\par}
{\pard\par}
{\pard\fi360\qj Twenty-four hours earlier, Sarah had been planning her resignation...\par}
\page
}
```

### RTF Special Characters

- `\'` - Hex escape (e.g., `\'e9` for é)
- `\u` - Unicode escape (e.g., `\u169` for ©)
- `\emdash` - Em dash (—)
- `\endash` - En dash (–)
- `\lquote` - Left single quote (')
- `\rquote` - Right single quote (')
- `\ldblquote` - Left double quote (")
- `\rdblquote` - Right double quote (")

### RTF Escaping Rules

These characters must be escaped:
- `\` → `\\`
- `{` → `\{`
- `}` → `\}`

## 6. Markdown to RTF Conversion

### Markdown Elements to Convert

| Markdown | RTF | Notes |
|----------|-----|-------|
| `**bold**` | `\b bold\b0` | Bold text |
| `*italic*` | `\i italic\i0` | Italic text |
| `# Heading 1` | `\fs32\b Heading\b0\fs24` | Large heading |
| `## Heading 2` | `\fs28\b Heading\b0\fs24` | Medium heading |
| Blank line | `\par\par` | Paragraph separator |
| `***` or `* * *` | `\qc * * *\par` | Scene break (centered) |
| `---` | `\qc * * *\par` | Scene break alternative |
| Line break | `\line` | Soft return |

### Paragraph Detection Algorithm

```
1. Split text on double newlines (\n\n or \n\s*\n)
2. Each section = one paragraph
3. Within paragraph: replace single \n with space
4. Trim whitespace
5. Apply RTF formatting
```

### Dialog Handling

Dialog should be preserved as-is within paragraphs:
- Opening quote: `"`
- Closing quote: `"`
- Em dashes: `—` → `\emdash`
- Keep paragraph structure

## 7. Kindle Direct Publishing (KDP) Requirements

### Accepted Formats

1. **EPUB** - Recommended (HTML-based)
2. **MOBI** - Legacy format
3. **DOC/DOCX** - Microsoft Word
4. **HTML** - Direct HTML
5. **RTF** - Rich Text Format (limited)

### RTF Limitations for KDP

**Pros:**
- Simple, text-based
- Widely supported
- Easy to generate programmatically

**Cons:**
- No interactive TOC (Kindle auto-generates from headings)
- Limited styling control vs. HTML/EPUB
- May lose some formatting during conversion
- No embedded fonts
- No advanced layout features

**Recommendation:** RTF works for basic fiction books. For advanced formatting, use EPUB.

### KDP Conversion Notes

When uploading RTF to KDP:
1. Amazon converts RTF → MOBI/KPF automatically
2. Preview carefully in Kindle Previewer tool
3. Check on multiple devices/apps
4. Verify TOC auto-generation worked
5. Check scene breaks didn't disappear

## 8. Alternative Export Formats

### Option 1: Combined Markdown

Simplest option:
```markdown
# Book Title
by Author Name

## Copyright
...

---

# Chapter 1
Content...

# Chapter 2
Content...
```

Then convert with Pandoc or similar.

### Option 2: HTML

More control than RTF:
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Book Title</title>
  <style>
    body { font-family: Georgia, serif; }
    h1 { text-align: center; font-size: 2em; }
    p { text-indent: 2em; margin: 0; }
    .scene-break { text-align: center; margin: 1em 0; }
  </style>
</head>
<body>
  <h1>Chapter 1</h1>
  <p>First paragraph...</p>
  <p>Second paragraph...</p>
  <p class="scene-break">* * *</p>
</body>
</html>
```

### Option 3: EPUB (via Pandoc)

Most professional option:
1. Generate combined markdown
2. Create metadata.yaml
3. Run: `pandoc -o book.epub metadata.yaml book.md`
4. Upload EPUB to KDP

## 9. AgenticAuthor Implementation Plan

### Step 1: Add Book Metadata

**Location:** `config.yaml`

```yaml
name: my-novel
created_at: 2025-01-15T10:30:00Z
model: anthropic/claude-sonnet-4
book_metadata:
  title: "The Shadow Protocol"
  subtitle: "A Thriller"
  author: "Jane Doe"
  series: ""
  series_number: null
  isbn: ""
  copyright_year: 2025
  publisher: "Self-Published"
  edition: "First Edition"
```

### Step 2: Create Frontmatter Template

**File:** `frontmatter.md` (created on project init)

```markdown
---
# Frontmatter Template
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
```

### Step 3: /metadata Command

```bash
# View all metadata
/metadata

# Set individual fields
/metadata title "The Shadow Protocol"
/metadata author "Jane Doe"
/metadata subtitle "A Thriller"
/metadata isbn "978-1-234567-89-0"
/metadata copyright 2025
/metadata series "Shadow Series"
/metadata series_number 1
```

### Step 4: /export Command

```bash
# Export to RTF
/export rtf

# Export to combined markdown
/export markdown

# Export to HTML (future)
/export html

# Specify output file
/export rtf output.rtf
```

### Step 5: RTF Exporter Architecture

**New module:** `src/export/rtf_exporter.py`

```python
class RTFExporter:
    def __init__(self, project: Project):
        self.project = project

    def export(self, output_path: Path) -> None:
        """Export project to RTF format."""
        rtf = self._build_rtf()
        output_path.write_text(rtf, encoding='utf-8')

    def _build_rtf(self) -> str:
        """Build complete RTF document."""
        parts = []
        parts.append(self._rtf_header())
        parts.append(self._title_page())
        parts.append(self._page_break())
        parts.append(self._copyright_page())
        parts.append(self._page_break())

        # Optional frontmatter sections
        frontmatter = self._process_frontmatter()
        if frontmatter.get('dedication'):
            parts.append(frontmatter['dedication'])
            parts.append(self._page_break())
        if frontmatter.get('acknowledgments'):
            parts.append(frontmatter['acknowledgments'])
            parts.append(self._page_break())

        # Chapters
        parts.append(self._all_chapters())

        parts.append(self._rtf_footer())
        return ''.join(parts)
```

## 10. Formatting Decision Matrix

| Content Type | First-line Indent | Blank Lines | Alignment |
|--------------|-------------------|-------------|-----------|
| First paragraph after heading | NO | YES (after heading) | Left/Justify |
| Body paragraphs | YES (0.25-0.5") | NO | Justify |
| First paragraph after scene break | NO | YES (after break) | Left/Justify |
| Scene break line | NO | YES (before/after) | Center |
| Chapter heading | NO | NO | Center |
| Title page elements | NO | YES | Center |
| Copyright text | NO | YES | Left |

## 11. Testing Strategy

1. **Generate RTF from test project**
2. **Open in Word/LibreOffice** - Verify formatting preserved
3. **Convert to EPUB** - Use Calibre: RTF → EPUB
4. **Test in Kindle Previewer** - Amazon's official tool
5. **Upload to KDP** - Test actual conversion
6. **Check on devices** - Kindle e-reader, phone app, tablet

## 12. Future Enhancements

1. **HTML export** - Better control than RTF
2. **EPUB export** - Via Pandoc integration
3. **Cover page integration** - Add cover image
4. **TOC generation** - Manual or auto-generated
5. **Back matter** - About author, other books
6. **Custom CSS** - For HTML/EPUB exports
7. **Styling presets** - Different formatting styles
8. **Preview mode** - Preview before export

## 13. References

- Kindle Direct Publishing Guidelines: https://kdp.amazon.com/en_US/help/topic/G200645680
- RTF Specification: Microsoft RTF 1.9.1 Specification
- EPUB Best Practices: IDPF EPUB 3.0 Spec
- Professional Book Design: "The Elements of Typographic Style" by Robert Bringhurst
