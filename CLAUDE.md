# CLAUDE.md

Guidance for Claude Code when working with AgenticAuthor. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed file formats and system design.

## Overview

AgenticAuthor uses Claude Code skills for AI-powered book generation. No separate application - Claude Code is the orchestrator.

**Workflow:** premise → treatment → structure plan → prose

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
├── taxonomies/            # 13 JSON files (1 base + 12 genre)
├── misc/
│   └── prose-style-card.md
├── .claude/skills/        # Skill definitions
└── books/                 # Book projects (separate git repo)
    └── {project}/
        ├── project.yaml
        ├── premise.md
        ├── treatment.md
        ├── structure-plan.md  # Novels only
        ├── chapters/          # Novels only
        └── story.md           # Short stories only
```

## Core Principles

### Context is King

Always include full context from previous stages when generating prose:
- premise.md, treatment.md, structure-plan.md (100% each)
- All previous chapters (100% each)
- misc/prose-style-card.md (at repo root)

Never truncate context. Token costs are negligible vs quality loss.

### Quality First

- Follow prose-style-card.md strictly
- Never generate placeholder content
- Each generation should be publication-ready

### Git Everything

Every skill operation commits to the books/ git repo. This enables iteration and rollback.

## Key Paths

- **Book files:** `books/{project}/`
- **Style card:** `AgenticAuthor/misc/prose-style-card.md` (repo root)
- **Taxonomies:** `AgenticAuthor/taxonomies/` (repo root)

The prose style card and taxonomies are at the repo root, NOT inside book projects.
