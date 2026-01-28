---
name: select-book
description: Select a book project to work on.
argument-hint: "[book-name]"
---

Select a book project to work on. All subsequent `/generate`, `/iterate`, `/status`, `/review`, and `/export` commands will operate on this book.

## Usage

```
/select-book [book-name]
```

## Arguments

- `book-name` (optional): Name of the book project to select. If not provided, list available books.

## Instructions

### Step 1: List Available Books

Read the `books/` directory to find available projects:

```bash
ls -d books/*/ 2>/dev/null | xargs -I{} basename {}
```

Filter out system directories (like `.git`).

### Step 2: Select Book

If `book-name` argument provided:
- Verify the project exists in `books/{book-name}/`
- Verify `project.yaml` exists
- If valid, update `books/active-book.md`

If `book-name` not provided:
- Display the list of available books
- Ask user to select one:

```
Available book projects:
  1. {book-name-1}
  2. {book-name-2}
  3. {book-name-3}

Which project would you like to work on?
```

### Step 3: Verify Project

Before setting as active, verify the project has a valid `project.yaml`:

```bash
cat books/{book-name}/project.yaml
```

If `project.yaml` is missing, warn the user:

```
Warning: {book-name} is missing project.yaml.
This may be an incomplete or corrupted project.

Set as active anyway? (y/n)
```

### Step 4: Update Active Book File

Edit `books/active-book.md` to set the selected project:

```markdown
# Active Book

The currently selected book project.

```yaml
project: {book-name}
```

To change the active book, use `/select-book`.
```

### Step 5: Show Confirmation

Display confirmation with project details:

```
Active book set to: {book-name}

  Title: {title from project.yaml}
  Author: {author from project.yaml}
  Genre: {genre from project.yaml}
  Length: {length from project.yaml}

All commands (/generate, /iterate, /status, /review, /export) will now operate on this project.

To see project status: /status
To switch projects: /select-book
```

### Step 6: Show Current Active Book (No Args, Already Set)

If called with no arguments and there's already an active book, show:

```
Current active book: {book-name}

  Title: {title}
  Author: {author}
  Genre: {genre}
  Length: {length}

Available projects:
  1. {book-name-1} {" (active)" if current}
  2. {book-name-2}
  3. {book-name-3}

Select a different project?
```

## Clearing Active Book

To clear the active book (so commands will prompt):

```
/select-book none
```

This sets `project: null` in `active-book.md`.

## Error Handling

- If `books/` directory doesn't exist, suggest running `/new-book` first
- If no projects exist, suggest running `/new-book` first
- If specified project doesn't exist, show available options
