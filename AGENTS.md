# Repository Guidelines

Keep this guide concise. Treat `CLAUDE.md` and `ARCHITECTURE.md` as the sources of truth.

## Project Structure

- See `ARCHITECTURE.md` for the complete layout and roles.
- In brief: `.claude/skills/` holds skill definitions; `books/` stores per-project artifacts; `taxonomies/` configures genres; `misc/` contains style cards.

## Skills

Skills are markdown files in `.claude/skills/` that define Claude Code operations:

- `new-book.md` - Create new book projects
- `generate.md` - Generate content at each stage
- `iterate.md` - Refine content with feedback
- `status.md` - Show project progress
- `export.md` - Export book to single file

## Adding New Skills

1. Create `.claude/skills/your-skill.md`
2. Define purpose, arguments, and step-by-step instructions
3. Document in `ARCHITECTURE.md` and `CLAUDE.md`

## Commit Guidelines

- Format: `<Type>: <summary>` (e.g., `Add: ...`, `Update: ...`, `Fix: ...`)
- ≤72 chars, imperative mood
- Commit after each meaningful change
- Link `ARCHITECTURE.md` when making architectural changes

## File Conventions

- `.md` - Human-readable content (prose, premises, treatments, skills)
- `.yaml` - Project metadata
- `.json` - Genre taxonomies
