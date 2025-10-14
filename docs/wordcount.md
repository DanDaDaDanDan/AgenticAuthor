# Word Count System Documentation

This document explains how AgenticAuthor calculates and distributes word counts from the form level down to individual prose generation, why it often achieves only 50-60% of target word counts, and how published novels actually work.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [The Generation Pipeline](#the-generation-pipeline)
3. [Code Implementation](#code-implementation)
4. [The Problem](#the-problem)
5. [Industry Research](#industry-research)
6. [Case Studies](#case-studies)
7. [Recommendations](#recommendations)

---

## System Architecture

### Core Concepts

AgenticAuthor uses a **hierarchical word count system** based on two independent axes:

1. **Form** (complexity axis) - Determines event count
   - flash_fiction, short_story, novelette, novella, novel, epic, series
   - Each form has a word count range (e.g., novel: 50K-110K)
   - Determines how many events the story needs

2. **Pacing** (depth axis) - Determines words per event
   - fast, moderate, slow
   - Determines how deeply each event is developed
   - Independent of form

**Formula**: `total_words = events × words_per_event`

### Words Per Event by Form and Pacing

From `depth_calculator.py:29-62`:

```python
WORDS_PER_EVENT = {
    'novel': {
        'fast': (650, 950, 800),        # (min, max, typical)
        'moderate': (800, 1100, 950),
        'slow': (1000, 1400, 1200)
    },
    'novella': {
        'fast': (600, 850, 700),
        'moderate': (750, 950, 850),
        'slow': (900, 1150, 1000)
    },
    # ... etc
}
```

**Example**: Novel with moderate pacing = **950 words per event** (baseline)

### Act-Aware Multipliers

The system adjusts both event counts and words-per-event based on three-act structure:

**Event Distribution** (`depth_calculator.py:75-93`):
- Act I: 1.3× events (more setup, world-building)
- Act II: 1.0× events (standard development)
- Act III: 0.7× events (focused climax)

**Words-Per-Event Multipliers** (`depth_calculator.py:95-113`):
- Act I: 0.95× w/e (efficient setup)
- Act II: 1.00× w/e (baseline)
- Act III: 1.35× w/e (deeper emotional intensity)

**Why Act III Gets Deeper**: Fewer events but more emotional weight. A climactic confrontation needs 2,000+ words to land properly, while early exposition can be 800 words.

---

## The Generation Pipeline

### Step 1: Determine Total Words

**Priority order** (`chapters.py:1082-1103`):
1. User-specified: `/generate chapters 95000`
2. Stored value: `chapters.yaml → metadata → target_word_count`
3. Calculated from taxonomy: `length_scope + genre`
   - Example: novel + fantasy = 80K × 1.15 = 92,000 words

**Genre Modifiers** (`depth_calculator.py:129-143`):
- Fantasy/Sci-Fi: +15% (worldbuilding)
- Mystery/Thriller: -5% (tight pacing)
- Horror: -8% (tension/pace)
- YA: -15% (younger readers)
- Literary: +10% (deeper prose)

### Step 2: Calculate Story Structure

From `depth_calculator.py:315-391`:

```python
def calculate_structure(target_words, pacing, length_scope):
    # 1. Detect form from word count
    form = detect_form(target_words)  # e.g., 92K → 'novel'

    # 2. Get baseline words per event
    base_we = get_base_words_per_event(form, pacing)  # 950 w/e

    # 3. Calculate total events
    total_events = target_words / base_we  # 92K ÷ 950 = 97 events

    # 4. Calculate chapter count
    chapter_length_target = CHAPTER_LENGTH_TARGETS[form]  # 4000 for novels
    chapter_count = target_words / chapter_length_target  # 92K ÷ 4000 = 23 chapters
    chapter_count = max(15, chapter_count)  # Minimum 15 for novels

    # 5. Calculate average events per chapter
    avg_events_per_chapter = total_events / chapter_count  # 97 ÷ 23 = 4.2

    return {
        'form': 'novel',
        'base_we': 950,
        'total_events': 97,
        'chapter_count': 23,
        'avg_events_per_chapter': 4.2,
        # ...
    }
```

### Step 3: Distribute Events Across Chapters

From `depth_calculator.py:458-495`:

```python
def distribute_events_across_chapters(total_events, chapter_count, form):
    # Apply act-based multipliers
    distribution = []
    for chapter_num in range(1, chapter_count + 1):
        act = get_act_for_chapter(chapter_num, chapter_count)

        # Act I chapters get 1.3× events, Act III get 0.7× events
        multiplier = ACT_EVENT_MULTIPLIERS[form][act]
        events = avg_events * multiplier

        distribution.append(max(3, int(events)))

    # Normalize to hit exact total
    return distribution  # e.g., [5, 5, 5, 4, 4, 4, 3, 3, 3, ...]
```

**Example for 23-chapter novel with 97 events**:
- Chapters 1-6 (Act I): 5-6 events each
- Chapters 7-17 (Act II): 4 events each
- Chapters 18-23 (Act III): 3 events each

### Step 4: Calculate Per-Chapter Word Targets

From `depth_calculator.py:427-455`:

```python
def calculate_chapter_word_target(chapter_number, total_chapters, event_count, form, pacing):
    # Get act-aware words per event
    act = get_act_for_chapter(chapter_number, total_chapters)
    act_we = get_act_words_per_event(form, pacing, act)

    # Example:
    # Chapter 3 (Act I): 950 × 0.95 = 903 w/e
    # Chapter 12 (Act II): 950 × 1.00 = 950 w/e
    # Chapter 21 (Act III): 950 × 1.35 = 1,283 w/e

    return event_count * act_we
```

**Result**:
- Chapter 3: 5 events × 903 w/e = **4,515 words**
- Chapter 12: 4 events × 950 w/e = **3,800 words**
- Chapter 21: 3 events × 1,283 w/e = **3,849 words**

### Step 5: Generate Chapter Outlines (LLM)

Prompt from `chapters.py:621-698`:

```
STORY DEPTH ARCHITECTURE (ACT-AWARE):
This story varies depth by act position to create narrative rhythm.
Each chapter's word target is calculated using act-specific words-per-event:

Chapter 3 (Act I): 5 events × 903 w/e = 4,515 words
Chapter 12 (Act II): 4 events × 950 w/e = 3,800 words
Chapter 21 (Act III): 3 events × 1,283 w/e = 3,849 words

TASK:
Generate comprehensive chapter outlines, numbered 1 through 23.

For each chapter, follow the EXACT specifications above:
- key_events: MATCH THE EVENT COUNT specified above for this chapter
  * Each event should be specific and complete
  * Events will be developed with act-appropriate depth during prose generation
  * Act III events need MORE depth even though there are fewer of them
- word_count_target: USE THE EXACT TARGET from the spec above
```

**What the LLM generates**:
```yaml
- number: 3
  title: "The Splintering"
  key_events:
    - The Fiction Clan's desperate defense fails catastrophically...
    - Mara races through the collapsing clan territories...
    - In the Periodicals section, Mara finds evidence of betrayal...
    - Chen organizes a desperate war council...
    - As first Eraser breach teams enter, Mara neural-loads SOPHIA...
  word_count_target: 4515
```

**The Problem**: The LLM often ignores the event count and generates 6-10 events instead of 5.

### Step 6: Generate Prose (LLM)

Prompt from `prose.py:268-331`:

```
Generate full prose for a chapter using this self-contained story context.

TASK:
Generate 4,515 words of polished narrative prose for:
- Chapter 3: "The Splintering"
- 5 key events

SCENE DEVELOPMENT (CRITICAL - ACT-AWARE):
You have 5 key events to cover in 4,515 words.
This means AVERAGE of ~903 words per event.

[Provides guidance on scene types: setup, standard, climactic]

TARGET: 4,515 words total = 5 events × ~903 w/e average
```

**What the LLM generates**: Often 2,500-3,000 words (55-66% of target)

---

## Code Implementation

### Key Files

1. **`src/generation/depth_calculator.py`** (564 lines)
   - All word count calculations
   - Form detection, event distribution, act multipliers
   - Scene depth guidance

2. **`src/generation/chapters.py`** (1,300+ lines)
   - Multi-phase chapter generation
   - Calls DepthCalculator for structure
   - Builds prompts with act-aware specifications

3. **`src/generation/prose.py`** (600+ lines)
   - Sequential chapter prose generation
   - Loads chapters.yaml (self-contained format)
   - Uses word_count_target from outlines

### Critical Methods

**`DepthCalculator.calculate_structure()`** - `depth_calculator.py:315-391`
- Input: total_words, pacing, length_scope
- Output: Complete structure dict (form, events, chapters, base_we, etc.)
- Called by: `chapters.py:1107` during chapter generation

**`DepthCalculator.distribute_events_across_chapters()`** - `depth_calculator.py:458-495`
- Input: total_events, chapter_count, form
- Output: List of event counts per chapter
- Uses ACT_EVENT_MULTIPLIERS for three-act distribution

**`DepthCalculator.calculate_chapter_word_target()`** - `depth_calculator.py:427-455`
- Input: chapter_number, total_chapters, event_count, form, pacing
- Output: Word count target for this specific chapter
- Uses ACT_WE_MULTIPLIERS for act-aware depth

**`ChapterGenerator._generate_chapter_batch()`** - `chapters.py:547-752`
- Generates 2-8 chapters per batch
- Builds prompt with per-chapter specifications
- Returns parsed YAML chapter outlines

**`ProseGenerator.generate_chapter_sequential()`** - `prose.py:184-374`
- Loads chapters.yaml (self-contained format)
- Extracts word_count_target from chapter outline
- Generates prose for single chapter

---

## The Problem

### Actual vs Target Word Counts

**pechter project** - 14 chapters generated with Claude Opus 4.1:

| Chapter | Target | Actual | % | Events (in outline) | Actual w/e | Target w/e |
|---------|--------|--------|---|---------------------|------------|------------|
| 1       | 3,800  | 1,871  | 49% | 4                   | 468        | 950        |
| 2       | 3,800  | 2,731  | 72% | 5                   | 546        | 760        |
| 3       | 3,800  | 4,130  | **109%** ✅ | 9              | 459        | 422        |
| 4       | 3,200  | 2,334  | 73% | 4                   | 584        | 800        |
| 5       | 3,200  | 2,226  | 70% | 4                   | 557        | 800        |
| 6       | 3,200  | 2,375  | 74% | 6                   | 396        | 533        |
| 7       | 3,200  | 2,552  | 80% | 4                   | 638        | 800        |
| 8       | 3,200  | 2,275  | 71% | 4                   | 569        | 800        |
| 9       | 3,200  | 2,581  | 81% | 5                   | 516        | 640        |
| 10      | 3,200  | 1,959  | 61% | 5                   | 392        | 640        |
| 11      | 3,240  | 2,505  | 77% | **10**              | **251**    | 324        |
| 12      | 3,240  | 2,246  | 69% | 6                   | 374        | 540        |
| 13      | 3,240  | 2,019  | 62% | 5                   | 404        | 648        |
| 14      | 11,880 | 2,971  | **25%** ❌ | **10**        | **297**    | 1,188      |

**Summary Statistics**:
- **Total target**: ~51,680 words
- **Total actual**: 34,775 words
- **Achievement rate**: **67.3%** ❌
- **Average actual w/e**: **429 w/e** (target: ~800 w/e)
- **Achievement**: **54% of target w/e** ❌

### Root Causes

1. **Event Count Mismatch**
   - System specifies: 4-5 events per chapter
   - LLM generates: 6-10 events in outline
   - More events = each gets less development

2. **LLM Prioritizes "Reasonable Chapter Length"**
   - LLMs have internal heuristics for chapter length
   - ~2,000-2,500 words feels "right" regardless of target
   - Distributes this budget evenly across events

3. **High Event Counts Crush w/e Ratio**
   - Chapter 11: 10 events → only **251 w/e** (29% of target)
   - Chapter 14: 10 events → only **297 w/e** (25% of target!)
   - Chapters with 4-5 events: averaged **540 w/e** (60% of target)
   - Chapters with 9-10 events: averaged **315 w/e** (35% of target!)

4. **Event Granularity Problem**
   - Prompts ask for "key events" as bullet points
   - LLMs interpret these as summaries, not full scenes
   - Each bullet becomes a paragraph (200-400 words)
   - Not enough depth for true scene development

---

## Industry Research

### How Published Novels Actually Work

**Average Novel Structure** (from Save the Cat, Story Grid, Writer's Digest):
- **Length**: 80,000-100,000 words
- **Chapters**: 20-30 chapters
- **Chapter length**: 2,500-5,000 words
- **Scenes per chapter**: **2-4 major beats** (NOT 6-10 granular bullets)
- **Reading time**: 10-20 minutes per chapter (reader psychology)

### Professional Scene Structure

Authors think in **SCENES**, not bullet points:

**1. Setup Scene** (500-1,000 words)
- Establish location and atmosphere
- Introduce immediate conflict or goal
- Hook reader into what's about to happen

**2. Standard Dramatic Scene** (1,200-2,000 words)
- Full dialogue exchanges with reactions
- Internal thoughts and emotional processing
- Sensory details and atmosphere
- Action with consequences
- Character decisions and revelations

**3. Climactic Scene** (2,000-3,500 words)
- Deep character work and emotional depth
- Full sensory immersion (sights, sounds, smells, textures)
- Time dilation - important moments get space
- Multiple POV reactions if ensemble cast
- Satisfying emotional payoff

### Example: Harry Potter Chapter Breakdown

**Harry Potter and the Philosopher's Stone, Chapter 7** ("The Sorting Hat"):
- **Length**: ~4,200 words
- **Scenes**: 3 major scenes
  1. Great Hall entrance and setup (800 words)
  2. Sorting ceremony with multiple students (2,400 words)
  3. Harry's sorting and feast (1,000 words)
- **Average w/e**: ~1,400 words per scene

Notice: **3 scenes**, not "7 key events." Each scene is fully developed.

### Why Bullet Points Fail

**Current AgenticAuthor approach**:
```yaml
key_events:
  - Harry enters the Great Hall for the first time
  - Students are sorted into houses
  - Hermione goes to Gryffindor
  - Ron goes to Gryffindor
  - Harry is sorted (internal conflict with hat)
  - Dumbledore gives speech
  - Feast begins
```

**Problems**:
1. **7 bullets** encourage TELLING, not SHOWING
2. Each becomes a summary paragraph (300-500 words)
3. Total: 2,100-3,500 words vs 4,200 actual
4. No room for sensory details, dialogue subtext, emotional beats

**Professional author approach**:
```
Scene 1: Great Hall entrance
- Full sensory description (candles, ceiling, atmosphere)
- Harry's wonder and nervousness
- Dialogue with classmates
- Building anticipation

Scene 2: Sorting ceremony
- Multiple students sorted (showing house personalities)
- Rising tension as Harry waits
- Internal dialogue with Sorting Hat (full conversation)
- Moment of choice and relief

Scene 3: Post-sorting feast
- Dumbledore's speech
- Food appearing (magical moment)
- Meeting other Gryffindors
- Harry's sense of belonging
```

**Result**: Each scene is 800-2,400 words of SHOWED narrative, not summarized bullet points.

---

## Case Studies

### Case Study 1: pechter Chapter 3 - The Success

**Specifications**:
- Form: Novel, Pacing: Moderate, Act: Act I
- Events specified: 9 events
- Target: 3,800 words (9 × 422 w/e)
- Actual: 4,130 words (**109% of target**) ✅

**Why it succeeded**:
1. High event count (9) forced granular storytelling
2. Each "event" became a mini-scene (400-500 words)
3. LLM couldn't rush through 9 distinct beats in 2,500 words
4. Result: Hit the target by accident

**The problem with this approach**:
- 9 events is cognitively overwhelming in an outline
- Loses the "big picture" scene structure
- Difficult to maintain narrative flow across so many beats
- Not how professional authors structure chapters

**Actual scene structure in generated prose**:
The 9 outline events expanded to ~15-20 micro-scenes:
1. Fiction Clan servers screaming
2. Joaquin trapped in narrative loop
3. Petra in alcove repeating
4. Mara's internal dialogue with SOPHIA
5. Navigating through smoke
6. Encountering Joaquin at terminal
7. Burn and Erasers arriving
8. Charges detonating
9. Escape through corridors
10. Joaquin's final words
11. Transition to Periodicals section
12. Finding security footage
13. David in map room
14. SOPHIA stabilizing David
15. Mara moving toward Great Hall

Average per micro-scene: ~275 words

**The lesson**: More events → more words, but at the cost of scene coherence.

### Case Study 2: pechter Chapter 11 - The Failure

**Specifications**:
- Events specified: **10 events**
- Target: 3,240 words (10 × 324 w/e)
- Actual: 2,505 words (77% of target)
- **Actual w/e: 251 words** (only 29% of 850 baseline!)

**Why it failed**:
1. 10 events is too many
2. LLM defaulted to "reasonable chapter length" (~2,500 words)
3. Distributed that evenly: 2,500 ÷ 10 = 250 words per event
4. Result: Every event became a rushed summary

**The breakdown**:
- 10 outline bullets
- ~2,500 words generated
- Each event got ~250 words
- No room for dialogue, sensory details, or emotional depth
- Reads like a plot summary, not a novel

### Case Study 3: fight-gig Chapters (Not Yet Generated)

**Specifications** (from current chapters.yaml):
- Form: Novel (Psychological Thriller), Pacing: Escalating
- Total: 76,000 words, 19 chapters
- Baseline: 800 w/e (fast pacing tier)

**Sample chapter targets**:
- Chapter 1: 5 events × 902 w/e = **4,510 words**
- Chapter 8: 4 events × 950 w/e = **3,800 words**
- Chapter 18: 3 events × 1,282 w/e = **3,846 words** (Act III boost)

**Predicted results** (based on pechter data):
- 4-5 events per chapter: Will achieve ~60-70% of target
- Actual: ~2,500-3,000 words per chapter
- Actual w/e: ~500-600 words per event

**The events in fight-gig are complex**:

**Chapter 1, Event 2**:
> "A customer named Bradley Chen claims his $47 sushi order never arrived despite Maya's timestamped photo proof, triggering an automatic contract violation that drops her rating below 4.7 and locks her into punishment tier assignments"

This **single event** needs:
- Notification arriving (200w)
- Reading complaint and checking proof (300w)
- Contacting support (400w)
- Automated response and rating drop (200w)
- Emotional reaction (300w)
- Calculating financial impact (200w)

**Realistic need**: **1,500-1,800 words** for full development

**Current allocation**: 902 words ❌

---

## Recommendations

### Short-Term Fixes (Prompt Engineering)

1. **Change terminology**: "key_events" → "major_scenes"
   - Signals to LLM that each needs full development
   - Reduces cognitive load from 9 bullets to 3-4 scenes

2. **Add scene structure guidance** to chapter generation prompt:
   ```
   Each scene should include:
   - Setup (location, characters, initial situation)
   - Conflict/goal (what characters want)
   - Development (dialogue, action, reactions)
   - Resolution/transition (outcome, next scene hook)
   ```

3. **Reduce event counts**:
   - Current: 4-5 events → 3-4 events per chapter
   - Increases w/e from 950 → 1,200-1,400
   - Aligns with professional novel structure

4. **Add prose prompt emphasis** (carefully):
   ```
   Note: Each event is a FULL SCENE, not a summary paragraph.
   - Setup scenes: 600-800 words
   - Standard scenes: 1,000-1,500 words
   - Climactic scenes: 1,500-2,000 words
   ```

### Medium-Term Fixes (System Changes)

1. **Change baseline w/e for novels**:
   - Current: moderate novel = 950 w/e
   - Proposed: moderate novel = 1,200 w/e
   - Impact: Fewer events (80K ÷ 1,200 = 67 events vs 84 events)

2. **Implement scene-based chapter generation**:
   - Generate "scene outlines" instead of "event lists"
   - Each scene includes: goal, conflict, stakes, outcome
   - More aligned with professional story structure

3. **Add scene depth heuristics**:
   - Analyze event complexity in generated outlines
   - Warn if events are too granular
   - Suggest combining or expanding events

4. **Iterative event refinement**:
   - After generating outlines, analyze event density
   - Offer to combine events if >6 per chapter
   - Offer to expand events if <3 per chapter

### Long-Term Fixes (Architecture)

1. **Two-phase chapter generation**:
   - Phase 1: Generate high-level scene structure (3-4 scenes)
   - Phase 2: Expand each scene into detailed beats
   - Better control over granularity

2. **Event complexity scoring**:
   - Analyze outline events for complexity indicators
   - Adjust per-event word budgets based on complexity
   - Complex events (courtroom scenes, battles) get more words

3. **Learn from generated prose**:
   - After prose generation, analyze actual w/e achieved
   - Adjust future event counts based on empirical data
   - Build model-specific profiles (Claude tends toward 2,500w chapters, GPT-4 toward 3,000w)

4. **Scene templates by genre**:
   - Thriller: action scenes need 1,500-2,000w
   - Romance: emotional beats need 1,000-1,500w
   - Mystery: revelation scenes need 1,200-1,800w
   - Apply templates during outline generation

---

## Appendix: Full Data Tables

### pechter Detailed Analysis

| Ch | Target | Actual | % | Events | Act | Base w/e | Act mult. | Target w/e | Actual w/e | Delta |
|----|--------|--------|---|--------|-----|----------|-----------|------------|------------|-------|
| 1  | 3,800  | 1,871  | 49% | 4    | I   | 950      | 0.95      | 903        | 468        | -48%  |
| 2  | 3,800  | 2,731  | 72% | 5    | I   | 950      | 0.95      | 760        | 546        | -28%  |
| 3  | 3,800  | 4,130  | 109% | 9   | I   | 950      | 0.95      | 422        | 459        | +9%   |
| 4  | 3,200  | 2,334  | 73% | 4    | I   | 800      | 0.95      | 760        | 584        | -23%  |
| 5  | 3,200  | 2,226  | 70% | 4    | II  | 800      | 1.00      | 800        | 557        | -30%  |
| 6  | 3,200  | 2,375  | 74% | 6    | II  | 800      | 1.00      | 533        | 396        | -26%  |
| 7  | 3,200  | 2,552  | 80% | 4    | II  | 800      | 1.00      | 800        | 638        | -20%  |
| 8  | 3,200  | 2,275  | 71% | 4    | II  | 800      | 1.00      | 800        | 569        | -29%  |
| 9  | 3,200  | 2,581  | 81% | 5    | II  | 800      | 1.00      | 640        | 516        | -19%  |
| 10 | 3,200  | 1,959  | 61% | 5    | II  | 800      | 1.00      | 640        | 392        | -39%  |
| 11 | 3,240  | 2,505  | 77% | 10   | III | 800      | 1.35      | 324        | 251        | -23%  |
| 12 | 3,240  | 2,246  | 69% | 6    | III | 800      | 1.35      | 540        | 374        | -31%  |
| 13 | 3,240  | 2,019  | 62% | 5    | III | 800      | 1.35      | 648        | 404        | -38%  |
| 14 | 11,880 | 2,971  | 25% | 10   | III | 800      | 1.35      | 1,188      | 297        | -75%  |

### Event Count Impact

| Event Range | Chapters | Avg Target w/e | Avg Actual w/e | Achievement | Avg Total Words |
|-------------|----------|----------------|----------------|-------------|-----------------|
| 3-4 events  | 5        | 850            | 540            | 64%         | 2,358           |
| 5 events    | 4        | 710            | 491            | 69%         | 2,379           |
| 6 events    | 2        | 537            | 385            | 72%         | 2,311           |
| 9-10 events | 3        | 645            | 336            | 52%         | 3,202           |

**Key insight**: 3-5 events per chapter achieves better w/e ratios than 6+ events.

---

## References

- **Code**: `src/generation/depth_calculator.py`, `src/generation/chapters.py`, `src/generation/prose.py`
- **Books**: Save the Cat Writes a Novel, Story Grid, Writer's Digest Novel Writing guides
- **Data**: pechter project (fc116f4 commit), fight-gig chapters.yaml
- **Models tested**: Claude Opus 4.1 (primary), Claude Sonnet 4 (testing)
