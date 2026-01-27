# CLAUDE.md

Guidance for Claude Code when working with AgenticAuthor. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed file formats and system design.

## Overview

AgenticAuthor uses Claude Code skills for AI-powered book generation. No separate application - Claude Code is the orchestrator.

**User commands:** `/generate premise` → `/generate treatment` → `/generate prose`

Planning steps (treatment-approach, structure-plan, chapter-plans) are implicit — the AI generates them automatically before the main output.

## Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/generate` | Generate premise, treatment, or prose |
| `/iterate` | Refine content with natural language feedback |
| `/review` | Analyze content against quality standards |
| `/status` | Show project progress |
| `/export` | Export book to single file |

## Structure

```
AgenticAuthor/
├── taxonomies/            # 14 JSON files (base, 12 genre, style)
├── misc/
│   └── prose-style-card.md
├── .claude/skills/        # Skill definitions
└── books/                 # Book projects (separate git repo)
    └── {project}/
        ├── project.yaml
        ├── premise.md
        ├── treatment-approach.md
        ├── treatment.md
        ├── structure-plan.md    # All project types
        ├── summaries.md         # Generated after prose
        ├── chapter-plans/       # Generation plans (novels)
        ├── chapters/            # Prose chapters (novels)
        ├── short-story-plan.md  # Generation plan (short stories/novelettes)
        └── short-story.md       # Complete story (short stories/novelettes)
```

## Core Principles

### Self-Contained Stages

Each stage's output contains everything the next stage needs. Read only one step back, never two.

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| treatment | premise + taxonomies | — |
| structure-plan | treatment only | premise |
| chapter-plan | structure-plan + summaries + prev chapter-plans | premise, treatment |
| prose | chapter-plan + summaries + prev chapters | premise, treatment, structure-plan |

**Why:** This prevents conflicts when iterating. If you change treatment, structure-plan sees the update automatically. Premise becomes "historical" (the seed), not the contract.

### Plan Before Writing

Automatically generate planning documents before major outputs:

**`/generate treatment`** creates `treatment-approach.md` first, then `treatment.md` with Story Configuration section (carries forward style, tone, themes from premise).

**`/generate prose`** creates structure-plan and chapter/story plans first. Each includes Story Configuration so downstream stages are self-contained.

### Quality First

- Follow the prose style in the current stage's Story Configuration
- Never generate placeholder content
- Each generation should be publication-ready

### Git Everything

Every skill operation commits to the books/ git repo. This enables iteration and rollback.

## Key Paths

- **Book files:** `books/{project}/`
- **Style card:** `AgenticAuthor/misc/prose-style-card.md` (repo root)
- **Taxonomies:** `AgenticAuthor/taxonomies/` (repo root)

The prose style card and taxonomies are at the repo root, NOT inside book projects.
