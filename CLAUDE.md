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

**Critical Architecture: Scene-Based Word Count System** 🎬
- **Problem Solved**: Old system achieved only 50-60% of target word counts (e.g., 2,300/3,800 words)
- **Root Cause**: LLMs treated "key_events" as bullet point summaries (200-500 words) instead of full dramatic scenes
- **Solution**: Complete refactoring to scene-based architecture with structured scene format

**Scene Structure (New Format)**:
```yaml
scenes:
  - scene: "Scene Title"              # Brief title (2-4 words)
    location: "Where it happens"      # Setting
    pov_goal: "What character wants"  # Character objective
    conflict: "What prevents it"      # Obstacle
    stakes: "What's at risk"          # Consequences
    outcome: "How it resolves"        # Resolution
    emotional_beat: "Internal change" # Character arc
    sensory_focus:                    # Atmosphere
      - "Sensory detail 1"
      - "Sensory detail 2"
    target_words: 1300                # Scene target (act-specific)
```

**Key Changes**:
- **Math Layer** (depth_calculator.py): All constants renamed (WORDS_PER_EVENT → WORDS_PER_SCENE), +35-37% increases, scene clamping (2-4 per chapter)
- **Chapter Generation** (chapters.py): 3 major prompts updated to generate structured scenes, emphasize "COMPLETE DRAMATIC UNITS"
- **Prose Generation** (prose.py): Complete prompt rewrite with 4-part scene structure, SHOW vs TELL examples, MINIMUM (not average) word counts
- **Backward Compatible**: All systems support both 'scenes' (new) and 'key_events' (old) formats

**Expected Impact**: 80-100% word count achievement (vs 50-60% baseline), professional scene quality

**Recent Major Features (v0.3.0 and Unreleased)**:
- **Multi-Phase Chapter Generation** 🚀 - Reliable chapter generation with automatic resume
  - Three phases: Foundation (metadata/characters/world) → Batched Chapters → Assembly
  - Adaptive batching based on model capacity (2-8 chapters per batch)
  - Full context in every batch (premise + treatment + foundation + previous summaries)
  - Progress saved after each phase (can inspect partial results)
  - Automatic resume on network drops (saves 25-30% tokens vs retry)
  - Benefits: 4x shorter streams (30-60s vs 3+ min), incremental success, clear progress
- **Self-Contained Chapters Architecture** - chapters.yaml includes everything for prose generation
  - chapters.yaml has 4 sections: metadata, characters, world, chapters
  - Prose generation ONLY uses chapters.yaml (no premise/treatment needed)
  - Unidirectional data flow: premise → treatment → chapters → prose (no sync back)
  - /cull command for cascade deletion (prose, chapters, treatment, premise)
  - Dry-run mode for multi-model competition (validate without saving)
- **Automatic genre detection** - LLM auto-detects genre from concept
- **Interactive taxonomy editor** - Full-screen checkbox UI for taxonomy selection
- **Interactive model selector** - Live-filtering model search with keyboard navigation
- **Taxonomy iteration** - Modify story parameters and regenerate premise
- **Strict model enforcement** - Single user-selected model for ALL operations (no fallbacks)
- **Multi-model competition mode** - Generate with 3 models in parallel, judge picks winner (tournament mode)
  - **NEW**: Competition mode works during iteration (`/iterate chapters` runs tournament)
  - Feedback incorporated into all competing models, judge evaluates results
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
/cull prose       # Delete prose files (or chapters/treatment/premise - cascades downstream)
/multimodel       # Toggle multi-model competition mode (3 generators + 1 judge)
/multimodel config # Configure competition models and judge
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
├── premise_metadata.json  ← Single source of truth (text + taxonomy)
├── treatment.md
└── story.md               ← Single complete story (no chapters/)
```

**vs. Novel Structure:**
```
books/my-novel/
├── premise_metadata.json  ← Single source of truth (text + taxonomy)
├── treatment.md
├── chapters.yaml          ← Full metadata + outlines
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

### Multi-Model Competition
```python
# Enable tournament mode
/multimodel  # Toggle on/off

# Configure models
/multimodel config           # Show current configuration
/multimodel add <model>      # Add competitor
/multimodel remove <model>   # Remove competitor
/multimodel judge <model>    # Set judge model
/multimodel reset            # Reset to defaults

# Generation with competition (when enabled)
/generate treatment
→ Runs 3 models in parallel (grok-4-fast, claude-sonnet-4.5, claude-opus-4.1)
→ Shows all candidates side-by-side
→ Judge model (gemini-2.5-pro) evaluates with criteria
→ Displays scores and reasoning
→ Winner auto-saved, all candidates saved to multimodel/
→ Git commit includes judging results

# Files created:
project/multimodel/
  ├── treatment_20250106_143022_x-ai_grok-4-fast.md
  ├── treatment_20250106_143022_anthropic_claude-sonnet-4-5.md
  ├── treatment_20250106_143022_anthropic_claude-opus-4-1.md
  └── decisions.json  # Full judging history
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
│   ├── premise_metadata.json # LOD3 - Single source of truth (premise text + taxonomy)
│   ├── treatment.md         # LOD2
│   ├── chapters.yaml        # LOD2 - Self-contained (metadata, characters, world, outlines)
│   ├── chapters/            # LOD0 prose
│   │   └── chapter-*.md
│   ├── analysis/            # Analysis results
│   │   ├── commercial.md
│   │   ├── plot.md
│   │   └── ...
│   ├── multimodel/          # Multi-model competition results
│   │   ├── *_candidate_*.md # All candidate outputs
│   │   └── decisions.json   # Judging history
│   └── project.yaml         # Metadata
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
- `src/generation/depth_calculator.py` - **Scene-based depth architecture** with act-aware word count calculation (mathematical, no LLM)
  - All methods use "scene" terminology: `get_base_words_per_scene()`, `get_act_words_per_scene()`, `distribute_scenes_across_chapters()`
  - Constants: WORDS_PER_SCENE (1,100-1,600 w/s), ACT_SCENE_MULTIPLIERS, ACT_WS_MULTIPLIERS
  - Scene clamping: 2-4 scenes per chapter (professional novel structure)
  - +35-37% word targets vs old event-based system
- `src/generation/chapters.py` - Chapter outline generation with structured scene format
  - Generates 9-field scene structures (scene/location/pov_goal/conflict/stakes/outcome/emotional_beat/sensory_focus/target_words)
  - Prompts emphasize "COMPLETE DRAMATIC UNITS (1,000-2,000 words), NOT bullet point summaries"
  - Backward compatible: accepts both 'scenes' (new) and 'key_events' (old)
- `src/generation/prose.py` - Prose generation with 4-part scene structure
  - Scene-by-scene breakdown embedded in prompt
  - 4-part structure: Setup (15-20%) → Development (40-50%) → Climax (15-20%) → Resolution (15-20%)
  - SHOW vs TELL examples (50 words vs 380 words = 7.6x difference)
  - Emphasizes MINIMUM (not average) word counts per scene
- `src/generation/wordcount.py` - Word count assignment with scene-based calculations
  - Uses `scene_count × act_ws` formula (was `event_count × act_we`)
  - Supports both structured scenes and legacy key_events
- `src/generation/multi_model.py` - Multi-model competition coordinator with judging logic
- `src/generation/iteration/` - Natural language feedback processing (coordinator, intent, diff, scale)
- `src/generation/cull.py` - Content deletion manager with cascade (prose → chapters → treatment → premise)
- `src/storage/git_manager.py` - Git operations wrapper
- `src/generation/analysis.py` - Comprehensive story analysis
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