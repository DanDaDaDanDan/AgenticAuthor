---
name: new-book
description: Create a new book project. Use when starting any length from flash fiction to epic novels.
argument-hint: "[book-name]"
---

Create a new book project with metadata.

## Usage

```
/new-book [book-name]
```

## Arguments

- `book-name` (optional): Name for the book project (used as directory name)

## Instructions

### Step 1: Gather Information

If `book-name` was not provided as an argument, ask the user:
- What would you like to name your book project? (This will be used as the directory name)

Then ask:
- What genre will this book be? Present these options:
  1. Fantasy
  2. Science Fiction
  3. Romance
  4. Horror
  5. Mystery/Thriller
  6. Urban Fantasy
  7. Romantasy
  8. Contemporary Fiction
  9. Literary Fiction
  10. Historical Fiction
  11. Young Adult
  12. Other (use generic taxonomy)

- What length is this project?
  1. Flash fiction (single file, ~500-1,500 words) - generates `short-story.md`
  2. Short story (single file, ~1,500-7,500 words) - generates `short-story.md`
  3. Novelette (single file, ~7,500-17,500 words) - generates `short-story.md`
  4. Novella (chaptered, ~17,500-40,000 words) - generates `chapters/` directory
  5. Novel (chaptered, ~40,000-120,000 words) - generates `chapters/` directory
  6. Epic (chaptered, ~120,000+ words) - generates `chapters/` directory

- Is this a standalone or part of a series?
  1. Standalone (complete story in one book)
  2. Duology (book 1 or 2 of two-book arc)
  3. Trilogy (book 1, 2, or 3 of three-book arc)
  4. Series (part of 4+ book series)
  5. Serial/Episodic (ongoing episodes)

- What is the working title? (Can be different from project name)
- Who is the author name to use?

### Step 2: Create Project Structure

Create the directory structure:

```
books/{book-name}/
├── project.yaml
└── chapters/        (only for novella, novel, epic)
```

Use the Bash tool to create the directories:
```bash
mkdir -p books/{book-name}/chapters  # for novella, novel, epic
# OR
mkdir -p books/{book-name}           # for flash fiction, short stories, novelettes
```

### Step 3: Create project.yaml

Write the project.yaml file with the gathered information.

**Important:** Store genre, length, and series_structure as taxonomy keys (lowercase with underscores) to enable downstream tooling:

```yaml
name: {book-name}
title: {working-title}
author: {author-name}
genre: {genre-key}  # e.g., fantasy, science-fiction, mystery-thriller
length: {length-key}  # e.g., flash_fiction, short_story, novelette, novella, novel, epic
series_structure: {series_structure-key}  # e.g., standalone, duology, trilogy, series, serial
created: {today's date in YYYY-MM-DD format}
```

**Genre key mapping:**
| User Selection | genre value in YAML |
|---------------|---------------------|
| Fantasy | fantasy |
| Science Fiction | science-fiction |
| Romance | romance |
| Horror | horror |
| Mystery/Thriller | mystery-thriller |
| Urban Fantasy | urban-fantasy |
| Romantasy | romantasy |
| Contemporary Fiction | contemporary-fiction |
| Literary Fiction | literary-fiction |
| Historical Fiction | historical-fiction |
| Young Adult | young-adult |
| Other | generic |

**Length key mapping:**
| User Selection | length value in YAML |
|---------------|----------------------|
| Flash fiction | flash_fiction |
| Short story | short_story |
| Novelette | novelette |
| Novella | novella |
| Novel | novel |
| Epic | epic |

**Series structure key mapping:**
| User Selection | series_structure value in YAML |
|---------------|-------------------------------|
| Standalone | standalone |
| Duology | duology |
| Trilogy | trilogy |
| Series | series |
| Serial/Episodic | serial |

### Step 4: Initialize Git (if needed)

Check if books/.git exists. If not, initialize git:

```bash
cd books && git init
```

### Step 5: Create Initial Commit

Stage and commit the new project:

```bash
cd books && git add {book-name}/ && git commit -m "Add: Initialize {book-name} project"
```

### Step 6: Set as Active Book

Create or update `books/active-book.md` to set the new project as active. The file format is:

```
# Active Book

The currently selected book project.

[yaml code block with: project: {book-name}]

To change the active book, use `/select-book`.
```

Replace the `project:` value in the YAML block with the new book name.

Commit the active book update:

```bash
cd books && git add active-book.md && git commit -m "Update: Set {book-name} as active book"
```

### Step 7: Confirm Creation

Display a summary:

```
Created new book project: {book-name}

  Location: books/{book-name}/
  Title: {working-title}
  Author: {author-name}
  Genre: {genre}
  Length: {length}
  Series: {series_structure}

This project is now active. All commands will operate on it.

Next step:
  Run /generate premise to create your story concept

To switch projects later: /select-book
```

## Genre to Taxonomy Mapping

Map the user's genre choice to the taxonomy file:

| Genre | Taxonomy File |
|-------|--------------|
| Fantasy | fantasy-taxonomy.json |
| Science Fiction | science-fiction-taxonomy.json |
| Romance | romance-taxonomy.json |
| Horror | horror-taxonomy.json |
| Mystery/Thriller | mystery-thriller-taxonomy.json |
| Urban Fantasy | urban-fantasy-taxonomy.json |
| Romantasy | romantasy-taxonomy.json |
| Contemporary Fiction | contemporary-fiction-taxonomy.json |
| Literary Fiction | literary-fiction-taxonomy.json |
| Historical Fiction | historical-fiction-taxonomy.json |
| Young Adult | young-adult-taxonomy.json |
| Other | generic-taxonomy.json |

## Notes

- Project names should be lowercase with hyphens (e.g., "my-fantasy-book")
- The `books/` directory is at the repository root
- All book projects share a single git repository in `books/`
