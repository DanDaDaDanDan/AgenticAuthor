# CLAUDE.md

This file provides guidance to Claude Code when working with AgenticAuthor.

## Project Overview

AgenticAuthor is a **Claude Code skills-based** system for AI-powered book generation. Claude Code is the orchestrator - there is no separate application, API client, or REPL.

**Core Workflow:** premise → treatment → structure plan → prose

**Key Features:**
- Natural language iteration with git-backed version control
- Quality-first prose generation using the prose style card
- Genre taxonomies for consistent story elements
- Claude Code skills handle all operations

## Available Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/generate` | Generate premise, treatment, plan, or prose |
| `/iterate` | Refine content with natural language feedback |
| `/status` | Show project progress |
| `/export` | Export book to single file |

Run any skill by typing it in Claude Code (e.g., `/new-book my-fantasy`).

## Repository Structure

```
AgenticAuthor/
├── CLAUDE.md              # This file
├── ARCHITECTURE.md        # Architecture documentation
├── taxonomies/            # Genre classification (12 JSON files)
│   ├── fantasy-taxonomy.json
│   ├── science-fiction-taxonomy.json
│   └── ...
├── misc/
│   └── prose-style-card.md  # Style guidance for prose
├── .claude/
│   └── skills/            # Skill definitions
└── books/                 # Book projects (separate git repo)
    └── {book-name}/
        ├── project.yaml   # Metadata
        ├── premise.md     # Core concept
        ├── treatment.md   # Story outline
        ├── structure-plan.md  # Chapter plan (novels)
        ├── chapters/      # Prose chapters (novels)
        └── story.md       # Complete story (short stories)
```

## Core Principles

### 1. Context is King

**Always include full context from previous stages when generating.**

For prose generation, include:
- premise.md (100%)
- treatment.md (100%)
- structure-plan.md (100%)
- All previous chapters (100%)
- prose-style-card.md (100%)

Token costs are negligible compared to quality loss from missing context.

### 2. Quality First

- Follow the prose style card guidelines strictly
- Never generate placeholder or skeleton content
- Each generation should be publication-ready

### 3. Git Everything

- Every operation commits to git
- This enables natural language iteration ("make it darker" just works)
- Users can review history, diff versions, and revert changes

### 4. Natural Language Iteration

Users can refine any content with plain English:
- "Make the protagonist more conflicted"
- "Add more tension to chapter 3"
- "The pacing feels slow, tighten it up"

## Quick Start

```bash
# Navigate to AgenticAuthor
cd AgenticAuthor

# Create a new book
/new-book my-fantasy

# Generate content
/generate premise
/generate treatment
/generate plan
/generate prose

# Check progress
/status

# Iterate on content
/iterate prose "add more sensory details"

# Export final book
/export
```

## Taxonomy Files

Located in `taxonomies/`, these provide genre-specific options:

| File | Genre |
|------|-------|
| fantasy-taxonomy.json | Fantasy |
| science-fiction-taxonomy.json | Science Fiction |
| romance-taxonomy.json | Romance |
| horror-taxonomy.json | Horror |
| mystery-thriller-taxonomy.json | Mystery/Thriller |
| urban-fantasy-taxonomy.json | Urban Fantasy |
| romantasy-taxonomy.json | Romantasy |
| contemporary-fiction-taxonomy.json | Contemporary Fiction |
| literary-fiction-taxonomy.json | Literary Fiction |
| historical-fiction-taxonomy.json | Historical Fiction |
| young-adult-taxonomy.json | Young Adult |
| generic-taxonomy.json | Generic (fallback) |

Each taxonomy contains subgenres, themes, world types, and other genre-specific elements to guide story development.

## Prose Style Card

The `misc/prose-style-card.md` defines writing standards:

- **Readability:** Flesch Reading Ease 60-80
- **Sentence length:** 12-16 words average
- **Dialogue:** 35-50% in character scenes
- **POV:** Single POV per scene
- **Pacing:** POISE structure (Purpose, Obstacle, Interaction, Stakes, End-turn)

Always apply these guidelines when generating prose.

## Git Commits

**Commit changes regularly with descriptive messages.**

- Commit after each generation or iteration
- Format: `Type: Short description` (e.g., "Add: Generate premise for my-book")
- Common types: Add, Update, Iterate

## Important Notes

- The `books/` directory has its own git repository
- Each book project is self-contained in `books/{project}/`
- Short stories use `story.md` instead of `chapters/`
- Novels use `structure-plan.md` + `chapters/` directory
