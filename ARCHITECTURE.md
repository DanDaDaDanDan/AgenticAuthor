# AgenticAuthor — Architecture

AgenticAuthor uses Claude Code skills to generate books. There is no separate application - Claude Code is the orchestrator.

## Design Philosophy

- **Self-Contained Stages:** Each stage's output contains everything the next stage needs. You only read one step back, never two. This ensures iteration on any stage doesn't create conflicts with earlier stages.
- **Quality First:** Follow the prose style in the current stage's configuration. Never generate placeholder content.
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
│   ├── prose-style-card.md   # Detailed guidance for Commercial prose style
│   ├── dedication.md         # Example dedication
│   └── backmatter-sloane-grey.md
├── .claude/
│   └── skills/               # Claude Code skill definitions
│       ├── new-book/SKILL.md
│       ├── generate/SKILL.md
│       ├── iterate/SKILL.md
│       ├── review/SKILL.md
│       ├── status/SKILL.md
│       └── export/SKILL.md
└── books/                    # Book projects (separate git repo)
    └── .git/
```

## Project Structure

Each book project lives in `books/{project}/`:

```
books/{project}/
├── project.yaml         # Metadata (name, title, author, genre, length)
├── premise.md           # Core concept and story foundation
├── treatment-approach.md # Planning rationale for treatment
├── treatment.md         # Story outline with act structure
├── structure-plan.md    # Scene/chapter plan (all project types)
├── summaries.md         # Prose summaries (generated after prose)
├── chapter-plans/       # Chapter generation plans (novels only)
│   ├── chapter-01-plan.md
│   ├── chapter-02-plan.md
│   └── ...
├── chapters/            # Prose chapters (novels only)
│   ├── chapter-01.md
│   ├── chapter-02.md
│   └── ...
├── short-story-plan.md  # Story generation plan (short stories only)
├── short-story.md       # Complete story (short stories only)
└── export/              # Exported files
```

## Skills

Skills are defined in `.claude/skills/{skill}/SKILL.md`:

| Skill | Directory | Purpose |
|-------|-----------|---------|
| `/new-book` | new-book/ | Create a new book project |
| `/generate` | generate/ | Generate premise, treatment, or prose |
| `/iterate` | iterate/ | Refine content with feedback |
| `/review` | review/ | Analyze content against quality standards |
| `/status` | status/ | Show project progress |
| `/export` | export/ | Export book to single file |

## Generation Flow

Three user commands with implicit planning steps:

| Command | Implicit Steps | Output |
|---------|----------------|--------|
| `/generate premise` | — | premise.md |
| `/generate treatment` | treatment-approach.md | treatment.md |
| `/generate prose` | structure-plan.md, chapter/story plans | chapters/ or short-story.md |

### Short Stories (≤15,000 words)

```
/generate premise    → premise.md
/generate treatment  → [treatment-approach.md] → treatment.md
/generate prose      → [structure-plan.md] → [short-story-plan.md] → short-story.md
```

### Novels (>15,000 words)

```
/generate premise    → premise.md
/generate treatment  → [treatment-approach.md] → treatment.md
/generate prose      → [structure-plan.md] → [chapter-NN-plan.md → chapter-NN.md] × N
```

Bracketed steps `[...]` are implicit — generated automatically and presented for review before proceeding. Research shows explicit planning before prose generation significantly improves quality (Gurung & Lapata, 2025).

## Context Flow

**Principle:** Each stage reads only the immediately prior stage. Each stage's output is self-contained, carrying forward all information needed by downstream stages.

```
premise.md (seed document)
    ↓ reads premise
treatment.md (self-contained: includes Story Configuration from premise)
    ↓ reads treatment only
structure-plan.md (self-contained: includes style config + characters)
    ↓ reads structure-plan + summaries + previous chapter-plans
chapter-plan.md (self-contained for that chapter)
    ↓ reads chapter-plan + summaries + previous chapters
prose
```

**What each stage reads:**

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| treatment | premise + taxonomies | — |
| structure-plan | treatment only | premise |
| chapter-plan | structure-plan + summaries + prev chapter-plans | premise, treatment |
| prose | chapter-plan + summaries + prev chapters | premise, treatment, structure-plan |

**Why this matters for iteration:** If you iterate on treatment and change the ending, structure-plan only reads treatment—it sees the updated version. Premise becomes "historical" (the seed that started things), not the contract. No conflicts between stages.

**Prose generation uses implicit planning:** Before writing, the AI generates structure-plan.md (if missing) and chapter/story plans. Each is presented for review before proceeding.

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

### treatment-approach.md

Lightweight planning document generated before the full treatment. Analyzes the premise and outlines the intended approach.

```markdown
# Treatment Approach

## Premise Analysis

**Core conflict:** {How the central conflict will drive the story structure}
**Protagonist arc:** {Starting state → transformation → ending state}
**Antagonist role:** {How the opposing force will be deployed across the narrative}
**Stakes escalation:** {How stakes will build throughout the story}

## Theme Integration

- **{Primary theme}:** {How it will manifest in plot/character choices}
- **{Secondary theme}:** {Where it will appear}

## Proposed Structure

**Structure type:** {Three-act / Four-act / Five-act / Episodic / Other}
**Reasoning:** {Why this structure fits the premise}

**Act overview:**
- Act I: {One sentence on setup approach}
- Act II: {One sentence on confrontation/complication approach}
- Act III: {One sentence on resolution approach}

## Subplots

- **{Subplot 1}:** {Brief description and connection to main plot}
- **{Subplot 2}:** {Brief description}

## Potential Challenges

- {Any gaps in the premise that need resolution}
- {Structural tensions to navigate}
- {Pacing considerations}

## Style Considerations

**Prose approach impact:** {How the selected style affects treatment choices}
**Pacing implications:** {How pacing preference shapes scene density}
```

### treatment.md

The treatment is **self-contained** — it includes all story configuration from premise so downstream stages don't need to read premise.

```markdown
# Treatment

## Story Configuration

Carried forward from premise (authoritative for all downstream stages):

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Length:** {novel/novelette/short-story} (~{word count} words)
- **Genre:** {genre/subgenre}
- **Target Audience:** {demographic}
- **Content Rating:** {rating}
- **Tone:** {emotional quality}
- **Themes:** {primary}, {secondary}

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

## World Elements

{Setting and world-building details carried forward from premise}
```

### structure-plan.md (Novels)

The structure plan is **self-contained** — it includes story configuration from treatment so chapter-plans don't need to read treatment.

```markdown
# Structure Plan

## Story Configuration

Carried forward from treatment:

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Tone:** {emotional quality}
- **Content Rating:** {rating}

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {perspective approach}

## Characters

Brief reference for continuity:

- **{Protagonist}:** {one-line arc summary}
- **{Antagonist/Key character}:** {one-line role summary}

## Chapter Breakdown

### Chapter 1: {Title}

**POV:** {character}
**Setting:** {location/time}
**Word count target:** {estimate}

**Treatment reference:** {which act/scenes from treatment this covers}

**Summary:** {what happens}

**Scene breakdown:**
1. {Scene 1 - brief description}
2. {Scene 2 - brief description}

**Chapter goals:**
- {plot advancement}
- {character development}

**Ends with:** {hook/turn}

---

{Continue for each chapter}
```

### structure-plan.md (Short Stories)

The structure plan is **self-contained** — it includes story configuration from treatment so story-plans don't need to read treatment.

```markdown
# Structure Plan

## Story Configuration

Carried forward from treatment:

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Tone:** {emotional quality}
- **Content Rating:** {rating}

## Overview

- **Target word count:** {estimate}
- **Number of scenes:** {count}
- **POV:** {narrative perspective}
- **Timespan:** {how much time the story covers}

## Characters

Brief reference for continuity:

- **{Protagonist}:** {one-line arc summary}
- **{Other key characters}:** {one-line role summary}

## Scene Breakdown

### Scene 1: {Title/Description}

**Setting:** {where and when}
**Word count target:** {estimate}
**Purpose:** {what this scene accomplishes}

**Beat-by-beat:**
1. {Opening beat}
2. {Development}
3. {Turn/Hook}

**Character state:** {emotional state at scene end}

---

{Continue for each scene}

## Story Arc Mapping

- **Opening hook:** Scene {X}
- **Complication:** Scene {X}
- **Climax:** Scene {X}
- **Resolution:** Scene {X}
```

### summaries.md

Generated after prose. Provides compressed context for continuity.

**For novels:**
```markdown
# Chapter Summaries

### Chapter 1: {Title}

{2-4 sentence summary}

**Key events:** {bullet list}
**Character states:** {where main characters end emotionally}

---

{Continue for each chapter}
```

**For short stories:**
```markdown
# Story Summary

{3-5 sentence summary of the complete story}

**Key beats:**
- Opening: {1 sentence}
- Complication: {1 sentence}
- Climax: {1 sentence}
- Resolution: {1 sentence}
```

### chapter-plans/chapter-{NN}-plan.md

External generation plan created before each chapter's prose. Saved for review, iteration, and debugging.

```markdown
# Chapter {N} Plan: {Title}

## Structure Plan Reference
- Treatment reference: {which act/scenes this covers}
- Summary: {planned summary from structure-plan}
- Chapter goals: {from structure-plan}
- Ends with: {planned hook/turn}

## Continuity Check
- {Open threads and their status}
- {Character emotional states entering this chapter}
- {Key established details}
- Promises to readers: {things set up that need payoff}

## Character States
### {POV Character}
- Emotional state: {current mental/emotional state}
- Goal this chapter: {what they want}
- Internal conflict: {tension}
- Voice notes: {how their mental state affects prose voice}

## Scene-by-Scene Breakdown
### Scene 1: {Description}
- Purpose: {why this scene exists}
- Conflict/Tension: {driver}
- Key beats: {specific moments}
- Ends with: {transition}

## Style Notes
- Pacing: {fast/slow/mixed}
- Tone: {emotional quality}
- Dialogue vs narration: {balance}
- Sensory focus: {what senses to emphasize}

## Length Strategy
{2-4 sentences analyzing how this chapter will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls
- {Thing to avoid or be careful about}
- {Continuity risk}
```

### short-story-plan.md

External generation plan for short stories. Similar to chapter plans but covers the entire story.

```markdown
# Story Plan: {Title}

## Structure Plan Reference
- Story arc: {the planned arc from structure-plan}
- Scene count: {number}
- Target word count: {estimate}

## Character States
### {Protagonist}
- Starting emotional state: {where they begin}
- Goal: {what they want}
- Internal conflict: {tension}
- Voice notes: {how to render their perspective}

## Scene-by-Scene Breakdown
### Scene 1: {Description}
- Purpose: {why this scene exists}
- Conflict/Tension: {driver}
- Key beats: {specific moments}
- Ends with: {transition}

## Style Notes
- Pacing: {rhythm}
- Tone: {quality}
- Dialogue vs narration: {balance}
- Sensory focus: {what senses to emphasize}

## Length Strategy
{2-4 sentences analyzing how this story will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls
- {Thing to avoid}
- {Risk to watch for}
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

Style is **selected per-project** during premise generation, then **carried forward** into treatment's Story Configuration section.

**Style approaches:**
- **Commercial** - Clear, readable, mass-market. See `misc/prose-style-card.md` for detailed guidance.
- **Literary** - Denser prose, longer sentences, thematic depth
- **Minimalist** - Spare, precise, subtext-heavy
- **Pulp** - Fast, punchy, action-driven
- **Lyrical** - Poetic, atmospheric, sensory-rich
- **Conversational** - Strong narrative voice, personality-driven

The style flows through the pipeline: premise → treatment (Story Configuration) → structure-plan → chapter-plan (Style Notes). Each stage carries the configuration forward so downstream stages don't need to look backward.

## Git Integration

- The `books/` directory has its own git repository
- Every skill operation commits changes
- Commit messages follow the format: `Type: Description`
- History enables iteration and rollback

## Extending the System

### Adding a New Skill

1. Create `.claude/skills/your-skill/SKILL.md`
2. Add YAML frontmatter with name, description, and argument-hint
3. Define the skill's purpose, arguments, and instructions
4. Document in this file and CLAUDE.md

### Adding a New Taxonomy

1. Create `taxonomies/your-genre-taxonomy.json`
2. Follow the structure of existing taxonomies
3. Add genre mapping in skills that use taxonomies
