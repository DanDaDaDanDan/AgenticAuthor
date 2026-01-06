# AgenticAuthor - Comprehensive Architecture Guide

**Version:** 1.0  
**Last Updated:** 2026-01-06  
**Status:** Complete and Verified

## Executive Summary

AgenticAuthor is a sophisticated AI-powered book generation CLI that uses a structured "Level of Detail" (LOD) approach to progressively build books from concept to finished prose. The system orchestrates multiple LLM calls through OpenRouter, manages multi-file project storage with git version control, and provides natural language iteration capabilities.

**Core Workflow:**
```
Premise (LOD3) → Treatment (LOD2) → Chapters (LOD1) → Prose (LOD0)
```

Key innovation: **Natural language iteration** with LLM judge validation, semantic diffs, and automatic git commits for version control and rollback.

---

## Part 1: Core Philosophy and Design Principles

### 1.1 Foundational Principles

#### Full-Context First
- **Philosophy:** Provide LLMs with ALL relevant context. Quality matters more than token savings.
- **Impact:** Generous context inclusion (100k tokens ≈ $0.50) enables better coherence and consistency.
- **Implementation:** `LODContextBuilder` assembles complete context from multi-file storage.

#### Fail Fast, No Fallbacks
- **Philosophy:** Missing artifacts or configuration should halt with clear errors, never silently substitute.
- **Bad:** `premise = self.project.get_premise() or ""`
- **Good:** `if not premise: raise Exception("Generate premise first")`
- **Implementation:** Early checks in all generation modules.

#### Single-Model Policy
- **Philosophy:** Respect user's selected model for ALL operations.
- **Impact:** Prevents cost/quality surprises from fallbacks.
- **Implementation:** Each generator requires explicit model parameter, raises ValueError if missing.

#### Markdown-First Generation
- **Philosophy:** LLMs produce better creative content in markdown; structure extracted post-hoc if needed.
- **Storage:** Raw `.md` files (LLM output) + optional `.yaml` extraction (structural needs).
- **Benefits:** Higher quality prose, easier diffs, human-readable debugging.
- **Implementation:** `MarkdownExtractor` parses markdown files on-the-fly.

#### Deterministic Interfaces
- **Philosophy:** All prompts enforce strict output formats (YAML/JSON/Markdown) for reliable parsing.
- **Hard Fences:** LLM context uses clear `[SYSTEM]` / `[USER]` and section markers to avoid source bleed.
- **Validation:** Prose generation requires real beat files present (no silent fallbacks).

#### Global Plan, Local Fidelity
- **Philosophy:** Plan the ENTIRE story arc in one LLM call; write prose sequentially with prior prose as authoritative context.
- **Single-Shot Planning:** `chapter_single_shot.j2` generates all chapters with anti-redundancy guardrails.
- **Sequential Prose:** Each chapter uses full prior prose + beats to maintain coherence.

#### Quality Over Word Counts
- **Philosophy:** Chapter targets guide breadth, not length. Prose naturally "breathes" to serve story needs.
- **Structure Values (Calculated):** Word count targets, chapter count (from `DepthCalculator`).
- **Creative Values (LLM-Generated):** Themes, character arcs, world-building (stored in foundation).

#### Traceability by Default
- **Philosophy:** Every project auto-commits to shared git repo; analysis/debug artifacts saved to disk.
- **Storage:** `.agentic/logs/` (session logs), `.agentic/debug/<project-name>/` (analysis outputs).
- **Commits:** Project-prefixed messages, atomic per operation.

#### Creative vs. Mathematical Separation
- **Foundation (Creative):** Genre, themes, characters, world (LLM-generated, raw markdown).
- **Structure (Mathematical):** Word count targets, chapter count, pacing (calculated from taxonomy via `DepthCalculator`).
- **Principle:** Never store structure values in foundation to keep generation rules separate from creative content.

---

## Part 2: System Architecture Overview

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI/REPL Layer                           │
│  (interactive.py: /new, /generate, /iterate, /analyze, etc.)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼─────┐  ┌─────────▼────────┐  ┌────▼──────────┐
│  Generation │  │  Storage/Git     │  │  Analysis     │
│   Modules   │  │  Management      │  │   System      │
│   (LOD      │  │  (git_manager.py)│  │  (analyzer.py)│
│  pipeline)  │  │                  │  │               │
└────────┬────┘  └──────────────────┘  └────┬──────────┘
         │                                   │
         └──────────────────┬────────────────┘
                            │
        ┌───────────────────┼──────────────────┐
        │                   │                  │
┌───────▼──────┐  ┌─────────▼────────┐  ┌────▼──────────┐
│  OpenRouter  │  │   Prompt System  │  │   Project     │
│    API       │  │   (PromptLoader) │  │   Models      │
│   Client     │  │   + Jinja2       │  │  (Project.py) │
└──────────────┘  └──────────────────┘  └───────────────┘
```

### 2.2 Core Data Flow

**Input → Processing → Storage → Retrieval Pattern:**

```
User Input (REPL)
    ↓
Command Router (interactive.py)
    ↓
Specific Generator (premise.py, treatment.py, etc.)
    ↓
PromptLoader renders template
    ↓
OpenRouter API call
    ↓
LLM Response
    ↓
Project Model saves to disk
    ↓
GitManager commits to shared repo
    ↓
Display to user
```

---

## Part 3: Complete File Organization and Hierarchy

### 3.1 Project Root Structure

```
AgenticAuthor/
├── ARCHITECTURE.md                   # Original (concise) architecture overview
├── CLAUDE.md                         # Development guidance for Claude Code
├── AGENTS.md                         # Contributor guidelines
├── README.md                         # User-facing quickstart
├── LICENSE                          # MIT License
├── pyproject.toml                   # Python package config (setuptools, Black, Mypy, etc.)
├── .gitignore                       # VCS ignore patterns
├── .gitattributes                   # Git attributes (line endings, etc.)
│
├── src/                             # All application code
│   ├── __init__.py                 # Package marker
│   │
│   ├── api/                        # OpenRouter API integration
│   │   ├── __init__.py
│   │   ├── auth.py                # API key validation (must start with 'sk-or-')
│   │   ├── models.py              # Model dataclass, discovery, pricing
│   │   ├── openrouter.py          # Async OpenRouter client (completion, streaming, retry)
│   │   └── streaming.py           # Stream handling + token counters
│   │
│   ├── cli/                        # Command-line interface (REPL)
│   │   ├── __init__.py
│   │   ├── main.py                # Typer entry point (agentic, repl, new commands)
│   │   ├── interactive.py         # Main REPL orchestrator (500+ lines)
│   │   │                          # Routes /generate, /iterate, /analyze, /model, etc.
│   │   ├── command_completer.py   # Tab-completion metadata
│   │   ├── model_selector.py      # Interactive model selection UI
│   │   ├── taxonomy_editor.py     # Interactive taxonomy selection/editing
│   │   └── auto_suggest.py        # Input assistance utilities
│   │
│   ├── config/                     # Configuration management
│   │   ├── __init__.py            # exports get_settings()
│   │   ├── settings.py            # Settings loader via pydantic-settings
│   │   └── constants.py           # App constants
│   │
│   ├── export/                     # Output export formats
│   │   ├── __init__.py
│   │   ├── md_exporter.py         # Markdown export helpers
│   │   ├── rtf_exporter.py        # RTF format for word processors
│   │   └── dedication_generator.py # Dedication text generation
│   │
│   ├── generation/                 # Core generation pipeline (LOD system)
│   │   ├── __init__.py            # Exports generators
│   │   │
│   │   ├── premise.py             # Premise generation (LOD3)
│   │   │                          # Handles batch generation, taxonomy integration
│   │   ├── treatment.py           # Treatment generation (LOD2)
│   │   │                          # Expands premise with 3-act structure
│   │   ├── chapters.py            # Chapter outline generation (LOD1)
│   │   │                          # Foundation + beat sheets, single-shot planning
│   │   ├── prose.py               # Full prose generation (LOD0)
│   │   │                          # Sequential, uses style cards, fidelity validation
│   │   │
│   │   ├── variants.py            # Multi-variant generation (temperature fan-out)
│   │   │                          # Generates 4 variants in parallel
│   │   ├── judging.py             # LLM-based variant selection
│   │   │                          # Judges variants, saves decisions
│   │   │
│   │   ├── short_story.py         # Short-form flow (≤2 chapters)
│   │   │                          # Generates single story.md file
│   │   ├── depth_calculator.py    # Structure sizing
│   │   │                          # Chapter count, word targets, pacing
│   │   ├── lod_context.py         # Context builder (markdown format)
│   │   │                          # Assembles prompt context from multi-file storage
│   │   ├── cull.py                # Content deletion/pruning
│   │   ├── copy_editor.py         # Copy-editing pass
│   │   ├── improvement.py         # Content improvement coordination
│   │   ├── kdp_metadata.py        # Publishing metadata generation
│   │   ├── taxonomies.py          # Taxonomy loading and merging
│   │   │
│   │   ├── analysis/              # Editorial analysis subsystem
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Analysis interfaces (Issue, Strength, Recommendation)
│   │   │   ├── analyzer.py        # Analysis coordinator (1000+ lines)
│   │   │   ├── unified_analyzer.py # Single-pass editorial analysis
│   │   │   └── treatment_deviation_analyzer.py # Foundation vs treatment checks
│   │   │
│   │   └── iteration/             # Natural language iteration system (v0.4.0)
│   │       ├── __init__.py
│   │       ├── iterator.py        # Main iteration orchestrator (795 lines)
│   │       │                      # Validates, generates, judges, shows diffs, commits
│   │       ├── history.py         # Iteration history tracking
│   │       ├── judge.py           # LLM judge validation
│   │       └── semantic_diff.py   # Human-readable change summaries
│   │
│   ├── models/                     # Data structures
│   │   ├── __init__.py            # Exports Project, ChapterOutline, etc.
│   │   ├── project.py             # Main project model (1373 lines)
│   │   │                          # Handles file I/O, migrations, metadata
│   │   ├── story.py               # Story structures and helpers
│   │   └── taxonomy.py            # Taxonomy models and formatters
│   │
│   ├── prompts/                    # Jinja2 templates for LLM prompts
│   │   ├── __init__.py            # PromptLoader class
│   │   ├── config.yaml            # Prompt metadata (temperature, format, tokens)
│   │   │
│   │   ├── generation/            # Core LOD prompts (29 files)
│   │   │   ├── premise_main.j2
│   │   │   ├── premise_with_taxonomy.j2
│   │   │   ├── treatment_generation.j2
│   │   │   ├── chapter_foundation.j2
│   │   │   ├── chapter_single_shot.j2
│   │   │   ├── prose_generation.j2
│   │   │   ├── prose_iteration.j2
│   │   │   ├── prose_full_iteration.j2
│   │   │   ├── dedication_generation.j2
│   │   │   ├── premise_iteration.j2
│   │   │   ├── treatment_iteration.j2
│   │   │   ├── chapter_iteration.j2
│   │   │   └── ... (4 more: improvement, iterations, etc.)
│   │   │
│   │   ├── analysis/              # Editorial analysis prompts
│   │   │   ├── chapter_judging.j2
│   │   │   ├── semantic_diff.j2
│   │   │   ├── unified_analysis.j2
│   │   │   ├── treatment_deviation.j2
│   │   │   ├── genre_detection.j2
│   │   │   └── taxonomy_extraction.j2
│   │   │
│   │   ├── editing/               # Copy-editing prompts
│   │   │   └── copy_edit.j2
│   │   │
│   │   ├── kdp/                   # Publishing metadata prompts
│   │   │   ├── author_bio.j2
│   │   │   ├── description.j2
│   │   │   └── keywords.j2
│   │   │
│   │   ├── iteration/             # Iteration utility prompts
│   │   │   ├── premise_revision.j2
│   │   │   └── taxonomy_update.j2
│   │   │
│   │   └── validation/            # Validation/fidelity prompts
│   │       ├── iteration_fidelity.j2
│   │       ├── prose_fidelity.j2
│   │       ├── treatment_fidelity.j2
│   │       └── improvement_validation.j2
│   │
│   ├── storage/                    # Version control integration
│   │   ├── __init__.py
│   │   └── git_manager.py         # Git operations (init, add, commit, diff, log, rollback)
│   │
│   └── utils/                      # Utility functions
│       ├── __init__.py
│       ├── tokens.py              # Token estimation and budgeting
│       ├── yaml_utils.py          # YAML parsing and sanitization
│       ├── markdown_extractors.py # Markdown parsing for structured data
│       ├── session_logger.py      # I/O interception to logs
│       └── logging.py             # Log setup, rotation, cleanup
│
├── taxonomies/                      # Genre/form taxonomies (JSON)
│   ├── base-taxonomy.json          # Shared categories
│   ├── fantasy-taxonomy.json
│   ├── romance-taxonomy.json
│   ├── science-fiction-taxonomy.json
│   ├── mystery-thriller-taxonomy.json
│   ├── horror-taxonomy.json
│   ├── contemporary-fiction-taxonomy.json
│   ├── historical-fiction-taxonomy.json
│   ├── literary-fiction-taxonomy.json
│   ├── young-adult-taxonomy.json
│   ├── urban-fantasy-taxonomy.json
│   ├── romantasy-taxonomy.json
│   └── generic-taxonomy.json
│
├── docs/                            # Comprehensive user documentation
│   ├── USER_GUIDE.md              # Complete user guide
│   ├── CHANGELOG.md               # Version history
│   └── IMPLEMENTATION_STATUS.md   # Feature tracking
│
├── misc/                            # Support assets
│   ├── example-backmatter.md
│   └── default-dedication.md
│
├── .agentic/                        # Global debug/logs (at repo root, NOT in books/)
│   ├── logs/                       # Session logs (agentic_YYYYMMDD.log)
│   ├── debug/                      # Debug artifacts by project
│   ├── history                     # REPL command history
│   └── backups/                    # Automated backups (copy-edit originals)
│
└── books/                           # All user projects (shared git repo at this level)
    ├── .git/                        # Shared git repository
    └── <project-name>/              # Each project is a folder
        ├── project.yaml             # Project metadata (name, created_at, genre, etc.)
        │
        ├── premise/                 # Premise artifacts
        │   ├── premise_metadata.json # Single source of truth (premise text + metadata)
        │   ├── premises_candidates.json # Batch generation candidates
        │   └── iteration_history.json # Premise iteration feedback log
        │
        ├── treatment/               # Treatment artifacts
        │   ├── treatment.md          # Raw markdown
        │   ├── treatment_metadata.json # Treatment metadata
        │   ├── iteration_history.json # Treatment iteration feedback log
        │   └── combined.md           # Optional snapshot (premise + treatment)
        │
        ├── chapter-beats/           # Chapter structure (NEW MARKDOWN FORMAT)
        │   ├── foundation.md         # Foundation (metadata + characters + world)
        │   ├── chapter-01.md         # Individual chapter outlines
        │   ├── chapter-02.md
        │   ├── ...
        │   ├── chapter-NN.md
        │   ├── iteration_history.json # Chapter iteration feedback log
        │   └── combined.md           # Optional snapshot (all beats + foundation)
        │
        ├── chapter-beats-variants/  # Multi-variant artifacts (if generated)
        │   ├── foundation.md         # Shared foundation
        │   ├── variant-1/            # Temperature 0.55
        │   │   ├── chapter-01.md
        │   │   └── ...
        │   ├── variant-2/            # Temperature 0.60
        │   ├── variant-3/            # Temperature 0.65
        │   ├── variant-4/            # Temperature 0.70
        │   ├── decision.json         # Winner + reasoning
        │   └── combined.md           # All variants (for review)
        │
        ├── chapters/                # Final prose chapters
        │   ├── chapter-01.md         # Final prose (sequential generation)
        │   ├── chapter-02.md
        │   ├── ...
        │   ├── chapter-NN.md
        │   ├── iteration_history.json # Prose iteration feedback log
        │   └── combined.md           # Optional full prose snapshot
        │
        ├── chapters-edited/         # Copy-edited prose (optional)
        │   ├── chapter-01.md
        │   └── ...
        │
        ├── story.md                 # Short-form prose (≤2 chapters only)
        │
        ├── analysis/                # Editorial analysis reports
        │   ├── unified-analysis.md   # Single-pass comprehensive analysis
        │   ├── treatment-deviation.md # Foundation vs treatment issues
        │   └── ...
        │
        ├── exports/                 # Publishing artifacts
        │   ├── frontmatter.md        # Title page, copyright, dedication
        │   ├── dedication.md         # Generated dedication
        │   ├── publishing-metadata.md # KDP metadata (author bio, keywords)
        │   ├── <title>_YYYYMMDD.rtf # RTF export with timestamp
        │   └── <title>_YYYYMMDD.md  # Markdown export with timestamp
        │
        └── misc/                    # Project-specific assets
            └── prose-style-card.md   # Style guide (used during generation)
```

### 3.2 Storage Architecture Deep Dive

**Principle: Markdown-First with Optional YAML Extraction**

Storage uses a layered approach:

```
LLM generates markdown
    ↓
Saved as raw .md files (foundation.md, chapter-NN.md)
    ↓
When needed for validation/analysis:
    ├→ Parse with MarkdownExtractor
    └→ Get structured dict
        ├→ Pass to prompts (dict format)
        └→ Optionally save as YAML (legacy compatibility)
```

**Why this design:**
1. **Fidelity:** LLM markdown quality > conversion to YAML
2. **Debugging:** See exactly what LLM generated
3. **Diffs:** Markdown diffs are human-readable
4. **Flexibility:** Parser handles format variations gracefully

**File Format Legend:**
- `.md` — Canonical creative content (foundation, beats, prose, analysis)
- `.yaml` — Structured metadata (project config, iteration history)
- `.json` — Machine-readable metadata (premise selections, decisions)
- `.j2` — Jinja2 prompt templates

---

## Part 4: The Generation Pipeline (Level of Detail System)

### 4.1 LOD Overview

The system uses a **reverse-number Level of Detail (LOD)** system:

```
LOD3: PREMISE (abstract, concept)
  ↓ Expands to...
LOD2: TREATMENT (narrative arc, 3-act structure)
  ↓ Expands to...
LOD1: CHAPTERS (detailed outlines, beats, character arcs)
  ↓ Expands to...
LOD0: PROSE (full dramatized narrative)
```

**Key Property:** Each level is **self-contained** yet builds on lower LOD:
- Prose generation uses ONLY chapters.yaml (self-contained)
- Chapter generation uses premise + treatment (input context)
- Treatment generation uses premise (input context)
- Premise generation uses user concept + taxonomy

### 4.2 Generation Module Details

#### 4.2.1 Premise Generation (LOD3)
**File:** `src/generation/premise.py`

**Purpose:** Generate story concept from user input + taxonomy

**Process:**
1. Load selected taxonomy (genre, tone, themes, etc.)
2. Render `premise_main.j2` or `premise_with_taxonomy.j2`
3. Call OpenRouter with JSON output format
4. Save to `premise/premise_metadata.json` (single source of truth)
5. Support batch generation of multiple candidates
6. Iteration support: modify taxonomy, regenerate premise

**Output Structure:**
```json
{
  "premise": "2-3 sentence story concept",
  "protagonist": "Main character description",
  "antagonist": "Opposing force",
  "stakes": "What's at risk",
  "hook": "Unique element",
  "themes": ["theme1", "theme2"],
  "selections": {
    "genre": ["fantasy", "adventure"],
    "tone": ["epic", "hopeful"],
    ...
  }
}
```

**Key Methods:**
- `generate()` — Generate single premise
- `generate_batch()` — Generate multiple candidates
- `regenerate_with_taxonomy()` — Use specific taxonomy selections
- `iterate_taxonomy()` — Modify taxonomy based on feedback

---

#### 4.2.2 Treatment Generation (LOD2)
**File:** `src/generation/treatment.py`

**Purpose:** Expand premise into full narrative outline with 3-act structure

**Process:**
1. Load premise (single source of truth from premise_metadata.json)
2. Use `LODContextBuilder.build_markdown_context('premise')` for input
3. Render `treatment_generation.j2` with target word count
4. Call OpenRouter with streaming output
5. Save to `treatment/treatment.md` (raw markdown)
6. Create optional snapshot in `treatment/combined.md`

**Output:** ~2500-word prose narrative covering:
- Act I (25%): Setup, ordinary world, inciting incident
- Act II (50%): Rising action, midpoint turn, complications  
- Act III (25%): Climax, resolution, denouement
- Character arcs, plot points, thematic elements, world-building

**Key Methods:**
- `generate()` — Generate treatment from premise
- `iterate()` — Regenerate based on feedback

---

#### 4.2.3 Chapter Generation (LOD1)
**File:** `src/generation/chapters.py`

**Purpose:** Generate chapter outlines with foundation (characters, world, metadata)

**Two-Phase Process:**

**Phase 1: Foundation Generation**
1. Extract characters, world, themes from treatment
2. Calculate structure via `DepthCalculator` (chapter count, pacing)
3. Generate metadata (narrative style, POV, tone)
4. Saves to `chapter-beats/foundation.md` (raw markdown)

**Phase 2: Single-Shot Chapter Planning**
1. Plan ALL chapters in ONE LLM call (prevents duplication)
2. Provide anti-redundancy guardrails and act anchors
3. Render `chapter_single_shot.j2` with global story arc
4. Save individual chapters to `chapter-beats/chapter-NN.md`

**Chapter Outline Format:**
```
# Chapter NN: Title
## Summary
[1-2 sentence summary]

## Key Events
[Bullet list of plot events]

## Character Developments
[How characters grow/change]

## Scenes
[Scene breakdown]
```

**Multi-Variant Support:**
- `VariantManager` generates 4 variants with different temperatures (0.55-0.70)
- `JudgingCoordinator` uses LLM to select best variant
- Saves decisions to `chapter-beats-variants/decision.json`

**Special Case: Short Stories**
- If ≤2 chapters, use `short_story.py` instead
- Generates single `story.md` file (no chapter breakdown)

**Key Methods:**
- `generate()` — Full foundation + chapters generation
- `_generate_foundation()` — Foundation only
- `_generate_single_shot()` — All chapters at once

---

#### 4.2.4 Prose Generation (LOD0)
**File:** `src/generation/prose.py`

**Purpose:** Generate full dramatized narrative for each chapter

**Architecture: Sequential + Context-Aware**

**Process:**
1. Load chapters.yaml (self-contained, has metadata + chars + world + beats)
2. For each chapter:
   - Load current chapter outline
   - Load all PRIOR prose (full text)
   - Render `prose_generation.j2` with complete context
   - Generate prose for current chapter
   - Save to `chapters/chapter-NN.md`
3. Optionally create `chapters/combined.md` snapshot

**Key Innovation: Self-Contained chapters.yaml**
- Contains EVERYTHING prose generation needs
- No need to access premise.md or treatment.md
- Includes:
  - metadata: genre, pacing, tone, themes, narrative_style
  - characters: full profiles with backgrounds, motivations, arcs
  - world: setting, locations, systems, atmosphere
  - chapters: detailed outlines with events, beats

**Style Cards:**
- Optional `misc/prose-style-card.md` defines prose style
- Includes: voice, POV, tone, pacing, dialogue, description, technical elements
- Auto-generated from first chapter prose for consistency
- Used by default for all subsequent chapters

**Validation:**
- Checks prose against beats for fidelity
- Optional surgical iteration for fixes without full regeneration

**Key Methods:**
- `generate_prose()` — Generate all or specific chapters
- `generate_single_chapter()` — Generate one chapter
- `calculate_prose_context_tokens()` — Token budgeting

---

### 4.3 Context Building System
**File:** `src/generation/lod_context.py`

**Purpose:** Assemble context from multiple files in markdown format for LLM prompts

**Philosophy:**
- `context_level` parameter indicates "what INPUT to include", not what you're generating
- Returns native markdown format (NOT YAML) for LLM prompts
- Supports `include_downstream` for consistency checks

**Context Levels:**
- `'premise'` — Just premise
- `'treatment'` — Premise + treatment
- `'chapters'` — Premise + treatment + chapters outline
- `'prose'` — Everything (for analysis)

**Key Methods:**
- `build_markdown_context()` — Returns markdown strings for LLM prompts
- `build_context()` — Returns structured dicts (for metadata extraction)

**Example:**
```python
# Generating treatment: use premise as context
context = builder.build_markdown_context(
    project=project,
    context_level='premise'  # Include premise as input
)
# Returns: "# PREMISE\n..." (markdown format)

# Then prompt asks: "Based on this premise, generate a treatment..."
```

---

## Part 5: The Prompting System

### 5.1 Prompt Architecture

**File:** `src/prompts/__init__.py` (PromptLoader class)

**Design: Template-Based with Metadata**

```
Template Files (.j2)
    ↓
Render with Jinja2 (variables substituted)
    ↓
Parse [SYSTEM] / [USER] sections
    ↓
Combine with metadata (temperature, format, tokens)
    ↓
Send to OpenRouter API
```

**Template Format:**
```jinja2
[SYSTEM]
You are a creative writing expert...
[Consider these guidelines...]

[USER]
Generate a premise for {{ genre }} genre.
User concept: {{ user_input }}

Return JSON with structure:
{
  "premise": "...",
  "protagonist": "...",
  ...
}
```

### 5.2 Metadata System
**File:** `src/prompts/config.yaml`

**Purpose:** Store configuration for each prompt (NOT in template files)

**Configuration per prompt:**
```yaml
generation/prose_generation:
  temperature: 0.8
  format: "text"
  reserve_tokens: 6000

analysis/chapter_judging:
  temperature: 0.1  # Low for consistent judging
  format: "text"
```

**PromptLoader Methods:**
- `render()` — Render template and split into system/user
- `get_metadata()` — Get config for prompt
- `get_temperature()` — Extract temperature with default
- `get_format()` — Extract expected output format

### 5.3 Prompt Templates Catalog

**Generation Prompts (29 files):**
- `premise_main.j2` — Basic premise generation
- `premise_with_taxonomy.j2` — Premise with genre-specific options
- `treatment_generation.j2` — Treatment from premise
- `chapter_foundation.j2` — Foundation extraction
- `chapter_single_shot.j2` — All chapters in one call (anti-redundancy)
- `prose_generation.j2` — Prose with prior context
- `prose_iteration.j2` — Surgical prose fixes
- `prose_full_iteration.j2` — Full prose regeneration
- `[premise|treatment|chapter]_iteration.j2` — LOD-level regeneration
- `dedication_generation.j2` — Dedication text
- `improvement_incorporation.j2` — Apply improvement suggestions
- And more...

**Analysis Prompts (7 files):**
- `chapter_judging.j2` — Select best variant
- `semantic_diff.j2` — Human-readable changes
- `unified_analysis.j2` — Editorial analysis (duplicates, strengths, next steps)
- `treatment_deviation.j2` — Check foundation vs treatment
- `genre_detection.j2` — Auto-identify genre
- `taxonomy_extraction.j2` — Extract taxonomy from content
- `content_improvement.j2` — Suggest improvements

**Other Categories:**
- **Editing:** `copy_edit.j2` — Copy-editing pass
- **KDP:** `author_bio.j2`, `description.j2`, `keywords.j2` — Publishing metadata
- **Validation:** `iteration_fidelity.j2`, `prose_fidelity.j2`, `treatment_fidelity.j2` — Fidelity checks
- **Iteration:** `premise_revision.j2`, `taxonomy_update.j2` — Iteration utilities

---

## Part 6: The Natural Language Iteration System (v0.4.0)

### 6.1 Iteration Architecture
**Files:** `src/generation/iteration/` (4 files, 1119 lines total)

**Purpose:** Allow users to refine content using natural language feedback with LLM judge validation

**Core Components:**

#### 6.1.1 Iterator (iterator.py - 795 lines)
**Main coordinator for iteration workflow**

**Process:**
1. User sets iteration target: `/iterate prose` (or premise, treatment, chapters)
2. User provides feedback: "make it darker and more suspenseful"
3. Load context + iteration history
4. Show context summary (what's loaded)
5. Check downstream impact (editing premise may cull treatment/chapters)
6. Save old content for comparison
7. Regenerate with feedback in loop (up to 3 attempts)
   - LLM judge validates changes match feedback
   - If judge rejects, retry with adjusted prompt
8. Generate semantic diff (human-readable, not raw git diff)
9. Get user approval
10. Finalize: save, cull downstream, update history, commit to git

**Key Methods:**
- `iterate()` — Main coordination method
- `_generation_loop()` — Try/validate loop with judge
- `_finalize_iteration()` — Save, cull, commit
- `_get_user_approval()` — Show diff and ask

**Safety Features:**
- Warning on first iteration (test on cloned projects)
- Judge validation prevents hallucination
- Git commits for easy rollback
- `git reset --hard HEAD~1` to undo

#### 6.1.2 History (history.py - 117 lines)
**Track iteration feedback and context per LOD level**

**Stores:**
```json
{
  "iterations": [
    {
      "timestamp": "2026-01-06T12:34:56Z",
      "feedback": "make it darker",
      "semantic_summary": "Changed tone to darker, more suspenseful",
      "attempt": 1
    }
  ]
}
```

**Purpose:**
- Provide context for iterative LLM prompts
- Show cumulative feedback history
- Enable context-aware regeneration

**Methods:**
- `add()` — Record new iteration
- `count()` — How many iterations so far
- `get_context_for_llm()` — Formatted history for prompts

#### 6.1.3 Judge (judge.py - 116 lines)
**LLM-based validation that changes match feedback**

**Validates:**
- Generated content actually addresses feedback
- No hallucination or off-topic changes
- Regeneration succeeded

**Process:**
1. Compare old vs new content
2. Render `iteration_fidelity.j2` with diff context
3. Call LLM with low temperature (0.1 for consistency)
4. Get verdict: approved/rejected
5. Track attempts in iteration loop

**Methods:**
- `validate()` — Check if changes match feedback
- Retry logic in Iterator up to 3 attempts

#### 6.1.4 Semantic Diff (semantic_diff.py - 85 lines)
**Generate human-readable change summaries**

**Purpose:** Show what changed WITHOUT git diffs (easier to understand)

**Process:**
1. Render `semantic_diff.j2` with context
2. LLM generates summary of changes
3. Display to user for approval
4. Examples:
   - "Changed Chapter 3 tone from light to darker, added internal monologue"
   - "Expanded character backstory in foundation"
   - "Modified treatment Act II pacing"

**Key Methods:**
- `generate_diff()` — Create semantic summary

### 6.2 Iteration Targets and Capabilities

**Supported Targets:**
- `premise` — Regenerate premise with feedback
- `treatment` — Regenerate treatment with feedback
- `chapters` — Regenerate chapter outlines with feedback
- `prose` — Regenerate prose with feedback

**Downstream Cascade:**
```
If you iterate premise:
  - User can choose to cull treatment, chapters, prose
  - All downstream content regenerated from new premise

If you iterate treatment:
  - User can choose to cull chapters, prose
  - Chapters/prose regenerated from new treatment

If you iterate chapters:
  - User can choose to cull prose
  - Prose regenerated from new chapters

If you iterate prose:
  - No downstream impact (final level)
```

**Debug Storage:**
- All iteration attempts saved to `.agentic/debug/<project-name>/iteration/`
- Includes original, attempt, judge verdict
- Enables analysis of why iterations succeeded/failed

---

## Part 7: The Analysis System

### 7.1 Analysis Architecture
**Files:** `src/generation/analysis/` (4 files)

**Purpose:** Provide editorial feedback to guide improvements

**Components:**

#### 7.1.1 Base Classes (base.py)
**Data structures for analysis results**

```python
@dataclass
class Issue:
    category: str          # "PLOT HOLE", "CHARACTER INCONSISTENCY"
    severity: Severity    # CRITICAL | HIGH | MEDIUM | LOW
    location: str         # "Chapter 3, Act II opening"
    description: str      # What's wrong
    impact: str           # How it affects the story
    suggestion: str       # How to fix it
    confidence: int       # 0-100

@dataclass
class Strength:
    category: str         # What aspect is strong
    description: str      # Specific positive element
    location: str         # Where this appears

@dataclass
class Recommendation:
    description: str      # Actionable step for A+ grade
    confidence: int       # 0-100
    rationale: str        # Why it would help

@dataclass
class AnalysisResult:
    dimension: str        # "Plot & Structure", "Characters", etc.
    score: float          # 0-10
    summary: str          # Brief overview
    issues: List[Issue]
    strengths: List[Strength]
    path_to_plus: PathToAPlus
```

#### 7.1.2 Unified Analyzer (unified_analyzer.py)
**Single-pass comprehensive editorial analysis**

**Analyzes:**
- Plot & structure
- Character development
- World-building
- Theme and meaning
- Prose quality
- Pacing and engagement

**Output:** Single markdown report with structured analysis

#### 7.1.3 Treatment Deviation Analyzer (treatment_deviation_analyzer.py)
**Checks foundation vs treatment for contradictions**

**Validates:**
- Characters match between foundation and treatment
- World-building is consistent
- Plot elements align
- Themes are reinforced

#### 7.1.4 Analysis Coordinator (analyzer.py - 1000+ lines)
**Orchestrates analysis workflow**

**Process:**
1. Load project content (premise, treatment, chapters, prose)
2. Run multiple analyzers in parallel
3. Aggregate results
4. Generate markdown report
5. Save to `analysis/` directory

**Key Methods:**
- `analyze()` — Run full analysis
- `generate_report()` — Create markdown output

**Report Location:** `projects/<name>/analysis/`

---

## Part 8: The API Layer

### 8.1 OpenRouter Client
**File:** `src/api/openrouter.py`

**Purpose:** Async OpenRouter API interaction with retry logic, streaming, token budgeting

**Key Features:**
- **Async/await:** Non-blocking API calls
- **Streaming:** Real-time output to console
- **Token Budgeting:** Calculate max_tokens from context length - headroom
- **Retry Logic:** Automatic retries with exponential backoff
- **Model Discovery:** Cache available models
- **Timeout Handling:** 2-hour cap for reasoning models that pause 5+ minutes

**Connection Strategy:**
```python
connector = aiohttp.TCPConnector(
    enable_cleanup_closed=True,
    force_close=False,            # Allow HTTP keep-alive
    keepalive_timeout=60,
    limit=100,
    limit_per_host=10
)

timeout = aiohttp.ClientTimeout(
    total=7200,      # 2 hour total cap
    connect=30,      # 30s to establish
    sock_read=None   # NO read timeout for reasoning models pausing
)
```

**Key Methods:**
- `completion()` — Single completion request
- `streaming_completion()` — Streaming with token counting
- `json_completion()` — JSON output format
- `discover_models()` — Fetch available models
- `estimate_tokens()` — Token count estimation

### 8.2 Streaming Handler
**File:** `src/api/streaming.py`

**Purpose:** Handle streaming responses with real-time display

**Features:**
- Token counting
- Real-time console output (via Rich)
- Stream error handling

### 8.3 Model Data
**File:** `src/api/models.py`

**Data Structures:**
```python
class ModelPricing:
    prompt: float      # Cost per 1k prompt tokens
    completion: float  # Cost per 1k completion tokens
    request: float     # Cost per request

class Model:
    id: str
    name: str
    context_length: int
    pricing: ModelPricing
    top_provider: Dict
    created: datetime
    updated: datetime
```

**Key Methods:**
- `estimate_cost()` — Calculate cost for token counts
- `get_max_output_tokens()` — Max completion tokens

### 8.4 Authentication
**File:** `src/api/auth.py`

**Validation:**
- API key must start with `'sk-or-'`
- Environment variable: `OPENROUTER_API_KEY`
- Raises ValueError if invalid

---

## Part 9: The Project Model

### 9.1 Project Class
**File:** `src/models/project.py` (1373 lines)

**Purpose:** Central abstraction for project I/O, file management, and migrations

**Key Features:**
- **Multi-directory Architecture:** Premise, treatment, chapters, analysis, exports
- **File I/O:** Unified methods for loading/saving all artifacts
- **Migrations:** Automatic upgrade from old flat structure to new folder-based
- **Metadata Management:** Merged project.yaml (config + metadata)
- **Backward Compatibility:** Supports legacy YAML files while preferring markdown

**Directory Properties:**
```python
@property
def premise_dir(self) -> Path      # books/<project>/premise/
@property
def treatment_dir(self) -> Path    # books/<project>/treatment/
@property
def chapter_beats_dir(self) -> Path # books/<project>/chapter-beats/
@property
def chapters_dir(self) -> Path     # books/<project>/chapters/
@property
def analysis_dir(self) -> Path     # books/<project>/analysis/
@property
def exports_dir(self) -> Path      # books/<project>/exports/
```

**File I/O Methods:**
```python
# Premise
get_premise() -> Optional[str]
get_premise_metadata() -> Optional[Dict]
save_premise_metadata(metadata: Dict)

# Treatment
get_treatment() -> Optional[str]
save_treatment(content: str)

# Chapters (new format: chapter-beats/)
get_foundation() -> Optional[Dict]
get_chapters() -> Optional[List[Dict]]
get_chapter_beat(num: int) -> Optional[Dict]
save_foundation_markdown(text: str)
save_chapter_beat_markdown(num: int, text: str)

# Prose
get_chapter(num: int) -> Optional[str]
save_chapter(num: int, content: str)
list_chapters() -> List[Path]

# Story (short-form)
get_story() -> Optional[str]
save_story(content: str)

# Metadata
get_book_metadata(key: Optional[str] = None)
set_book_metadata(key: str, value)
```

**Context Assembly:**
```python
# Write combined snapshots
write_combined_markdown(target: str) -> Path  # premise, chapters, prose

# Split combined back to individual files
split_combined_markdown(target: str) -> Tuple[int, int, int]
```

**Metadata Structure:**
```python
class ProjectMetadata(BaseModel):
    name: str
    created_at: datetime
    updated_at: datetime
    story_type: Optional[str]      # short_form | long_form
    book_metadata: Dict             # title, author, copyright_year
    genre: Optional[str]
```

**Migrations:**
- Auto-migrate from flat structure (premise.md, treatment.md) to folder structure
- Auto-merge config.yaml into project.yaml
- Idempotent (safe to run multiple times)

---

## Part 10: The CLI/REPL Interface

### 10.1 REPL Architecture
**File:** `src/cli/interactive.py` (500+ lines)

**Purpose:** Main command router and workflow orchestrator

**Command Handlers:**
```python
commands = {
    'new': self.new_project,
    'open': self.open_project,
    'clone': self.clone_project,
    'status': self.show_status,
    'model': self.change_model,
    'generate': self.generate_content,      # /generate premise|treatment|chapters|prose
    'iterate': self.iterate_command,        # /iterate prose (+ natural language feedback)
    'analyze': self.analyze_story,
    'export': self.export_story,
    'help': self.show_help,
    'quit': self.exit_session,
    # ... more
}
```

**Key Workflows:**

**Generation Flow:**
```
/generate premise
  ↓ (returns premise, auto-prompts for model if not set)
/generate treatment
  ↓
/generate chapters [--auto] [--variants]
  ↓
/finalize chapters (if variants)
  ↓
/generate prose all
  ↓ (optional: /iterate prose)
```

**Iteration Flow:**
```
/iterate prose
  ↓ (sets iteration_target = 'prose')
System shows context, asks for approval
  ↓
User provides natural language feedback (no / prefix)
  ↓
System regenerates with judge validation
  ↓
System shows semantic diff
  ↓
User approves (y/n)
  ↓
System commits to git
```

### 10.2 Command Details

**`/new <project-name>`**
- Create new project folder under `books/`
- Initialize git repo (at `books/` level if first project)
- Prompt for model selection

**`/model`** or **`/model <name>`**
- Select/change model for subsequent operations
- Interactive selection with context length display
- Can check available models via `/models`

**`/generate <target> [options]`**
Targets: premise, treatment, chapters, prose
Options vary by target:
- `prompt: <text>` — Custom prompt for generation
- `--auto` — Auto-select chapter count
- `--variants` — Generate 4 variants (chapters only)
- `--no-style-card` — Skip style card (prose only)
- `--file <path>` — Use file for premise (skip interactive flow)

**`/iterate <target>`**
- Set iteration target and wait for feedback
- User provides plain English feedback (no `/` prefix)
- System validates, shows diff, commits

**`/analyze [--detailed]`**
- Run comprehensive editorial analysis
- Save report to `analysis/` directory
- Optional detailed breakdown by dimension

**`/export <format> [--frontmatter] [--rtf]`**
- Export to markdown, RTF, or complete book package
- Include frontmatter if available

---

## Part 11: Storage and Version Control

### 11.1 Git Integration
**File:** `src/storage/git_manager.py`

**Architecture: Shared Repository at books/ Level**

**Why Shared:**
- All projects in one git repo
- Shared commit history
- Easier rollback across projects
- Simpler cleanup

**Key Methods:**
```python
def init() -> bool                    # Initialize shared repo
def status() -> str                   # Git status
def add(files: Optional[List[str]]) -> bool
def commit(message: str) -> bool
def diff(cached: bool = False) -> str
def log(limit: int = 10) -> str
def rollback(commit_hash: str) -> bool
```

**Commit Strategy:**
- **Project-Prefixed Messages:** `[project-name] Operation: feedback`
- **Automatic Commits:** After every generation step
- **Atomic Operations:** Each conceptual operation = 1 commit

**Example Commits:**
```
[my-book] Generate: Premise from concept
[my-book] Generate: Treatment from premise
[my-book] Generate: Chapter variants (4 attempts)
[my-book] Finalize: Selected variant 2
[my-book] Generate: Prose chapter 1
[my-book] Iterate prose: make it darker (judge: approved, attempt 1)
```

### 11.2 Logging System
**Files:** `src/utils/logging.py`, `src/utils/session_logger.py`

**Architecture:**
- **Session Logs:** `~/.agentic/logs/agentic_YYYYMMDD.log`
- **Debug Artifacts:** `.agentic/debug/<project-name>/`
- **Rotation:** Daily log files, automatic cleanup

**Features:**
- Intercept console output to logs
- Capture all LLM I/O
- Trace execution flow
- Enable post-mortem analysis

---

## Part 12: Architectural Patterns and Design Decisions

### 12.1 Core Design Patterns

#### Single Responsibility Pattern
Each module has one job:
- `PremiseGenerator` — Only premise generation
- `TreatmentGenerator` — Only treatment expansion
- `ChapterGenerator` — Only chapter planning
- `ProseGenerator` — Only prose writing
- `LODContextBuilder` — Only context assembly
- `JudgingCoordinator` — Only variant selection
- `Iterator` — Only iteration coordination

#### Builder Pattern
- `LODContextBuilder` — Assemble context from files
- `DepthCalculator` — Build structure from taxonomy
- `VariantManager` — Build multiple variants

#### Template Pattern
- Jinja2 templates as parameterized prompts
- PromptLoader fills in variables
- Consistent structure across all generation types

#### Observer Pattern
- GitManager tracks all changes
- SessionLogger records I/O
- Analysis reports notify user of issues

#### Context Pattern
- `build_context()` — Dict structure for metadata
- `build_markdown_context()` — String format for LLM prompts

#### Strategy Pattern
- Multiple analyzers (unified, deviation, etc.)
- Multiple exporters (markdown, RTF, etc.)
- Multiple judges (variant selection, iteration validation)

### 12.2 Architecture Decision Records (ADR)

#### ADR-001: Shared Git at books/ Level
**Decision:** One shared repository for all projects at `books/.git`

**Rationale:**
- Simpler management than per-project repos
- Enables cross-project history analysis
- Reduces git overhead

**Impact:** All projects commit with project-prefixed messages

---

#### ADR-002: Markdown-First Storage
**Decision:** Store foundation and beats as raw markdown, extract to dicts as needed

**Rationale:**
- LLMs generate better markdown than YAML
- Human-readable for debugging
- Markdown diffs are clearer
- Graceful parser handles format variations

**Impact:**
- Save files as `.md` not `.yaml`
- Parse with `MarkdownExtractor` when structure needed
- Backward compatible with legacy YAML

---

#### ADR-003: Self-Contained chapters.yaml
**Decision:** chapters.yaml includes ALL data needed for prose generation (no premise/treatment access required)

**Rationale:**
- Prose generation works independently
- Can regenerate prose without premise changes
- Supports isolated prose iteration

**Contents:**
- metadata (genre, tone, style)
- characters (full profiles)
- world (setting, systems)
- chapters (outlines with beats)

**Impact:** Prose generator uses only `chapters.yaml`, ignores premise/treatment

---

#### ADR-004: Fail Fast, No Fallbacks
**Decision:** Missing required artifacts or config should raise exceptions, never silently substitute

**Examples:**
```python
# BAD
premise = self.project.get_premise() or ""  # Fallback to empty

# GOOD
premise = self.project.get_premise()
if not premise:
    raise Exception("No premise found. Generate with /generate premise")
```

**Impact:**
- Clear error messages to users
- Prevents subtle bugs from missing data
- Forces explicit workflow order

---

#### ADR-005: Single-Shot Chapter Planning
**Decision:** Generate ALL chapters in one LLM call, not sequentially

**Rationale:**
- Prevents duplicate events (LLM sees full arc)
- Natural character progression (no repeated developments)
- Anti-redundancy guardrails in prompt

**Impact:**
- Chapters are planned as cohesive whole
- Better global story structure
- Single API call reduces latency

---

#### ADR-006: Iteration Judge Validation
**Decision:** LLM judge validates content matches feedback before showing user

**Rationale:**
- Prevents wasted iterations from hallucination
- Provides confidence level on changes
- Reduces back-and-forth cycles

**Impact:**
- Small token cost per iteration (~1000 tokens)
- Higher success rate
- Better UX

---

#### ADR-007: Global .agentic Directory
**Decision:** Centralized `.agentic/` at repo root (NOT per-project)

**Rationale:**
- Simpler debug analysis across projects
- Shared logs and backups
- Easier cleanup

**Structure:**
```
.agentic/
├── logs/
├── debug/<project-name>/
├── history
└── backups/
```

---

### 12.3 Data Flow Architecture

**End-to-End Data Flow:**

```
1. USER INPUT
   └→ REPL (interactive.py)

2. COMMAND ROUTING
   └→ Routes to specific command handler
      (generate_content, iterate_command, etc.)

3. CONTENT GENERATION
   ├→ Load existing context (LODContextBuilder)
   ├→ Build markdown input
   ├→ Render Jinja2 template (PromptLoader)
   ├→ Call OpenRouter API (OpenRouterClient)
   ├→ Handle streaming output (StreamHandler)
   ├→ Parse response (MarkdownExtractor if needed)
   └→ Validate structure

4. PERSISTENCE
   ├→ Save to project files (Project model)
   ├→ Update metadata
   └→ Commit to git (GitManager)

5. USER DISPLAY
   ├→ Rich formatted output
   ├→ Stream progress for long operations
   └→ Logging to disk

6. ITERATION CYCLE (if user provides feedback)
   ├→ Load history (IterationHistory)
   ├→ Regenerate with feedback
   ├→ Validate with judge (IterationJudge)
   ├→ Generate semantic diff (SemanticDiffGenerator)
   ├→ Get user approval
   ├→ Finalize (save, cull downstream, commit)
   └→ Return to step 5
```

---

## Part 13: Extension Points

### 13.1 Adding New Prompts

**Step 1: Create Template**
```
src/prompts/analysis/new-analysis.j2

[SYSTEM]
You are an expert analyst...

[USER]
Analyze this content for {{ analysis_type }}:
{{ content }}

Return JSON with:
{
  "findings": [...],
  "recommendations": [...]
}
```

**Step 2: Add Metadata**
```yaml
# src/prompts/config.yaml
analysis/new-analysis:
  temperature: 0.3
  format: "json"
  reserve_tokens: 2000
```

**Step 3: Use in Code**
```python
prompts = self.prompt_loader.render(
    "analysis/new-analysis",
    analysis_type="plot",
    content=story_text
)
result = await self.client.json_completion(
    model=self.model,
    prompt=prompts['user'],
    system_prompt=prompts['system'],
    temperature=self.prompt_loader.get_temperature("analysis/new-analysis")
)
```

### 13.2 Adding New Generators

**Template:**
```python
from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader

class NewGenerator:
    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        if not model:
            raise ValueError("Model required")
        self.client = client
        self.project = project
        self.model = model
        self.prompt_loader = get_prompt_loader()

    async def generate(self, context: Dict) -> str:
        # Build context using LODContextBuilder
        # Render prompt with PromptLoader
        # Call API via OpenRouterClient
        # Save via Project model
        # Commit via GitManager
        pass
```

### 13.3 Adding New Analyzers

**Template:**
```python
from .base import AnalysisResult, Issue, Severity

class NewAnalyzer:
    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        self.client = client
        self.project = project
        self.model = model

    async def analyze(self) -> AnalysisResult:
        # Load content
        # Call LLM for analysis
        # Extract issues and strengths
        # Return AnalysisResult
        pass
```

### 13.4 Adding New Exporters

**Location:** `src/export/`

**Template:**
```python
class NewExporter:
    def __init__(self, project: Project):
        self.project = project

    def export(self, output_path: Path) -> bool:
        # Load chapters
        # Format for target format
        # Write to path
        # Return success
        pass
```

---

## Part 14: Workflow Integration Examples

### 14.1 Complete Book Generation Workflow

```python
# 1. Start REPL
agentic

# 2. Create project
/new my-novel

# 3. Select model
/model  # Choose from available models

# 4. Generate premise
/generate premise
# (or: /generate premise --file concept.txt)

# 5. Generate treatment
/generate treatment

# 6. Generate chapters with variants
/generate chapters --variants

# 7. Finalize chapter variants
/finalize chapters
# (selects best variant)

# 8. Generate prose
/generate prose all
# (generates all chapters sequentially)

# 9. Iterate as needed
/iterate prose
# User: "make it darker and more suspenseful"
# System: regenerates, validates, shows diff, commits

# 10. Analyze
/analyze --detailed

# 11. Export
/export rtf
# (creates RTF file in exports/)
```

### 14.2 Cloning for Safe Experimentation

```python
/clone my-novel my-novel-dark
# Creates copy for experimentation

/switch my-novel-dark
# Switch active project

/iterate prose
# "make darker, add more gothic elements"
# Changes only affect clone

# If successful, can merge back manually
# If failed, original preserved
```

### 14.3 Git Operations

```bash
# View history
cd books
git log --oneline | head -20

# See specific project commits
git log --oneline -- my-novel/

# Rollback to previous version
git reset --hard HEAD~1

# Compare versions
git diff HEAD~1 -- my-novel/chapters/

# Create branches for major variations
git branch my-novel-ending-a
git branch my-novel-ending-b
```

---

## Part 15: Configuration and Setup

### 15.1 Environment Configuration

**Required:**
```bash
export OPENROUTER_API_KEY="sk-or-..."
```

**Optional:**
```bash
export AGENTIC_LOG_LEVEL="DEBUG"
export AGENTIC_DATA_DIR="/custom/path"
```

### 15.2 Settings System
**File:** `src/config/settings.py`

**Uses pydantic-settings for configuration hierarchy:**
1. Environment variables (highest priority)
2. `.env` file
3. Built-in defaults (lowest priority)

**Key Settings:**
- `openrouter_api_key` — API authentication
- `openrouter_base_url` — API endpoint
- `active_model` — Current model selection
- `data_dir` — Where books/ directory lives

---

## Part 16: Testing and Quality Assurance

### 16.1 Code Quality Tools

**Configured in pyproject.toml:**

**Black:** Code formatting
```toml
[tool.black]
line-length = 100
target-version = ["py311"]
```

**Ruff:** Linting
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "RUF"]
```

**MyPy:** Type checking
```toml
[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true
```

**Pytest:** Testing framework
```bash
pytest tests/
pytest --cov=src tests/  # With coverage
```

### 16.2 Testing Recommendations

Given the AI-dependent nature of the system, focus on:
1. **Unit tests:** Configuration, data structures, utilities
2. **Integration tests:** Generation pipeline with mocked API
3. **Snapshot tests:** Prompt rendering consistency
4. **Manual tests:** Full workflows on cloned projects (as per CLAUDE.md)

---

## Part 17: Common Questions and Troubleshooting

### 17.1 Why do some files become `.md` and others `.yaml`?

**Answer:**
- **New generation** → Saves as `.md` (raw LLM output)
- **Legacy projects** → May have `.yaml` files (auto-migrated)
- **Both supported:** Parser handles either format

To migrate old `.yaml` to `.md`:
1. Run any generation step (treats `.yaml` as fallback)
2. Files will be rewritten as `.md` on next save

### 17.2 Why doesn't my prose generation access premise/treatment?

**Answer:**
This is intentional! `chapters.yaml` is **self-contained**:
- Contains all metadata, characters, world
- Prose generator works independently
- Allows prose iteration without premise changes

If you modify premise/treatment, you MUST regenerate chapters to reflect changes.

### 17.3 Can I manually edit files?

**Answer:** Yes!
- Edit `.md` files directly (prose, foundation, etc.)
- Edit `.json` files for metadata
- Avoid editing while generation is running
- Manual edits don't auto-commit (must git commit manually)

### 17.4 How do I rollback changes?

**Answer:**
```bash
cd books
# See what changed
git log --oneline

# Rollback one generation
git reset --hard HEAD~1

# Rollback multiple
git reset --hard HEAD~5
```

### 17.5 What's the maximum context length for iteration?

**Answer:**
Depends on selected model:
- Check via `/models` command (shows context_length)
- System automatically calculates headroom
- Raises error if content too large

---

## Part 18: Performance Considerations

### 18.1 Token Budgeting

**How System Calculates Max Tokens:**

```python
# 1. Estimate context tokens
context_tokens = estimate_tokens(premise + treatment + chapters)

# 2. Add response buffer
response_needed = 6000  # ~4000-5000 words + buffer

# 3. Calculate safe max
max_tokens = min(
    model.context_length - headroom,
    available_tokens - context_tokens - response_needed
)
```

**Headroom:** ~2000 tokens safety margin (avoid hitting limit mid-generation)

### 18.2 Optimization Tips

1. **Use `--auto` for chapters** — Lets LLM choose optimal count
2. **Limit iteration attempts** — Judge retries up to 3 times
3. **Check model context before large projects** — See TOKENS in `/models`
4. **Use style cards** — Reuse from first chapter to avoid regenerating

### 18.3 Cost Estimation

**Typical book (~80k words):**
- Premise: 500 tokens
- Treatment: 3000 tokens
- Chapters (30 chapters): 8000 tokens
- Prose: 20000 tokens
- **Total: ~31,500 tokens**

**Iteration:** Adds 5000-10000 tokens per cycle

**Cost varies:** Depends on model pricing (Claude vs Mistral vs others via OpenRouter)

---

## Conclusion

AgenticAuthor's architecture is built around these core ideas:

1. **Structured Iteration:** Level-of-Detail progression from concept to prose
2. **Full Context:** Generous context inclusion for LLM quality
3. **Fail Fast:** Clear errors, no silent fallbacks
4. **Markdown-First:** Better creative output, human-readable storage
5. **Natural Language Feedback:** Iterate with plain English, not commands
6. **Version Control:** Every change committed, easy rollback
7. **Extensibility:** New prompts, generators, and analyzers plug in cleanly

The system respects user choice (single model policy), maintains traceability (git commits), and prioritizes quality over artificial constraints (no word count pressure).

---

## Appendix A: File Count Summary

```
Python Files:         55 files (~11,000 lines)
Prompt Templates:     29 files (generation, analysis, etc.)
Configuration:         1 file (config.yaml)
Taxonomies:           12 files (genres + base)
Documentation:         4 files (README, ARCHITECTURE, etc.)
Tests:                TBD (needs rebuild for v0.4.0)

Key Modules by Size:
- interactive.py:      500+ lines (REPL orchestrator)
- project.py:         1373 lines (Project model)
- analyzer.py:        1000+ lines (Analysis coordinator)
- prose.py:            ~600 lines (Prose generation)
- chapters.py:        1000+ lines (Chapter generation)
- iterator.py:         795 lines (Iteration coordinator)
```

---

**Document Status:** Complete  
**Last Verified:** January 6, 2026  
**Maintainers:** AgenticAuthor Contributors  
**Version:** 1.0 (Comprehensive, Self-Contained)

