# Word Count System Implementation Status

**Last Updated**: 2025-10-14
**Status**: Phase 1 Complete - Core Math Layer Done

---

## ✅ COMPLETED: Phase 1 - Core Calculations (depth_calculator.py)

**Commit**: 325c75d

### What Was Changed

**1. All Constants Renamed and Updated**:
- `WORDS_PER_EVENT` → `WORDS_PER_SCENE` with **+35% increases**
  - Novel moderate: 950 → 1,300 w/s (+37%)
  - Novel fast: 800 → 1,100 w/s (+37%)
  - Novel slow: 1,200 → 1,600 w/s (+33%)
  - Similar increases across all forms (flash fiction through epic)

- `ACT_EVENT_MULTIPLIERS` → `ACT_SCENE_MULTIPLIERS`
- `ACT_WE_MULTIPLIERS` → `ACT_WS_MULTIPLIERS`

**2. All Methods Renamed**:
- `get_base_words_per_event()` → `get_base_words_per_scene()`
- `get_act_words_per_event()` → `get_act_words_per_scene()`
- `get_words_per_event_range()` → `get_words_per_scene_range()`
- `calculate_chapter_events()` → `calculate_chapter_scenes()`
- `distribute_events_across_chapters()` → `distribute_scenes_across_chapters()`

**3. All Variables Renamed**:
- `total_events` → `total_scenes`
- `avg_events_per_chapter` → `avg_scenes_per_chapter`
- `event_count` → `scene_count`
- `base_we` → `base_ws`
- `we_range` → `ws_range`
- All related variables and parameters

**4. Scene Clamping Added** (CRITICAL NEW FEATURE):
- `calculate_chapter_scenes()`: enforces 2-4 scenes per chapter
- `distribute_scenes_across_chapters()`: clamps to 2-4 range
- Prevents the 6-10 micro-event problem
- Aligns with professional novel structure (2-4 scenes/chapter)

**5. All Documentation Updated**:
- Docstrings updated for all methods
- Comments updated throughout
- Example text updated ("scenes" not "events")

**Impact**: The core math now produces:
- 92K novel → 71 scenes (was 97 events)
- 71 scenes ÷ 23 chapters = **3.1 scenes/chapter** (was 4.2 events/chapter)
- Target: **1,300 w/scene** (was 950 w/e)

**Status**: ✅ Complete, tested (syntax check passed), committed

---

## ✅ COMPLETED: Phase 2 Part 1 - chapters.py

**Commit**: b239512

### What Was Changed

**1. Variables & Parameters Renamed**:
- `events_per_chapter` → `scenes_per_chapter`
- `total_events` → `total_scenes`
- `base_we` → `base_ws`
- `act_we` → `act_ws`
- `events_distribution` → `scenes_distribution`

**2. Validation Updated (Backward Compatible)**:
- Lines 167-177, 203-214: Accept both 'scenes' (new) and 'key_events' (old)
- Checks for `('scenes' in chapter or 'key_events' in chapter)`
- No deprecation warnings yet (will add in future iteration)

**3. Three Major Prompts Updated**:

**`_generate_chapter_batch()` (lines 648-723)**:
- Replaced "key_events: 8-10 plot beats" with structured "scenes: 2-4 dramatic units"
- Full scene structure specification:
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
- Emphasizes: "COMPLETE DRAMATIC UNITS (1,000-2,000 words when written)"
- Adds: "NOT bullet point summaries - these are FULL SCENES with structure"
- Guidance: "Professional novels use 2-4 full scenes per chapter, NOT 6-10 bullet points"

**`_resume_generation()` (lines 839-881)**:
- Updated to use "scenes" or match previous format for consistency
- Shows full scene structure in examples
- Instructs LLM to match format from partial generation

**`generate_with_competition()` (lines 1499-1525)**:
- Same scene structure as batch generation
- Competition mode will generate scene-based outlines

**4. Method Calls Updated**:
- Line 1242: `events_per_chapter=` → `scenes_per_chapter=`

**5. Comments & Display Updated**:
- All "events" references → "scenes"
- Console: "words/event" → "words/scene"
- Comments: "event count" → "scene count"

**Impact**: The prompts now clearly signal to LLMs: write FULL DRAMATIC SCENES (1,000-2,000 words), NOT bullet point summaries (200-500 words). This is the critical change that should drive word count achievement from 50-60% to 80-100%.

**Status**: ✅ Complete, syntax verified, committed

---

## 🔄 IN PROGRESS: Phase 2 Part 2 - prose.py

### Next Critical File to Update

**Priority 2: prose.py** (~600 lines)
- [ ] Update prose generation prompts (lines ~268-331)
  - Scene-by-scene breakdown
  - 4-part scene structure (setup, development, climax, resolution)
  - SHOW vs TELL examples
  - Words-per-scene targets (not average, but minimum)
- [ ] Update context building
  - Use scene structure from chapters.yaml

**Priority 3: YAML Schema & Loaders**
- [ ] Define new scene structure in schema
- [ ] Update src/utils/yaml_loader.py
  - Support both formats (backward compat)
  - Migration helpers
- [ ] Update Project model if needed

---

## 📋 Remaining Work

### Phase 3: Iteration System
- [ ] `src/generation/iteration/intent.py` - scene terminology
- [ ] `src/generation/iteration/diff.py` - scene diffs
- [ ] `src/generation/iteration/coordinator.py` - scene context

### Phase 4: CLI & Display
- [ ] `src/cli/interactive.py` - status display for scenes
- [ ] Update /status command output
- [ ] Update chapter info display

### Phase 5: Documentation
- [ ] `docs/USER_GUIDE.md` - scenes vs events
- [ ] `docs/DEVELOPER_GUIDE.md` - scene structure
- [ ] `docs/IMPLEMENTATION_STATUS.md` - mark complete
- [ ] `CLAUDE.md` - scene-based system
- [ ] `docs/CHANGELOG.md` - v0.4.0 entry

### Phase 6: Testing
- [ ] Generate test chapter with new system
- [ ] Verify scene structure
- [ ] Measure word count achievement
- [ ] Compare to baseline (50-60% → target 80-100%)

---

## Technical Decisions Made

### 1. Scene Clamping: 2-4 Scenes Per Chapter
**Rationale**: Professional novels use 2-4 scenes per chapter, not 6-10 bullet points.
**Implementation**: Added `max(2, min(4, scenes))` in calculate_chapter_scenes() and distribute_scenes_across_chapters()

### 2. Words-Per-Scene Increase: +35-37%
**Rationale**: Professional scenes are 1,200-2,000 words, not 400-500 word summaries.
**Implementation**: All WORDS_PER_SCENE constants increased proportionally

### 3. Backward Compatibility Required
**Rationale**: Existing projects have "key_events" in chapters.yaml
**Implementation**: Loaders must accept both formats, with deprecation warnings

---

## New Scene Structure (To Be Implemented)

```yaml
scenes:
  - scene: "Fiction Clan's Fall"                    # Scene title
    location: "Fiction territory server rooms"       # Setting
    pov_goal: "Survive and save Joaquin"           # What POV wants
    conflict: "Erasers reverse narrative loops"     # What prevents it
    stakes: "Loss of Fiction archive"              # What's at risk
    outcome: "Joaquin saved, servers destroyed"    # How it resolves
    emotional_beat: "Witnessing Eraser horror"     # Character arc
    sensory_focus:                                   # 2-3 key details
      - "Smoke from burning books"
      - "Screams of trapped minds"
    target_words: 1400                              # Scene target

  - scene: "Betrayal Evidence"
    location: "Periodicals section with David"
    pov_goal: "Find how breach happened"
    conflict: "Footage shows traitor, David breaks"
    stakes: "Alliance trust / David's sanity"
    outcome: "Evidence found but manipulated"
    emotional_beat: "Trust shattered"
    sensory_focus:
      - "EM distortion in footage"
      - "David's fragmented speech"
    target_words: 1200
```

**vs. Old Structure**:
```yaml
key_events:
  - "Fiction Clan's defense fails catastrophically..."
  - "Mara races through collapsing territories..."
  - "Mara finds evidence of betrayal..."
```

**Benefits**:
1. Signals to LLM: "Write full scenes, not summaries"
2. Provides structure for dramatic development
3. Specifies target words per scene (not just chapter total)
4. Includes emotional and sensory guidance
5. Aligns with professional screenplay/novel structure

---

## Expected Results

### Current System (Baseline)
- Target: 3,800 words for chapter with 5 events
- Actual: 2,300 words (60% achievement)
- Actual w/e: 460 words per event
- Quality: 3/5 (rushed micro-scenes)

### Scene-Based System (Goal)
- Target: 3,800 words for chapter with 3 scenes
- Expected: 3,040-3,800 words (80-100% achievement)
- Expected w/s: 1,000-1,400 words per scene
- Quality: 4/5 (full dramatic units)

---

## Files Modified So Far

1. ✅ `src/generation/depth_calculator.py` - Complete refactoring
2. ✅ `docs/wordcount-rethink-2025.md` - Comprehensive analysis (31K words)
3. ✅ `docs/wordcount-implementation-todo.md` - Implementation plan (18K words)
4. ✅ `docs/wordcount-implementation-status.md` - This file

**Total Changes**: 564 lines in depth_calculator.py (122 additions, 121 deletions)

---

## Next Immediate Steps

1. **Update chapters.py prompts** - Replace "key_events" with structured "scenes"
2. **Update prose.py prompts** - Add 4-part scene structure guidance
3. **Test single chapter** - Verify system works end-to-end
4. **Measure results** - Compare to 50-60% baseline
5. **Iterate if needed** - Adjust prompts/structure based on results

**Estimated Remaining Work**: 8-12 hours across chapters.py, prose.py, iteration system, CLI, and docs

---

## References

- **Analysis**: `docs/wordcount-rethink-2025.md`
- **Implementation Plan**: `docs/wordcount-implementation-todo.md`
- **Original Research**: `docs/wordcount.md`, `docs/wordcount-iteration.md`
- **Commit**: 325c75d (depth_calculator refactoring)
