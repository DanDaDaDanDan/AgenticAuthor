# Changelog

All notable changes to AgenticAuthor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **Dead Code and Unused Scripts** 🧹 (**Phase 1**)
  - Removed unused methods from `src/utils/tokens.py`:
    - `split_text_for_context()` - Text chunking for context limits, never used
    - `estimate_json_tokens()` - JSON token estimation, never imported
  - Removed obsolete utility scripts from root directory:
    - `analyze_logs.py` - Log debugging helper, never integrated
    - `init_shared_git.py` - Redundant (git init is automatic in interactive.py)
    - `verify_prose_iteration.py` - One-time verification script, no longer needed
  - Removed `src/utils/import_converter.py`:
    - Converter for old story-export JSON format
    - Only referenced in CHANGELOG, never imported by main code
  - Removed `scripts/update_chapters_for_scenes.py`:
    - One-time migration script with hardcoded path
    - No longer needed after scene system migration
  - Empty `scripts/` directory remains for future utility scripts
  - **Impact**: Cleaner codebase, no functional changes (~862 lines removed)

- **Dead Code from Core Modules** 🧹 (**Phase 2**)
  - **`src/cli/interactive.py`** - Removed unused components:
    - Imports: `re`, `importlib`, `sys`, `rprint` (never used in code)
    - `Story` import from models (write-only variable)
    - `self.story` variable and all assignments (lines 235-239, 889, 1003) - never read
    - `reload_modules()` method (45 lines) - defined but not registered in commands dict
    - **Total**: ~55 lines removed
  - **`src/generation/chapters.py`** - Removed legacy batched generation methods:
    - `_find_last_complete_chapter()` method (94 lines) - old truncation recovery
    - `_fix_truncated_yaml()` method (36 lines) - YAML repair for truncation
    - Jinja2 Template import (unused)
    - `DEFAULT_CHAPTERS_TEMPLATE` constant (deprecated)
    - **Reason**: Sequential generation has built-in resume via generate() loop
    - **Total**: ~132 lines removed
  - **`src/api/streaming.py`** - Removed legacy streaming methods:
    - Rich progress imports: `Progress`, `SpinnerColumn`, `TextColumn` (only used by dead methods)
    - `handle_sse_stream()` old version (90 lines) - basic streaming
    - `stream_with_progress()` method (41 lines) - wrapper around old method
    - `collect_stream()` method (12 lines) - simple wrapper
    - **Reason**: Replaced by `handle_sse_stream_with_status()` and `handle_json_stream_with_display()`
    - **Total**: ~144 lines removed
  - **Verification Process**:
    - Used Task agent to analyze large files (interactive.py, chapters.py, streaming.py)
    - Classified findings: HIGH confidence (13 items) → removed, MEDIUM (4 items) → kept, LOW → kept
    - Grep verification for each item before removal
    - Confirmed no external calls to removed methods
  - **Overall Impact**: ~331 lines of dead code removed, codebase maintainability improved
  - **No Functional Changes**: All removed code was unreachable or unused

### Added

- **Sequential Chapter Generation Architecture** 🔄 **[MAJOR REFACTORING]** (commit 5d52156)
  - **Problem**: Batched generation caused 95% information loss between batches (only 3/60 fields passed via summaries)
  - **Result**: Duplicate chapters (Ch 6/10, Ch 7/11) covering same events
  - **Root Cause**: `_summarize_chapters()` passed only number/title/summary between batches
  - **Solution**: Complete rewrite from batched to sequential generation with full context accumulation

  **Architecture Changes**:
  - **Old Format**: Single `chapters.yaml` with all chapters + batched generation
  - **New Format**: Individual files in `chapter-beats/` directory:
    - `foundation.yaml` (metadata + characters + world) - generated once
    - `chapter-01.yaml` through `chapter-NN.yaml` - generated sequentially
  - **Context Flow**:
    - Chapter 1: sees foundation only
    - Chapter 2: sees foundation + FULL chapter 1 (100% detail)
    - Chapter N: sees foundation + FULL chapters 1 through N-1
    - **Zero information loss** (was 95% loss with summaries)

  **Code Changes**:
  - Project Model (`src/models/project.py`):
    - Added `chapter_beats_dir` property
    - Added `get_foundation()` / `save_foundation()`
    - Added `get_chapter_beat()` / `save_chapter_beat()` / `list_chapter_beats()`
    - Updated `get_chapters()` / `get_chapters_yaml()` for backward compatibility
  - Chapter Generator (`src/generation/chapters.py`):
    - Added `_generate_single_chapter()` (~200 lines) - generates one chapter with full context
    - Rewrote `generate()` main loop (~500 lines) - sequential generation with resume checks
    - Removed obsolete methods (~690 lines):
      - `_calculate_batch_size()` (no batching)
      - `_generate_chapter_batch()` (replaced by sequential calls)
      - `_resume_generation()` (built-in resume via file checking)
      - `_merge_yaml()` (individual files don't need merging)

  **User-Facing Features**:
  - **Resume Capability**: Before generation, checks for existing `chapter-beats/`
    ```
    ⚠️  Found 5 existing chapters

    What would you like to do?
      1. Continue from chapter 6 (resume)
      2. Regenerate all chapters from scratch
      3. Abort generation

    > Choice 1: Loads foundation + existing chapters, continues from chapter 6
    > Choice 2: Deletes chapters, keeps foundation, regenerates all chapters
    >           (Note: Foundation is kept - it represents stable story structure)
    >           (Use /iterate to change story structure/foundation)
    > Choice 3: Aborts generation
    ```
  - **Progress Display**:
    ```
    [1/3] Loading existing foundation...
    ✓ Foundation loaded

    [2/3] Generating chapters sequentially...
    Generating chapter 6/20...
    ✓ Chapter 6/20 complete
    ```
  - **Error Recovery**: Clear failure point, completed chapters saved, can resume
  - **Foundation Intelligence**: On resume, uses foundation's stored metadata (word count, chapter count) instead of recalculating

  **Benefits**:
  - ✅ Eliminates duplicate scenes/events (root cause fixed)
  - ✅ Each chapter sees 100% of previous detail, not 5% summaries
  - ✅ User-controlled resume (choose continue/regenerate/abort)
  - ✅ Incremental saves (inspect partial results anytime)
  - ✅ Foundation loaded on resume (not regenerated, saves ~2,000 tokens + 30-45s)
  - ✅ Foundation metadata reused on resume (ensures consistency with existing chapters)
  - ✅ Better error recovery (resume from exact chapter number)
  - ✅ Foundation preserved on regenerate (stable story structure)

  **Backward Compatibility**:
  - Old format (`chapters.yaml`) still supported for reading
  - `get_chapters_yaml()` aggregates new format transparently
  - Prose generation and analysis work unchanged
  - No migration needed for existing projects

- **Treatment Analysis for Initial Generation** 📖 (commit bd1c585)
  - **Problem**: All novels of same genre got identical word counts (e.g., all sci-fi → 92K) regardless of actual story complexity
  - **Solution**: LLM analyzes treatment to determine organic word count for first-time generation
  - **Analysis Factors**:
    1. Story complexity (plot threads)
    2. Character count (number with significant arcs)
    3. World-building needs (alternate history, magic systems, etc.)
    4. Subplot density
    5. Natural pacing (fast-paced action vs deliberate literary)
    6. Timeline span (days vs months/years)
  - **Constraints**: Still respects form ranges (e.g., novel: 50k-120k)
  - **Display**: Shows "📊 Treatment Analysis Results" with LLM's chosen word count
  - **Example**: Tight thriller might get 60K words instead of genre default 92K
  - **Files Modified**: `src/generation/chapters.py`
  - **Note**: Only affects initial generation (not iteration)

- **Simplified /analyze Command** 🎯 (commit 86be6ea)
  - **Problem**: Over-engineered prompt with 8 rigid dimensions, 12 instructions, forced categorization limited LLM's ability to provide organic feedback
  - **Solution**: Drastically simplified prompt for free-form, authentic feedback
  - **Before**:
    - 130+ lines of prescriptive instructions
    - 8 forced dimensions (plot, character, worldbuilding, dialogue, prose, theme, narrative, commercial)
    - Complex JSON: priority_fixes, path_to_a_plus, dimension_scores, confidence percentages, severity levels
    - Progress: "⏳ Plot... ⏳ Character... ⏳ Worldbuilding... ⏳ Theme..."
  - **After**:
    - ~25 lines: "Rate the quality and provide constructive criticism"
    - Simple JSON: `grade`, `grade_justification`, `overall_assessment`, `feedback[]`, `strengths[]`, `next_steps`
    - Progress: "⏳ Reading and evaluating..."
  - **Display Format**:
    ```
    📊 Analysis: Chapters

    Grade: B+ (Very Good)
    Strong plotting but pacing issues in Act II

    📝 Feedback:
      • Act II drags - consolidate chapters 9-11
      • Protagonist motivation unclear in chapter 5

    ✓ Strengths:
      • Excellent world-building
      • Strong character voice

    🎯 Next Steps:
      Consolidate middle chapters to tighten pacing
    ```
  - **Benefits**:
    - LLM identifies what actually matters (not forced into categories)
    - More authentic, honest feedback
    - Faster, cheaper analysis (shorter prompt)
    - "Next steps" more actionable than complex recommendations
  - **Files Modified**: `src/generation/analysis/unified_analyzer.py`, `src/cli/interactive.py`

### Changed
- **Scene-Based Word Count System** 🎬 **[MAJOR REFACTORING]**
  - **Problem**: Current system achieves only 50-60% of target word counts (e.g., 2,300/3,800 words)
  - **Root Cause**: LLMs treat "key_events" as bullet point summaries (200-500 words) instead of full dramatic scenes (1,200-2,000 words)
  - **Solution**: Complete refactoring from event-based to scene-based architecture

  **Mathematical Changes (depth_calculator.py)**:
  - All constants renamed: `WORDS_PER_EVENT` → `WORDS_PER_SCENE`
  - Word targets increased +35-37%:
    - Novel moderate: 950 w/e → 1,300 w/s (+37%)
    - Novel fast: 800 w/e → 1,100 w/s (+37%)
    - Novel slow: 1,200 w/e → 1,600 w/s (+33%)
  - Scene clamping: 2-4 scenes per chapter (not 6-10 events)
  - All methods renamed: `get_base_words_per_scene()`, `get_act_words_per_scene()`, etc.
  - Impact: 92K novel → 71 scenes ÷ 23 chapters = 3.1 scenes/chapter (was 4.2 events/chapter)

  **Chapter Generation (chapters.py)**:
  - Three major prompts updated with structured scene format:
  - New 9-field scene structure in YAML:
    ```yaml
    scenes:
      - scene: "Scene Title"
        location: "Where it happens"
        pov_goal: "What character wants"
        conflict: "What prevents it"
        stakes: "What's at risk"
        outcome: "How it resolves"
        emotional_beat: "Internal change"
        sensory_focus: ["Detail 1", "Detail 2"]
        target_words: 1300  # Act-specific
    ```
  - Prompts emphasize: "COMPLETE DRAMATIC UNITS (1,000-2,000 words), NOT bullet point summaries"
  - Validation accepts both 'scenes' (new) and 'key_events' (old) for backward compatibility

  **Prose Generation (prose.py)** - MOST CRITICAL CHANGES:
  - Complete prompt rewrite with scene-by-scene breakdown
  - 4-part scene structure: Setup (15-20%) → Development (40-50%) → Climax (15-20%) → Resolution (15-20%)
  - Changed from "AVERAGE" to "MINIMUM" word counts (repeated emphasis)
  - Added SHOW vs TELL example:
    - ❌ TELLING: "Sarah was angry... She confronted him..." (50 words - rushed summary)
    - ✅ SHOWING: Full dialogue scene with action/emotion (380 words - full scene) = 7.6x difference
  - Multiple critical reminders:
    - "COMPLETE DRAMATIC UNIT" (not summary)
    - "Do NOT summarize or rush"
    - "Let moments breathe"
    - "SHOW character emotions through action, dialogue, physical reactions"
    - "Include sensory details in EVERY scene"
  - If using structured scenes, embeds full scene details in prompt before generation

  **Supporting Systems**:
  - wordcount.py: Updated for scene terminology, supports both formats
  - All old method references removed from codebase
  - Backward compatibility maintained throughout

  **Expected Impact**:
  - Word count achievement: 50-60% → 80-100% (+30-40 percentage points)
  - Example chapter: 2,300 words → 3,040-3,800 words (+32-65%)
  - Quality: 3/5 (micro-scenes) → 4/5 (full dramatic units)

  **Files Modified**:
  - `src/generation/depth_calculator.py` (commit 325c75d)
  - `src/generation/chapters.py` (commit b239512)
  - `src/generation/prose.py` (commit 51cff67)
  - `src/generation/wordcount.py` (commit e050fe8)

  **Documentation**:
  - `docs/wordcount-rethink-2025.md` - 31K word comprehensive analysis
  - `docs/wordcount-implementation-todo.md` - 18K word implementation plan
  - `docs/wordcount-implementation-status.md` - Live progress tracking
  - `docs/IMPLEMENTATION_SUMMARY.md` - Complete overview with testing results
  - `docs/SCENE_SYSTEM_TEST_RESULTS.md` - Baseline testing and validation

  **Testing & Validation** (same day as implementation):
  - Tested on steampunk-moon project (11 chapters, 41,380 words)
  - **OLD System Baseline Confirmed**:
    - Target miscalculation bug discovered: Chapter targets summed to 193% of project target (80K vs 41K)
    - Micro-scene problem validated: 476 words/event actual (should be 950+)
    - Apparent achievement: 61% (false negative due to inflated targets)
    - Real achievement: 118% of project total
  - **NEW System Projections**:
    - Chapter 1 comparison: 9 events/8,500 target (OLD) → 4 scenes/4,180 target (NEW)
    - Realistic targets that align with project totals
    - Expected achievement: 80-100% (vs 50-60% baseline)
  - **Bug Found & Fixed**: Scene distribution normalization (see Fixed section)
  - All test scenarios pass: Scene clamping (2-4) respected, totals match exactly
  - Status: Production-ready, awaiting live generation test with API

### Added
- **Intelligent Word Count Defaults** 📊
  - Smart default word counts based on length_scope + genre
  - **Problem**: Hardcoded 50K default was minimum for novels, not typical; no genre considerations
  - **Solution**: Genre-aware defaults using form midpoints and industry-standard modifiers
  - **Form defaults** (midpoints): novel=80K, novella=35K, epic=155K, short_story=4.5K
  - **Genre modifiers**: fantasy/sci-fi +15%, mystery/horror/thriller -5 to -8%, YA -15%, literary +10%
  - **Examples**:
    - Mystery novel: 80K × 0.95 = 76,000 words
    - Fantasy novel: 80K × 1.15 = 92,000 words
    - YA novel: 80K × 0.85 = 68,000 words
    - Epic fantasy: 155K × 1.15 = 178,250 words
  - **Priority**: Stored value (chapters.yaml) > calculated from taxonomy > fallback
  - **Genre inference**: Auto-detects from taxonomy subgenre selections if not explicitly set
  - Removed unreliable "treatment × 20" estimation
  - New method: `DepthCalculator.get_default_word_count(length_scope, genre)`
  - Updated: chapters.py, interactive.py, project.py
  - User can still override: `/generate chapters 95000`

### Fixed
- **Scene Distribution Normalization** 🎬 **[Scene System Bug Fix]**
  - Fixed critical bug in scene distribution that violated 2-4 scene clamp
  - **Problem**: Normalization blindly added excess scenes to final chapter without respecting clamp
  - **Impact**: Chapter 11 in test case would get 8 scenes (violates max 4), breaking professional structure
  - **Root cause**: Line 494 in depth_calculator.py: `distribution[-1] += diff` added all excess to last chapter
  - **Discovery**: Found during baseline testing on steampunk-moon project (2025-10-14)
  - **Solution**: Implemented iterative distribution algorithm
    - Distributes scenes across ALL chapters with room (< 4), not just last
    - Respects 2-4 scene clamp throughout distribution
    - Input validation: raises ValueError if total_scenes < chapter_count
    - Warning system: logs if distribution outside recommended range (chapter_count * 2-4)
    - Fallback protection: minimum 1 scene per chapter as last resort
  - **Test Results** (All Pass):
    - steampunk-moon (38 scenes, 11 chapters): [4,4,4,4,4,4,4,4,2,2,2] ✓
    - Perfect scenario (33 scenes, 11 chapters): [4,4,4,3,3,3,3,3,2,2,2] ✓
    - Short story (6 scenes, 2 chapters): [4,2] ✓
    - Novella (50 scenes, 15 chapters): [4,4,4,4,4,3,3,3,3,3,3,3,3,3,3] ✓
  - All distributions match target exactly and respect 2-4 clamp
  - Fixed: src/generation/depth_calculator.py (distribute_scenes_across_chapters method)
  - Commit: 8caa4dc

- **Backward Compatibility: Scene and Key Events Support** 🎬 **[Scene System Fix]**
  - Fixed validation and analysis to support both 'scenes' (new) and 'key_events' (old) formats
  - **Problem**: analyzer.py and lod_parser.py only checked for 'key_events', not new 'scenes' format
  - **Impact**:
    - Chapter validation would fail with new scene format
    - Analysis reporting wouldn't display scene information
    - Chapter comparison for iteration wouldn't detect scene changes
  - **Discovery**: Found during verification after scene system implementation (2025-10-14)
  - **Solution**:
    - analyzer.py: Support both formats with detection of structured vs simple scenes
    - lod_parser.py: Updated validation to accept EITHER 'scenes' OR 'key_events' (one required)
    - lod_parser.py: Updated comparison logic to check both formats
    - chapters.py: Updated docstring from "events_per_chapter" to "scenes_per_chapter"
  - **Result**: Old projects with key_events continue working, new projects use scenes
  - Fixed: src/generation/analysis/analyzer.py, src/generation/lod_parser.py, src/generation/chapters.py
  - Commit: 63fd226

- **Prose Generation: Logger Error and Retry Logic** 📝
  - Fixed two critical issues with `/generate prose` command
  - **Issue 1: Logger not defined error**
    - **Problem**: Chapter 15 failed with "name 'logger' is not defined"
    - **Root cause**: `handle_sse_stream_with_status()` in streaming.py:757 used logger but didn't import it
    - **Solution**: Added logger imports at method start (same pattern as handle_json_stream_with_display)
    - Fixed: src/api/streaming.py lines 588-593
  - **Issue 2: No retry on failure**
    - **Problem**: Prose generation stopped immediately on first error, no retry attempts
    - **Symptom**: "Stopping sequential generation due to error" after Chapter 15 failed
    - **Solution**: Added retry mechanism with exponential backoff (2 attempts, 2s/4s delays)
    - Shows clear feedback: "🔄 Retry 1/2 for Chapter N..."
    - Fixed: src/generation/prose.py lines 436-478
  - **Impact**: Chapter failures will retry automatically instead of stopping generation

- **Removed 5-Minute Timeout on Generation** ⏱️
  - Removed hard 5-minute timeout on feedback processing (chapter generation, iteration)
  - **Problem**: Long operations like chapter generation (10-15 minutes) were timing out prematurely
  - **Symptom**: "Operation timed out after 5 minutes" error during chapter generation
  - **Root cause**: `asyncio.wait_for()` wrapper with 300-second limit in interactive.py:491
  - **Solution**: Removed timeout wrapper - let operations run as long as needed
  - **Why safe**: API client has proper timeouts (180s between chunks, catches real connection failures)
  - **Impact**: Chapter generation can now complete without artificial time limits
  - Note: sock_read timeout (180s between chunks) is still active as safety valve

- **Taxonomy Loading and Form Detection** 🔧
  - Fixed schema mismatch where `Project.get_taxonomy()` looked for 'taxonomy' key but metadata uses 'selections'
  - **Problem**: Chapter generation ignored user's taxonomy length_scope selection (e.g., "novel"), falling back to word-count detection
  - **Symptom 1**: 50,000-word projects with "novel" selected were detected as "novella" instead
  - **Symptom 2**: "unhashable type: 'list'" error when generating chapters
  - **Root cause 1**: `get_taxonomy()` returned None because it looked for wrong JSON key ('taxonomy' vs 'selections')
  - **Root cause 2**: Boundary condition - 50,000 words matched both novella (max) and novel (min), returned first match
  - **Root cause 3**: Taxonomy save overwrote entire premise_metadata.json with just selections, losing premise text
  - **Root cause 4**: Taxonomy values are lists (e.g., `['novel']`) but code expected strings, causing hash errors
  - **Solution**:
    - Changed `Project.get_taxonomy()` to return `data.get('selections')` (src/models/project.py:271)
    - Fixed taxonomy save to preserve full metadata structure (src/cli/interactive.py:691-693)
    - Changed `detect_form()` to check larger forms first, preferring novel over novella at boundaries (src/generation/depth_calculator.py:129)
    - Taxonomy editor now receives explicit `selections` dict instead of full metadata (src/cli/interactive.py:631)
    - Extract first value from list when using taxonomy values (src/generation/chapters.py:1042-1054, src/generation/wordcount.py:85-91)
  - **Result**: User's taxonomy selections are now respected, 50K words correctly identified as novel, chapter generation works
  - **Impact**: Affects all chapter generation and word count assignment using taxonomy
  - Backward compatible with existing projects

- **CRITICAL: Premise Iteration Detection** 🔧
  - Fixed intent analyzer incorrectly categorizing premise changes as "project" changes
  - **Problem**: User changes like "change Maya Chen to Maya Trent" appeared successful but didn't actually update premise_metadata.json
  - **Root cause**: Intent analyzer checked for `premise.md` (old format) instead of `premise_metadata.json` (new format introduced in v0.3.0)
  - **Symptom**: Intent analyzer thought no premise existed (`has_premise: False`), so it marked character renames as project-level changes
  - **Result**: Coordinator called `_execute_patch()` with `target_type='project'`, which doesn't handle premise updates
  - **Solution**: Changed line 253 in `intent.py` from `project.premise_file.exists()` to `project.premise_metadata_file.exists() or project.premise_file.exists()`
  - **Impact**: Premise iteration now works correctly - character names, protagonist changes, and all other premise modifications are properly detected and applied
  - Added comprehensive logging throughout iteration flow for future debugging
  - Backward compatible: Still checks `premise.md` as fallback for old projects

- **Streaming Display for Batch Premise Generation** 📺
  - Fixed `/generate premises` command not showing streaming output during generation
  - **Problem**: Users saw no output for 600+ tokens, then all results appeared at once
  - **Symptom**: "NO DISPLAY CONTENT" warnings every 50 tokens in logs, no visible streaming
  - **Root cause**: Array-first streaming mode only checked for first object `{` once when array `[` was detected
  - **Detail**: If the `{` arrived in a later token batch after `[`, the `in_first_object` flag never got set, so field detection never ran
  - **Solution**: Split array_first detection into 3 distinct phases
    - Phase 1: Detect array start `[` (once)
    - Phase 2: Detect first object `{` (continuously until found)
    - Phase 3: Detect field `"premise":` (continuously until found)
  - **Result**: Streaming output starts as soon as premise text begins generating
  - **Impact**: Batch premise generation now provides real-time feedback instead of silent waiting
  - Changed: src/api/streaming.py lines 159-182

- **JSON Markdown Fences in Streaming** 📺
  - Fixed issue where JSON responses wrapped in \`\`\`json fences were visible during streaming
  - **Problem**: Users saw ugly markdown code fences (\`\`\`json...\`\`\`) during premise generation
  - **Root cause 1**: streaming.py displayed raw content with fences, cleanup happened AFTER streaming
  - **Root cause 2**: No prompt instruction telling LLMs to avoid markdown formatting
  - **Solution 1**: Real-time fence stripping in streaming.py during mode="full" (lines 270-291)
  - **Solution 2**: Added explicit prompt instruction "Do NOT wrap in markdown code fences" in openrouter.py:464
  - **Result**: Clean JSON display during streaming, dual protection (prompt + cleanup)
  - Dual approach ensures clean display even if LLM ignores instructions

- **CRITICAL: Act-Aware Depth Architecture** 📐
  - Fixed critical bug where Act III chapters were 24% SHORTER than Act I
  - **Problem**: Climaxes felt rushed and underweight due to flat words-per-event calculation
  - **Root cause**: Act III had fewer events (focused conflict) but same depth per event as Act I
  - **Solution**: Added act-based words-per-event multipliers (ACT_WE_MULTIPLIERS)
  - Act multipliers vary depth by story position:
    - Act I: 0.95× baseline (efficient setup, many events to cover)
    - Act II: 1.00× baseline (standard development)
    - Act III: 1.35× baseline (DEEPER emotional intensity and detail)
  - **Result**: Act III now 8% LONGER than Act I with appropriate emotional depth
  - Mathematical model: `word_count_target = event_count × (base_we × act_we_mult)`
  - Example (80K novel): Act I avg 4,510 words/ch → Act III avg 4,872 words/ch
  - New methods in DepthCalculator:
    - `get_act_for_chapter()` - Determines act from position
    - `get_act_words_per_event()` - Returns act-adjusted words per event
    - `calculate_chapter_word_target()` - Calculates act-aware word target
  - Fixed edge case: Small chapter counts (≤3) now get proper act distribution
  - Updated chapters.py to use act-aware calculations in batch generation
  - Updated wordcount.py to recalculate with act multipliers
  - Updated prose.py to remind LLM about act-specific depth needs
  - Transparency: Mathematical model replaces LLM word count assignment
    - Deterministic (same input = same output)
    - Free (no API calls)
    - Transparent formula visible to users
    - Act multipliers provide sufficient nuance
  - **Impact**: Forward-looking only (doesn't affect existing content)
  - **Benefits**: Climaxes have appropriate intensity, reader expectations met, better three-act pacing

- **Taxonomy Length Scope Support** 📏
  - calculate_structure() now respects user's explicit `length_scope` from taxonomy
  - Priority: `taxonomy.length_scope` > `detect_form(target_words)` > fallback
  - Users can force "novella" treatment even for 60K+ word counts
  - Consistent behavior across chapters.py, wordcount.py, prose.py

### Improved
- **REPL Keybinding**: Escape key now clears current input line
  - Press Escape to instantly clear typed text in the prompt
  - Updated documentation to reflect actual Escape behavior
  - Improves user experience when starting over with input

### Added
- **Auto-Open Last Project** 🚀
  - Automatically opens the last opened project on startup
  - Saves `last_opened_project` to config.yaml whenever a project is loaded
  - Displays "Auto-opened: [project-name]" message to distinguish from manual opens
  - Gracefully handles missing projects (clears setting with warning)
  - Improves workflow: no need to manually `/open` project every session
  - Implemented in Settings class and InteractiveSession.run()


- **Intelligent Word Count Assignment** 📊
  - `/wordcount` command assigns word count targets to chapters based on content
  - Analyzes chapter complexity, key events, and narrative structure
  - Uses LLM to intelligently distribute word counts across chapters
  - Considers story pacing (climax chapters longer, setup shorter)
  - Ensures total matches desired book length from taxonomy
  - Word count ranges by book length:
    - Flash Fiction: 300-1,500 words
    - Short Story: 1,500-7,500 words
    - Novelette: 7,500-20,000 words
    - Novella: 20,000-50,000 words
    - Novel: 50,000-110,000 words
    - Epic: 110,000-200,000 words
  - Shows before/after comparison with deltas
  - Auto-commits changes to git
  - WordCountAssigner class in `src/generation/wordcount.py`
  - Typical chapters: 2,000-5,000 words (setup shorter, climax longer)
  - Use cases: after chapter generation, balancing pacing, adjusting book length

- **Interactive Premise Generation with Length Selection** 📏
  - `/generate premise` now asks three upfront questions when run without arguments:
    1. Story concept - enter your idea
    2. Genre - select from list or choose "Auto-detect"
    3. Story length - choose from 6 options (flash fiction → epic)
  - Length options with word counts and reading times:
    - Flash Fiction: 500-1,500 words (~5 min)
    - Short Story: 1,500-7,500 words (~15-30 min)
    - Novelette: 7,500-17,500 words (~45-90 min)
    - Novella: 17,500-40,000 words (~2-4 hours)
    - Novel: 40,000-120,000 words (~6-12 hours)
    - Epic: 120,000+ words (~12+ hours)
  - New `_select_length_interactive()` method shows all options with descriptions
  - `_select_genre_interactive()` updated with auto-detect as first option
  - `PremiseGenerator.generate()` accepts `length_scope` parameter
  - Length guidance included in premise generation prompt
  - Length automatically saved to taxonomy selections for treatment/chapters
  - Backwards compatible: command-line syntax still works
  - Display shows selected length during generation
  - Goal: Better premises that match target story length from the start

### Changed
- **Analysis System Revamp** 🎯
  - Added confidence scores (0-100%) to all analysis issues
  - Confidence requirement: Only report issues with >70% confidence
  - Self-critical evaluation: "Better to miss a minor issue than report a false positive"
  - New "Path to A+ Grade" section:
    - Current assessment explaining why story isn't A+ yet
    - Specific recommendations with confidence scores
    - Option to say "unable to determine" if no clear path exists
  - Updated prompt with 5 new confidence requirements instructions
  - Updated JSON response structure to include confidence fields
  - Updated CLI display to show confidence percentages
  - Updated markdown reports to include confidence scores and path to A+
  - Goal: Focus on genuine improvements rather than endlessly finding issues

### Added
- **Professional Copy Editing System** ✏️
  - `/copyedit [--auto]` command for comprehensive copy editing pass
  - Sequential processing of all chapter prose files with accumulated context
  - Context architecture: chapters.yaml + edited chapters + remaining original chapters
  - Pronoun consistency detection (special focus on unisex names: Alex, Jordan, Sam)
  - Continuity checking across all chapters (character details, timeline, terminology)
  - Forward reference support (all remaining chapters visible during editing)
  - Quality verification: paragraph structure, dialogue markers, scene breaks
  - Preview system with statistics before applying changes
  - Timestamped backups (`.agentic/backups/copy_edit_YYYYMMDD_HHMMSS/`)
  - Checkpoint saving for resume capability
  - Temperature 0.3 for precision over creativity
  - Token usage constant (~200k): redistributes between edited and original
  - CopyEditor class in `src/generation/copy_editor.py`
  - Comprehensive prompt with clear editing scope and examples
  - Integration with CLI command system
  - Git commit after completion
- **Concept Mashup Generator** 🎬
  - Creative premise ideas from movie + modifier combinations
  - `/generate concepts [count]` command (default 50, range 1-100)
  - 300 movies × 103 modifiers = 30,900 possible concepts
  - Examples: "Star Wars with lawyers", "Toy Story in space"
  - Interactive numbered selection
  - Selected concept feeds into premise generation with auto-genre detection
  - Data files: `misc/movies.txt`, `misc/story-modifiers.txt`
  - ConceptMashupGenerator class in `src/generation/concept_mashup.py`
  - Duplicate detection ensures unique combinations
  - Tab completion for `/generate concepts` command
- **Comprehensive Documentation Updates** 📚
  - Updated USER_GUIDE.md with all recent features (short story, concepts, multi-phase)
  - Updated DEVELOPER_GUIDE.md with implementation patterns
  - Added short story workflow documentation
  - Added concept mashup integration guide
  - Added multi-phase chapter generation architecture details
  - Organized features by importance and recency
- **Short Story Workflow** 📖
  - Automatic detection: Stories with ≤2 expected chapters use simplified flow
  - Single-file generation: story.md instead of chapters/ directory
  - Skip chapters.yaml: goes directly premise → treatment → story.md
  - ShortStoryGenerator class for optimized short-form prose
  - Prompts emphasize unity of effect and single-sitting experience
  - Iteration support: diff-based patching of story.md
  - Detection from taxonomy (length_scope) or word count (≤7,500)
  - Status display shows story type (Flash Fiction/Short Story/Novelette)
  - Force flag: `/generate chapters --force` to override auto-detection
  - Supports flash fiction (500-1,500), short story (1,500-7,500), novelette (7,500-17,500)
  - File structure: premise.md + treatment.md + story.md (no chapters.yaml)
  - Backward compatible: existing projects with chapters/ continue to work
- **Multi-Phase Chapter Generation System** 🚀
  - Three-phase generation for improved reliability:
    - Phase 1: Foundation (metadata + characters + world) ~2,000 tokens, ~30-45s
    - Phase 2: Chapter Batches (adaptive batching based on model capacity) ~30-60s per batch
    - Phase 3: Assembly (merge and validation)
  - Adaptive batch sizing:
    - Large models (16k+): 8 chapters per batch
    - Medium models (8-16k): 5 chapters per batch
    - Small models (4-8k): 3 chapters per batch
    - Very small models (<4k): 2 chapters per batch
  - Full context passing to every batch:
    - Complete premise + treatment in every call
    - Foundation (metadata, characters, world) in every batch
    - Previous chapter summaries for narrative continuity
  - Progress saving after each phase (`chapters.partial.foundation.yaml`, `chapters.partial.batch_1.yaml`, etc.)
  - Incremental success - don't lose everything on network drop
  - Batch retry logic (2 attempts per batch)
  - Benefits over single-shot:
    - 4x shorter streams (30-60s vs 3+ minutes)
    - Network drop only loses current batch, not entire generation
    - Can inspect/iterate on partial results
    - Clear progress indicators
- **Automatic Resume on Truncation** 🔄
  - Detects YAML truncation from network drops
  - Analyzes partial generation to find last complete chapter
  - Automatically resumes for missing chapters with custom prompt
  - Merges partial + continuation with validation
  - Token efficient: Resume saves ~25-30% vs full retry
  - Works for chapters section only (limitation: can't resume if truncation in foundation)
  - Handles unterminated strings and incomplete YAML gracefully
  - Three-level recovery: parse as-is → fix YAML → pattern matching
- **Enhanced Network Reliability** 🌐
  - TCP keep-alive configuration in OpenRouter client
  - Increased sock_read timeout: 120s → 180s
  - HTTP keep-alive enabled with connection pooling
  - Better handling of silent connection drops
  - Fixed usage statistics display when stream truncates

### Fixed
- **Mouse Text Selection on Mac** 🖱️
  - Fixed mouse selection not working in REPL
  - Changed `mouse_support=True` to `False` in PromptSession (line 192)
  - Text selection now works normally with click and drag
  - Copy with Cmd+C (Mac) or Ctrl+C (Windows/Linux)
  - Matches behavior of model_selector and taxonomy_editor which already had mouse_support=False
  - Updated USER_GUIDE.md troubleshooting section

- **Word Count Assignment API Call** 🔧
  - Fixed `/wordcount` command calling non-existent `generate_text()` method
  - Changed to use `json_completion()` which exists in OpenRouterClient
  - Updated `_parse_response()` to handle dict instead of string (json_completion returns parsed JSON)
  - Added try/except with fallback to equal distribution on LLM failure
  - Fixed import: `from models import` → `from ..models import` (relative import)
  - Fixed import: `from api.client import APIClient` → `from ..api import OpenRouterClient`
  - Fixed model attribute: `self.model` → `self.settings.active_model` in interactive.py
  - **Fixed JSON prompt example**: Quoted all keys (`"1": 3000` not `1: 3000`) - JSON spec requires quoted keys
  - Added explicit instruction: "Keys must be quoted strings"
  - Removed ellipsis from example to avoid confusion
  - Matches established pattern: premise.py, treatment.py, chapters.py all use json_completion()

- **CRITICAL: Partial Chapter Update Merge** 🚨
  - Fixed catastrophic data loss bug when LLM returns partial chapter updates during iteration
  - **Problem**: When LLM returned only updated chapters (e.g., chapters 4,7,11 of 11 total), parser blindly overwrote chapters.yaml, losing metadata, characters, world, and all other chapters
  - **Example**: steampunk-moon project corrupted from 931 lines (full structure) to 551 lines (only 3 chapters)
  - **Root cause**: `lod_parser.py` lines 169-173 fell into "legacy list format" branch and directly dumped list to file
  - **Fix**: Added `_save_chapters_list()` method (85 lines) that intelligently detects partial updates:
    - Compares new chapter count vs existing chapter count
    - If partial (3 < 11): MERGE updated chapters into existing structure, preserve metadata/characters/world
    - If complete (11+ >= 11): Replace chapters list only, still preserve structure sections
    - Always maintains self-contained format integrity
  - **Prevents**: Data loss during chapter iteration, need for manual git restoration
  - **Testing**: Manual verification confirmed correct detection and merge behavior
- **Premise Iteration** 🔧
  - **Critical Fix**: Premise iteration now always uses "regenerate" strategy, never "patch"
  - Added explicit check in `IterationCoordinator._determine_scale()` to return "regenerate" for premise
  - Added defensive check in `ScaleDetector._apply_heuristics()` for premise target type
  - Reason: Premise is too short (2-3 sentences) for diff-based patching
  - **Critical Fix**: Coordinator now calls `generator.iterate()` instead of `generator.generate()`
  - `iterate()` method designed specifically for premise iteration with feedback
  - `generate()` creates brand new premise from scratch (wrong for iteration)
  - **Critical Fix**: Premise iteration now preserves taxonomy selections
  - Updated `premise.iterate()` to request full JSON including `selections` field
  - Added explicit instruction to preserve existing taxonomy unless feedback changes it
  - Increased `min_response_tokens` from 800 to 1200 for complete response
  - Fixes issue where taxonomy selections were lost during iteration
  - Fixes "stuff is cut off" issue - response was incomplete
- **Copy Editor Context Architecture** 🏗️
  - Removed premise.md and treatment.md from copy editor context (no longer needed)
  - Added ALL remaining original chapters for forward reference support
  - Updated context structure to use self-contained chapters.yaml
  - chapters.yaml contains everything: metadata, characters, world, chapter outlines
  - premise.md and treatment.md are historical artifacts after multi-phase generation
  - Token usage stays constant (~200k) instead of growing
  - Removed word count change warning (copy editing focuses on correctness, not length)
  - Deleted unused SEQUENTIAL_PROSE_TEMPLATE from prose.py (85 lines of dead code)
- **Chapter Count Calculation** 🔢
  - Removed arbitrary min (8) and max (30) chapter limits
  - Changed from 3,000 to 3,500 words per chapter target
  - Simple division-based calculation: `total_words // 3500`
  - Naturally scales from novellas (2 chapters) to epics (57 chapters)
  - Multi-phase generation can handle any chapter count
- **Act Determination Bug** 🎭
  - Fixed bug where batch generation used wrong total for act calculation
  - Now passes `total_chapters` parameter to `_generate_chapter_batch()`
  - Correct act boundaries across all batches (Act I: 25%, Act II: 50%, Act III: 25%)
- **Analysis Compatibility** 🔍
  - Fixed analyzer to handle both list and dict formats for `systems_and_rules` and `social_context`
  - Maintains backward compatibility with old chapters.yaml format
  - New format uses structured lists with system/description fields
- **Token Count Display** 📊
  - Fixed inconsistency between streaming display and usage line
  - Now shows actual API completion tokens instead of counted tokens
  - Summary displayed after usage correction for accurate numbers
  - Fixed "1684 tokens" vs "4832 tokens" discrepancy
- **Chapter Iteration Compatibility** 🔄
  - Fixed LODContextBuilder to return flat structure for chapter iteration
  - Previously nested chapters.yaml under 'chapters' key, breaking parser detection
  - Now returns: `{metadata: ..., characters: ..., world: ..., chapters: [...]}`
  - Parser updated to handle both flat and nested formats for backward compatibility
  - Ensures `/iterate chapters` works correctly with new multi-phase generation

### Changed
- **Premise Storage Consolidation** 📦
  - **Single source of truth**: premise_metadata.json contains both premise text AND taxonomy selections
  - **Eliminated premise.md**: No longer generated (was duplicate of text in premise_metadata.json)
  - Backward compatibility: Old projects with premise.md still work (reads from .md if .json missing text)
  - Methods updated:
    - `Project.get_premise()` reads from JSON first, fallback to .md
    - `Project.save_premise_metadata()` saves full structure (replaces separate .md + .json writes)
    - `Project.save_premise()` deprecated with warning
  - All generators updated to use save_premise_metadata()
  - Documentation updated across CLAUDE.md, USER_GUIDE.md, DEVELOPER_GUIDE.md
  - Import/conversion utilities (lod_parser.py, import_converter.py) still support premise.md for legacy data
- **Self-Contained Chapters Architecture** 🏗️
  - chapters.yaml now includes ALL context for prose generation:
    - `metadata`: Genre, tone, themes, narrative_style, target_word_count, etc.
    - `characters`: Complete profiles with backgrounds, motivations, arcs, relationships
    - `world`: Setting overview, locations, systems, social_context
    - `chapters`: Individual chapter outlines with beats and character developments
  - Prose generation ONLY uses chapters.yaml (no premise/treatment needed)
  - Unidirectional data flow: premise → treatment → chapters → prose
  - No cross-level synchronization (simplified architecture)
  - Chapter generation extracts ALL material information from treatment
  - LLM adapts metadata from taxonomy to match actual story

- **Book Metadata and Export System** 📚
  - `/metadata [key] [value]` command to view and set book metadata
  - Metadata fields: title, author, copyright_year (minimal, essential fields only)
  - Validation: title and author required for export; copyright year 1900-2100
  - Copyright year automatically set to current year if not specified
  - Auto-creates frontmatter template on first metadata set
  - `/export rtf [filename]` - Professional RTF export for Kindle/ebook publishing
  - `/export markdown [filename]` - Combined markdown export
  - RTF features:
    - Times New Roman font (ebook standard)
    - Professional paragraph formatting (first-line indent 0.25", justification)
    - First paragraph after headings/scene breaks has NO indent (professional standard)
    - Title page with centered title and author
    - Copyright page with legal text (fiction disclaimer, all rights reserved)
    - Chapter headers with numbers and titles
    - Scene breaks (centered * * *)
    - Markdown to RTF conversion (bold, italic, em dashes)
    - Variable replacement in frontmatter templates ({{title}}, {{author}}, {{copyright_year}})
  - Frontmatter template system:
    - Auto-created `frontmatter.md` with sections (title page, copyright, dedication, acknowledgments)
    - Variable placeholders for metadata
    - Edit template to customize sections
  - Default export paths: `exports/book-title.rtf`, `exports/book-title.md`
  - Tab completion for /metadata and /export commands
  - Critical bug fixes:
    - Escape RTF special characters (\\, {, }) BEFORE adding RTF codes (prevents corruption)
    - Professional formatting: no first-line indent on first paragraph after chapter headings or scene breaks
    - Scene break detection: check for centered `\qc * * *` specifically, not any occurrence of "* * *" in text
    - Strip markdown chapter headings from prose to prevent duplication in exports

- **Kindle Publishing Documentation** 📖
  - Comprehensive research on Amazon KDP metadata requirements
  - Complete guide to book descriptions (100-150 words optimal, HTML formatting, best practices)
  - Keyword strategy (7 boxes, 50 characters each, research methods)
  - Category selection guide (BISAC codes, Amazon categories, competition analysis)
  - Author bio best practices (fiction vs nonfiction approaches)
  - Comparable titles (comp titles) guidance
  - Pricing strategies (70% vs 35% royalty, territory rights)
  - Marketing and launch checklists
  - Three comprehensive documentation files:
    - `KINDLE_PUBLISHING_METADATA_RESEARCH.md` - In-depth research (10 sections, 500+ lines)
    - `PUBLISHING_METADATA_TEMPLATE.md` - Fill-in template for each book (14 sections)
    - `EXPORT_AND_PUBLISHING_GUIDE.md` - Step-by-step workflow from export to launch

- **LLM-Powered KDP Metadata Generation** 🤖
  - `/generate marketing` command for automatic metadata generation
  - New `KDPMetadataGenerator` class in `src/generation/kdp_metadata.py`
  - Generates essential Amazon KDP marketing metadata:
    - **Book Description**: 100-150 words, HTML formatted with compelling hook, conflict, stakes, and CTA
    - **Keywords**: 7 keyword boxes (50 characters each) optimized for Amazon search
  - Context building from all book content:
    - Premise, treatment, chapters.yaml (genre, themes, characters)
    - First chapter prose sample (writing style)
  - Selective generation: `all`, `description`, `keywords`
  - Saves to simplified `publishing-metadata.md` file alongside RTF export
  - Progress spinners and formatted output display
  - Prerequisites validation (title/author set, content exists)
  - Uses project's selected model for all generation
  - Tested and verified with real book project
  - Simplified template: just description and keywords (the essentials)

- **Content Deletion System** 🗑️
  - `/cull <target>` command for explicit content deletion
  - Cascade deletion with confirmation:
    - `/cull prose` - Delete all chapter-XX.md files
    - `/cull chapters` - Delete chapters.yaml → cascade to prose
    - `/cull treatment` - Delete treatment.md → cascade to chapters + prose
    - `/cull premise` - Delete premise.md + metadata → cascade to all
  - Confirmation prompt before deletion
  - Git commit after successful deletion
  - CullManager class handles all deletion logic

- **Unified LOD Context System** 🏗️
  - New architecture: files stay separate, LLM sees/edits unified YAML
  - LODContextBuilder: Combines all files into single YAML structure for LLM
  - LODResponseParser: Splits LLM's YAML response back to individual files
  - Dry-run mode for multi-model competition (validate without saving)
  - All generators now use unified context (treatment, chapters, prose)
  - Enhanced validation: Ensures all required sections present in responses

### Fixed
- **Multi-Model Competition Architecture** ✅
  - Fixed race conditions where parallel models overwrote each other's files
  - Added `dry_run` parameter to `parse_and_save()` for validation without saving
  - Each competitor now generates with `dry_run=True`, winner saved with `dry_run=False`
  - Updated all `generate_with_competition()` methods to use new pattern
- **Dead Code Removal** 🧹
  - Removed obsolete iteration methods: `iterate()`, `iterate_chapter()`, `iterate_prose()`
  - All iteration now goes through `IterationCoordinator._execute_patch()`
  - Removed 200+ lines of duplicate/obsolete code from `lod_sync.py`
  - Removed old `_build_context()` and `_get_lod_content()` methods
- **LOD Sync Consistency Check** ✅
  - Updated `check_consistency()` to use LODContextBuilder instead of old methods
  - Now builds unified YAML context for more accurate consistency checking
- **Prose Validation** ✅
  - Fixed validation to check for `premise` and `treatment` sections (not just `chapters` and `prose`)
  - Ensures LLM returns complete YAML structure as requested
- **Encoding Auto-Fix** ✅
  - Standardized encoding handling across all file readers
  - Auto-fix files to UTF-8 when wrong encoding detected
  - Consistent behavior in `lod_context.py` and `lod_sync.py`

### Changed ⚠️  BREAKING
- **Shared Git Repository Architecture**
  - Changed from per-project git repos to single shared repo at `books/.git`
  - All commits now prefixed with project name: `[project-name] commit message`
  - Simpler architecture, better multi-project management
  - **Migration**: Remove old `.git` directories from individual projects
  - Repository auto-created on first run if it doesn't exist
  - Manual initialization available: `python3 init_shared_git.py`
  - Projects now committed to shared repository with prefixed messages

### Removed
- **LOD Synchronization System** ⚠️  BREAKING
  - Removed `/sync` command entirely
  - Removed `lod_sync.py` file and all LODSyncManager code
  - Removed automatic upward sync during iteration
  - Removed cross-level consistency checking
  - Simplified architecture: unidirectional data flow only
  - **Why**: Sync added complexity without clear benefit. Self-contained chapters.yaml provides all needed context.

- **Automatic Culling on Modification** ⚠️  BREAKING
  - Removed automatic cascade deletion when upstream content changes
  - Now explicit via `/cull` command only
  - Users have full control over when content is deleted

- **prose_status Field**
  - Removed prose_status tracking from chapters.yaml
  - No longer needed with explicit `/cull` command

### Added
- **Multi-Model Competition Mode** 🏆
  - `/multimodel` command to toggle tournament mode
  - Runs 3+ models in parallel (grok-4-fast, claude-sonnet-4.5, claude-opus-4.1)
  - Judge model (gemini-2.5-pro) evaluates and picks winner
  - Side-by-side candidate comparison with detailed scores
  - Full transparency: see all outputs, scores, and reasoning
  - All candidates saved to `multimodel/` folder for review
  - Git commits include judging results
  - Configurable: add/remove competitors, change judge
  - Prompt indicator: `(MULTI-MODEL)` when active
  - Status shows all competition models and judge
  - Works for treatment, chapters, and prose generation
  - **Iteration support**: Multi-model mode now works during iteration
    - `/iterate chapters` in multi-model mode runs competition
    - Feedback incorporated into all competing models
    - Winner selected based on how well feedback was addressed

- **Smart Chapter Iteration** 🔧
  - chapters.yaml now supports both patch and regenerate modes
  - Scale detection analyzes YAML content to choose appropriate method
  - Patch mode: Fast unified diffs for targeted edits (10-15x faster)
  - Regenerate mode: Full AI regeneration for structural changes
  - Examples:
    - "Change chapter 3 title" → Patch (seconds)
    - "Add foreshadowing chapters 4,8" → Regenerate with context (minutes)
    - "Fix typo in chapter 5" → Patch (seconds)
  - Existing chapters included in iteration prompt for true modification

- **Project Cloning** 📋
  - `/clone [name]` command to duplicate projects
  - Complete copy of all content (premise, treatment, chapters, prose, analysis)
  - Committed to shared git with message: "Clone project: source → destination"
  - Prompts to switch to cloned project after creation
  - Useful for experiments and variations

### Fixed
- **Treatment Generation Error**
  - Fixed "model is not defined" error in treatment metadata
  - Changed from undefined `model` variable to `self.model`
- **Interactive Model Selector Error**
  - Fixed "asyncio.run() cannot be called from a running event loop" error
  - Changed `app.run()` to `await app.run_async()` for async compatibility
  - Made `select_model_interactive()` async function
- **Project-Local State Files**
  - Moved all state files from user-level `~/.agentic/` to project-local `./.agentic/`
  - All state now in `.agentic/` directory:
    - Logs: `.agentic/logs/` (moved from `./logs/`)
    - Config: `./config.yaml` (project root)
    - History: `.agentic/history` (command history)
    - Premise history: `.agentic/premise_history.json`
    - Debug files: `.agentic/debug/`
  - Everything is now project-local for better isolation
  - Single hidden directory contains all AgenticAuthor state

## [0.3.0] - 2025-10-05

### Added ⭐ MAJOR RELEASE
- **Batch Premise Generation** 🎯
  - `/generate premises <count>` command (1-30 premises)
  - Single LLM call generates multiple unique options
  - Interactive numbered selection
  - Each premise includes full taxonomy selections
  - All candidates saved to `premises_candidates.json`
  - Streaming output shows first premise as it generates
  - Auto-commits with selection noted
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

## ✅ Recently Completed (Unreleased)

### Short Story Workflow
- [x] Auto-detection based on word count and taxonomy
- [x] ShortStoryGenerator class implementation
- [x] Single-file generation (story.md)
- [x] Streamlined flow (premise → treatment → story)
- [x] Optimized prompts for short-form
- [x] Iteration support via diff-based patching
- [x] Export compatibility (RTF and Markdown)
- [x] Force flag for overriding auto-detection
- [x] Status display shows story type

### Concept Mashup Generator
- [x] ConceptMashupGenerator class
- [x] Load movies and modifiers from data files
- [x] Generate unique random combinations
- [x] Interactive numbered selection
- [x] Integration with premise generation
- [x] Tab completion for command
- [x] Statistics and validation
- [x] Error handling for missing data files

### Multi-Phase Chapter Generation
- [x] Three-phase generation system (Foundation → Batches → Assembly)
- [x] Adaptive batch sizing based on model capacity
- [x] Full context passing to every batch
- [x] Progress saving after each phase
- [x] Auto-resume on network drops
- [x] Batch retry logic
- [x] Token efficiency improvements
- [x] Clear progress indicators

### Copy Editing System
- [x] CopyEditor class implementation
- [x] Sequential processing with accumulated context
- [x] Context architecture: chapters.yaml + edited + remaining chapters
- [x] Pronoun consistency detection (unisex names)
- [x] Continuity checking across all chapters
- [x] Forward reference support (all chapters visible)
- [x] Quality verification with preview
- [x] Timestamped backups and checkpoints
- [x] CLI integration (/copyedit command)
- [x] Git commit after completion

### Premise Iteration Fixes
- [x] Always use "regenerate" strategy (not "patch")
- [x] Call generator.iterate() (not generator.generate())
- [x] Preserve taxonomy selections in response
- [x] Increased token allocation (800→1200)
- [x] Fixed "cut off" response issue
- [x] Fixed taxonomy data loss issue

### Context Architecture Improvements
- [x] Documented self-contained chapters.yaml
- [x] Clarified premise.md/treatment.md as historical artifacts
- [x] Defined context patterns by operation type
- [x] Copy editor uses full story context (edited + remaining)
- [x] Removed dead code (SEQUENTIAL_PROSE_TEMPLATE)
- [x] Removed word count warnings from copy editing

### Documentation
- [x] USER_GUIDE.md updated with recent features
- [x] DEVELOPER_GUIDE.md updated with implementation patterns
- [x] DEVELOPER_GUIDE.md context architecture section added
- [x] CHANGELOG.md entries for all recent work
- [x] Short story workflow documentation
- [x] Concept mashup integration guide
- [x] Multi-phase chapter generation architecture
- [x] Copy editing system documentation
- [x] Premise iteration fixes documented

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

1. **Mouse Scrolling**: Full-screen editors (model selector, taxonomy editor) don't support mouse scrolling
2. **Tab Completion**: Press Tab twice for suggestions in some terminals
3. **Token Counting**: Not implemented for all models

## 📈 Test Coverage

**Test suite removed in v0.3.0** - needs complete rebuild to match current architecture.

Previous coverage (v0.2.0 - now outdated):
- 187 total tests (171 unit, 16 integration)
- ~85% coverage across core modules

**TODO for future:**
- Rebuild test suite for v0.3.0+ features
- Test interactive editors
- Test batch premise generation
- Test auto genre detection
- Test strict model enforcement

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
