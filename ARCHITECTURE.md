# AgenticAuthor — Architecture

AgenticAuthor uses Claude Code skills to generate books. There is no separate application - Claude Code is the orchestrator.

## Design Philosophy

- **Context is King:** Provide complete context from all previous stages. Quality over token thrift.
- **Quality First:** Follow the prose style card strictly. Never generate placeholder content.
- **Git Everything:** Every operation commits to git for version history and iteration.
- **Natural Language Iteration:** Users refine content with plain English feedback.

## Repository Layout

```
AgenticAuthor/
├── CLAUDE.md              # Claude Code guidance
├── ARCHITECTURE.md        # This file
├── taxonomies/            # Story classification (14 JSON files)
│   ├── base-taxonomy.json
│   ├── style-taxonomy.json
│   ├── fantasy-taxonomy.json
│   ├── science-fiction-taxonomy.json
│   ├── romance-taxonomy.json
│   ├── horror-taxonomy.json
│   ├── mystery-thriller-taxonomy.json
│   ├── urban-fantasy-taxonomy.json
│   ├── romantasy-taxonomy.json
│   ├── contemporary-fiction-taxonomy.json
│   ├── literary-fiction-taxonomy.json
│   ├── historical-fiction-taxonomy.json
│   ├── young-adult-taxonomy.json
│   └── generic-taxonomy.json
├── misc/
│   ├── prose-style-card.md   # Style guidance for prose generation
│   ├── copy-edit.md          # Copy editing guidelines
│   ├── dedication.md         # Example dedication
│   └── backmatter-sloane-grey.md
├── .claude/
│   └── skills/               # Claude Code skill definitions
│       ├── new-book.md
│       ├── generate.md
│       ├── iterate.md
│       ├── review.md
│       ├── status.md
│       └── export.md
└── books/                    # Book projects (separate git repo)
    └── .git/
```

## Project Structure

Each book project lives in `books/{project}/`:

```
books/{project}/
├── project.yaml         # Metadata (name, title, author, genre, length)
├── premise.md           # Core concept and story foundation
├── treatment.md         # Story outline with act structure
├── structure-plan.md    # Chapter plan (novels only)
├── chapters/            # Prose chapters (novels only)
│   ├── chapter-01.md
│   ├── chapter-02.md
│   └── ...
├── story.md             # Complete story (short stories only)
└── export/              # Exported files
```

## Skills

Skills are markdown files in `.claude/skills/` that define operations:

| Skill | File | Purpose |
|-------|------|---------|
| `/new-book` | new-book.md | Create a new book project |
| `/generate` | generate.md | Generate premise, treatment, plan, or prose |
| `/iterate` | iterate.md | Refine content with feedback |
| `/review` | review.md | Analyze content against quality standards |
| `/status` | status.md | Show project progress |
| `/export` | export.md | Export book to single file |

## Generation Flow

### Short Stories (≤15,000 words)

```
premise.md → treatment.md → story.md
```

- No structure plan needed
- Single prose file output

### Novels (>15,000 words)

```
premise.md → treatment.md → structure-plan.md → chapters/
```

- Structure plan defines chapter breakdown
- Individual chapter files

## Context Flow

Each stage receives full context from prior stages:

```
premise.md (includes prose style selections)
    ↓
treatment.md + premise.md
    ↓
structure-plan.md + treatment.md + premise.md
    ↓
chapters/*.md + structure-plan.md + treatment.md + premise.md
    ↓
(optional: prose-style-card.md for Commercial style reference)
```

## File Formats

### project.yaml

```yaml
name: my-book
title: The Dragon's Wake
author: Jane Doe
genre: fantasy
length: novel
created: 2025-01-25
```

### premise.md

```markdown
# Premise

{2-3 paragraph concept}

## Core Elements

- **Protagonist:** {name and traits}
- **Antagonist:** {opposing force}
- **Central Conflict:** {main conflict}
- **Stakes:** {consequences of failure}
- **Hook:** {unique compelling element}

## Setting

{world/time/place description}

## Themes

- {Primary theme}
- {Secondary theme}

## Tone

- **Tone:** {emotional quality}
- **Mood:** {atmosphere}

## Prose Style

- **Approach:** {Commercial/Literary/Minimalist/Pulp/Lyrical/Conversational}
- **Pacing:** {Fast/Measured/Slow-burn}
- **Dialogue density:** {High/Moderate/Low}
- **POV:** {narrative perspective}
- **Custom notes:** {user preferences}

## Taxonomy Selections

- **Subgenre:** {from taxonomy}
- **Length:** {word count}
- **Target Audience:** {demographic}
```

### treatment.md

```markdown
# Treatment

## Story Overview

{Complete story arc summary}

## Act Structure

### Act I: {Title}
{Setup, inciting incident, first plot point}

### Act II: {Title}
{Rising action, midpoint, complications}

### Act III: {Title}
{Climax, resolution, ending}

## Character Arcs

{Character development details}

## Subplots

{Secondary storylines}
```

### structure-plan.md (Novels)

```markdown
# Structure Plan

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {perspective approach}

## Chapter Breakdown

### Chapter 1: {Title}

**POV:** {character}
**Setting:** {location/time}
**Word count target:** {estimate}

**Summary:** {what happens}

**Chapter goals:**
- {plot advancement}
- {character development}

**Ends with:** {hook/turn}

---

{Continue for each chapter}
```

## Taxonomy System

Taxonomies in `taxonomies/` provide story classification (14 JSON files):

**Base Taxonomy (`base-taxonomy.json`):**
- Story length (flash fiction → epic)
- Target audience (middle grade → adult)
- Content rating (clean → explicit)
- Series structure (standalone → serial)
- Pacing, POV, ending type

**Genre Taxonomies (12 files):**
- Subgenres specific to the genre
- Thematic elements common to the genre
- World types and settings
- Genre-specific tropes and archetypes
- Plot structures typical of the genre

**Style Taxonomy (`style-taxonomy.json`):**
- Prose approach (Commercial, Literary, Minimalist, Pulp, Lyrical, Conversational)
- Dialogue density preferences
- Pacing style options
- Best-for recommendations per genre

Skills read taxonomies to present options during premise generation. User selections are recorded in premise.md.

## Prose Style

Style is **selected per-project** during premise generation, not mandated globally.

**Style approaches:**
- **Commercial** - Clear, readable, mass-market. See `misc/prose-style-card.md` for detailed guidance.
- **Literary** - Denser prose, longer sentences, thematic depth
- **Minimalist** - Spare, precise, subtext-heavy
- **Pulp** - Fast, punchy, action-driven
- **Lyrical** - Poetic, atmospheric, sensory-rich
- **Conversational** - Strong narrative voice, personality-driven

The selected style is recorded in `premise.md` under "Prose Style" and guides all prose generation for that project. `misc/prose-style-card.md` remains as an optional detailed reference for Commercial style.

## Git Integration

- The `books/` directory has its own git repository
- Every skill operation commits changes
- Commit messages follow the format: `Type: Description`
- History enables iteration and rollback

## Extending the System

### Adding a New Skill

1. Create `.claude/skills/your-skill.md`
2. Define the skill's purpose, arguments, and instructions
3. Document in this file and CLAUDE.md

### Adding a New Taxonomy

1. Create `taxonomies/your-genre-taxonomy.json`
2. Follow the structure of existing taxonomies
3. Add genre mapping in skills that use taxonomies
