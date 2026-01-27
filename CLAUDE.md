# CLAUDE.md

Guidance for Claude Code when working with AgenticAuthor. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed file formats and system design.

## Overview

AgenticAuthor uses Claude Code skills for AI-powered book generation. No separate application - Claude Code is the orchestrator.

**Workflow:** premise → treatment → structure plan → generation plan → prose (all project types)

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

Before generating prose, create an external generation plan file:
- Saved to `chapter-plans/` (novels) or `short-story-plan.md` (short stories)
- Analyzes plan requirements, continuity, character states, style
- Presented to user for review before prose generation
- Enables iteration on approach before committing to prose

External plans improve quality and make debugging easier.

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
