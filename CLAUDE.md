# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Documentation Updates

Update these files when making relevant changes:
- **`docs/IMPLEMENTATION_STATUS.md`** - Feature completion, bugs, test status
- **`docs/USER_GUIDE.md`** - User-facing features and commands
- **`docs/DEVELOPER_GUIDE.md`** - Architecture and implementation details
- **`docs/CHANGELOG.md`** - Version history and releases
- **`README.md`** - Quick start only (keep minimal)

## Git Commits

**Commit changes regularly with descriptive messages.**

- Commit after each meaningful change
- Format: `Type: Short description` (e.g., "Fix: Resolve duplication issue")
- Common types: Fix, Add, Update, Refactor, Docs

## Verification Process

**After completing ANY feature or fix, ALWAYS verify:**

1. **Code Review** - Read all modified files completely
2. **Edge Cases** - Empty inputs, boundaries, error paths, cancellation
3. **Integration** - Compatible with existing systems
4. **Documentation** - Updated all relevant docs
5. **User Experience** - Clear errors, consistent patterns

Even "trivial" changes need verification. Takes 5-10 minutes, prevents hours of debugging.

## Project Overview

AgenticAuthor is a Python CLI for AI-powered book generation using OpenRouter API.

**Core Flow:** premise → treatment → chapters → prose (Level of Detail approach)

**Key Innovation:** Natural language iteration with git-backed version control.

**Architecture Highlights:**
- Quality-first prose generation (no word count pressure)
- Multi-variant chapter generation with LLM judging
- Self-contained chapters.yaml for prose generation
- Short story support (≤2 chapters → single story.md file)
- Shared git repository at books/ level

For detailed feature descriptions, see `docs/CHANGELOG.md` and `docs/DEVELOPER_GUIDE.md`.

## Core Principles

### 1. Natural Language First
Always listening for feedback, no explicit iteration commands needed.

### 2. Single Model Policy
**CRITICAL:** Use the user's selected model for ALL operations. Never fall back or substitute.

```python
if not model:
    raise ValueError("No model selected. Use /model to select.")
```

### 3. Fail Early, No Fallbacks
Never use `or ""` or hardcoded defaults. Get actual data from API.

```python
# BAD
premise = self.project.get_premise() or ""

# GOOD
premise = self.project.get_premise()
if not premise:
    raise Exception("No premise found. Generate with /generate premise")
```

### 4. Context is King
**Always prioritize complete context over token savings.**

- Include full chapters.yaml + all previous prose for generation
- Include all chapters for iteration
- Ask user if uncertain about context inclusion
- Token costs are negligible vs quality (100k tokens ≈ $0.50-1.00)

### 5. UI/UX Inline
- No modal dialogs - everything in terminal flow
- Numbered lists for selection
- Progressive disclosure
- Rich for formatted output

## Key Commands

```bash
# Setup
pip install -e .
export OPENROUTER_API_KEY="sk-or-..."

# Basic workflow
agentic                    # Start REPL
/new my-book              # Create project
/model                    # Select model interactively
/generate premise         # Generate premise
/generate treatment       # Generate treatment
/generate chapters        # Generate chapter variants
/finalize chapters        # Select best variant
/generate prose all       # Generate full prose
```

See `docs/USER_GUIDE.md` for complete command reference.

## Repository Structure

```
AgenticAuthor/
├── CLAUDE.md             # This file
├── docs/                 # All detailed documentation
│   ├── USER_GUIDE.md    # User documentation
│   ├── DEVELOPER_GUIDE.md # Technical details
│   ├── CHANGELOG.md     # Features and versions
│   └── IMPLEMENTATION_STATUS.md # Current status
├── src/                  # Source code
│   ├── generation/      # Core generation logic
│   ├── cli/            # REPL and UI
│   └── prompts/        # Jinja2 templates
└── books/               # Generated projects
    └── .git/           # Shared git repo
```

## Key Implementation Files

- **Generation:** `premise.py`, `treatment.py`, `chapters.py`, `prose.py`
- **Iteration:** `src/generation/iteration/` - Natural language processing
- **Variants:** `variant_manager.py` - Multi-variant generation
- **CLI:** `interactive.py` - Main REPL
- **Prompts:** `src/prompts/` - All LLM prompt templates

For implementation details, see `docs/DEVELOPER_GUIDE.md`.

## Important Notes

- OpenRouter API key must start with 'sk-or-'
- Every operation auto-commits to git
- Logs in `./logs/agentic_YYYYMMDD.log`
- Generation requires: premise → treatment → chapters → prose
- Test suite needs rebuilding for v0.3.0+

## Getting Help

- User guide: `docs/USER_GUIDE.md`
- Developer guide: `docs/DEVELOPER_GUIDE.md`
- Changelog: `docs/CHANGELOG.md`
- Implementation status: `docs/IMPLEMENTATION_STATUS.md`