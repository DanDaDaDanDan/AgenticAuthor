# Beat-Driven Scene Architecture

## Philosophy

**"Design in beats, publish in scenes"**

AgenticAuthor uses a top-down beat-driven architecture where word budgets cascade from the book level down to individual beats within scenes. This ensures precise word count control and professional story structure.

## Top-Down Word Budgeting Flow

```
BOOK (Total Words)
  ↓ Act Weights [25%, 50%, 25%]
ACTS (Act I, Act II, Act III)
  ↓ Peak Multipliers
CHAPTERS (with roles: inciting_setup, midpoint, crisis, climax, escalation)
  ↓ Glue Fraction (75% scenes, 25% transitions)
SCENES (with impact ratings: 1=connective, 2=important, 3=set-piece)
  ↓ Beat Weights
BEATS (setup, obstacle, complication, reversal, consequence, exit)
```

## Concrete Example

**Given:** 80,000-word novel, 20 chapters

### Level 1: Acts (25% / 50% / 25%)
- **Act I**: 80,000 × 0.25 = **20,000 words** (Chapters 1-5)
- **Act II**: 80,000 × 0.50 = **40,000 words** (Chapters 6-15)
- **Act III**: 80,000 × 0.25 = **20,000 words** (Chapters 16-20)

### Level 2: Chapters with Peak Multipliers

**Act I (20,000 words across 5 chapters):**
- Ch 1: inciting_setup (×1.25) → 4,762 words
- Ch 2-5: escalation (×1.0) → 3,810 words each

**Act II (40,000 words across 10 chapters):**
- Ch 6-7: escalation (×1.0) → 4,082 words each
- **Ch 8: midpoint (×1.50) → 6,122 words** ← Peak chapter
- Ch 9-13: escalation (×1.0) → 4,082 words each
- Ch 14: crisis (×1.30) → 5,306 words
- Ch 15: escalation (×1.0) → 4,082 words

**Act III (20,000 words across 5 chapters):**
- Ch 16-19: escalation (×1.0) → 3,636 words each
- **Ch 20: climax (×1.50) → 5,455 words** ← Peak chapter

### Level 3: Scenes with Glue Fraction

**Example: Chapter 8 (midpoint) = 6,122 words, 4 scenes**

- **Glue fraction**: 25% (transitions, exposition, chapter opening/closing)
- **Scene budget**: 6,122 × 0.75 = **4,592 words** for actual scenes
- **Glue budget**: 6,122 × 0.25 = **1,530 words** for transitions

**Scene allocation with impact ratings:**

Scene | Impact | Multiplier | Words | Purpose
------|--------|------------|-------|--------
1     | 1      | 0.75×      | 918   | Connective (first scene)
2     | 2      | 1.0×       | 1,224 | Important
3     | 3      | 1.25×      | 1,531 | Set-piece (midpoint scene)
4     | 1      | 0.75×      | 918   | Connective (last scene)
**Total** | | | **4,591** | (scene budget)

### Level 4: Beats within Scene 3 (set-piece, 1,531 words)

Using 6-beat pattern with weights [10%, 15%, 20%, 25%, 20%, 10%]:

Beat | Type         | Weight | Words | Purpose
-----|--------------|--------|-------|------------------------------------------
1    | setup        | 10%    | 153   | Establish location, character state
2    | obstacle     | 15%    | 230   | First complication arises
3    | complication | 20%    | 306   | Stakes increase
4    | **reversal** | **25%** | **383** | **Peak moment - decision point**
5    | consequence  | 20%    | 306   | Immediate aftermath
6    | exit         | 10%    | 153   | Bridge to next scene with hook

**Note:** The reversal beat (4) gets the most words (25%) - this is the turn, the peak moment of the scene.

## Key Concepts

### 1. Glue Fraction (default 25%)

**Glue** = transitions, exposition, chapter openings/closings not inside dramatic scenes.

- **Scene budget** = Chapter words × (1 - glue_fraction)
- **Typical range**: 20-30%
- **Too low** (< 20%): Chapters feel abrupt, scenes crash into each other
- **Too high** (> 30%): Chapters feel padded with unnecessary exposition

### 2. Peak Multipliers

High-leverage chapters get more words:

Role | Multiplier | When Applied | Purpose
-----|------------|--------------|--------
inciting_setup | 1.25× | Chapter 1 | Hook + world establishment
**midpoint** | **1.50×** | Middle of Act II | **Game-changer (biggest multiplier)**
crisis | 1.30× | End of Act II | All-is-lost moment
**climax** | **1.50×** | Last chapter | **Payoff + resolution**
escalation | 1.0× | Other chapters | Standard progression
denouement | 0.9× | Penultimate | Wind-down (shorter)

**Why midpoint and climax get 1.50×:**
- These are the two biggest moments in three-act structure
- Midpoint: Everything changes (knowledge/power flip)
- Climax: Everything pays off (resolution of main conflict)

### 3. Scene Impact Ratings

Scenes are assigned impact ratings (1-3) based on position and chapter role:

Impact | Type       | Multiplier | When Applied
-------|------------|------------|----------------------------------
1      | Connective | 0.75×      | First/last scenes in chapter
2      | Important  | 1.0×       | Most middle scenes
3      | Set-piece  | 1.25×      | Middle scenes in peak chapters

**Auto-assignment rules:**
- First scene in chapter → impact=1 (connective - transition in)
- Last scene in chapter → impact=1 (connective - transition out)
- Middle scenes in regular chapters → impact=2 (important)
- Middle scenes in midpoint/crisis/climax chapters → impact=3 (set-piece)

### 4. Beat Weights

Beats are the smallest unit - individual moves within a scene.

**5-beat pattern:** [15%, 20%, 30%, 20%, 15%]
- Best for: Short scenes (< 1,000 words)
- Turn gets 30% of scene words

**6-beat pattern:** [10%, 15%, 20%, 25%, 20%, 10%]
- Best for: Standard scenes (1,000-1,500 words)
- Turn gets 25% of scene words

**7-beat pattern:** [10%, 12%, 18%, 25%, 18%, 12%, 5%]
- Best for: Complex scenes (> 1,500 words)
- Turn gets 25% of scene words
- Includes separate reveal beat

**Beat types:**
- **setup**: Establish location, character state
- **obstacle**: First complication
- **complication**: Stakes increase
- **reveal** (7-beat only): New information
- **reversal/turn**: Peak moment - decision, revelation, confrontation
- **consequence**: Immediate aftermath
- **exit**: Bridge forward with hook

## Extended Scene Structure

Every scene in chapters.yaml has this structure:

```yaml
scenes:
  - scene: "Brief Title"              # 2-4 words
    location: "Where it happens"      # Specific place
    objective: "convince mentor"      # VERB phrase (fail-able)
    opposition: "mentor's doubt"      # Active force (not circumstances)
    value_shift: "ignored → heard"    # X → Y (before → after)
    outcome: "partial win"            # How it resolves
    exit_hook: "mentor asks question" # Forward momentum
    emotional_beat: "confidence"      # Internal change
    tension:                          # Tension tags (vary across scenes)
      - "social-pressure"
      - "timer"
    plants:                           # Setup for later payoffs
      - "Mention of artifact"
    payoffs:                          # Payoffs from earlier plants
      - "Callback to Ch 2 promise"
    impact: 2                         # 1=connective, 2=important, 3=set-piece
    sensory_focus:
      - "Stale coffee smell"
      - "Fluorescent buzz"
    target_words: 1224
    beats:                            # 5-7 beats with types and targets
      - type: "setup"
        note: "Office morning, mentor reading reports"
        target_words: 122
      - type: "obstacle"
        note: "Mentor dismisses protagonist's theory"
        target_words: 184
      - type: "complication"
        note: "New evidence contradicts protagonist"
        target_words: 245
      - type: "reversal"
        note: "Protagonist reframes evidence, mentor pauses"
        target_words: 306    # ← Biggest beat (25%)
      - type: "consequence"
        note: "Mentor agrees to one more chance"
        target_words: 245
      - type: "exit"
        note: "Mentor asks about artifact from Ch 2"
        target_words: 122
```

## Scene Hygiene Requirements

Every scene MUST have:

1. **objective**: A fail-able VERB phrase
   - ✅ "convince mentor to reopen case"
   - ❌ "talk to mentor" (not fail-able)
   - ❌ "feeling upset" (not a verb)

2. **opposition**: An ACTIVE force (not just circumstances)
   - ✅ "mentor's skepticism and department politics"
   - ❌ "circumstances make it hard" (too vague)
   - ❌ "it's difficult" (passive)

3. **value_shift**: Explicit X → Y format
   - ✅ "ignored → heard"
   - ✅ "safe → exposed"
   - ✅ "ignorant → informed"
   - ❌ "things change" (not specific)

4. **exit_hook**: Points forward (question, decision, reveal, peril)
   - ✅ "Mentor asks about the missing artifact"
   - ✅ "Phone rings - it's the killer"
   - ✅ "She decides to break the rules"
   - ❌ "Scene ends" (no forward momentum)

5. **tension tags**: Vary across scenes (avoid repeating same tag 3+ times)
   - timer, secrecy, pursuit, environment, moral, social-pressure, puzzle

6. **plants or payoffs**: At least ONE per scene
   - plant = setup for later payoff
   - payoff = callback to earlier plant
   - Tracks story cohesion

## Pacing Anchors

Peak chapters should fall within expected percentage ranges:

Anchor | Expected Range | Example (80k words)
-------|----------------|--------------------
Inciting incident | 0-10% | By 8,000 words (Ch 1-2)
Act II break | 20-28% | 16,000-22,400 words (Ch 4-6)
**Midpoint** | **48-55%** | **38,400-44,000 words (Ch 9-11)**
Crisis | 72-78% | 57,600-62,400 words (Ch 14-16)
Climax | 85-95% | 68,000-76,000 words (Ch 18-20)

**Validation happens automatically after chapter generation.**

If anchors drift > 5% outside expected range, system shows:
```
⚠️  Pacing Check:
  ✓ Inciting incident at 8% (expected 0-10%)
  ✓ Midpoint at 52% (expected 48-55%)
  ✗ Crisis at 68% (expected 72-78%) - Consider moving crisis later
  ✓ Climax at 90% (expected 85-95%)
```

## Metadata Fields

Foundation metadata includes beat architecture settings:

```yaml
metadata:
  genre: "mystery"
  target_word_count: 80000
  chapter_count: 20
  glue_fraction: 0.25              # NEW: 25% for transitions
  act_weights: [0.25, 0.50, 0.25]  # NEW: Act percentages
  # ... other fields
```

These are set automatically but can be edited in chapters.yaml if needed.

## Word Count Accuracy

**Old system (scene lookup tables):**
- Achieved 50-60% of target (e.g., 2,300/3,800 words)
- Problem: LLMs treated "key_events" as bullet summaries

**New system (top-down budgeting + beat structure):**
- Expected: 80-100% of target
- Improvements:
  1. Explicit beat structure prevents summarization
  2. Top-down budgeting ensures math adds up
  3. Impact ratings balance scene lengths
  4. Beat weights emphasize turn/reversal (prevents rushed climaxes)

## Generation Flow

### Phase 1: Calculate Budget
```python
budget = DepthCalculator.calculate_top_down_budget(
    total_words=80000,
    chapter_count=20,
    form='novel',
    act_weights=[0.25, 0.50, 0.25],
    glue_fraction=0.25
)
```

Returns:
- act_budgets: [20000, 40000, 20000]
- chapter_budgets: List of dicts with number, role, words_total, words_scenes

### Phase 2: Generate Foundation
Foundation includes metadata with glue_fraction and act_weights.

### Phase 3: Generate Chapters Sequentially
For each chapter:
1. Get chapter budget from top-down calculation
2. Assign scene impacts based on chapter role
3. Calculate scene budgets from chapter's words_scenes
4. Calculate beat budgets for each scene (5-7 beats)
5. LLM generates chapter with full beat structure
6. Auto-validate scene hygiene (objective, opposition, value_shift, etc.)

### Phase 4: Validate Pacing
After all chapters generated:
1. Calculate cumulative word positions of peak chapters
2. Check if they fall within pacing anchor ranges
3. Display results (all checks pass or suggestions)

### Phase 5: Generate Prose
Prose generation uses beat structure as detailed blueprint:
- Each scene expanded beat-by-beat
- Beat targets guide word distribution
- Turn/reversal beats get most focus (25-30% of scene)

## Benefits

1. **Predictable word counts**: Math guarantees targets (within 5-10%)
2. **Professional structure**: Peak chapters naturally emphasized
3. **Scene variety**: Impact ratings prevent monotony
4. **Beat-level precision**: Turn moments get proper weight
5. **Automatic validation**: Hygiene checks catch weak scenes
6. **Pacing alignment**: Anchors ensure story hits marks
7. **No commands needed**: Everything automatic and intelligent

## Comparison to User's Document

This implementation matches the provided beat-driven architecture document with these adaptations:

**Matches:**
- ✅ Top-down budgeting (Book → Acts → Chapters → Scenes → Beats)
- ✅ Glue fraction (20-30% for transitions)
- ✅ Peak multipliers for high-leverage chapters
- ✅ Scene impact ratings (1-3)
- ✅ Beat weight patterns (turn gets 25-30%)
- ✅ Scene hygiene (objective, opposition, value_shift, exit_hook)
- ✅ Tension tags for variety
- ✅ Plants/payoffs tracking
- ✅ Pacing anchors validation

**Adaptations:**
- Sequential generation (one chapter at a time with full context accumulation)
- chapter-beats/ file structure (foundation.yaml + chapter-NN.yaml)
- Auto-assignment of scene impacts (based on position + chapter role)
- LLM generates beat notes (not pre-defined)
- Glue fraction stored in metadata (editable)
- Validation happens automatically (no commands)

All adaptations enhance the system without conflicting with the core philosophy.
