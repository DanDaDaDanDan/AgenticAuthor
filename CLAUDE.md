# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

AgenticAuthor is a Python CLI for iterative AI-powered book generation using OpenRouter API. It follows a Level of Detail (LOD) approach: premise (LOD3) → treatment/chapters (LOD2) → full prose (LOD0).

**Key Innovation**: Natural language iteration with git-backed version control. Users simply describe what they want changed, and the system handles intent checking, execution, and auto-commits.

## Quick Start Commands

```bash
# Setup
pip install -e .  # Install in development mode

# Run
agentic                  # Start REPL
agentic my-book         # Open specific project
agentic --new fantasy   # Create new project

# Testing
pytest tests/ --reset-fixtures  # Run with clean test book
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
- See `src/storage/git_manager.py` in plan.md

### Analysis System
Based on dv-story-generator's comprehensive analysis:
- Commercial viability (0-100% market ready)
- Plot holes with severity levels
- Character consistency tracking
- Results in `analysis/` directory with git SHA references
- See "Analysis System" section in plan.md

### Test Strategy
- Real book fixture using grok-4-fast (cheap model)
- Git-based test isolation
- See "Test-Driven Development Strategy" in plan.md

## Implementation Approach

1. Start with `plan.md` - it contains the complete implementation blueprint
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
- See `plan.md` for detailed implementations and code examples

## Documentation

- **plan.md** (PRIMARY): Complete implementation blueprint with code examples
- **LOD.md**: Level of Detail system from dv-story-generator
- **overview.md**: Original concept document
- **taxonomies/**: Genre-specific JSON files for story generation