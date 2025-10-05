# Changelog

All notable changes to AgenticAuthor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-10-05

### Added ⭐ MAJOR RELEASE
- **Interactive Model Selector** 🎯
  - Full-screen model selection with live fuzzy search
  - Type to filter models instantly - no menus needed
  - Shows pricing ($X/1M tokens) and provider for each model
  - Current model marked with "← current" indicator
  - Keyboard navigation: ↑↓ to navigate, ENTER to select, ESC to cancel
  - Displays up to 15 models at once with relevance scoring
  - Access with `/model` (no arguments)
  - Replaces old numbered list selection
- **Interactive Taxonomy Editor** 🎯
  - Full-screen checkbox interface for precise taxonomy control
  - All taxonomy categories in navigable tabs (pacing, themes, POV, etc.)
  - Multi-select checkboxes with visual indication (✓)
  - Keyboard controls:
    * ↑↓ - Navigate options in current category
    * Space - Toggle selected option
    * Tab/Shift+Tab - Switch between categories
    * Enter - Save changes
    * Esc - Cancel
  - Access with `/iterate taxonomy` (no feedback text)
  - Works alongside natural language taxonomy iteration
- **Automatic Genre Detection** 🤖
  - LLM auto-detects genre from story concept
  - No manual genre selection needed for `/generate premise`
  - High accuracy with confidence scoring
  - Temperature 0.3 for consistent detection
  - Example: "a detective story" → auto-detects "mystery-thriller"
  - Example: "magical library" → auto-detects "fantasy"
- **Taxonomy Iteration System** 🔄
  - Modify story parameters and regenerate premise
  - Two modes:
    1. **Natural language**: Describe changes in plain English
       - Example: `make it standalone and change pacing to fast`
       - LLM analyzes feedback and updates selections
       - Optionally regenerates premise if changes are significant
    2. **Interactive editor**: Checkbox UI for precise control
       - Visual selection of all taxonomy options
       - Real-time preview of selections
  - Returns structured response with reasoning
  - Auto-commits changes with descriptive messages
- **Strict Model Enforcement** 🔒
  - Single user-selected model for ALL LLM operations
  - No hardcoded model names in generation code
  - No fallback models - raises clear error if model not selected
  - Ensures consistent cost and quality across all operations
  - Applies to: premise, treatment, chapters, prose, intent analysis, diff generation, scale detection
  - Error message: "No model selected. Use /model <model-name> to select a model."

### Added (Earlier Features)
- **Comprehensive Story Analysis System** ⭐ MAJOR FEATURE
  - Multi-dimensional analysis across 8 critical axes
  - `/analyze` command with multiple targets (premise, treatment, chapters, prose)
  - Analysis dimensions:
    * Plot & Structure: plot holes, pacing, cause/effect, foreshadowing
    * Character Consistency: voice, motivation, arcs, relationships
    * World-Building: logic, geography, timeline, systems
    * Dialogue Quality: naturalism, subtext, character voice
    * Prose & Style: clarity, repetition, active voice, clichés
    * Thematic Coherence: theme clarity, symbols, integration
    * Narrative Technique: POV, tense, distance, hooks
    * Commercial Viability: market fit, hook strength, target audience
  - Structured markdown reports saved to `analysis/` directory
  - Executive summary with overall grade (A-F) and scores
  - Issue severity classification (CRITICAL/HIGH/MEDIUM/LOW)
  - Specific location references for all issues
  - Concrete fix suggestions for each problem
  - Positive highlights alongside issues
  - Git SHA tracking for reproducibility
  - Uses Claude 3.5 Sonnet for quality analysis
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

## Planned for Next Release (0.4.0)

### To Add
- [ ] Export functionality (md, html, epub, pdf)
- [ ] Git branching and merging for experiments
- [ ] Multi-model comparison for generations
- [ ] Character sheets and tracking
- [ ] World-building wiki

### To Improve
- [ ] Test coverage to 100% for all modules
- [ ] Performance optimization for large projects
- [ ] Better error recovery and user guidance
- [ ] Batch generation for multiple chapters

## Version History

- **0.3.0** (2025-10-05): Interactive editors, auto genre detection, taxonomy iteration, strict model enforcement
- **0.2.0** (2025-09-23): Enhanced premise generation with taxonomies, logging, and testing
- **0.1.0** (2025-09-23): Initial release with core infrastructure
- **Target 1.0.0**: Q1 2025 - Full feature release with complete generation pipeline

## Current Implementation Status

## ✅ Recently Completed (v0.3.0)

### Interactive Editors
- [x] Model selector with live fuzzy search
- [x] Taxonomy editor with checkbox interface
- [x] Full-screen UI using prompt_toolkit
- [x] Keyboard navigation (↑↓, SPACE, TAB, ENTER, ESC)
- [x] Real-time filtering and visual feedback

### Automatic Genre Detection
- [x] LLM-based genre detection from concepts
- [x] Confidence scoring and validation
- [x] Integration with premise generation
- [x] Support for all 11 genres

### Taxonomy Iteration
- [x] Natural language taxonomy modification
- [x] Interactive checkbox editor fallback
- [x] Premise regeneration based on taxonomy changes
- [x] Structured response with reasoning

### Model Enforcement
- [x] Removed all hardcoded models from generators
- [x] Removed all fallback model logic
- [x] Required model parameter in all generators
- [x] Clear error messages when model not selected
- [x] Applied to all LLM operations (premise, treatment, chapters, prose, iteration)

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

### Analysis System
- [x] Plot & Structure analysis (plot holes, pacing, foreshadowing)
- [x] Character Consistency analysis (voice, motivation, arcs)
- [x] World-Building Coherence analysis (logic, geography, systems)
- [x] Dialogue Quality analysis (naturalism, subtext, voice)
- [x] Prose & Style analysis (clarity, repetition, clichés)
- [x] Thematic Coherence analysis (theme clarity, symbols)
- [x] Narrative Technique analysis (POV, tense, hooks)
- [x] Commercial Viability analysis (market fit, target audience)
- [x] AnalysisCoordinator orchestrating all analyzers
- [x] Markdown report generation with git SHA tracking
- [x] `/analyze` command integration with interactive REPL
- [x] Rich CLI display with scores, issues, and highlights

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

### 2025-10-05 (v0.3.0)
- **MAJOR**: Interactive editors for model selection and taxonomy editing
- **MAJOR**: Automatic genre detection from story concepts
- **MAJOR**: Taxonomy iteration with natural language and interactive UI
- **MAJOR**: Strict model enforcement across all operations (no fallbacks)
- Added `src/cli/model_selector.py` - Live fuzzy search model selector
- Added `src/cli/taxonomy_editor.py` - Full-screen checkbox taxonomy editor
- Enhanced `src/generation/premise.py` with `detect_genre()`, `iterate_taxonomy()`, `regenerate_with_taxonomy()`
- Fixed model enforcement in all generators (premise, treatment, chapters, prose, iteration)
- Updated `/model` command to launch interactive selector when no args provided
- Updated `/iterate taxonomy` to support both natural language and interactive editing

### 2025-09-23 (v0.2.0)
- **MAJOR**: Enhanced premise generation with genre taxonomies
