# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Documentation Updates

**You MUST update the following documentation files whenever making relevant changes:**

1. **`docs/IMPLEMENTATION_STATUS.md`** - Update when:
   - Completing a feature (move from In Progress to Completed)
   - Starting new work (add to In Progress)
   - Finding bugs (add to Known Issues)
   - Changing test coverage
   - Making any significant changes (add to Recent Changes with date)

2. **`docs/USER_GUIDE.md`** - Update when:
   - Adding new commands or features
   - Changing user-facing behavior
   - Updating command examples
   - Adding usage instructions

3. **`docs/DEVELOPER_GUIDE.md`** - Update when:
   - Changing architecture or design
   - Adding new APIs or components
   - Updating development setup
   - Adding implementation patterns

4. **`docs/CHANGELOG.md`** - Update when:
   - Completing features or fixing bugs
   - Preparing releases
   - Updating project status
   - Tracking known issues

5. **`README.md`** (root) - Update when:
   - Changing quick start instructions only
   - Keep minimal - points to full docs

**Always check these files at the end of your work session and update them!**

## CRITICAL: Git Commit Workflow

**You MUST commit changes to git after every meaningful change with a descriptive commit message.**

### When to Commit

Commit immediately after:
1. **Bug fixes** - "Fix chapter iteration compatibility with multi-phase generation"
2. **Feature implementations** - "Add automatic resume on network truncation"
3. **Documentation updates** - "Update CHANGELOG with iteration fixes"
4. **Refactoring** - "Refactor LODContextBuilder to return flat structure for chapters"
5. **Test additions/fixes** - "Add tests for YAML recovery logic"
6. **Any working state** - Don't let multiple changes accumulate without commits

### Commit Message Guidelines

**Format:**
```
<Type>: <Short description (50 chars max)>

<Detailed explanation if needed (wrap at 72 chars)>
- Bullet points for multiple changes
- Why the change was needed
- What problem it solves
```

**Types:**
- `Fix:` - Bug fixes
- `Add:` - New features
- `Update:` - Updates to existing features
- `Refactor:` - Code restructuring without behavior change
- `Docs:` - Documentation only changes
- `Test:` - Test additions or fixes
- `Chore:` - Build, dependencies, tooling

**Good Examples:**
```bash
git add .
git commit -m "Fix: Chapter iteration compatibility with multi-phase generation

- LODContextBuilder now returns flat structure for chapter iteration
- Parser handles both flat and nested formats for backward compatibility
- Fixes parser format detection which checks for metadata at top level"

git add .
git commit -m "Add: Automatic resume on truncation for chapter generation

- Detects YAML truncation from network drops
- Analyzes partial to find last complete chapter
- Resumes for missing chapters with custom prompt
- Saves ~25-30% tokens vs full retry"

git add .
git commit -m "Docs: Update CHANGELOG and CLAUDE.md with iteration fixes"
```

**Bad Examples:**
```bash
git commit -m "fix"  # Too vague
git commit -m "updates"  # No information
git commit -m "work in progress"  # Commit working states with better description
```

### Workflow

1. Make changes to code
2. Test that changes work
3. **CRITICAL: Ultrathink and double-check implementation** (see section below)
4. Update relevant documentation
5. Stage all changes: `git add .`
6. Commit with descriptive message: `git commit -m "Type: Description"`
7. Continue to next change

**DO NOT accumulate multiple unrelated changes before committing.**
**Each logical change should be its own commit.**

## CRITICAL: Ultrathink and Double-Check Implementation

**After completing ANY feature work or bug fix, ALWAYS perform this verification:**

### Step-by-Step Verification Process

1. **Read All Modified Code**
   - Read every file you changed completely
   - Don't assume you remember what you wrote
   - Fresh eyes catch bugs that seemed correct while coding

2. **Check Edge Cases**
   - Empty inputs (empty strings, empty lists, None values)
   - Boundary conditions (0, 1, max values)
   - Invalid inputs (wrong types, out of range)
   - Error paths (file not found, network errors, timeouts)
   - Cancellation (Ctrl+C, EOF, Enter to cancel)

3. **Verify Integration Points**
   - Does new code work with existing systems?
   - Are all imports correct?
   - Are all function signatures compatible?
   - Is error handling consistent with rest of codebase?
   - Are return types correct?

4. **Check Documentation Updates**
   - Help text updated?
   - Command completions updated?
   - Error messages clear and helpful?
   - All references to the feature included?
   - CLAUDE.md updated if adding new patterns?

5. **Review Algorithm Logic**
   - No infinite loops?
   - No off-by-one errors?
   - Proper deduplication?
   - Thread-safe if concurrent?
   - Memory leaks prevented?

6. **Verify File Operations**
   - Correct paths (absolute vs relative)?
   - Proper encoding (UTF-8)?
   - File handles closed (use `with` statements)?
   - Directories exist before writing?
   - Permissions checked?

7. **Check User Experience**
   - Clear error messages with actionable next steps?
   - Consistent with existing UX patterns?
   - Colors readable on different terminal themes?
   - Keyboard interrupts handled gracefully?
   - Progress feedback for long operations?

8. **Test Scenarios Matrix**

   Create mental test scenarios:
   ```
   | Scenario                  | Expected Result          | Verified |
   |---------------------------|--------------------------|----------|
   | Happy path                | Works correctly          | ✓        |
   | Empty input               | Clear error or default   | ✓        |
   | Invalid input             | Clear error message      | ✓        |
   | Boundary (min)            | Handles correctly        | ✓        |
   | Boundary (max)            | Handles correctly        | ✓        |
   | Cancel operation          | Graceful exit            | ✓        |
   | Files missing             | Clear error with path    | ✓        |
   | Network error             | Retry or clear error     | ✓        |
   ```

9. **Check Git Commit**
   - All new files staged?
   - No accidentally committed debug code?
   - No accidentally committed secrets?
   - Commit message descriptive?
   - No unrelated changes in commit?

### Example Verification (Real Example)

**Feature:** Concept mashup generator

**Verification performed:**
- ✅ Read concept_mashup.py line by line
- ✅ Verified file loading handles UTF-8, empty files, missing files
- ✅ Verified combination algorithm: deduplication works, no infinite loops, max_attempts safety valve
- ✅ Verified CLI integration: count validation, error messages, display formatting
- ✅ Tested edge cases: count=0, count>max, files missing, cancellation
- ✅ Verified integration with premise generation: concept string passed correctly
- ✅ Checked documentation: help text, command completer, error messages all updated
- ✅ Verified git commit: misc/ files included, good commit message
- ✅ No issues found, approved for merge

### When to Skip This Step

**NEVER.**

Even for "trivial" changes, quick verification catches:
- Typos in variable names
- Copy-paste errors
- Missing imports
- Broken integration points
- Poor error messages

**Time investment:** 5-10 minutes per feature
**Bugs prevented:** Often 2-3 per feature
**ROI:** Massive

## Project Summary

AgenticAuthor is a Python CLI for iterative AI-powered book generation using OpenRouter API. It follows a Level of Detail (LOD) approach: premise (LOD3) → treatment/chapters (LOD2) → full prose (LOD0).

**Key Innovation**: Natural language iteration with git-backed version control. Users simply describe what they want changed, and the system handles intent checking, execution, and auto-commits.

**Critical Architecture: Quality-First Prose Generation** ✨
- **Problem Solved**: Word count targets caused LLMs to artificially fragment and duplicate content
- **Root Cause**: `num_scenes = len(key_events)` treated plot points as separate scenes → LLM created 9 dramatic scenes with 9 "reversals" → massive duplication
- **Solution**: Quality-first architecture - removed all word count pressure from prompts

**Quality-First Philosophy**:
- Let LLM determine natural scene structure (typically 2-4 scenes per chapter)
- Focus on "write excellently" not "write exactly N words"
- Chapters breathe based on content, not arithmetic
- Trust narrative instincts over numerical targets

**Key Changes** (Refactor completed 2025-10-19):
- **depth_calculator.py**: Simplified from 566 → 284 lines (50% reduction)
  - Kept: Chapter count calculation, act distribution (25%/50%/25%), peak roles
  - Removed: Word budgeting, scene budgets, beat calculations, glue fractions
- **wordcount.py**: DELETED entirely (361 lines removed)
- **prose.py**: Complete quality-first prompt rewrite
  - Removed: Word count targets, scene fragmentation, arithmetic pressure
  - Added: Chapter summary, key moments list, SHOW vs TELL examples
  - Focus: "Write excellent prose" with natural scene breaks
- **chapters.py**: Removed per-chapter word_count_target field
  - Uses foundation's overall target_word_count for display only
- **Backward Compatible**: Supports both new and legacy chapter formats

**Expected Impact**: Eliminates duplication, natural scene flow, quality-focused prose, variable chapter lengths (2k-5k words based on story needs)

**Recent Major Features (v0.3.0 and Unreleased)**:
- **Multi-Variant Chapter Generation with LLM Judging** 🎯 - Generate multiple chapter outline options and let LLM select the best
  - Workflow: `/generate chapters` → `/finalize chapters` → `/generate prose`
  - Generates 4 variants in parallel with different temperatures (0.65, 0.70, 0.75, 0.80)
  - LLM judge evaluates all variants with minimal structure (free to use own criteria)
  - Winner automatically copied to chapter-beats/ for prose generation
  - Transparent decision tracking in decision.json
  - Storage: chapter-beats-variants/ for variants, chapter-beats/ for finalized winner
  - Benefits: Multiple creative options, objective evaluation, better chapter quality
  - Clean architecture: Reuses ChapterGenerator._generate_single_shot() (no code duplication)
- **Sequential Chapter Generation** 🔄 - Zero information loss with full context accumulation (deprecated in favor of multi-variant)
  - Three phases: Foundation (metadata/characters/world) → Sequential Chapters → Assembly
  - File structure: `chapter-beats/foundation.yaml` + `chapter-beats/chapter-NN.yaml`
  - Each chapter sees 100% of previous chapters (not 5% summaries - eliminates duplicate scenes)
  - User-controlled resume capability (continue/regenerate/abort prompt)
  - Progress saved incrementally (can inspect partial results)
  - Foundation loaded on resume (saves ~2,000 tokens + 30-45s)
  - Benefits: Zero loss, short streams (30-60s/chapter), incremental saves, better error recovery
- **Self-Contained Chapters Architecture** - chapters.yaml includes everything for prose generation
  - chapters.yaml has 4 sections: metadata, characters, world, chapters
  - Prose generation ONLY uses chapters.yaml (no premise/treatment needed)
  - Unidirectional data flow: premise → treatment → chapters → prose (no sync back)
  - /cull command for cascade deletion (prose, chapters, treatment, premise)
- **Automatic genre detection** - LLM auto-detects genre from concept
- **Interactive taxonomy editor** - Full-screen checkbox UI for taxonomy selection
- **Interactive model selector** - Live-filtering model search with keyboard navigation
- **Taxonomy iteration** - Modify story parameters and regenerate premise
- **Strict model enforcement** - Single user-selected model for ALL operations (no fallbacks)
- **Smart chapter iteration** - chapters.yaml supports patch and regenerate modes
  - Patch: Fast unified diffs for targeted edits (10-15x faster)
  - Regenerate: Full AI regeneration for structural changes
  - Existing chapters included in iteration prompt for true modification
- **Short Story Workflow** 📖 - Simplified flow for short-form stories (≤2 chapters)
  - Automatic detection: ≤2 chapters = short-form (flash fiction, short story, novelette)
  - Single file: story.md instead of chapters/ directory
  - Skip chapters.yaml: goes directly from treatment → prose
  - Optimized prompts: emphasizes unity of effect, single-sitting experience
  - Iteration: diff-based patching of story.md with full context
  - Status display: shows story type and word count instead of chapter count
  - Force flag: `--force` on /generate chapters to override detection

**Previous Features (v0.2.0)**:
- Genre-specific taxonomy support (11 genres with autocomplete)
- Smart input detection (brief premise vs standard vs detailed vs treatment)
- History tracking to avoid repetitive generations
- Comprehensive logging system (`./logs/`)
- Enhanced tab completion for commands, genres, and models

## Quick Start Commands

```bash
# Setup
pip install -e .  # Install in development mode
export OPENROUTER_API_KEY="sk-or-your-key-here"

# Run
agentic           # Start REPL (main interface)

# In REPL - all commands use / prefix:
/new my-book      # Create new project
/open my-book     # Open existing project
/clone my-book-v2 # Clone current project to new name
/status           # Check project status
/models           # List available models
/model            # Interactive model selector (live filtering)
/model grok       # Or use fuzzy search directly
/generate premise "a magical library"  # Auto-detects genre (fantasy)
/generate premises 5 fantasy "a magical library"  # Generate 5 options to choose from
/iterate taxonomy # Interactive taxonomy editor
/generate treatment           # Generate treatment from premise
/generate chapters            # Generate 4 chapter outline variants (parallel)
/finalize chapters            # LLM judges variants and selects winner
/generate prose all           # Generate full prose from finalized chapters
/cull prose       # Delete prose files (or chapters/treatment/premise - cascades downstream)
/logs             # View recent log entries
/help             # Show all commands
```

## Short Story Workflow

**For stories ≤ 7,500 words (flash fiction, short stories, novelettes):**

```bash
# 1. Create project and select short story length
/new my-short-story
/model grok-4-fast  # Select model
/generate premise "a brief concept"
/iterate taxonomy   # Select "short_story" in length_scope category

# 2. Generate treatment (structural outline)
/generate treatment

# 3. Generate complete story (single file)
/generate prose     # Creates story.md (NOT chapters!)

# 4. Iterate on story
"Make the ending more ambiguous"
"Add more sensory details in the opening"
"Change protagonist's motivation"

# 5. Check status
/status  # Shows "Type: Short Story (~3,500 words target)"
         # Story: ✓  (3,200 words)

# 6. Export
/metadata title "My Short Story"
/metadata author "Your Name"
/export rtf my-story.rtf
```

**File Structure (Short Story):**
```
books/my-short-story/
├── premise/
│   └── premise_metadata.json  ← Single source of truth (text + taxonomy)
├── treatment/
│   └── treatment.md
└── story.md                   ← Single complete story (no chapters/)
```

**vs. Novel Structure:**
```
books/my-novel/
├── premise/
│   └── premise_metadata.json  ← Single source of truth (text + taxonomy)
├── treatment/
│   └── treatment.md
├── chapter-beats/             ← Chapter structure (source of truth)
│   ├── foundation.yaml        ← Metadata, characters, world
│   └── chapter-NN.yaml        ← Individual chapter outlines
└── chapters/
    ├── chapter-01.md
    ├── chapter-02.md
    └── ...
```

## Testing After Changes

**Note: Test suite removed as of v0.3.0 - needs rebuilding to match current architecture**

Manual testing checklist after making changes:
```bash
# Check the REPL starts
agentic

# Then in REPL test these commands:
/help             # Should show all commands
/models           # Should list OpenRouter models (needs API key)
/new test-book    # Should create a project
/model            # Should launch interactive model selector
/generate premise # Should show genre selection or auto-detect
/generate premises 5 fantasy  # Should generate 5 options with streaming
/iterate taxonomy # Should launch interactive taxonomy editor
/logs             # Should show log location
/status           # Should show project info
/exit             # Should exit cleanly
```

**TODO: Rebuild test suite for v0.3.0+**
- Test interactive editors (model_selector, taxonomy_editor)
- Test batch premise generation
- Test auto genre detection
- Test strict model enforcement
- Test taxonomy iteration
- Integration tests with real API calls

## Core Architecture Principles

1. **Natural Language First**: Always listening for feedback, no explicit commands needed
2. **Shared Git Repository**: Single git repo at books/ level, commits prefixed with project name
3. **Single Active Model**: One model at a time for ALL operations (switchable)
4. **File-Based Storage**: Human-readable markdown/YAML files
5. **Smart Intent Checking**: Confidence-based routing (>0.8 execute, else clarify)
6. **No Modal Dialogs**: All interactions are inline in the CLI, never modal popups
7. **Fail Early, No Fallbacks**: Use actual facts (API data), never assumptions or fallbacks

## Model Selection Policy

**CRITICAL: Always use the user's selected model for ALL LLM calls. NEVER choose a different model.**

- **No hardcoded models**: Never use hardcoded model names in generation code
- **No fallback models**: If no model is selected, raise a clear error - don't fall back to a default
- **No model substitution**: Don't pick a "better" model for specific tasks (diff generation, intent analysis, etc.)
- **Single model for everything**: The user's selected model must be used for ALL operations:
  - Premise generation
  - Treatment generation
  - Chapter generation
  - Prose generation
  - Intent analysis
  - Diff generation
  - Scale detection
  - All other LLM calls

**Error handling:**
```python
if not model:
    raise ValueError("No model selected. Use /model <model-name> to select a model.")
```

**Why:** Users choose models based on cost, speed, and quality tradeoffs. Silently using a different model violates this choice and can cause unexpected costs or behavior.

## UI/UX Principles (Following Claude Code)

### Inline Everything
- **No modal dialogs or popup windows** - everything happens in the terminal flow
- Use numbered lists for selection (e.g., "1. project-a  2. project-b")
- Simple prompts for user input ("> Enter choice: ")
- Progressive disclosure - show information as needed
- Maintain context in the terminal scrollback

### Selection Patterns
```
Available projects:
  1. my-fantasy-novel • fantasy • 5,000 words • updated today
  2. sci-fi-story • science-fiction • 10,000 words • updated yesterday
  3. romance-draft • romance • 2,500 words • updated 5 days ago

Enter number to select, or press Enter to cancel:
>
```

### Feedback and Progress
- Use Rich for colored, formatted output
- Show progress inline with status updates
- Keep responses concise and actionable
- Errors and warnings inline, not in popups

## Key Systems to Understand

### Model Capability Detection
```python
# ALWAYS use actual model capabilities from API
model_obj = await client.get_model(model)
if not model_obj:
    raise Exception(f"Failed to fetch model capabilities for {model}")

# Use actual limits, not assumptions
max_output = model_obj.get_max_output_tokens()
context_length = model_obj.context_length

# Check capabilities
if not model_obj.has_sufficient_context(required_tokens):
    raise Exception(f"Model has insufficient context: {context_length} < {required_tokens}")
```

### Taxonomy System
```python
# Genre-specific generation parameters
from src.generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory
from src.generation.premise import PremiseGenerator

# Auto-detect genre from concept
generator = PremiseGenerator(client, project, model)
genre = await generator.detect_genre("a wizard discovers magic is breaking")
# Returns: "fantasy"

# Load genre taxonomy
loader = TaxonomyLoader()
taxonomy = loader.load_merged_taxonomy(genre)

# Interactive taxonomy editing
/iterate taxonomy  # Launches full-screen checkbox editor

# Or natural language
/iterate taxonomy
make it a standalone and change pacing to fast

# Analyze input type
analysis = PremiseAnalyzer.analyze(user_input)
if analysis['is_treatment']:  # 200+ words
    # Preserve as treatment, extract taxonomy
else:
    # Generate or enhance premise
```

### Smart Input Detection
```
Input Analysis:
- < 20 words: Brief premise → Full generation + auto-detect genre
- 20-100 words: Standard premise → Enhancement + auto-detect genre
- 100-200 words: Detailed premise → Structuring
- 200+ words: Treatment → Preserve + extract taxonomy
```

### Iteration Flow
```python
User: "Add more dialogue to chapter 3"
→ Intent check (single LLM call with JSON response)
→ High confidence: Execute + auto-commit "Iterate chapter 3: add dialogue"
→ Low confidence: Ask clarification

# Taxonomy iteration
/iterate taxonomy
→ Interactive editor OR natural language
→ Update taxonomy selections
→ Optionally regenerate premise
→ Auto-commit changes
```

### LOD Context Structure
```python
# CRITICAL: Context structure depends on iteration target

# Chapter iteration (editing chapters.yaml):
# LODContextBuilder returns FLAT structure (not nested under 'chapters' key)
context = {
    'metadata': {...},    # Genre, pacing, tone, themes, etc.
    'characters': [...],  # Full character profiles
    'world': {...},      # Setting, locations, systems
    'chapters': [...]    # Chapter outlines
}

# Prose iteration (editing chapter-NN.md):
# Context includes chapters.yaml + all chapter prose
context = {
    'chapters': {        # Nested for prose context
        'metadata': {...},
        'characters': [...],
        'world': {...},
        'chapters': [...]
    },
    'prose': [           # All chapter prose for full context
        {'chapter': 1, 'text': '...'},
        {'chapter': 2, 'text': '...'},
        # ...
    ]
}

# WHY: Parser detects NEW format by checking for metadata/characters/world
# at TOP LEVEL. Nesting breaks detection.
```

### Git Integration
- Auto-commit with descriptive messages
- Unified diff support
- Full git operations (rollback, branch, diff)
- See `docs/IMPLEMENTATION_GUIDE.md` for code examples

### Analysis System
Based on dv-story-generator's comprehensive analysis:
- Commercial viability (0-100% market ready)
- Plot holes with severity levels
- Character consistency tracking
- Results in `analysis/` directory with git SHA references
- See `docs/IMPLEMENTATION_GUIDE.md` for analysis patterns

### Test Strategy
- Real book fixture using grok-4-fast (cheap model)
- Git-based test isolation
- See `docs/DEVELOPMENT.md` for testing approach

## Implementation Approach

1. Start with `docs/IMPLEMENTATION_GUIDE.md` - contains detailed code patterns
2. Build in this order: Core Config → API Client → REPL → Generation → Iteration → Analysis
3. Use subprocess for git (simpler than GitPython)
4. Test with real generated content, not mocks

## Project File Structure

```
books/                      # All projects root
├── .git/                    # **SHARED** git repo for ALL projects
├── [project-name-1]/
│   ├── .agentic/            # Project-local AgenticAuthor state
│   │   ├── logs/            # Session logs
│   │   ├── history          # Command history
│   │   ├── premise_history.json # Generation history
│   │   └── debug/           # Debug output
│   ├── config.yaml          # Project configuration
│   ├── premise/             # LOD3 - Premise artifacts
│   │   ├── premise_metadata.json  # Single source of truth (text + taxonomy)
│   │   └── premises_candidates.json  # Batch generation results (when using /generate premises N)
│   ├── treatment/           # LOD2 - Treatment artifacts
│   │   └── treatment.md
│   ├── chapter-beats-variants/  # LOD2 - Multi-variant generation (temporary)
│   │   ├── foundation.yaml  # Shared foundation for all variants
│   │   ├── variant-1/       # Variant 1 (temp=0.65, Conservative)
│   │   │   └── chapter-*.yaml
│   │   ├── variant-2/       # Variant 2 (temp=0.70, Balanced-Conservative)
│   │   │   └── chapter-*.yaml
│   │   ├── variant-3/       # Variant 3 (temp=0.75, Balanced-Creative)
│   │   │   └── chapter-*.yaml
│   │   ├── variant-4/       # Variant 4 (temp=0.80, Creative)
│   │   │   └── chapter-*.yaml
│   │   └── decision.json    # LLM judging decision record
│   ├── chapter-beats/       # LOD2 - Chapter structure (finalized winner)
│   │   ├── foundation.yaml  # Metadata, characters, world
│   │   └── chapter-*.yaml   # Individual chapter outlines (from winning variant)
│   ├── chapters.yaml        # LOD2 - Self-contained (deprecated, for backward compatibility)
│   ├── chapters/            # LOD0 - Prose
│   │   └── chapter-*.md
│   ├── story.md             # LOD0 - Complete story (for short stories ≤2 chapters only)
│   ├── analysis/            # Analysis results
│   │   ├── commercial.md
│   │   ├── plot.md
│   │   └── ...
│   ├── exports/             # Export artifacts
│   │   ├── frontmatter.md   # Book frontmatter
│   │   ├── dedication.md    # Book dedication
│   │   └── *.rtf, *.md      # Exported books
│   └── project.yaml         # Project metadata
└── [project-name-2]/
    └── ... (same structure)
```

### Shared Git Architecture

**CRITICAL**: Single git repository at `books/.git` manages ALL projects.

Commits are prefixed with project name:
```
[my-novel] Generate premise: fantasy
[my-novel] Generate treatment: 2500 words
[sci-fi-story] Generate premise: sci-fi
[my-novel] Iterate chapter 3: add dialogue
```

Implementation in `InteractiveSession`:
```python
def _init_shared_git(self):
    """Initialize shared git at books/ level."""
    books_dir = self.settings.books_dir
    self.git = GitManager(books_dir)  # Points to books/.git
    if not (books_dir / ".git").exists():
        self.git.init()
        self.git.commit("Initialize books repository")

def _commit(self, message: str):
    """Commit with project name prefix."""
    if self.project:
        prefixed = f"[{self.project.name}] {message}"
    else:
        prefixed = message
    self.git.add()
    self.git.commit(prefixed)
```

**Project model has NO git attribute. No per-project repositories.**

## Key Implementation Files

- `src/generation/taxonomies.py` - Genre taxonomy system and premise analysis
- `src/generation/premise.py` - Premise generation with auto-detection, taxonomy iteration
- `src/generation/depth_calculator.py` - **Quality-first structure calculator** (mathematical, no LLM)
  - Calculates chapter count from total words (~3500 words per chapter)
  - Distributes chapters across acts (25% / 50% / 25%)
  - Assigns peak roles (inciting_setup, midpoint, crisis, climax, denouement, escalation)
  - No word budgeting - provides structural guidance only
  - Simplified from 566 → 284 lines (50% reduction)
- `src/generation/chapters.py` - Chapter outline generation (single-shot with global arc planning)
  - Generates all chapters in ONE LLM call with complete story view
  - Prevents event duplication by planning entire arc before generating details
  - Uses simple key_events format (proven quality from historical testing)
  - Backward compatible: accepts both foundation + individual files and legacy formats
- `src/generation/prose.py` - **Quality-first prose generation**
  - Prompts focus on "write excellent prose" not "write N words"
  - Key moments listed (not counted as separate scenes)
  - SHOW vs TELL examples (380-word full scene vs 20-word summary)
  - Natural scene breaks (typically 2-4 scenes per chapter)
  - Fixed token estimates (5000-6000) - no dependency on word count targets
- `src/generation/multi_model.py` - Multi-model competition coordinator with judging logic
- `src/generation/variant_manager.py` - Chapter variant generation and judging
- `src/generation/iteration/` - Natural language feedback processing (coordinator, intent, diff, scale)
- `src/generation/cull.py` - Content deletion manager with cascade (prose → chapters → treatment → premise)
- `src/storage/git_manager.py` - Git operations wrapper
- `src/generation/analysis/` - Comprehensive story analysis (unified analyzer, treatment deviation analyzer)
- `src/cli/interactive.py` - REPL with prompt_toolkit, logging, and interactive editors
- `src/cli/command_completer.py` - Advanced tab completion with genre support
- `src/cli/taxonomy_editor.py` - Full-screen checkbox UI for taxonomy selection
- `src/cli/model_selector.py` - Interactive model selector with live fuzzy search
- `src/utils/logging.py` - Comprehensive logging system

## Fail-Early Paradigm

**CRITICAL: Never implement fallbacks. Always fail early with clear error messages.**

### Error Handling Philosophy

1. **No Silent Failures**: Never use `or ""`, `or []`, `or {}` to mask missing data
2. **No Fallback Values**: Don't hardcode fallback model names, token limits, or defaults
3. **Use Actual Facts**: Get capabilities from OpenRouter API, not assumptions
4. **Clear Error Messages**: Tell user exactly what's missing and how to fix it

### Examples

**❌ BAD - Silent fallback:**
```python
premise = self.project.get_premise() or ""  # Masks missing premise
if model and 'grok' in model.lower():  # Assumes based on name
    min_tokens = 2500  # Hardcoded assumption
```

**✅ GOOD - Fail early:**
```python
premise = self.project.get_premise()
if not premise:
    raise Exception("No premise found. Generate premise first with /generate premise")

model_obj = await self.client.get_model(model)
if not model_obj:
    raise Exception(f"Failed to fetch model capabilities for {model}")

max_output = model_obj.get_max_output_tokens()  # Use actual API data
```

### When Fallbacks ARE Acceptable

1. **Caching**: Return cached data when API fails (with warning)
2. **Optional Features**: Taxonomy, genre selection (truly optional)
3. **Query Operations**: Git operations that legitimately return None/False
4. **User Experience**: Silent autocomplete failures (warn on startup, not during typing)

### Implementation Pattern

```python
# 1. Fetch required data
data = await get_required_data()

# 2. Check immediately
if not data:
    raise Exception("Clear message: what's missing and what to do")

# 3. Use the data
process(data)  # No conditionals needed
```

## Context is King: Always Prioritize Quality Over Token Cost

**CRITICAL PRINCIPLE: When building prompts or context for LLM calls, ALWAYS prioritize giving complete, relevant context over optimizing for token cost.**

### Core Philosophy

1. **Quality over Cost**: Better to spend tokens and get great results than save tokens and get mediocre results
2. **Context is Cheap, Regeneration is Expensive**: A few thousand extra context tokens costs pennies. Regenerating because of insufficient context costs time, money, and user frustration
3. **When in Doubt, Ask**: If unsure whether to include something in context, ASK the user rather than making assumptions
4. **Full Context by Default**: Err on the side of including more context, not less

### Examples

**❌ BAD - Token optimization that hurts quality:**
```python
# Prose generation with minimal context
def generate_prose(chapter):
    # Only include current chapter outline
    context = f"Chapter {chapter.number}: {chapter.title}"
    # Missing: full chapters.yaml, previous prose, character details, etc.
```

**✅ GOOD - Full context for quality:**
```python
# Prose generation with complete context
def generate_prose(chapter, all_chapters_yaml, previous_prose):
    # Include EVERYTHING the LLM needs to write well:
    # - Full chapters.yaml (metadata, characters, world, all chapter outlines)
    # - All previous prose (for continuity, consistency)
    # - Current chapter's full outline with scene structure
    # Even if this is 50k-100k tokens, it's worth it for quality
```

### When to Include Full Context

**ALWAYS include full context for:**
- **Prose generation**: Full chapters.yaml + all previous prose + current chapter outline
- **Chapter iteration**: Full treatment + all existing chapters + feedback
- **Copy editing**: Full chapters.yaml + ALL chapter prose (edited + remaining originals)
- **Analysis**: All available content (premise + treatment + chapters + prose)

**Example from the codebase:**
```python
# Sequential chapter generation - each chapter sees 100% of previous chapters
# NOT 5% summaries, but FULL chapter outlines
for chapter_num in range(1, chapter_count + 1):
    previous_chapters = []
    for prev_num in range(1, chapter_num):
        prev_chapter_data = self.project.get_chapter_beat(prev_num)
        previous_chapters.append(prev_chapter_data)  # FULL detail, not summary

    # Generate with FULL context
    chapter_data = await self._generate_single_chapter(
        foundation=foundation,           # Full metadata, characters, world
        previous_chapters=previous_chapters,  # FULL previous chapters
        ...
    )
```

### When in Doubt: ASK

If you're unsure whether to include something in context:

**❌ DON'T:**
- Assume it's not needed
- Skip it to save tokens
- Use a summary instead of full content
- Make a unilateral decision

**✅ DO:**
- Ask the user: "Should I include X in the context? It will add ~Y tokens but may improve quality."
- Explain the tradeoff clearly
- Let the user decide based on their priorities
- Document the decision for future reference

### Example Scenarios

**Scenario 1: Prose Generation**
```
❌ "I'll summarize previous chapters to save tokens"
✅ "Should I include all previous chapter prose for continuity?
   This adds ~30k tokens (~$0.15) but ensures perfect consistency."
```

**Scenario 2: Chapter Iteration**
```
❌ "I'll only send the chapters being modified"
✅ "Should I include all existing chapters as context for iteration?
   The LLM can see how changes fit with the rest of the story.
   Adds ~5k tokens (~$0.02)."
```

**Scenario 3: Copy Editing**
```
❌ "I'll edit chapters one at a time without context"
✅ Using full context by default:
   - chapters.yaml (metadata, characters, world)
   - All edited chapters so far
   - All remaining original chapters for forward reference
   Total: ~200k tokens, but ensures perfect consistency
```

### Cost Reality Check

**Token costs are VERY cheap compared to the value of quality:**
- 10,000 tokens ≈ $0.05-0.10 (most models)
- 100,000 tokens ≈ $0.50-1.00 (most models)
- Regenerating because of poor quality: $$$$ + user frustration

**User time is valuable:**
- Fixing a poorly generated chapter: 30-60 minutes
- Cost of that time >>> cost of a few thousand extra tokens

### The Single-Shot Chapter Generation Architecture

This project uses **single-shot chapter generation** (all chapters in ONE LLM call) to maintain global arc planning:

```python
# OLD batched/sequential systems: Fragmentation or complexity
# Batched: 95% information loss between batches
# Sequential: Better context but high complexity (deprecated)

# NEW single-shot system: Global arc planning + zero duplication
# All chapters generated in ONE call with complete story view
# LLM plans entire story BEFORE generating any individual chapter details
# Result: Perfect continuity, no duplicates, unique plot roles per chapter
```

**Why we made this choice:**
- Token cost: Slightly higher (~10-20% more tokens)
- Quality improvement: MASSIVE (eliminated duplicates, improved consistency)
- **Conclusion: Worth it every single time**

### Summary

**Golden Rules:**
1. ✅ Full context by default - never summarize unless explicitly required
2. ✅ Ask when uncertain - user makes final call on tradeoffs
3. ✅ Quality over pennies - token costs are negligible compared to quality
4. ✅ Document decisions - explain why you included/excluded context
5. ✅ Trust the architecture - Sequential generation exists for full context

**Remember:** We chose sequential generation SPECIFICALLY to enable full context passing. Honor that architectural decision by always including complete context.

## Important Notes

- OpenRouter API key must start with 'sk-or-'
- Every operation creates a git commit automatically
- Analysis files include git SHA for reproducibility
- Use structured JSON for intent checking responses
- Logs are written to `./logs/agentic_YYYYMMDD.log`
- Genre taxonomies are in `docs/taxonomies/` directory
- Model selection: use specified model or project default or settings default (NOT a fallback chain)
- Tab completion works for commands, genres, and models
- **Test suite:** Removed in v0.3.0 (needs rebuilding for new architecture)
- **All generation requires:** premise → treatment → chapters → prose (fail if missing)
- **Premise storage:** Single source of truth in `premise_metadata.json` (text + taxonomy). Old projects with `premise.md` are supported via backward compatibility.

## Repository Structure

```
AgenticAuthor/
├── CLAUDE.md               # AI assistant instructions (this file)
├── .env                    # API keys (git-ignored)
├── pyproject.toml          # Python package config
├── src/                    # Source code
├── docs/                   # All documentation
│   ├── USER_GUIDE.md      # Complete user guide
│   ├── DEVELOPER_GUIDE.md # Developer reference
│   ├── CHANGELOG.md       # Version history & status
│   ├── LOD.md             # Level of Detail system
│   └── taxonomies/        # Genre taxonomy files
├── taxonomies/             # Genre taxonomy JSON files
└── books/                  # Generated book projects
```