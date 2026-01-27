# CLAUDE.md

Guidance for Claude Code when working with AgenticAuthor. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed file formats and system design.

## Overview

AgenticAuthor uses Claude Code skills for AI-powered book generation. No separate application - Claude Code is the orchestrator.

**User commands:** `/generate premise` → `/generate treatment` → `/generate plan` → `/generate prose`

Planning steps (treatment-approach, chapter-plans) are implicit — the AI generates them automatically before the main output.

## Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/generate` | Generate premise, treatment, plan, or prose |
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
        ├── short-story-plan.md  # Generation plan (short stories)
        └── short-story.md       # Complete story (short stories)
```

## Core Principles

### Context is King

Always include full context from previous stages when generating prose:
- premise.md (includes prose style selections), treatment.md, structure-plan.md (100% each)
- chapter-plans/ or short-story-plan.md (generation plans)
- summaries.md (quick reference for continuity)
- All previous chapters (100% each)
- misc/prose-style-card.md only if premise uses Commercial style

Never truncate context. Token costs are negligible vs quality loss.

### Plan Before Writing

Automatically generate planning documents before major outputs:

**`/generate treatment`** creates `treatment-approach.md` first:
- Analyzes premise systematically (conflict, arcs, themes)
- Proposes structure and identifies potential challenges
- User reviews before treatment generation proceeds

**`/generate prose`** creates chapter/story plans first:
- `chapter-plans/` (novels) or `short-story-plan.md` (short stories)
- Analyzes continuity, character states, style
- User reviews before prose generation proceeds

These implicit planning steps improve quality and enable iteration before committing to the main output.

### Quality First

- Follow the prose style selected in premise.md (Commercial/Literary/Minimalist/Pulp/Lyrical/Conversational)
- Never generate placeholder content
- Each generation should be publication-ready

### Git Everything

Every skill operation commits to the books/ git repo. This enables iteration and rollback.

## Key Paths

- **Book files:** `books/{project}/`
- **Style card:** `AgenticAuthor/misc/prose-style-card.md` (repo root)
- **Taxonomies:** `AgenticAuthor/taxonomies/` (repo root)

The prose style card and taxonomies are at the repo root, NOT inside book projects.
