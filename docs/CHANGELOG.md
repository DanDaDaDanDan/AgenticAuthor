# Changelog

All notable changes to AgenticAuthor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Natural Language Iteration System** ⭐ MAJOR FEATURE
  - Process feedback with natural language (no explicit commands needed)
  - Smart intent analysis with confidence scoring
  - Automatic patch vs regenerate detection
  - Unified diff format for precise, reviewable changes
  - Components:
    * `IntentAnalyzer`: Parses natural language to structured JSON
    * `ScaleDetector`: Determines patch (<30% change) vs regenerate (>30%)
    * `DiffGenerator`: Creates and applies unified diffs
    * `IterationCoordinator`: Orchestrates the full iteration flow
  - Auto-commit with descriptive messages
  - Confidence-based routing (>0.8 execute, <0.8 clarify)
  - Full documentation in `docs/ITERATION.md`
  - Examples:
    * "Add more dialogue to chapter 3" → Generates patch
    * "Rewrite premise to be darker" → Full regeneration
- **Inline Project Selection**
  - `/open` command now shows numbered list for selection (no modal)
  - Displays project metadata (genre, word count, last updated)
  - Type number to select, Enter to cancel
  - Can still provide project name directly as argument
  - Follows Claude Code UI patterns - everything inline
- **Development `/reload` Command**
  - Reloads Python modules without restarting the app
  - Useful for testing changes during development
  - Note: Some changes still require full restart

### Improved
- **LLM Streaming Display**
  - Added enhanced streaming display with live status updates
  - Shows: model name, elapsed time, token count, tokens/sec
  - Cleaner inline display without distracting elements
  - Compact token usage after completion: `1,234 + 567 = 1,801 tokens | $0.0234`

### Fixed
- **Mouse Scrolling During Generation**
  - Fixed issue where scrolling with mouse during streaming would corrupt the display
  - Added new `console.status()` display mode that keeps status bar fixed at bottom
  - Content now streams to scrollable area without cursor positioning conflicts
  - Configurable via `streaming_display_mode` setting (status/live/simple)
- **Cost Calculation**
  - Fixed pricing calculation (was multiplying by 1,000,000 instead of 1,000)
  - Now correctly shows cost per 1k tokens
- **Tab Completion**
  - Tab now immediately completes when there's only one match instead of showing a menu
  - Changed `complete_while_typing` to `False` so completions only show on Tab press
  - Example: `/op` + Tab → immediately completes to `/open` (no menu needed)
- **Async Error in `/open` Command**
  - Fixed "asyncio.run() cannot be called from a running event loop" error
  - Changed back to sync with inline selection (no modal)

## [0.2.0] - 2025-09-23

### Added
- **Enhanced Premise Generation**
  - Genre-specific taxonomy support for 11 genres (fantasy, sci-fi, romance, mystery, horror, etc.)
  - Smart input detection (brief premise vs standard vs detailed vs treatment)
  - History tracking to avoid repetitive generations
  - Interactive genre selection with fallback prompts
  - Automatic genre normalization and alias support
  - Preservation of existing treatments (200+ words)
- **Advanced Command Completion**
  - Tab completion for all slash commands
  - Genre autocomplete for `/generate premise` command
  - Model fuzzy search and tab completion
  - Context-aware completion suggestions
- **Comprehensive Logging System**
  - Debug logging to `./logs/agentic_YYYYMMDD.log`
  - `/logs` command to view recent log entries
  - Automatic daily log rotation
  - Full error tracking and debugging support
- **Taxonomy System** (`src/generation/taxonomies.py`)
  - TaxonomyLoader for managing genre-specific parameters
  - PremiseAnalyzer for input type detection
  - PremiseHistory for tracking generations
  - Support for base + genre-specific taxonomy merging
- **Test Suite Expansion**
  - 187 total tests (171 unit, 16 integration)
  - Real API integration tests with grok-4-fast model
  - 100% coverage attempt for core modules
  - Tests for all new features

### Changed
- PremiseGenerator now supports multiple generation modes based on input length
- Model parameter follows fallback chain: specified → project → settings
- Enhanced `/generate premise` command with genre and concept parsing
- Improved error messages and user feedback

### Fixed
- Model attribute error in PremiseGenerator instantiation
- Tab completion not triggering on Tab key press
- Mouse selection issues in terminal (added shift+drag support note)
- CompleteStyle import error from prompt_toolkit
- API key validation expecting boolean instead of exceptions
- TokenUsageTracker import error (removed non-existent class)

## [0.1.0] - 2025-09-23

### Added
- Core infrastructure and project setup
- OpenRouter API client with streaming support
- Interactive REPL with prompt_toolkit
- Slash command system with auto-completion
- Project and story data models
- Git integration for version control
- Configuration management with .env support
- Model discovery and selection
- Basic test suite with pytest
- Comprehensive documentation structure

### Changed
- Commands now use `/` prefix (e.g., `/help` instead of `help`)
- Natural language input (without `/`) reserved for iteration

### Fixed
- InteractiveSession initialization order bug
- DateTime deprecation warnings (using timezone-aware UTC)
- Taxonomy serialization issues
- Test console compatibility issues

### Security
- API key validation (must start with 'sk-or-')
- .env file excluded from git
- No credentials in logs

## Planned for Next Release (0.3.0)

### To Add
- [ ] Complete generation system (treatment, chapters, prose)
- [ ] Natural language iteration with intent checking
- [ ] Story analysis system (commercial, plot, characters, world)
- [ ] Export functionality (md, html, epub, pdf)
- [ ] Git branching and merging for experiments

### To Improve
- [ ] Test coverage to 100% for all modules
- [ ] Performance optimization for large projects
- [ ] Better error recovery and user guidance
- [ ] Multi-model comparison for generations

## Version History

- **0.2.0** (2025-09-23): Enhanced premise generation with taxonomies, logging, and testing
- **0.1.0** (2025-09-23): Initial release with core infrastructure
- **Target 1.0.0**: Q1 2025 - Full feature release with complete generation pipeline

## Current Implementation Status

## ✅ Recently Completed (v0.2.0)

### Taxonomy System
- [x] Genre-specific taxonomy loading
- [x] Base + genre taxonomy merging
- [x] Category options extraction
- [x] 11 genre support (fantasy, sci-fi, romance, mystery, horror, etc.)

### Enhanced Premise Generation
- [x] Smart input detection (brief vs standard vs detailed vs treatment)
- [x] Treatment preservation (200+ words)
- [x] History tracking to avoid repetition
- [x] Interactive genre selection
- [x] Genre normalization and aliases
- [x] Taxonomy extraction from existing treatments

### Advanced Command Completion
- [x] Genre autocomplete for `/generate premise`
- [x] Context-aware completion
- [x] Tab key handler improvements

### Logging System
- [x] Comprehensive debug logging
- [x] Daily log rotation
- [x] `/logs` command implementation
- [x] Log file location: `./logs/`

### Generation System
- [x] Premise generation with multiple modes
- [x] Treatment generation
- [x] Chapter outline generation
- [x] Prose generation
- [x] Jinja2 templates integrated

## ✅ Recently Completed (Unreleased)

### Iteration System
- [x] Natural language intent checking
- [x] Confidence-based routing
- [x] Feedback processing (patch and regenerate)
- [x] Content modification via unified diffs
- [x] Auto-commit with descriptive messages
- [x] Scale detection (patch vs regenerate)
- [x] IntentAnalyzer, ScaleDetector, DiffGenerator, IterationCoordinator
- [x] Integration with interactive REPL

## 🚧 In Progress

### Analysis System
- [ ] Commercial viability analysis
- [ ] Plot hole detection
- [ ] Character consistency checking
- [ ] World-building analysis
- [ ] Element tracking

## 📋 Not Started

### Export System
- [ ] Markdown compilation
- [ ] HTML export
- [ ] EPUB generation
- [ ] PDF export
- [ ] Custom formats

### Advanced Features
- [ ] Multi-model collaboration
- [ ] Batch generation
- [ ] Style transfer
- [ ] Chapter dependencies
- [ ] Character sheets
- [ ] World-building wiki

### CLI Commands (Not Implemented)
- [ ] `/generate` - Needs generation system
- [ ] `/iterate` - Needs iteration system
- [ ] `/analyze` - Needs analysis system
- [ ] `/export` - Needs export system
- [ ] `/git` - Partially working

## 🐛 Known Issues

1. **Mouse Selection**: Hold Shift while dragging in Windows Terminal
2. **Tab Completion**: Press Tab twice for suggestions in some terminals
3. **Token Counting**: Not implemented for all models
4. **Coverage Measurement**: Module paths not always recognized by pytest-cov

## 📈 Test Coverage

Current Coverage: **~85%** (estimated)

- Config: 97% ✅
- Models: 94% ✅
- Taxonomies: 100% ✅
- Premise Generator: 95% ✅
- Command Completer: 98% ✅
- Logging: 100% ✅
- Interactive: 75% ✅
- API Client: 80% ✅
- Integration Tests: 16 tests with real API ✅

## Recent Changes

### 2025-09-23 (v0.2.0)
- **MAJOR**: Enhanced premise generation with genre taxonomies
