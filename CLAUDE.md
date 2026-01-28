# CLAUDE.md

Guidance for Claude Code when working with AgenticAuthor. See [ARCHITECTURE.md](ARCHITECTURE.md) for system overview.

## Overview

AgenticAuthor uses Claude Code skills for AI-powered book generation. No separate application - Claude Code is the orchestrator.

**User commands:** `/generate premise` → `/generate treatment` → `/generate prose`

Planning steps (treatment-approach, structure-plan, chapter-plans) are implicit — the AI generates them automatically before the main output.

## Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project (sets it as active) |
| `/select-book` | Select a book project to work on |
| `/generate` | Generate premise, treatment, or prose |
| `/iterate` | Refine content with natural language feedback |
| `/review` | Analyze content against quality standards |
| `/status` | Show project progress |
| `/export` | Export book to single file |

## Active Book

All skills operate on the **active book** stored in `books/active-book.yaml`. This avoids needing to specify the project for each command.

- `/new-book` automatically sets the new project as active
- `/select-book` switches to a different project
- All other commands use the active book (with fallback to current directory)

The file format:
```yaml
project: my-fantasy-novel
```

## Structure

```
AgenticAuthor/
├── taxonomies/            # 14 JSON files (base, 12 genre, style)
├── misc/
│   └── prose-style-*.md   # 6 style cards (commercial, literary, minimalist, pulp, lyrical, conversational)
├── .claude/skills/        # Skill definitions
└── books/                 # Book projects (separate git repo)
    ├── active-book.yaml     # Currently selected project
    └── {project}/
        ├── project.yaml         # Includes length, series_structure as taxonomy keys
        ├── premise.md           # YAML frontmatter with all taxonomy keys + display names
        ├── treatment-approach.md
        ├── treatment.md
        ├── structure-plan.md    # All project types
        ├── summaries.md         # Generated after prose
        ├── chapter-plans/       # Generation plans (novella/novel/epic)
        ├── chapters/            # Prose chapters (novella/novel/epic)
        ├── short-story-plan.md  # Generation plan (flash/short/novelette)
        └── short-story.md       # Complete story (flash/short/novelette)
```

## Core Principles

### Self-Contained Stages

Each stage's output contains everything the next stage needs. Read only one step back, never two.

**For novella/novel/epic (chaptered formats):**

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| treatment-approach | premise + taxonomies | — |
| treatment | treatment-approach + premise | — |
| structure-plan | treatment only | premise, treatment-approach |
| chapter-plan | structure-plan + summaries + prev chapter-plans | premise, treatment-approach, treatment |
| prose | chapter-plan + summaries + prev chapters + prose-style-{prose_style_key} | premise, treatment-approach, treatment, structure-plan |

**For flash/short/novelette (single-file formats):** Same principle — short-story-plan reads structure-plan, prose reads short-story-plan only.

**Why:** This prevents conflicts when iterating. If you change treatment, structure-plan sees the update automatically. Premise becomes "historical" (the seed), not the contract.

### Plan Before Writing

Automatically generate planning documents before major outputs:

**`/generate treatment`** creates `treatment-approach.md` first, then `treatment.md` with YAML frontmatter (carries forward style, tone, themes from premise).

**`/generate prose`** creates structure-plan and chapter/story plans first. Each includes frontmatter so downstream stages are self-contained.

### Quality First

- Follow the prose style in the current stage's frontmatter
- Never generate placeholder content
- Each generation should be publication-ready

### Sub-Agent Execution

Generation work runs in sub-agents with isolated context:

1. **Main agent** asks clarifying questions upfront, then spawns sub-agents
2. **Sub-agents** receive ONLY the files they need (per self-contained stages)
3. Sub-agents run autonomously to completion — no approval steps
4. Each sub-agent commits its work before returning

**Why sub-agents?**
- Context isolation prevents contamination from earlier stages
- Token efficiency — each generation uses minimal context
- Autonomy — `/generate prose` runs start-to-finish without interruption

**Main agent does NOT:**
- Ask for approval between generation steps
- Read files that sub-agents will read (wastes context)
- Generate content directly (except premise, which is interactive)

### Taxonomy Keys + Display Names

All YAML frontmatter stores **both** taxonomy keys (for tooling) and display names (for readability):

```yaml
# Keys enable deterministic tooling
target_audience_key: adult
content_rating_key: mature
prose_style_key: pulp

# Display names are human-readable
target_audience: "Adult"
content_rating: "Mature/R"
prose_style: "Pulp/Action"
```

**Required taxonomy categories** (from base-taxonomy.json):
- `length` — collected by `/new-book` (stored as `length_key` in frontmatter)
- `series_structure` — collected by `/new-book` (stored as `series_structure_key` in frontmatter)
- `target_audience` — collected by `/generate premise`
- `content_rating` — collected by `/generate premise`

### Git Everything

Every skill operation commits to the books/ git repo. This enables iteration and rollback.

## Key Paths

- **Book files:** `books/{project}/`
- **Style cards:** `misc/prose-style-{prose_style_key}.md` (commercial, literary, minimalist, pulp, lyrical, conversational)
- **Taxonomies:** `taxonomies/`

The prose style cards and taxonomies are at the repo root, NOT inside book projects.
