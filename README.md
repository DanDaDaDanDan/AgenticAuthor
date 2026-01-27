# AgenticAuthor

**AI-powered book generation using Claude Code skills.**

AgenticAuthor uses Claude Code as the orchestrator to help you write complete books through a structured, iterative process. It uses a "Level of Detail" approach, starting from a premise and progressively building up to full prose.

## Features

- **Structured Generation Pipeline**: premise → treatment → structure plan → generation plan → prose
- **Natural Language Iteration**: Give feedback in plain English to refine your content
- **Git-Backed Version Control**: Every change is automatically committed
- **Quality-First Approach**: No artificial word count pressure
- **Style Cards**: Define and maintain consistent prose style across your book
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

3. **Generate your book step by step:**
   ```
   /generate premise
   /generate treatment
   /generate plan        # Structure plan (all project types)
   /generate prose       # Includes chapter plan step
   ```

4. **Iterate with natural language:**
   ```
   /iterate prose "make it darker and more suspenseful"
   ```

5. **Export your book:**
   ```
   /export
   ```

## Available Skills

| Skill | Purpose |
|-------|---------|
| `/new-book` | Create a new book project |
| `/generate` | Generate premise, treatment, plan, or prose |
| `/iterate` | Refine content with natural language feedback |
| `/review` | Analyze content against quality standards |
| `/status` | Show project progress |
| `/export` | Export book to single file |

## Core Workflow

### 1. Premise Generation
The starting point - a high-level concept for your book including protagonist, antagonist, conflict, stakes, and themes.

### 2. Treatment
Expands the premise into a detailed outline with character arcs and plot structure (Act I, II, III).

### 3. Structure Plan
A chapter-by-chapter breakdown (novels) or scene-by-scene plan (short stories) with POV, settings, and goals.

### 4. Chapter/Story Plan
An external generation plan for each chapter (or the story), analyzing continuity, character states, and style before writing.

### 5. Prose Generation
Writes the actual prose following the style card guidelines. For novels, generates chapter-by-chapter. For short stories, generates a single short-story.md file.

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
    ├── treatment.md           # Detailed treatment
    ├── structure-plan.md      # Scene/chapter plan
    ├── summaries.md           # Prose summaries
    ├── chapter-plans/         # Generation plans (novels)
    │   ├── chapter-01-plan.md
    │   └── ...
    ├── chapters/              # Prose chapters (novels)
    │   ├── chapter-01.md
    │   └── ...
    ├── short-story-plan.md    # Generation plan (short stories)
    └── short-story.md         # Complete story (short stories)
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

## Style Card

The prose style card (`misc/prose-style-card.md`) defines writing standards:

- Readability: Flesch Reading Ease 60-80
- Sentence length: 12-16 words average
- Dialogue ratio: 35-50% in character scenes
- POV: Single POV per scene
- Pacing: POISE structure (Purpose, Obstacle, Interaction, Stakes, End-turn)

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture, file formats, and system design
- **[CLAUDE.md](CLAUDE.md)** - Claude Code guidance (for AI assistant)

## Core Principles

1. **Context is King** - Full context from prior stages, quality over token savings
2. **Quality First** - No artificial constraints on generation
3. **Git Everything** - Every operation commits for version history
4. **Natural Language** - Iterate using plain English feedback

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
