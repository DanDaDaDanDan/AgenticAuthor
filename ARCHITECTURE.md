# AgenticAuthor — Architecture

AgenticAuthor uses Claude Code skills to generate books. There is no separate application — Claude Code is the orchestrator.

## Design Philosophy

- **Self-Contained Stages:** Each stage's output contains everything the next stage needs. You only read one step back, never two.
- **Quality First:** Follow the prose style in the current stage's frontmatter. Never generate placeholder content.
- **Git Everything:** Every operation commits to git for version history and iteration.
- **Natural Language Iteration:** Users refine content with plain English feedback.

## Repository Layout

```
AgenticAuthor/
├── CLAUDE.md              # Claude Code guidance
├── ARCHITECTURE.md        # This file
├── taxonomies/            # Story classification (14 JSON files)
├── misc/
│   └── prose-style-*.md      # 6 style cards (commercial, literary, minimalist, pulp, lyrical, conversational)
├── .claude/
│   └── skills/               # Claude Code skill definitions
│       ├── new-book/SKILL.md
│       ├── select-book/SKILL.md
│       ├── generate/SKILL.md
│       ├── iterate/SKILL.md
│       ├── review/SKILL.md
│       ├── status/SKILL.md
│       └── export/SKILL.md
└── books/                    # Book projects (separate git repo)
    └── {project}/
```

## Project Structure

Each book project in `books/{project}/` contains:

| File | Purpose |
|------|---------|
| `project.yaml` | Metadata (name, title, author, genre, length) |
| `premise.md` | Core concept and story foundation |
| `treatment-approach.md` | Planning rationale (auto-generated) |
| `treatment.md` | Story outline with act structure |
| `structure-plan.md` | Scene/chapter breakdown |
| `summaries.md` | Prose summaries for continuity |
| `chapter-plans/` | Per-chapter generation plans (novels) |
| `chapters/` | Prose chapters (novels) |
| `short-story-plan.md` | Generation plan (short stories/novelettes) |
| `short-story.md` | Complete prose (short stories/novelettes) |

## Skills

All skills are defined in `.claude/skills/{skill}/SKILL.md`:

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/select-book` | Select a book project to work on |
| `/generate` | Generate premise, treatment, or prose |
| `/iterate` | Refine content with feedback |
| `/review` | Analyze without changes |
| `/status` | Show progress |
| `/export` | Export to single file |

## Generation Flow

Three user commands with implicit planning steps:

```
/generate premise    → premise.md

/generate treatment  → [treatment-approach.md] → treatment.md

/generate prose      → [structure-plan.md] → [plans] → prose
```

Bracketed steps `[...]` are generated automatically. Generation runs autonomously to completion; use `/iterate` afterward to refine.

**For novels:** Prose generates `chapter-plans/` and `chapters/` directories.

**For short stories/novelettes:** Prose generates `short-story-plan.md` and `short-story.md`.

## Self-Contained Stages

Each stage reads only its immediate predecessor. This prevents conflicts when iterating:

| Generating | Reads |
|------------|-------|
| treatment-approach | premise + taxonomies |
| treatment | treatment-approach + premise |
| structure-plan | treatment only |
| chapter-plan | structure-plan + summaries + previous chapter plan (if exists) |
| prose | plan + summaries + all previous chapters + prose-style-{prose_style_key} |

**Why this matters:** If you iterate on treatment and change the ending, structure-plan sees the update automatically because it only reads treatment. Premise becomes "historical" (the seed), not the contract.

Full context rules are in `.claude/skills/generate/SKILL.md`.

## Where to Find Details

| Topic | Location |
|-------|----------|
| File formats & templates | `.claude/skills/generate/SKILL.md` — Templates section |
| Context rules | `.claude/skills/generate/SKILL.md` — Context Management Summary |
| Sub-agent execution model | `.claude/skills/generate/SKILL.md` — Execution Model |
| Iteration guidelines | `.claude/skills/iterate/SKILL.md` |
| Review criteria | `.claude/skills/review/SKILL.md` |
| Taxonomy options | `taxonomies/*.json` |
| Prose style cards | `misc/prose-style-{prose_style_key}.md` |

## Extending the System

### Adding a New Skill

1. Create `.claude/skills/your-skill/SKILL.md`
2. Add YAML frontmatter with name, description, and argument-hint
3. Define the skill's purpose, arguments, and instructions
4. Update this file and CLAUDE.md

### Adding a New Taxonomy

1. Create `taxonomies/your-genre-taxonomy.json`
2. Follow the structure of existing taxonomies
3. Add genre mapping in `/new-book` and `/generate premise`
