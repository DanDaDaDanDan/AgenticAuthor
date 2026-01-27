---
name: new-book
description: Create a new book project. Use when starting a new novel, novelette, or short story.
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
  1. Short story (single file, ~1,500-7,500 words) - generates `short-story.md`
  2. Novelette (single file, ~7,500-17,500 words) - generates `short-story.md`
  3. Novel (multiple chapters, ~40,000-120,000 words) - generates `chapters/` directory

- What is the working title? (Can be different from project name)
- Who is the author name to use?

### Step 2: Create Project Structure

Create the directory structure:

```
books/{book-name}/
├── project.yaml
└── chapters/        (only for novels)
```

Use the Bash tool to create the directories:
```bash
mkdir -p books/{book-name}/chapters  # for novels
# OR
mkdir -p books/{book-name}           # for short stories/novelettes
```

### Step 3: Create project.yaml

Write the project.yaml file with the gathered information.

**Important:** Store the genre in lowercase with hyphens to match taxonomy filenames:

```yaml
name: {book-name}
title: {working-title}
author: {author-name}
genre: {genre-key}  # e.g., fantasy, science-fiction, mystery-thriller
length: novel  # or: novelette, short-story
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

### Step 6: Confirm Creation

Display a summary:

```
Created new book project: {book-name}

  Location: books/{book-name}/
  Title: {working-title}
  Author: {author-name}
  Genre: {genre}
  Length: {novel/novelette/short-story}

Next steps:
  1. cd books/{book-name}
  2. Run /generate premise to create your story concept
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
