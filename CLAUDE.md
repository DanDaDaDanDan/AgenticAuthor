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

2. **`docs/API_REFERENCE.md`** - Update when:
   - Adding new slash commands
   - Adding new Python APIs
   - Changing command syntax or behavior
   - Adding configuration options

3. **`docs/ARCHITECTURE.md`** - Update when:
   - Changing system design
   - Adding new components
   - Modifying data flow
   - Making architectural decisions

4. **`docs/DEVELOPMENT.md`** - Update when:
   - Changing development setup
   - Adding new development workflows
   - Updating testing approaches

5. **`docs/PROJECT_README.md`** - Update when:
   - Adding user-facing features
   - Changing installation process
   - Updating command examples

**Always check these files at the end of your work session and update them!**

## Project Summary

AgenticAuthor is a Python CLI for iterative AI-powered book generation using OpenRouter API. It follows a Level of Detail (LOD) approach: premise (LOD3) → treatment/chapters (LOD2) → full prose (LOD0).

**Key Innovation**: Natural language iteration with git-backed version control. Users simply describe what they want changed, and the system handles intent checking, execution, and auto-commits.

## Quick Start Commands

```bash
# Setup
pip install -e .  # Install in development mode

# Run
agentic           # Start REPL (main interface)

# In REPL - all commands use / prefix:
/new my-book      # Create new project
/open my-book     # Open existing project
/status           # Check project status
/models           # List available models
/help             # Show all commands
```

## Testing After Changes

Always test these commands after making changes:
```bash
# Unit tests
pytest tests/unit/ -v

# Check the REPL starts
agentic
# Then in REPL:
/help             # Should show all commands
/models           # Should list OpenRouter models (needs API key)
/new test-book    # Should create a project
/status           # Should show project info
/exit             # Should exit cleanly
```

## Core Architecture Principles

1. **Natural Language First**: Always listening for feedback, no explicit commands needed
2. **Git Everything**: Every book is a git repo, every change is a commit
3. **Single Active Model**: One model at a time for all operations (switchable)
4. **File-Based Storage**: Human-readable markdown/YAML files
5. **Smart Intent Checking**: Confidence-based routing (>0.8 execute, else clarify)

## Key Systems to Understand

### Iteration Flow
```python
User: "Add more dialogue to chapter 3"
→ Intent check (single LLM call with JSON response)
→ High confidence: Execute + auto-commit "Iterate chapter 3: add dialogue"
→ Low confidence: Ask clarification
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

- `src/generation/iteration.py` - Natural language feedback processing
- `src/storage/git_manager.py` - Git operations wrapper
- `src/generation/analysis.py` - Comprehensive story analysis
- `src/cli/interactive.py` - REPL with prompt_toolkit

## Important Notes

- OpenRouter API key must start with 'sk-or-'
- Every operation creates a git commit automatically
- Analysis files include git SHA for reproducibility
- Use structured JSON for intent checking responses

## Repository Structure

```
AgenticAuthor/
├── CLAUDE.md               # AI assistant instructions (this file)
├── .env                    # API keys (git-ignored)
├── pyproject.toml          # Python package config
├── src/                    # Source code
├── tests/                  # Test suite
├── docs/                   # All documentation
│   ├── README.md          # Documentation index
│   ├── PROJECT_README.md  # Main project README
│   ├── ARCHITECTURE.md    # System design
│   ├── API_REFERENCE.md   # Command/API reference
│   ├── DEVELOPMENT.md     # Dev guidelines
│   ├── IMPLEMENTATION_GUIDE.md  # Code patterns
│   ├── IMPLEMENTATION_STATUS.md # Progress tracking
│   ├── CHANGELOG.md       # Version history
│   ├── LOD.md             # Level of Detail system
│   └── taxonomies/        # Genre taxonomy files
└── books/                  # Generated book projects
```