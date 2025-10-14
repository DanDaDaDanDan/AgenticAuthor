# Word Count System Rework - Implementation TODO

**Status**: Planning Phase
**Start Date**: 2025-10-14
**Target Completion**: 2025-11-08 (4 weeks)

**Related Documents**:
- `wordcount-rethink-2025.md` - Comprehensive analysis and design
- `wordcount.md` - Current system documentation
- `wordcount-iteration.md` - Original testing plan

---

## Executive Summary

**The Change**: Rename "key_events" → "scenes" and restructure from 4-9 micro-events to 2-4 full dramatic scenes per chapter.

**Why**: LLMs achieve only 50-60% of word targets because we ask for "events" (bullet points = 200-500w summaries) when we should ask for "scenes" (dramatic units = 1,200-2,000w full development).

**Impact**:
- Increase baseline words-per-scene from 950 → 1,300 (37% increase)
- Reduce scenes-per-chapter from 4-5 → 3-4
- Add scene structure (goal, conflict, stakes, outcome, emotional beat)
- Achieve 80-100% of target word counts (vs current 50-60%)

---

## Phase 0: Pre-Implementation Testing (Week 1)

**MUST COMPLETE BEFORE ANY CODE CHANGES**

### Test 1: Baseline Control

**Goal**: Establish current system performance

- [ ] Clone pechter → wordcount-test-baseline
- [ ] Select Chapter 3 (or similar Act I chapter)
- [ ] Regenerate prose with current system
- [ ] Measure:
  - [ ] Total word count
  - [ ] Words per event (actual)
  - [ ] Achievement percentage
  - [ ] Scene structure quality (1-5 scale)
  - [ ] Reading quality (1-5 scale)
- [ ] Document baseline metrics

**Expected**: ~2,500 words (65% of 3,800 target), ~500 w/e, quality: 3/5

### Test 2: Simple Rename (Minimal Change)

**Goal**: Test if just renaming "events" → "scenes" changes behavior

**Changes**:
- Manually edit chapters.yaml: `key_events:` → `scenes:`
- Keep same 5 event descriptions
- NO other changes

- [ ] Update test chapter outline (rename only)
- [ ] Regenerate prose
- [ ] Measure same metrics as Test 1
- [ ] Compare to baseline

**Hypothesis**: Little to no difference (maybe 5-10% improvement)

### Test 3: Scene Structure (Medium Change)

**Goal**: Test if adding scene structure improves depth

**Changes**:
- Reduce from 5 events → 3 scenes
- Add full scene structure:
  ```yaml
  scenes:
    - scene: Fiction Clan's Fall
      location: Fiction territory server rooms
      pov_goal: Survive and save Joaquin
      conflict: Erasers reverse narrative loops
      stakes: Loss of entire Fiction archive
      outcome: Joaquin saved, servers destroyed
      emotional_beat: Witnessing Eraser horror
      target_words: 1,400
  ```
- Use existing prose prompt (no changes yet)

- [ ] Rewrite Chapter 3 outline with 3 structured scenes
- [ ] Regenerate prose with current prompt
- [ ] Measure metrics
- [ ] Compare to baseline

**Hypothesis**: 10-20% improvement, ~600-700 w/s achieved

### Test 4: Full System (Maximum Change)

**Goal**: Test complete scene-based system

**Changes**:
- Use 3 structured scenes from Test 3
- Update prose prompt with:
  - 4-part scene structure (setup, development, climax, resolution)
  - Word count guidance per part
  - SHOW vs TELL examples
  - Emphasis on "full dramatic unit"

- [ ] Create updated prose prompt (save to test file)
- [ ] Regenerate prose with new prompt
- [ ] Measure metrics
- [ ] Compare to all previous tests

**Success Criteria**:
- [ ] 3,040-3,800 words (80-100% achievement)
- [ ] 1,000-1,400 words per scene average
- [ ] Scene structure quality: 4/5 or higher
- [ ] Reading quality: 4/5 or higher

**If Test 4 succeeds** → Proceed to Phase 1 implementation
**If Test 4 fails** → Analyze why, adjust, retest before proceeding

### Testing Deliverables

- [ ] Create test results table comparing all 4 tests
- [ ] Save all generated prose samples
- [ ] Document what worked and what didn't
- [ ] Make GO/NO-GO decision for implementation
- [ ] Update wordcount-iteration.md with results
- [ ] Get user approval to proceed

---

## Phase 1: Core System Changes (Week 2)

**Prerequisites**: Test 4 succeeded, user approved implementation

### Task 1.1: Update depth_calculator.py

**File**: `src/generation/depth_calculator.py`

**Global Refactoring**:
- [ ] Rename WORDS_PER_EVENT → WORDS_PER_SCENE (line 29-62)
- [ ] Update all constants:
  ```python
  'novel': {
      'fast': (900, 1300, 1100),      # was (650, 950, 800)
      'moderate': (1100, 1600, 1300),  # was (800, 1100, 950)
      'slow': (1400, 2000, 1600)       # was (1000, 1400, 1200)
  }
  ```
- [ ] Rename all methods:
  - [ ] `get_base_words_per_event()` → `get_base_words_per_scene()`
  - [ ] `get_act_words_per_event()` → `get_act_words_per_scene()`
  - [ ] `distribute_events_across_chapters()` → `distribute_scenes_across_chapters()`
- [ ] Update calculate_structure() method:
  - [ ] total_events → total_scenes
  - [ ] avg_events_per_chapter → avg_scenes_per_chapter
  - [ ] Update return dict keys
- [ ] Add scene count clamping (2-4 scenes per chapter):
  ```python
  if avg_scenes_per_chapter < 2:
      chapter_count = total_scenes / 2
  elif avg_scenes_per_chapter > 4:
      total_scenes = chapter_count * 4
  ```
- [ ] Update all docstrings and comments
- [ ] Run Python syntax check: `python -m py_compile src/generation/depth_calculator.py`

**Testing**:
- [ ] Unit tests pass (if any exist)
- [ ] Manual test: calculate_structure(92000, 'moderate', 'novel')
  - [ ] Verify returns 71 scenes (not 97 events)
  - [ ] Verify 3.1 scenes/chapter (not 4.2 events/chapter)

### Task 1.2: Update chapters.yaml Schema

**Define New Schema**:
- [ ] Document new structure in `docs/schema-chapters.md`:
  ```yaml
  scenes:  # replaces key_events
    - scene: str (required)
      location: str (required)
      pov_goal: str (required)
      conflict: str (required)
      stakes: str (required)
      outcome: str (required)
      emotional_beat: str (required)
      sensory_focus: list[str] (optional)
      target_words: int (optional, default from depth calc)
  ```

**Update Loaders**:
- [ ] `src/utils/yaml_loader.py`:
  - [ ] Add scene schema validation
  - [ ] Support both old (key_events) and new (scenes) for backward compat
  - [ ] Add deprecation warning if key_events found
  - [ ] Auto-migrate: key_events → scenes with basic structure

**Update Project Model**:
- [ ] `src/models/project.py`:
  - [ ] Update get_chapters_yaml() to handle both formats
  - [ ] Add get_scenes(chapter_num) method
  - [ ] Add migration method: migrate_events_to_scenes()

**Testing**:
- [ ] Load old project with key_events (backward compat test)
- [ ] Load new project with scenes
- [ ] Test migration utility
- [ ] Verify validation catches invalid scene structures

### Task 1.3: Update Chapter Generation

**File**: `src/generation/chapters.py`

**Update Build Prompt** (line ~620-700):
- [ ] Replace event-based guidance with scene-based
- [ ] Add scene structure requirements:
  ```
  For each chapter, create 3-4 SCENES (not events, not bullet points).

  Each scene must include:
  - scene: Brief descriptive title
  - location: Physical setting
  - pov_goal: What POV character wants in this scene
  - conflict: What prevents them
  - stakes: What's at risk
  - outcome: How it resolves
  - emotional_beat: How character changes
  - sensory_focus: [2-3 key sensory details]
  - target_words: 1200-1800

  A SCENE is a complete dramatic unit, not a plot summary.
  Professional novels have 2-4 scenes per chapter.
  ```
- [ ] Add good/bad examples to prompt
- [ ] Update context building to pass scene structure info

**Update Foundation Phase**:
- [ ] Ensure foundation knows about scenes (not events)
- [ ] Update any event-related references

**Testing**:
- [ ] Generate new chapters.yaml for test project
- [ ] Verify scenes have all required fields
- [ ] Verify scene counts are 2-4 per chapter
- [ ] Check scene structure makes sense

---

## Phase 2: Prose Generation Updates (Week 2-3)

### Task 2.1: Update Prose Prompts

**File**: `src/generation/prose.py`

**Update generate_chapter() method** (line ~268-331):
- [ ] Replace event-based prompt with scene-based
- [ ] Add scene-by-scene breakdown:
  ```
  SCENES (from outline):

  Scene 1: "Fiction Clan's Fall" (1,400 words)
  - Location: Fiction territory server rooms
  - Goal: Mara survives attack and saves Joaquin
  - Conflict: Erasers reverse narrative loops
  - Outcome: Joaquin saved but servers destroyed
  - Emotional: Witnessing Eraser horror
  - Sensory: Smoke, screaming servers, taste of burnt imagination
  ```
- [ ] Add 4-part scene structure guidance:
  ```
  Each scene must follow dramatic structure:

  1. SETUP (20-25%): 240-350 words for 1,200w scene
     - Establish location with sensory details
     - POV character's state
     - Introduce goal

  2. DEVELOPMENT (40-50%): 480-600 words
     - Conflict unfolds
     - Dialogue with subtext
     - Action with consequences
     - Rising tension

  3. CLIMAX (15-20%): 180-240 words
     - Peak decision/revelation
     - Emotional intensity

  4. RESOLUTION (15-20%): 180-240 words
     - Aftermath
     - Bridge to next scene
  ```
- [ ] Add SHOW vs TELL examples:
  ```
  ✓ SHOW: "Joaquin's fingers blurred across the terminal, weaving
          narrative threads. The Eraser stepped into the pattern—and
          smiled. The threads reversed. Screams erupted as three
          defenders collapsed, eyes rolling back."

  ✗ TELL: "Joaquin tried to trap the Erasers but it backfired."
  ```
- [ ] Update word count targets:
  - [ ] Minimum per scene (not average)
  - [ ] Range acceptable (1,200-1,600 vs exactly 1,200)
  - [ ] Emphasize scenes are "complete dramatic units"

**Update Context Building**:
- [ ] Pass scene structure to prose generation
- [ ] Include sensory_focus if present
- [ ] Include target_words per scene

**Testing**:
- [ ] Generate prose for test chapter
- [ ] Verify scene structure in output
- [ ] Measure word counts per scene
- [ ] Check for SHOWING not TELLING

### Task 2.2: Update Multi-Phase Generation

**File**: `src/generation/chapters.py`

**Update Batched Generation**:
- [ ] Update batch prompts to use scenes not events
- [ ] Adjust token calculations (scenes have more metadata)
- [ ] Update progress display: "Scene 1/3" not "Event 1/5"

**Update Assembly Phase**:
- [ ] Verify scene-based chapters assemble correctly
- [ ] Update validation (check all scenes present)

**Testing**:
- [ ] Generate full book with multi-phase
- [ ] Verify all scenes included
- [ ] Check progress display
- [ ] Validate final chapters.yaml

---

## Phase 3: Iteration System Updates (Week 3)

### Task 3.1: Update Intent Analyzer

**File**: `src/generation/iteration/intent.py`

- [ ] Update terminology in prompts: event → scene
- [ ] Update example feedback:
  ```
  "Add more conflict to scene 2"
  "Make the first scene longer"
  "Combine scenes 3 and 4"
  ```
- [ ] Test intent detection with scene-based feedback

### Task 3.2: Update Diff Generation

**File**: `src/generation/iteration/diff.py`

- [ ] Update to handle scene structure in diffs
- [ ] Show scene-level changes (not just event text)
- [ ] Handle scene metadata changes (goal, conflict, etc.)

**Example diff**:
```diff
  scenes:
-   - scene: Market Meeting
+   - scene: Market Betrayal
      location: Night market
-     pov_goal: Get information
+     pov_goal: Force informant to reveal hideout location
      conflict: Informant is terrified
      ...
```

### Task 3.3: Update Patch Mode

**File**: `src/generation/iteration/coordinator.py`

- [ ] Update patch generation for scenes
- [ ] Ensure scene structure preserved in patches
- [ ] Test iteration on scene-based chapters

**Testing**:
- [ ] Iterate on test chapter: "Make first scene more tense"
- [ ] Verify scene structure maintained
- [ ] Check patch applies correctly
- [ ] Regenerate prose and verify changes

---

## Phase 4: CLI & Display Updates (Week 3)

### Task 4.1: Update Status Display

**File**: `src/cli/interactive.py`

- [ ] Update /status command:
  ```
  Chapters: 23 (71 scenes total, avg 3.1 scenes/chapter)
  Target: 1,300 w/scene
  ```
- [ ] Update chapter info display:
  ```
  Chapter 3: "The Splintering"
    Scenes: 3
    Target: 3,800 words
    1. Fiction Clan's Fall (1,400w)
    2. Betrayal Evidence (1,200w)
    3. Unity or Death (1,200w)
  ```

### Task 4.2: Update Command Completer

**File**: `src/cli/command_completer.py`

- [ ] Update autocomplete for scene-based commands
- [ ] Update help text

### Task 4.3: Add Migration Command

**New command**: `/migrate scenes`

- [ ] Add to interactive.py
- [ ] Call project.migrate_events_to_scenes()
- [ ] Show before/after summary
- [ ] Confirm before saving

**Testing**:
- [ ] Run /migrate scenes on old project
- [ ] Verify scenes created correctly
- [ ] Check chapters.yaml updated
- [ ] Ensure prose still loads correctly

---

## Phase 5: Documentation Updates (Week 3-4)

### Task 5.1: User-Facing Docs

- [ ] Update `docs/USER_GUIDE.md`:
  - [ ] Explain scenes vs events
  - [ ] Show scene structure example
  - [ ] Document /migrate command
  - [ ] Update all examples to use scenes

- [ ] Update `README.md`:
  - [ ] Quick start uses scenes
  - [ ] Example chapter.yaml with scenes

- [ ] Create `docs/MIGRATION_GUIDE.md`:
  - [ ] Why the change
  - [ ] How to migrate existing projects
  - [ ] What to expect (better word counts)
  - [ ] Troubleshooting

### Task 5.2: Developer Docs

- [ ] Update `docs/DEVELOPER_GUIDE.md`:
  - [ ] Scene structure schema
  - [ ] How depth calculator works with scenes
  - [ ] Scene generation prompts
  - [ ] Testing guidelines

- [ ] Update `docs/IMPLEMENTATION_STATUS.md`:
  - [ ] Mark scene system as implemented
  - [ ] Update known issues
  - [ ] Add scene-based generation to features

### Task 5.3: Internal Docs

- [ ] Update `CLAUDE.md`:
  - [ ] Scene-based system overview
  - [ ] When to use scenes vs short form
  - [ ] Scene structure requirements
  - [ ] Common patterns

- [ ] Update `docs/CHANGELOG.md`:
  - [ ] Add v0.4.0 section
  - [ ] Document breaking change
  - [ ] List all scene system changes
  - [ ] Migration instructions

---

## Phase 6: Validation & Testing (Week 4)

### Task 6.1: Integration Testing

- [ ] Test complete workflow start to finish:
  - [ ] /new test-novel
  - [ ] /generate premise
  - [ ] /generate treatment
  - [ ] /generate chapters (verify scenes created)
  - [ ] /generate prose (verify word counts hit 80-100%)
  - [ ] /iterate chapters "make scene 2 more intense"
  - [ ] /generate prose (verify iteration worked)
  - [ ] /export rtf

- [ ] Test migration workflow:
  - [ ] /open old-project
  - [ ] /migrate scenes
  - [ ] /generate prose
  - [ ] Verify output quality

### Task 6.2: Multi-Chapter Validation

- [ ] Generate complete 10-chapter book
- [ ] Measure achievement rates per chapter
- [ ] Calculate overall statistics:
  - [ ] Average words per scene (target: 1,000-1,400)
  - [ ] Achievement percentage (target: 80-100%)
  - [ ] Scene counts per chapter (target: 3-4)
  - [ ] Total word count vs target (target: 90-110%)

- [ ] Compare to baseline (pechter data):
  - [ ] Before: 50-60% achievement, ~500 w/e
  - [ ] After: 80-100% achievement, 1,000-1,400 w/s

**Success Criteria**:
- [ ] 80%+ of chapters hit 80-100% of target words
- [ ] Average w/s is 1,000+ (2× improvement over baseline)
- [ ] Reading quality is 4/5 or higher
- [ ] Scene structure is clear and professional

### Task 6.3: Model Comparison

Test with different models to see behavior:
- [ ] Claude Opus 4.1
- [ ] Claude Sonnet 4.5
- [ ] Grok-4-fast
- [ ] Gemini Pro 2.0

Measure:
- [ ] Which models respect scene structure best?
- [ ] Which achieve highest word counts?
- [ ] Are there model-specific patterns?

Document findings in wordcount-rethink-2025.md

---

## Phase 7: Rollout (Week 4)

### Task 7.1: Pre-Release

- [ ] All tasks in Phases 1-6 complete
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Migration guide ready
- [ ] User approval obtained

### Task 7.2: Release

- [ ] Merge to main branch
- [ ] Tag release: v0.4.0
- [ ] Update CHANGELOG.md
- [ ] Announce change to users

### Task 7.3: Monitoring

- [ ] Monitor user feedback for first week
- [ ] Track achievement rates on new projects
- [ ] Collect data on scene structure quality
- [ ] Be ready to hotfix if major issues

### Task 7.4: Post-Release

- [ ] Analyze data after 2 weeks
- [ ] Document lessons learned
- [ ] Update wordcount-rethink-2025.md with actual results
- [ ] Plan any needed adjustments

---

## Rollback Plan

**If scene system fails after release**:

1. [ ] Revert core changes to depth_calculator.py
2. [ ] Revert prompt changes in chapters.py and prose.py
3. [ ] Keep migration utilities (don't break migrated projects)
4. [ ] Support both event and scene formats indefinitely
5. [ ] Document why scene system failed
6. [ ] Return to baseline system

---

## Success Metrics

### Quantitative (Measured in Phase 6)

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| Word count achievement | 50-60% | 80-100% | ___ |
| Words per scene | ~500 w/e | 1,000-1,400 w/s | ___ |
| Scenes per chapter | 4-9 events | 3-4 scenes | ___ |
| Total words (92K target) | 61,000 | 82,800-92,000 | ___ |

### Qualitative (Subjective)

- [ ] Scene structure is clear and professional (4/5)
- [ ] Reading quality matches published novels (4/5)
- [ ] Dialogue is revealing not expository (4/5)
- [ ] Sensory details are integrated naturally (4/5)
- [ ] Pacing varies appropriately per scene (4/5)

---

## Dependencies

**Blockers**:
- Test 4 must succeed before starting Phase 1
- Phase 1 must complete before Phase 2
- Phase 3 depends on Phase 1 complete

**Parallel Work**:
- Phase 2 and Phase 3 can overlap (different files)
- Phase 4 can happen during Phase 3
- Phase 5 can happen during Phase 4

---

## Resources Needed

**Development Time**:
- Week 1: 8-12 hours (testing)
- Week 2: 12-16 hours (core changes)
- Week 3: 12-16 hours (iteration + CLI)
- Week 4: 8-12 hours (validation + docs)
- **Total**: 40-56 hours

**Testing**:
- LLM API costs for testing: ~$10-20 (generation tests)
- Human review time: 4-6 hours (reading generated prose)

---

## Risk Mitigation

### Risk: Testing Phase Fails

**Mitigation**:
- Have Test 1-4 planned in detail
- If Test 4 fails, analyze and adjust before proceeding
- Can fall back to hybrid approach (Test 3 level)

### Risk: Breaking Changes

**Mitigation**:
- Migration utilities ready
- Backward compatibility for 1 version
- Clear migration guide for users

### Risk: Scene System Doesn't Improve Word Counts

**Mitigation**:
- Phase 6 validation before release
- Rollback plan ready
- Can coexist with event system if needed

---

## Questions to Resolve

- [ ] Should Act-based multipliers change? (Current: 0.95×, 1.0×, 1.35×)
- [ ] Should we enforce 2-4 scenes or allow 1-5?
- [ ] Do we need scene_type field (action, dialogue, emotional, etc)?
- [ ] Should sensory_focus be required or optional?
- [ ] Migration: auto-migrate on load or explicit command?

**Decision deadline**: End of Week 1 (after testing)

---

## Next Immediate Steps

1. [ ] User reviews wordcount-rethink-2025.md
2. [ ] User approves testing plan
3. [ ] Execute Test 1 (baseline)
4. [ ] Execute Test 2 (rename)
5. [ ] Execute Test 3 (structure)
6. [ ] Execute Test 4 (full system)
7. [ ] Make GO/NO-GO decision
8. [ ] Begin Phase 1 if approved

---

## Document History

- **2025-10-14**: Created implementation TODO
- **Status**: Draft - Awaiting User Review
