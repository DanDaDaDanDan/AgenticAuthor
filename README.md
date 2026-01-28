# AgenticAuthor

**AI-powered book generation using Claude Code skills.**

AgenticAuthor uses Claude Code as the orchestrator to help you write complete books through a structured, iterative process. It uses a "Level of Detail" approach, starting from a premise and progressively building up to full prose.

## Features

- **Structured Generation Pipeline**: premise → treatment → prose (with automatic planning)
- **Natural Language Iteration**: Give feedback in plain English to refine your content
- **Git-Backed Version Control**: Every change is automatically committed
- **Quality-First Approach**: No artificial word count pressure
- **Per-Project Prose Styles**: Six style options selected during premise generation
- **Taxonomies**: 14 taxonomy files (base, 12 genre-specific, and style) guide story development

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed

## Quick Start

1. **Navigate to AgenticAuthor:**
   ```bash
   cd AgenticAuthor
   ```

2. **Create a new project:**
   ```
   /new-book my-fantasy
   ```

3. **Generate your book:**
   ```
   /generate premise
   /generate treatment
   /generate prose
   ```

4. **Iterate with natural language:**
   ```
   /iterate prose "make it darker and more suspenseful"
   ```

5. **Export your book:**
   ```
   /export
   ```

## Working with Multiple Projects

All commands operate on the **active book**. When you create a new project with `/new-book`, it automatically becomes active.

**Check current project:** Run `/select-book` with no arguments to see which project is active and list all available projects.

**Switch projects:**
```
/select-book my-other-book
```

The active book is stored in `books/active-book.yaml`.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/select-book` | Select a book project to work on |
| `/generate` | Generate premise, treatment, or prose |
| `/iterate` | Refine content with natural language feedback |
| `/review` | Analyze content against quality standards |
| `/status` | Show project progress |
| `/export` | Export book to single file |

## Core Workflow

Three user commands, with planning handled automatically:

| Command | Output | Implicit Steps |
|---------|--------|----------------|
| `/generate premise` | premise.md | — |
| `/generate treatment` | treatment.md | Generates treatment-approach.md first |
| `/generate prose` | chapters/ or short-story.md | Generates structure-plan.md and chapter/story plans first |

Each stage builds on the previous. Generation runs autonomously to completion — use `/iterate` afterward to refine any output.

## Natural Language Iteration

Refine any content using plain English feedback:

```
/iterate prose
"add more internal dialogue"
"focus more on the character's backstory"
"increase the tension in the climax"
```

Each iteration is committed to git, so you can always review history or revert changes.

## Project Structure

Generated projects are stored in the `books/` directory:

```
books/
├── .git/                      # Shared git repository
└── my-book/
    ├── project.yaml           # Metadata
    ├── premise.md             # Book premise
    ├── treatment-approach.md  # Treatment planning (auto-generated)
    ├── treatment.md           # Detailed treatment
    ├── structure-plan.md      # Scene/chapter plan
    ├── summaries.md           # Prose summaries
    ├── chapter-plans/         # Generation plans (novels)
    │   ├── chapter-01-plan.md
    │   └── ...
    ├── chapters/              # Prose chapters (novels)
    │   ├── chapter-01.md
    │   └── ...
    ├── short-story-plan.md    # Generation plan (short stories/novelettes)
    └── short-story.md         # Complete story (short stories/novelettes)
```

## Taxonomies

The `taxonomies/` directory contains 14 JSON files that guide story development:

**Base taxonomy:** Universal properties (length, audience, pacing, POV, content rating)

**Genre taxonomies (12):**
- Fantasy, Science Fiction, Romance, Horror
- Mystery/Thriller, Urban Fantasy, Romantasy
- Contemporary Fiction, Literary Fiction
- Historical Fiction, Young Adult, Generic

**Style taxonomy:** Prose style options (Commercial, Literary, Minimalist, Pulp, Lyrical, Conversational)

Genre and style selections are recorded in the project's `premise.md` and guide all subsequent generation.

## Prose Styles

Style is selected per-project during premise generation. Six approaches are available:

- **Commercial** - Clear, readable, mass-market appeal
- **Literary** - Denser prose, rewards close reading, thematic depth
- **Minimalist** - Spare, precise, subtext-heavy
- **Pulp** - Fast, punchy, momentum-driven
- **Lyrical** - Poetic, atmospheric, sensory-rich
- **Conversational** - Strong narrative voice, personality-driven

Each style has a corresponding reference card in `misc/prose-style-{style}.md` with detailed guidance.

The selected style is recorded in `premise.md` and guides all prose generation for that project.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture, file formats, and system design
- **[CLAUDE.md](CLAUDE.md)** - Claude Code guidance (for AI assistant)

## Core Principles

1. **Self-Contained Stages** - Each stage's output contains everything the next stage needs
2. **Quality First** - No artificial constraints on generation
3. **Git Everything** - Every operation commits for version history
4. **Natural Language** - Iterate using plain English feedback

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
