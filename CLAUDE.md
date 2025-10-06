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

## Project Summary

AgenticAuthor is a Python CLI for iterative AI-powered book generation using OpenRouter API. It follows a Level of Detail (LOD) approach: premise (LOD3) → treatment/chapters (LOD2) → full prose (LOD0).

**Key Innovation**: Natural language iteration with git-backed version control. Users simply describe what they want changed, and the system handles intent checking, execution, and auto-commits.

**New Features (v0.3.0)**:
- **Automatic genre detection** - LLM auto-detects genre from concept
- **Interactive taxonomy editor** - Full-screen checkbox UI for taxonomy selection
- **Interactive model selector** - Live-filtering model search with keyboard navigation
- **Taxonomy iteration** - Modify story parameters and regenerate premise
- **Strict model enforcement** - Single user-selected model for ALL operations (no fallbacks)

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
/status           # Check project status
/models           # List available models
/model            # Interactive model selector (live filtering)
/model grok       # Or use fuzzy search directly
/generate premise "a magical library"  # Auto-detects genre (fantasy)
/generate premises 5 fantasy "a magical library"  # Generate 5 options to choose from
/iterate taxonomy # Interactive taxonomy editor
/logs             # View recent log entries
/help             # Show all commands
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
2. **Git Everything**: Every book is a git repo, every change is a commit
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
books/[project-name]/
├── .git/                    # Version control
├── premise.md              # LOD3
├── premise_metadata.json   # Taxonomy selections
├── treatment.md            # LOD2
├── chapters.yaml           # LOD2 outlines
├── chapters/               # LOD0 prose
│   └── chapter-*.md
├── analysis/               # Analysis results
│   ├── commercial.md
│   ├── plot.md
│   └── ...
└── project.yaml            # Metadata
```

## Key Implementation Files

- `src/generation/taxonomies.py` - Genre taxonomy system and premise analysis
- `src/generation/premise.py` - Premise generation with auto-detection, taxonomy iteration
- `src/generation/iteration/` - Natural language feedback processing (coordinator, intent, diff, scale)
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