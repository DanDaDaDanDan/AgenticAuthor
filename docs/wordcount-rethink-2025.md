# Word Count System Rethink (2025-10-14)

## Executive Summary

After analyzing `wordcount.md` and `wordcount-iteration.md`, the core problem is clear: **we're asking LLMs to write the wrong thing**. We ask for "key events" (bullet points), which LLMs treat as summaries (200-500w each), when we should be asking for "scenes" (dramatic units, 1,200-2,000w each).

**Current Reality**:
- Target: 950 words per event (w/e)
- Actual: ~500 w/e (50-60% achievement)
- Structure: 4-9 events per chapter = micro-scenes

**Professional Reality**:
- Standard: 2-4 scenes per chapter
- Scene length: 1,200-2,000 words per scene
- Structure: Full dramatic units with setup, conflict, climax, resolution

**The Fix**: Stop fighting LLM instincts. Align our system with professional novel structure AND what LLMs naturally produce.

---

## Table of Contents

1. [Problem Analysis](#problem-analysis)
2. [Root Cause: Terminology & Granularity](#root-cause-terminology--granularity)
3. [Holistic Solution](#holistic-solution)
4. [Implementation Plan](#implementation-plan)
5. [Testing Strategy](#testing-strategy)
6. [Success Criteria](#success-criteria)
7. [Rollout Plan](#rollout-plan)

---

## Problem Analysis

### Current System Performance (pechter data)

| Metric | Current | Target | Achievement |
|--------|---------|--------|-------------|
| Average w/e | ~500 | ~950 | 53% |
| Chapter length | 2,300 | 3,800 | 61% |
| Events/chapter | 4-9 | 4-5 | Exceeds (bad) |
| Total word count | 34,775 | 51,680 | 67% |

### The Paradox

**Chapter 3 succeeded (109% of target)** but for the wrong reasons:
- Had 9 events (way too many)
- Each became a micro-scene (~400w)
- LLM couldn't skip beats, so wrote more
- Result: Hit word count but with shallow micro-scenes, not deep full scenes

**Chapters with 3-5 events performed best** (64-69% achievement), but still fell short.

### Why 900 w/e Fails

**The question "Is 900 w/e achievable?" is wrong**. Here's why:

1. **LLMs treat events as summaries**
   - "key_events" in bullet points signal "list the beats"
   - Each bullet becomes a paragraph (200-500w)
   - 900w for a bullet point feels excessive to the LLM

2. **Professional scenes are 1,200-2,000w**
   - Setup (300-500w)
   - Conflict development (500-1,000w)
   - Climax (200-400w)
   - Resolution/transition (200-300w)
   - Total: 1,200-2,200w naturally

3. **We're fighting LLM instincts**
   - LLMs want to write ~2,500w chapters
   - With 4-5 events, that's 500-625w each
   - We're asking for 900w each = 3,600-4,500w chapters
   - LLM compromises: writes usual 2,500w, divides by events = 500w each

### Should We Have Fewer Events?

**YES**. Emphatically.

**Current**: 4-9 events per chapter
**Professional**: 2-4 scenes per chapter
**Impact**:
- 92K novel ÷ 1,200 w/scene = 77 scenes ÷ 23 chapters = **3.3 scenes per chapter**
- Aligns with professional structure
- Each scene gets proper development (1,200-2,000w)
- LLM can write full dramatic units instead of summary paragraphs

### Should We Have More Chapters?

**Analysis**:

**Current calculation** (depth_calculator.py:108):
```python
chapter_count = target_words / CHAPTER_LENGTH_TARGETS[form]
# For novels: target_words / 4,000
# 92K novel = 23 chapters
```

**With scene-based approach**:
- Option A: Keep 23 chapters, reduce to 3-4 scenes each = fuller scenes
- Option B: Increase to 30 chapters, keep 2-3 scenes each = more frequent chapter breaks

**Recommendation**: **Option A** (keep current chapter counts)
- 2,500-5,000 words per chapter is professional standard
- Reader psychology: 10-20 minute reading sessions
- Fewer chapter transitions = better narrative flow
- Easier for LLM to maintain context within chapter

---

## Root Cause: Terminology & Granularity

### The Real Problem

**"key_events" vs "scenes"**

The term "key_events" is semantically wrong for what we want:

❌ **Current: "key_events"**
```yaml
key_events:
  - Fiction Clan's defense fails catastrophically
  - Mara races through collapsing territories
  - Mara finds evidence of betrayal
  - Chen organizes desperate war council
  - Mara neural-loads SOPHIA
```

**What this signals to LLM**:
- "List the plot points"
- "Summarize what happens"
- Each bullet = 1-2 paragraphs
- Focus on WHAT not HOW

✅ **Proposed: "scenes"**
```yaml
scenes:
  - scene: Fiction Clan's Fall
    location: Fiction territory server rooms
    pov_goal: Survive and save Joaquin
    conflict: Narrative loops trap defenders; Burn attacks
    stakes: Fiction Clan's millennia of stories at risk
    outcome: Joaquin saved but servers destroyed
    emotional_beat: Mara witnesses horrifying power of Erasers
    target_words: 1,400

  - scene: Betrayal Discovered
    location: Periodicals section
    pov_goal: Find evidence of how breach happened
    conflict: Security footage shows Reference Clan traitor
    stakes: Alliance trust shattered
    outcome: Evidence found but manipulated; David breaks down
    emotional_beat: Mara questions who to trust
    target_words: 1,200
```

**What this signals to LLM**:
- "Write a full dramatic scene"
- Each scene is a complete unit with structure
- 1,200-1,400 words is reasonable for a scene
- Focus on SHOWING not TELLING

### Cognitive Load

**Current: 9 events** (Chapter 3)
- Overwhelming to track
- Hard to see "big picture"
- Each event underdeveloped

**Proposed: 3-4 scenes**
- Easy to understand structure
- Each scene = clear dramatic unit
- Room for full development

---

## Holistic Solution

### 1. Terminology Change

**Global rename**: "key_events" → "scenes"

**Impact**:
- chapters.yaml schema change
- Chapter generation prompts
- Prose generation prompts
- All documentation

### 2. Structural Change

**Reduce scene counts per chapter**:

| Form | Current Events/Ch | Proposed Scenes/Ch |
|------|-------------------|--------------------|
| Novel | 4-5 | 3-4 |
| Novella | 3-4 | 2-3 |
| Short story | 1-2 | 1-2 |

**Increase words per scene**:

| Form | Pacing | Current w/e | Proposed w/scene | Increase |
|------|--------|-------------|------------------|----------|
| Novel | Fast | 800 | 1,100 | +37% |
| Novel | Moderate | 950 | 1,300 | +37% |
| Novel | Slow | 1,200 | 1,600 | +33% |

**Math check** (92K novel, moderate pacing):
- Current: 92K ÷ 950 w/e = 97 events ÷ 23 chapters = 4.2 events/ch
- Proposed: 92K ÷ 1,300 w/scene = 71 scenes ÷ 23 chapters = 3.1 scenes/ch ✅

### 3. Scene Structure in Outlines

Add structured scene information to chapter outlines:

**New schema**:
```yaml
chapters:
  - number: 3
    title: "The Splintering"
    pov: Mara
    act: Act I
    summary: [chapter summary]
    scenes:  # renamed from key_events
      - scene: Fiction Clan's Fall
        location: Fiction territory server rooms
        pov_goal: Survive the attack and save Joaquin
        conflict: Erasers reverse Joaquin's narrative loops
        stakes: Loss of Fiction Clan's entire archive
        outcome: Joaquin saved but servers destroyed
        emotional_beat: Witnessing Eraser power firsthand
        sensory_focus: [smoke, screaming servers, taste of burnt imagination]
        target_words: 1,400

      - scene: Betrayal Evidence
        location: Periodicals section with David
        pov_goal: Discover how the breach happened
        conflict: Footage shows Reference Clan traitor
        stakes: Alliance trust / David's sanity
        outcome: Evidence found but compromised
        emotional_beat: Trust shattered, David breaks
        sensory_focus: [electromagnetic distortion, David's fragmented speech]
        target_words: 1,200

      - scene: Unity or Death
        location: Great Hall war council
        pov_goal: Unite the clans before it's too late
        conflict: Brothers' hatred paralyzes response
        stakes: Everyone dies unless they work together
        outcome: Mara makes desperate choice to neural-load SOPHIA
        emotional_beat: From observer to actor
        sensory_focus: [crowd noise, Chen's authority cracking]
        target_words: 1,200

    character_developments: [...]
    relationship_beats: [...]
    word_count_target: 3,800
```

**Benefits**:
1. LLM understands each scene is a FULL dramatic unit
2. Clear structure (goal → conflict → outcome)
3. Emotional beats make scenes feel complete
4. Target words per scene (not just total)

### 4. Prompt Changes

**A. Chapter Generation Prompt** (chapters.py)

Current approach:
```
For each chapter, include:
- key_events: List 4-5 major plot points
```

Proposed approach:
```
For each chapter, create 3-4 SCENES (not events, not bullet points).

Each scene must be a COMPLETE DRAMATIC UNIT with:
- scene: Brief scene title (e.g., "The Confrontation")
- location: Physical setting
- pov_goal: What the POV character wants in this scene
- conflict: What prevents them from getting it
- stakes: What happens if they fail
- outcome: How the scene ends (success, failure, complication)
- emotional_beat: How POV character changes/feels by scene end
- sensory_focus: 2-3 key sensory details to emphasize
- target_words: 1,200-1,800 (varies by importance)

CRITICAL:
- A SCENE is not a plot summary
- A SCENE is a full dramatic unit with beginning, middle, end
- Professional novels have 2-4 scenes per chapter, not 6-10 bullet points
- Each scene should feel like a complete mini-story

Example GOOD scene structure:
✓ "The Market Betrayal"
  - Character arrives seeking information (goal)
  - Contact refuses to talk (conflict)
  - Character must decide: bribe, threaten, or walk away (stakes)
  - Character threatens, contact reveals info but warns of consequences (outcome)
  - Character feels compromised but empowered (emotional)

Example BAD event structure:
✗ "Character goes to market and gets information"
  (This is a plot summary, not a scene)
```

**B. Prose Generation Prompt** (prose.py)

Current approach:
```
Generate 3,800 words for Chapter 3 with 5 key events.
Average: ~760 words per event.

SCENE DEVELOPMENT:
- Setup scenes: 300-500 words
- Standard scenes: 600-900 words
- Climactic scenes: 1,000-1,500 words
```

Proposed approach:
```
Generate full prose for Chapter 3: "The Splintering"

TARGET: 3,800 words across 3 SCENES

SCENES (from outline):

Scene 1: "Fiction Clan's Fall" (1,400 words)
- Location: Fiction territory server rooms
- Goal: Mara must survive attack and save Joaquin
- Conflict: Erasers reverse narrative loops, trap defenders
- Outcome: Joaquin saved but Fiction archive destroyed
- Emotional: Witnessing true horror of Eraser power
- Sensory: Smoke, screaming servers, taste of burnt imagination

Scene 2: "Betrayal Evidence" (1,200 words)
- Location: Periodicals section with David
- Goal: Find out how breach happened
- Conflict: Security footage shows Reference traitor; David can't process
- Outcome: Evidence found but manipulated; David collapses
- Emotional: Mara's trust in alliance shattered
- Sensory: EM distortion, David's fragmented speech

Scene 3: "Unity or Death" (1,200 words)
- Location: Great Hall war council
- Goal: Unite clans before Erasers arrive
- Conflict: Brothers' hatred paralyzes everyone
- Outcome: Mara neural-loads SOPHIA out of desperation
- Emotional: Transformation from observer to actor
- Sensory: Crowd panic, Chen's failing authority

CRITICAL SCENE STRUCTURE:

Each scene must follow dramatic structure (NOT summary):

1. SETUP (20-25% of scene: 240-350 words for 1,200w scene)
   - Establish location with sensory details
   - POV character's immediate state (physical, emotional)
   - Introduce the goal/want for this scene
   - Create atmosphere and hook

2. DEVELOPMENT (40-50% of scene: 480-600 words)
   - Show the conflict unfolding
   - Dialogue with subtext and reactions
   - Action with consequences
   - Internal thoughts and processing
   - Sensory immersion
   - Rising tension

3. CLIMAX (15-20% of scene: 180-240 words)
   - Peak moment of decision or revelation
   - Emotional intensity at highest
   - Key action or dialogue
   - Turning point

4. RESOLUTION/TRANSITION (15-20% of scene: 180-240 words)
   - Immediate aftermath
   - Emotional/mental state after climax
   - Bridge to next scene
   - New question or complication raised

SHOWING vs TELLING:

✓ SHOW: "Joaquin's fingers blurred across the terminal, weaving narrative threads into a trap. The Eraser unit stepped into the pattern—and smiled. The threads reversed. Screams erupted behind Mara as three defenders collapsed, eyes rolling back, mouths forming words from stories they'd never read."

✗ TELL: "Joaquin tried to trap the Erasers but it was reversed and three defenders were trapped instead."

TARGET WORD COUNTS ARE MINIMUM:
- Scene 1: minimum 1,400 words (can go to 1,600)
- Scene 2: minimum 1,200 words (can go to 1,400)
- Scene 3: minimum 1,200 words (can go to 1,400)
- Total chapter: 3,800-4,400 words acceptable

Each scene is a COMPLETE DRAMATIC UNIT. Write them fully.
```

### 5. Code Changes Required

**A. depth_calculator.py**

```python
# Line 29-62: Rename WORDS_PER_EVENT → WORDS_PER_SCENE
WORDS_PER_SCENE = {
    'novel': {
        'fast': (900, 1300, 1100),      # was (650, 950, 800)
        'moderate': (1100, 1600, 1300),  # was (800, 1100, 950)
        'slow': (1400, 2000, 1600)       # was (1000, 1400, 1200)
    },
    # ... similar increases for all forms
}

# Line 315-391: Update calculate_structure()
def calculate_structure(target_words, pacing, length_scope):
    # 1. Detect form
    form = detect_form(target_words)

    # 2. Get baseline words per SCENE (renamed)
    base_w_per_scene = get_base_words_per_scene(form, pacing)

    # 3. Calculate total SCENES (not events)
    total_scenes = target_words / base_w_per_scene

    # 4. Calculate chapter count (unchanged)
    chapter_count = calculate_chapter_count(target_words, form)

    # 5. Calculate average SCENES per chapter
    avg_scenes_per_chapter = total_scenes / chapter_count

    # 6. Clamp to 2-4 scenes per chapter
    if avg_scenes_per_chapter < 2:
        # Need more chapters or accept very long scenes
        chapter_count = total_scenes / 2
    elif avg_scenes_per_chapter > 4:
        # Too many scenes, reduce total or add chapters
        total_scenes = chapter_count * 4

    return {
        'form': form,
        'base_w_per_scene': base_w_per_scene,
        'total_scenes': total_scenes,
        'chapter_count': chapter_count,
        'avg_scenes_per_chapter': avg_scenes_per_chapter,
    }
```

**B. chapters.yaml schema**

```yaml
# OLD:
chapters:
  - number: 1
    key_events:  # ❌
      - Event 1
      - Event 2

# NEW:
chapters:
  - number: 1
    scenes:  # ✅
      - scene: Scene title
        location: Where
        pov_goal: What character wants
        conflict: What prevents it
        stakes: What's at risk
        outcome: How it ends
        emotional_beat: Character arc
        sensory_focus: [detail1, detail2]
        target_words: 1200
```

**C. Migration for existing projects**

```python
# In Project class
def migrate_events_to_scenes(self):
    """Convert old key_events to new scenes structure."""
    chapters_yaml = self.get_chapters_yaml()
    if not chapters_yaml:
        return

    for chapter in chapters_yaml.get('chapters', []):
        if 'key_events' in chapter:
            # Convert to scenes
            scenes = []
            for event in chapter['key_events']:
                scenes.append({
                    'scene': self._extract_scene_title(event),
                    'description': event,  # Old event text
                    'target_words': 1200  # Default
                })
            chapter['scenes'] = scenes
            del chapter['key_events']

    self.save_chapters_yaml(chapters_yaml)
```

---

## Implementation Plan

### Phase 1: Core System Changes (Week 1)

**Priority 1: Update depth_calculator.py**

- [ ] Rename all `words_per_event` → `words_per_scene`
- [ ] Update WORDS_PER_SCENE constants (increase by ~35%)
- [ ] Update calculate_structure() to use scenes
- [ ] Update all method names: `get_base_words_per_event()` → `get_base_words_per_scene()`
- [ ] Update act multipliers (may need adjustment)
- [ ] Add scene count clamping (2-4 scenes per chapter)

**Priority 2: Update chapters.yaml schema**

- [ ] Define new scene structure (scene, location, pov_goal, conflict, stakes, outcome, emotional_beat, sensory_focus, target_words)
- [ ] Update YAMLLoader to handle new structure
- [ ] Create migration utility for existing projects
- [ ] Update validation logic

**Priority 3: Update chapter generation prompts**

- [ ] Rewrite scene generation guidance in chapters.py
- [ ] Add scene structure examples
- [ ] Emphasize "SCENE not EVENT" language
- [ ] Update context building for scene data

### Phase 2: Prose Generation Updates (Week 1-2)

**Priority 4: Update prose generation prompts**

- [ ] Rewrite prose.py scene development section
- [ ] Add 4-part scene structure (setup, development, climax, resolution)
- [ ] Update word count guidance (1,200-1,600 per scene)
- [ ] Add SHOW vs TELL examples
- [ ] Remove event-based language entirely

**Priority 5: Update iteration system**

- [ ] Update intent analyzer to understand "scene" vs "event"
- [ ] Update diff generation for scene structure
- [ ] Update patch mode for scene edits
- [ ] Test iteration with new structure

### Phase 3: Testing & Validation (Week 2)

**Priority 6: Single-chapter iterative testing**

See detailed testing strategy below.

**Priority 7: Multi-chapter validation**

- [ ] Test on complete short project (5-10 chapters)
- [ ] Measure achievement rates
- [ ] Compare to baseline data
- [ ] Adjust if needed

### Phase 4: Documentation & Migration (Week 2-3)

**Priority 8: Update all documentation**

- [ ] Update IMPLEMENTATION_STATUS.md
- [ ] Update USER_GUIDE.md (explain scenes vs events)
- [ ] Update DEVELOPER_GUIDE.md
- [ ] Create MIGRATION_GUIDE.md for existing projects
- [ ] Update CHANGELOG.md

**Priority 9: Backward compatibility**

- [ ] Ensure old projects with key_events still work
- [ ] Add deprecation warnings
- [ ] Provide migration command: `/migrate scenes`

---

## Testing Strategy

### Single-Chapter Iterative Test (Most Critical)

**Goal**: Validate that scene-based approach achieves 80-100% of target word count with better quality.

**Test Subject**: Create fresh chapter based on pechter Chapter 3 outline

**Test Matrix**:

| Test | Structure | Scenes | Target w/s | Chapter Target | Changes |
|------|-----------|--------|------------|----------------|---------|
| A. Baseline | key_events | 5 events | 950 w/e | 4,750w | (control - current system) |
| B. Scenes-Minimal | scenes | 3 scenes | 1,267 w/s | 3,800w | Rename only, minimal structure |
| C. Scenes-Structured | scenes | 3 scenes | 1,267 w/s | 3,800w | Full structure (goal/conflict/outcome) |
| D. Scenes-Detailed | scenes | 3 scenes | 1,267 w/s | 3,800w | + sensory/emotional beats + prose prompt update |

**Detailed Test D (Most Promising)**:

1. **Rewrite Chapter 3 outline** with 3 scenes:
   - Scene 1: "Fiction Clan's Fall" (1,400w)
   - Scene 2: "Betrayal and Breakdown" (1,200w) [combine betrayal + David]
   - Scene 3: "Unity or Death" (1,200w)
   - Total: 3,800w

2. **Use full scene structure**:
   ```yaml
   scenes:
     - scene: Fiction Clan's Fall
       location: Fiction territory server rooms
       pov_goal: Survive attack and save Joaquin
       conflict: Erasers reverse narrative loops, defenders trapped
       stakes: Millennia of stories lost forever
       outcome: Joaquin saved unconscious, servers destroyed
       emotional_beat: Mara witnesses true horror of Eraser power
       sensory_focus:
         - Smoke from burning books creating taste of destroyed imagination
         - Screams of defenders trapped in recursive stories
         - Heat from exploding servers
       target_words: 1400
   ```

3. **Update prose prompt** with 4-part scene structure guidance

4. **Generate and measure**:
   - Total word count
   - Words per scene
   - Achievement percentage
   - Scene structure quality (manual review)
   - Reading quality (does it feel like a novel?)

**Success Criteria for Test D**:
- 80-100% word count achievement (3,040-3,800w minimum)
- Each scene 1,000-1,600 words (average 1,200+)
- Clear scene structure visible
- Feels like published novel quality

**If Test D succeeds**: Move to multi-chapter validation
**If Test D fails**: Analyze why, adjust, retest

### Testing Protocol

```markdown
## Test Execution Checklist

### Setup
- [ ] Clone pechter → wordcount-test-scenes
- [ ] Back up original Chapter 3 outline
- [ ] Create 4 test variations (A, B, C, D)

### For Each Test (A, B, C, D)
- [ ] Update chapters.yaml with test structure
- [ ] Generate prose
- [ ] Measure word count (total and per scene)
- [ ] Calculate achievement percentage
- [ ] Read and qualitatively assess (1-5 scale)
- [ ] Note what worked/didn't work
- [ ] Save prose to test archive

### Data Collection
- [ ] Create comparison table
- [ ] Document prose samples (first 200w of each scene)
- [ ] Note LLM behavior patterns
- [ ] Identify best approach

### Analysis
- [ ] Which test achieved best word count?
- [ ] Which test had best scene structure?
- [ ] Which test felt most like published novel?
- [ ] What patterns emerged?
- [ ] Recommendations for final implementation

### Documentation
- [ ] Update wordcount-iteration.md with results
- [ ] Create decision record
- [ ] Propose final system changes
```

---

## Success Criteria

### Quantitative Metrics

| Metric | Baseline | Target | Stretch |
|--------|----------|--------|---------|
| Word count achievement | 50-60% | 80-100% | 95-105% |
| Words per scene (actual) | ~500 w/e | 1,000-1,400 w/s | 1,200-1,600 w/s |
| Scenes per chapter | 4-9 events | 3-4 scenes | 3 scenes |
| Chapter word count | 2,300 | 3,400-4,200 | 3,800-4,000 |

### Qualitative Metrics

**Scene Structure** (1-5 scale):
- Clear beginning, middle, end
- Goal/conflict/outcome visible
- Emotional arc present
- Sensory details integrated
- Smooth transitions

**Reading Quality** (1-5 scale):
- Feels like published novel
- Scenes are fully developed (not rushed)
- Dialogue is realistic and revealing
- Pacing varies appropriately
- "SHOWING" not "TELLING"

**Target**: 4/5 or higher on both metrics

---

## Rollout Plan

### Stage 1: Testing (Week 2)
- Run single-chapter iterative tests
- Validate best approach
- Document findings
- Get user approval for system changes

### Stage 2: Core Implementation (Week 3)
- Implement depth_calculator.py changes
- Update schema and loaders
- Update prompts
- Test on new projects only

### Stage 3: Migration (Week 4)
- Add migration utilities
- Test migration on existing projects
- Update all documentation
- Add deprecation warnings for key_events

### Stage 4: Production (Week 5+)
- Release to main
- Monitor user feedback
- Collect data on new achievement rates
- Iterate if needed

---

## Open Questions

### 1. Act-Based Multipliers

**Current**:
- Act I: 0.95× w/e (efficient setup)
- Act II: 1.00× w/e (baseline)
- Act III: 1.35× w/e (emotional depth)

**Question**: Do these still apply with scenes?

**Hypothesis**: Yes, but may need adjustment:
- Act I: 0.90× w/s (setup scenes shorter)
- Act II: 1.00× w/s (baseline)
- Act III: 1.25× w/s (climax scenes longer, but not as extreme)

**Resolution**: Test during validation phase

### 2. Event Count Variation

**Current**: 3-5 events specified, but LLM generates 6-10

**With scenes**: Will LLM respect 3-4 scene count better?

**Hypothesis**: Yes, because:
- Scenes have more structure (harder to subdivide)
- Fewer to track (3 vs 9)
- Professional novels have 2-4 scenes (LLM training data)

**Resolution**: Monitor during testing

### 3. Pacing Terminology

**Current**: fast, moderate, slow

**Question**: Should this change to align with scenes?

**Options**:
- Keep same (fast/moderate/slow)
- Change to scene-based (lean/standard/rich)
- Change to reader-based (quick/immersive/literary)

**Recommendation**: Keep current terminology, update internal calculations

### 4. Short Form Stories

**Current**: 1-2 events per chapter for short stories

**With scenes**: Still 1-2 scenes?

**Analysis**:
- Flash fiction (1,000w): 1 scene makes sense
- Short story (7,500w): 3-5 scenes total across 2-3 chapters (1-2 per chapter) ✓

**Resolution**: Keep current scene counts for short form

---

## Risk Assessment

### High Risk

**Risk**: Scene-based system still achieves only 60-70%
**Mitigation**: Testing phase validates before full implementation
**Fallback**: Hybrid approach (keep events, add scene annotations)

### Medium Risk

**Risk**: Breaking changes affect existing projects
**Mitigation**: Migration utilities + backward compatibility
**Fallback**: Deprecation period, both systems coexist

### Low Risk

**Risk**: Users don't understand "scenes" terminology
**Mitigation**: Clear documentation + examples
**Fallback**: Offer both "scenes" and "events" with guidance

---

## Next Steps

1. **Review this document** with user
2. **Get approval** for testing approach
3. **Execute Test D** (scene-based with full structure)
4. **Analyze results** and decide on implementation
5. **Begin Phase 1** if testing succeeds

---

## Appendix A: Scene Examples

### Example 1: Fantasy Scene Structure

```yaml
scene: The Throne Room Confrontation
location: King's throne room, late afternoon, amber light through stained glass
pov_goal: Convince the king to send troops to the northern border
conflict: King distrusts protagonist due to past betrayal, advisor sabotages
stakes: If no troops sent, northern villages will be overrun by week's end
outcome: King refuses, but queen privately agrees to send her personal guard
emotional_beat: Protagonist goes from hopeful to defeated to grateful
sensory_focus:
  - Cold marble under boots contrasts with warm sunlight
  - Advisor's perfume sickly sweet, cloying
  - King's voice echoes in vast chamber
target_words: 1,500
```

**Generated prose structure**:
- Setup (375w): Arrival, throne room description, protagonist's nervousness
- Development (750w): Presentation of evidence, advisor's interruptions, king's objections, dialogue escalates
- Climax (225w): King stands and refuses, room goes silent
- Resolution (150w): Queen's subtle nod as protagonist leaves, seed of hope

### Example 2: Thriller Scene Structure

```yaml
scene: The Parking Garage Chase
location: Underground parking garage, level P4, concrete and shadows
pov_goal: Reach the car before the assassin catches up
conflict: Assassin has clear sightlines, protagonist is injured
stakes: Death or capture (worse than death)
outcome: Protagonist reaches car but assassin shoots out tire, must flee on foot
emotional_beat: Controlled fear transforms to wild panic
sensory_focus:
  - Fluorescent lights flickering, creating strobe effect
  - Echo of footsteps amplified by concrete
  - Gasoline smell mixed with fresh blood
target_words: 1,300
```

**Generated prose structure**:
- Setup (260w): Stumbling out of elevator, seeing car across garage, wound check
- Development (650w): Running between cars, assassin's footsteps, hiding behind pillar, dash for car, fumbling with keys
- Climax (195w): Starting engine, tire explosion, window shatters
- Resolution (195w): Abandoning car, running for stairs, assassin's laughter echoes

---

## Appendix B: Prompt Comparison

### Current Prompt (chapters.py)

```
For each chapter, include:
- key_events: List of major plot points (4-5 events)
  * Each event should be specific and complete
  * Events will be developed during prose generation
```

### Proposed Prompt

```
For each chapter, create 3-4 SCENES (not bullet points, not plot summaries).

A SCENE is a complete dramatic unit that includes:

Required fields:
- scene: Descriptive title (e.g., "The Throne Room Confrontation")
- location: Physical setting with relevant details
- pov_goal: What POV character wants in this specific scene
- conflict: What prevents them from achieving the goal
- stakes: Immediate consequences if they fail
- outcome: How the scene resolves (success/failure/complication)
- emotional_beat: How POV character's emotional state changes
- sensory_focus: 2-3 sensory details to emphasize (array)
- target_words: 1,200-1,800 (varies by scene importance)

Think like a novelist:
- Each scene is a mini-story with beginning, middle, end
- Scenes are where character change happens
- Professional novels have 2-4 scenes per chapter
- A scene is NOT "Character does X" (that's a plot summary)
- A scene IS "Character enters X wanting Y, but Z prevents it, so..."

Example structure:
✓ Good scene: "The Market Betrayal"
  - Aria arrives at night market seeking her informant (goal)
  - Informant is terrified, refuses to talk, others are listening (conflict)
  - If Aria pushes, informant might be killed; if she walks away, she loses only lead (stakes)
  - Aria threatens violence, informant whispers location then flees into crowd (outcome)
  - Aria feels powerful but realizes she's becoming the thing she hates (emotional)
  - Sensory: Spice smell mixing with fear-sweat, distant drums, cobblestones slick with rain

✗ Bad event: "Aria goes to market and gets information from informant"
  (This is a plot summary, would generate 200-300 words of telling, not showing)

Generate 3-4 scenes per chapter using this structure.
```

---

## Appendix C: Code Migration Checklist

### Files to Update

**Core Generation**:
- [ ] `src/generation/depth_calculator.py` - Rename all event → scene
- [ ] `src/generation/chapters.py` - Update prompts and schema
- [ ] `src/generation/prose.py` - Update prompts
- [ ] `src/models/project.py` - Schema handling

**Iteration System**:
- [ ] `src/generation/iteration/intent.py` - Scene terminology
- [ ] `src/generation/iteration/diff.py` - Scene diffs
- [ ] `src/generation/iteration/coordinator.py` - Scene context

**CLI**:
- [ ] `src/cli/interactive.py` - Status display
- [ ] `src/cli/command_completer.py` - Autocomplete

**Utilities**:
- [ ] `src/utils/yaml_loader.py` - Schema validation
- [ ] `src/utils/migration.py` - Create new migration utility

**Documentation**:
- [ ] `docs/IMPLEMENTATION_STATUS.md`
- [ ] `docs/USER_GUIDE.md`
- [ ] `docs/DEVELOPER_GUIDE.md`
- [ ] `docs/CHANGELOG.md`
- [ ] `CLAUDE.md`
- [ ] `README.md`

### Testing Files

- [ ] Create `tests/test_scenes.py` - Test scene structure
- [ ] Update `tests/test_depth_calculator.py` - Test calculations
- [ ] Create integration tests for scene generation

---

## Document History

- **2025-10-14**: Initial comprehensive rethink based on wordcount.md and wordcount-iteration.md analysis
- **Author**: Claude (AI Assistant)
- **Status**: Draft - Awaiting User Review & Approval
