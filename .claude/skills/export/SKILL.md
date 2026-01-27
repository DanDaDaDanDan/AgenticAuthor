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

Detect the current project from working directory or ask user.

Read `project.yaml` for metadata.

### Step 2: Verify Completion

Check that all required files exist in `books/{project}/`:
- `premise.md`
- `treatment.md`
- For novels: `chapters/chapter-*.md` files
- For short stories/novelettes: `short-story.md`

If prose is incomplete, warn the user:

```
Warning: Prose generation is incomplete.
  - {X} of {Y} chapters exist

Export anyway? (The export will include only existing content)
```

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

{premise.md content}

## Treatment

{treatment.md content}

## Structure Plan

{structure-plan.md content, if exists}

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

### Step 6: Git Commit (Optional)

Ask user if they want to commit the export:

```
Commit export to git? (y/n)
```

If yes:
```bash
cd books && git add {project}/export/{project}.md && git commit -m "Add: Export {project} ({format} format)"
```

## Short Story/Novelette Export

For short stories and novelettes, the export is simpler since there's only one prose file:

**MD Format:**
```markdown
# {Title}

by {Author}

---

{short-story.md content}

---

*The End*
```

## Word Count Calculation

Calculate and display word counts:

```bash
# Count words in prose files
wc -w books/{project}/chapters/*.md
# or
wc -w books/{project}/short-story.md
```

Report:
- Per-chapter word counts
- Total prose word count
- Average chapter length (novels)

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
pandoc export/{project}.md -o export/{project}.epub
pandoc export/{project}.md -o export/{project}.pdf
```

Mention this option to users who need other formats.
