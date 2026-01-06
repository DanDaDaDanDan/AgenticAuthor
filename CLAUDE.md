# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Documentation Updates

When making relevant changes, keep these up to date:
- **`COMPREHENSIVE_ARCHITECTURE.md`** – Complete, self-contained architecture guide with full file hierarchy, design philosophies, and workflows (1800+ lines, 18 comprehensive sections)
- **`ARCHITECTURE.md`** – Concise high-level architecture overview with key design decisions
- **`AGENTS.md`** – Repository guidelines (structure, commands, style, testing, PR rules)

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

For a comprehensive deep-dive, see `COMPREHENSIVE_ARCHITECTURE.md` (1800+ lines, complete guide). For a concise overview, see `ARCHITECTURE.md`.

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
/generate prose all       # Generate full prose (uses style card by default)

# Iteration workflow (v0.4.0)
/iterate prose            # Set iteration target
make it darker            # Natural language feedback (no / prefix)
                          # System validates with judge, shows semantic diff, commits

# Style cards (prose generation)
# Style cards are used BY DEFAULT - stored in books/project/misc/prose-style-card.md
/generate prose           # Uses style card automatically
/generate prose --no-style-card  # Skip style card if needed
```

Use `/help` in the REPL and tab-completion for command hints.

## Repository Structure

```
AgenticAuthor/
├── CLAUDE.md                        # This file
├── COMPREHENSIVE_ARCHITECTURE.md    # Complete architecture guide (1800+ lines)
├── ARCHITECTURE.md                  # Concise architecture overview
├── AGENTS.md                        # Repository guidelines
├── src/                             # Source code
│   ├── generation/                  # Core generation logic
│   │   └── iteration/               # Natural language iteration (v0.4.0)
│   ├── cli/                         # REPL and UI
│   └── prompts/                     # Jinja2 templates
└── books/                           # Generated projects
    └── .git/                        # Shared git repo
```

## Key Implementation Files

- **Generation:** `premise.py`, `treatment.py`, `chapters.py`, `prose.py`
- **Iteration:** `src/generation/iteration/` - Natural language processing
- **Variants:** `variant_manager.py` - Multi-variant generation
- **CLI:** `interactive.py` - Main REPL
- **Prompts:** `src/prompts/` - All LLM prompt templates

For comprehensive implementation details, see `COMPREHENSIVE_ARCHITECTURE.md`. For a quick overview, see `ARCHITECTURE.md`.

## Important Notes

- OpenRouter API key must start with 'sk-or-'
- Every operation auto-commits to git
- Centralized .agentic folder at project root (NOT in books/)
  - Logs: `.agentic/logs/agentic_YYYYMMDD.log`
  - Debug files: `.agentic/debug/project-name/`
  - History: `.agentic/history`
- Generation requires: premise → treatment → chapters → prose
- Test suite needs rebuilding for v0.3.0+

**Iteration System (v0.4.0):**
- ✅ Implementation complete (4 files, 1119 lines, 6 prompt templates)
- ⚠️ Ready for testing on cloned projects ONLY (use `/clone`)
- Features: Judge validation, semantic diffs, git tracking, debug storage
- See `ARCHITECTURE.md` section 10 (Natural Language Iteration) for workflow details

## Getting Help

- **Comprehensive Guide:** `COMPREHENSIVE_ARCHITECTURE.md` - Complete architecture with 18 sections covering all system details
- **Quick Overview:** `ARCHITECTURE.md` - Concise high-level design and ADRs
- **REPL Help:** Use `/help` in the REPL for command reference
- **Code Comments:** Inline documentation in source files
