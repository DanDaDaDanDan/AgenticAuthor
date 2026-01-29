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

### Step 1: Detect Project and Gather Arguments

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, ask user which project to export (or suggest `/select-book`)

**Determine format:**
- If `format` argument provided, use it
- Otherwise, default to `md`

**Determine output path:**
- If `output-path` argument provided, use it
- Otherwise, default to `books/{project}/export/`

### Step 2: Spawn Export Sub-Agent

Use the Task tool to spawn an Export Sub-Agent with subagent_type `general-purpose`.

**Sub-agent prompt template:**

```
You are the Export Sub-Agent for AgenticAuthor.

## Task
Export the book "{project}" to format "{format}" at path "{output_path}".

## Instructions

### Step 1: Pre-Export Completeness Check

Read `books/{project}/project.yaml` for metadata (title, author, length_key, genre).

**Required files:**
- [ ] `01-premise.md` exists
- [ ] `03-treatment.md` exists
- [ ] `04-structure-plan.md` exists
- [ ] For novella/novel/epic (length_key): `06-chapters/chapter-*.md` files
- [ ] For flash/short/novelette (length_key): `06-story.md`

**Check ordering and consistency:**
- [ ] Chapter numbering is sequential (no gaps: 01, 02, 03...)
- [ ] All chapter files are non-empty
- [ ] Chapter count matches structure-plan

**If critical issues found (missing files, empty chapters, numbering gaps):**
Return a message describing the issues and recommend fixes. Do NOT proceed with export.

**If no critical issues**, proceed to export.

### Step 2: Read All Required Files

For md format:
- All chapter files (novella/novel/epic) OR `06-story.md` (flash/short/novelette)
- Optional front/back matter: dedication.md, epigraph.md, acknowledgments.md, author-note.md, about-author.md

For full format:
- All of the above PLUS:
- `01-premise.md`
- `03-treatment.md`
- `04-structure-plan.md`
- `05-story-plan.md` (flash/short/novelette, if exists)

### Step 3: Generate Export

Create the export directory if needed:

**PowerShell:**
```powershell
New-Item -ItemType Directory -Force -Path books/{project}/export | Out-Null
```

**MD Format (reader-ready):**

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

---

{Continue for all chapters...}

---

*The End*

---

{acknowledgments.md content, if exists}

---

{author-note.md content, if exists}

---

{about-author.md content, if exists}
```

Only include sections that exist. Omit `---` separators for missing sections.

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

{04-structure-plan.md content}

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

### Step 4: Calculate Word Count

Count words in all prose files and report:
- Per-chapter word counts (if chaptered)
- Total prose word count
- Average chapter length (novella/novel/epic)

### Step 5: Write Export File

Write to: `books/{project}/export/{project}.md`

### Step 6: Git Commit

**PowerShell:**
```powershell
cd books; git add {project}/export/{project}.md; git commit -m "Add: Export {project} ({format} format)"
```

### Step 7: Return Summary

Return a summary message:

```
Export complete!

  File: books/{project}/export/{project}.md
  Format: {md/full}
  Size: {word count} words

The exported file is ready for reading or further processing.

For other formats, use Pandoc:
  pandoc export/{project}.md -o export/{project}.epub
  pandoc export/{project}.md -o export/{project}.pdf
```
```

### Step 3: Report Result

When the sub-agent returns, relay the result to the user:
- If successful: show the export summary
- If blocked: show the issues and recommended fixes

## Why Sub-Agent?

Export is purely mechanical file assembly. The user doesn't need to discuss the process — they just want the file created. Running in a sub-agent:
- Keeps prose content out of main context
- Allows the export to run autonomously
- Returns a clean summary when done
