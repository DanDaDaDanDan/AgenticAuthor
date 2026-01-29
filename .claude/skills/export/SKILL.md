---
name: export
description: Export the book to a single combined file.
argument-hint: "[format] [output-path]"
---

Export the book to a single combined file.

## Usage

```
/export [format] [output-path]
```

## Arguments

- `format` (optional): Output format - `md` (default) or `full`
- `output-path` (optional): Where to save the export (default: `books/{project}/export/`)

## Instructions

### Step 1: Find Project

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, fall back to:
   - Detect the current project from working directory
   - If not found, ask user which project to export (or suggest `/select-book`)

Read `books/{project}/project.yaml` for metadata.

### Step 2: Pre-Export Completeness Check

Run a completeness check before exporting:

**Required files:**
- [ ] `01-premise.md` exists
- [ ] `03-treatment.md` exists
- [ ] `04-structure-plan.md` exists
- [ ] For novella/novel/epic: `06-chapters/chapter-*.md` files
- [ ] For flash/short/novelette: `06-story.md`

**Recommended (do not block export if missing):**
- [ ] For flash/short/novelette: `05-story-plan.md` exists (useful as the micro beat sheet / prose contract)
- [ ] For novella/novel/epic: `05-chapter-plans/chapter-*-plan.md` files exist (useful as generation plans / audit trail)

**Ordering and consistency:**
- [ ] Chapter numbering is sequential (no gaps: 01, 02, 03...)
- [ ] All chapter files are non-empty
- [ ] Chapter count matches structure-plan

**Report issues before proceeding:**

```
PRE-EXPORT CHECK
------------------------------------------------------------------------

Files:
  [x] 01-premise.md
  [x] 03-treatment.md
  [x] 04-structure-plan.md
  [x] 06-chapters/ (12 of 12 chapters)

Issues:
  [ ] Chapter 07 is empty (0 words)
  [ ] Missing chapter-08.md (numbering gap: 07 -> 09)

------------------------------------------------------------------------
```

If critical issues found (missing files, empty chapters, numbering gaps):
```
Export blocked. Fix these issues first:
  - Generate missing chapter 08: /generate prose
  - Check chapter 07 for content

Or force export with incomplete content? (y/n)
```

If no issues, proceed to export.

### Step 3: Choose Format

**Format: md (default)**
- Combines all chapters into a single markdown file
- Reader-ready format

**Format: full**
- Includes premise, treatment, and prose
- Useful for reference or archival

### Step 4: Generate Export

Create the export directory if needed:

```bash
mkdir -p books/{project}/export
```

**MD Format (reader-ready):**

```markdown
# {Title}

by {Author}

---

{Chapter 1 content}

---

{Chapter 2 content}

---

{Continue for all chapters...}

---

*The End*
```

**Full Format (complete reference):**

```markdown
# {Title}

by {Author}

Genre: {genre}
Length: {word count} words

---

# PART I: DEVELOPMENT

## Premise

{01-premise.md content}

## Treatment

{03-treatment.md content}

## Structure Plan

{04-structure-plan.md content, if exists}

## Story Plan (flash/short/novelette only)

{05-story-plan.md content, if exists}

---

# PART II: MANUSCRIPT

{All chapters with proper formatting}

---

# METADATA

- Project: {name}
- Created: {date}
- Total Words: {count}
- Chapters: {count}
- Last Modified: {date}
```

### Step 5: Write Export

Write the file and report:

```bash
# Write export file
# Example: books/my-novel/export/my-novel.md
```

```
Export complete!

  File: books/{project}/export/{project}.md
  Format: {md/full}
  Size: {word count} words

The exported file is ready for reading or further processing.
```

### Step 6: Git Commit

Commit the export (consistent with "git everything" principle):

```bash
cd books && git add {project}/export/{project}.md && git commit -m "Add: Export {project} ({format} format)"
```

This maintains version history for all exports.

## Flash/Short/Novelette Export

For flash fiction, short stories, and novelettes, the export is simpler since there's only one prose file:

**MD Format:**
```markdown
# {Title}

by {Author}

---

{06-story.md content}

---

*The End*
```

## Word Count Calculation

Calculate and display word counts:

```bash
# Count words in prose files
wc -w books/{project}/06-chapters/chapter-*.md
# or
wc -w books/{project}/06-story.md
```

Report:
- Per-chapter word counts
- Total prose word count
- Average chapter length (novella/novel/epic)

## Optional Front/Back Matter

If these files exist in the project directory, include them in the export:

| File | Location in Export |
|------|-------------------|
| `dedication.md` | After title page, before first chapter |
| `epigraph.md` | After dedication (if present), before first chapter |
| `acknowledgments.md` | After "The End", as back matter |
| `author-note.md` | After acknowledgments |
| `about-author.md` | At the very end |

**Check for these files:**
```bash
ls books/{project}/dedication.md books/{project}/epigraph.md books/{project}/acknowledgments.md books/{project}/author-note.md books/{project}/about-author.md 2>/dev/null
```

**Updated MD Format with optional matter:**

```markdown
# {Title}

by {Author}

---

{dedication.md content, if exists}

---

{epigraph.md content, if exists}

---

{Chapter 1 content}

---

{Chapter 2 content}

...

---

*The End*

---

{acknowledgments.md content, if exists}

---

{author-note.md content, if exists}

---

{about-author.md content, if exists}
```

Only include sections that exist. Omit the `---` separator for missing sections.

## Export Checklist

Before completing export, verify:

1. All chapter files exist and have content
2. Chapter numbering is sequential
3. No placeholder text remains
4. Title and author are set in project.yaml

## Additional Export Options (Future)

These formats could be added later:
- `epub` - eBook format
- `pdf` - Print-ready format
- `docx` - Word document

For now, the markdown export can be converted using external tools like Pandoc:

```bash
# From inside books/{project}/
pandoc export/{project}.md -o export/{project}.epub
pandoc export/{project}.md -o export/{project}.pdf
```

Mention this option to users who need other formats.
