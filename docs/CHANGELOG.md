# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added - 2025-10-23

#### Natural Language Iteration System
Complete implementation of always-on iteration system for natural language feedback on generated content.

**Core Features:**
- Always-on iteration mode - any non-command text becomes iteration feedback when target is set
- LLM judge validation loop - validates generated content matches user feedback before showing to user
- Semantic diff generation - human-readable change summaries (not raw git diffs)
- Iteration history tracking per LOD level with full metadata
- Downstream cascade handling (cull-all or keep-all when editing upstream content)
- Support for all targets: premise, treatment, chapters, prose
- Git integration with auto-commits (includes project name prefix)
- Safety warnings for destructive operations (first iteration only)
- Debug storage for all generation attempts with judge verdicts

**Implementation Files:**
- `src/generation/iteration/iterator.py` - Main coordinator (771 lines)
- `src/generation/iteration/history.py` - Iteration history tracking (118 lines)
- `src/generation/iteration/judge.py` - LLM validation (117 lines)
- `src/generation/iteration/semantic_diff.py` - Change summary generation (86 lines)

**Prompt Templates:**
- `src/prompts/validation/iteration_fidelity.j2` - Judge validation
- `src/prompts/analysis/semantic_diff.j2` - Semantic diff generation
- `src/prompts/generation/premise_iteration.j2` - Premise iteration
- `src/prompts/generation/treatment_iteration.j2` - Treatment iteration
- `src/prompts/generation/chapter_iteration.j2` - Chapter iteration
- `src/prompts/generation/prose_full_iteration.j2` - Full prose iteration

**CLI Integration:**
- `/iterate [target]` - Set iteration target or show current target
- Non-command text automatically routes to iteration when target is set
- Auto-set target after generation (e.g., `/generate premise` sets target to premise)
- Autocomplete support for iteration commands

**Workflow:**
1. Generate content: `/generate premise`
2. Target auto-set to premise
3. Provide feedback: "make it darker and add mystery"
4. System iterates with judge validation loop
5. Shows semantic diff for approval
6. Auto-commits on approval with git tracking

**Commits:**
- b605026: Initial implementation (11 files)
- c47ac13: Fixed missing subprocess import
- 161f98d: Fixed 6 critical bugs (format, git, safety, JSON, template)
- ec4c8fa: Fixed 2 critical bugs (missing context, output validation)

### Fixed - 2025-10-23

**Critical Bugs (Found During Ultrathink Review):**
1. Missing subprocess import for git operations
2. Chapter format mismatch - now handles both .md and .yaml formats
3. Git commit missing project name prefix for shared repository
4. JSON parsing without error handling - added clear error messages
5. No safety warning for destructive operations - added first-time warning
6. Prose template mismatch - created separate prose_full_iteration.j2
7. Missing chapters context in prose iteration prompts
8. No validation of LLM output format - added split validation

## [0.3.0] - 2025-10-XX (Previous Release)

### Added
- Multi-variant chapter generation with LLM judging
- Sequential chapter generation with full context accumulation
- Self-contained chapters architecture
- Automatic genre detection
- Interactive taxonomy editor
- Interactive model selector
- Taxonomy iteration
- Strict model enforcement
- Smart chapter iteration (patch/regenerate modes)
- Short story workflow (≤2 chapters)

### Changed
- Quality-first prose architecture (removed word count pressure)
- Scene-level key_events (3-5 instead of 8-10)
- Simplified depth_calculator (566 → 284 lines, 50% reduction)
- Removed wordcount.py entirely (361 lines)

## [0.2.0] - 2025-09-XX

### Added
- Genre-specific taxonomy support (11 genres)
- Smart input detection (brief/standard/detailed/treatment)
- History tracking to avoid repetitive generations
- Comprehensive logging system
- Enhanced tab completion

## Known Issues

- Test suite removed in v0.3.0 - needs rebuilding for current architecture
- Iteration system requires testing on cloned projects only (never production books)
- Documentation files (USER_GUIDE.md, DEVELOPER_GUIDE.md, IMPLEMENTATION_STATUS.md) need creation

## Testing Notes

**CRITICAL: Iteration Testing Protocol**
- ⚠️ ONLY test iteration on cloned projects: `/clone test-book-iteration`
- NEVER test on production books (destructive operation)
- Git commits created automatically for rollback capability
- Safety warning shown on first iteration

**Manual Test Checklist:**
1. Clone a test book project
2. Test premise iteration with simple feedback
3. Test treatment iteration
4. Test chapter iteration (verify format handling)
5. Test prose iteration
6. Verify git commits have correct format: `[project-name] Iterate target: feedback`
7. Verify iteration history tracking in `iteration_history.json`
8. Test downstream cascade (cull-all vs keep-all)
9. Test judge validation loop (approval/rejection)
10. Test semantic diff generation and display
