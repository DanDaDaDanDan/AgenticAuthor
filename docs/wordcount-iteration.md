# Word Count Iteration Testing

This document tracks experiments to improve word-per-event ratios in prose generation.

## Test Subject: pechter Chapter 3

**Baseline Chapter**: Chapter 3 ("The Splintering")
**Project**: pechter (git commit: fc116f4)
**Model**: Claude Opus 4.1
**Generation Date**: 2025-10-12

### Baseline Statistics

| Metric | Value |
|--------|-------|
| **Form** | Novel |
| **Pacing** | Moderate |
| **Act** | Act I |
| **Target Word Count** | 3,800 words |
| **Target Events** | 9 events |
| **Target w/e** | 422 w/e (3,800 ÷ 9) |
| **Actual Word Count** | 4,130 words |
| **Achievement Rate** | **109%** ✅ |
| **Actual w/e** | ~459 w/e |

### Why This Chapter Succeeded

Chapter 3 is the **only chapter in the pechter project** that exceeded its word count target. Analysis:

1. **High event count (9)** forced granular storytelling
2. Each "event" became a mini-scene (400-500 words)
3. LLM couldn't rush through 9 distinct beats in its usual 2,500-word budget
4. Result: Had to write more to cover all events

**The problem**: While this achieved the word count, it's not the ideal approach:
- 9 events is cognitively overwhelming in an outline
- Loses "big picture" scene structure
- Micro-scenes (400w each) lack depth compared to full scenes (1,500w)

### Chapter 3 Outline

From `pechter/chapters.yaml`:

```yaml
- number: 3
  title: The Splintering
  pov: Mara
  act: Act I
  summary: As the Eraser assault fractures the library's ecosystem, Mara witnesses
    the clan alliance crumble while SOPHIA's presence grows stronger in her mind.
    The Fiction Clan's devastating losses and the revelation that someone inside betrayed
    them forces Mara to make an impossible choice. She neural-loads SOPHIA directly
    into her memory as the Erasers breach the outer defenses.
  key_events:
  - The Fiction Clan's desperate defense of their servers fails catastrophically as
    Joaquin attempts to trap the Erasers in narrative loops, only to have the neural
    parasites reverse the effect and trap his own people in recursive stories until
    their minds shatter
  - Mara races through the collapsing clan territories, using her eidetic memory to
    navigate passages that others have forgotten, while SOPHIA's presence in her mind
    begins suggesting tactical solutions she shouldn't know
  - 'In the Periodicals section, Mara finds evidence of the betrayal: security footage
    showing a figure in Reference Clan robes disabling the Stacks Protocol, but the
    face is obscured by electromagnetic interference'
  - Chen organizes a desperate war council in the Great Hall where the clan leaders
    argue instead of planning, with Marcus and David's mutual hatred paralyzing any
    unified response while their people die
  - As the first Eraser breach teams enter the main library, Mara makes her desperate
    choice, neural-loading all of SOPHIA's code into her own memory despite knowing
    it could burn out her synapses or worse, transform her into something no longer
    human
  character_developments:
  - Mara's transformation accelerates as SOPHIA integrates deeper, giving her capabilities
    but stealing pieces of her humanity
  - The weight of witnessing the clans' failure forces Mara to evolve from observer
    to actor
  - She begins questioning whether survival requires sacrificing her identity
  relationship_beats:
  - Mara's relationship with SOPHIA shifts from fear to reluctant partnership
  - She sees the brothers' pain and recognizes how clan divisions destroy families
  - Chen's authority begins cracking under the weight of impossible choices
  tension_points:
  - Fiction Clan's servers are destroyed, millennia of stories lost
  - Evidence suggests a Reference Clan traitor, threatening all remaining alliances
  - Time is running out as Erasers breach the main defenses
  sensory_details:
  - Smoke from burning books creating a taste of destroyed imagination
  - The sound of minds trapped in narrative loops
  - Electromagnetic interference creating visual distortions in security footage
  subplot_threads:
  - The mystery of who disabled the Stacks Protocol
  - The brothers' long-separated reunion amid crisis
  word_count_target: 3800
```

### Scene Analysis of Generated Prose

The generated prose (4,130 words) expanded the 9 outline events into approximately **15-20 distinct micro-scenes**:

**Act 1: Fiction Clan Territory** (~1,500 words)
1. Fiction Clan servers screaming (opening hook)
2. Person trapped in narrative loop (Petra in alcove)
3. Mara's internal conflict with SOPHIA
4. Navigating through smoke and chaos
5. Encountering Joaquin at terminal
6. Burn and Erasers arriving
7. Charges detonating
8. Escape with unconscious Joaquin

**Act 2: Periodicals Section** (~1,300 words)
9. Finding security footage of betrayal
10. David in map room with corrupted data
11. David's cognitive breakdown
12. SOPHIA stabilizing David (direct neural contact)
13. David and Marcus backstory revelation
14. Fire spreading, evacuation urgency

**Act 3: Great Hall** (~1,330 words)
15. Refugee camp atmosphere
16. Chen maintaining order
17. Marcus confronting Mara
18. David arriving with saved data
19. Brothers' first meeting in 15 years
20. Mara amplifying her voice with SOPHIA
21. Decision to neural-merge all clans

**Average per micro-scene**: ~270 words (too short for full scene development)

### Prompt Used (Reconstructed)

Based on `prose.py:268-331`, the prose generation prompt would have been:

```
Generate full prose for a chapter using this self-contained story context.

STORY CONTEXT (chapters.yaml):
[Full premise + treatment + characters + world]

TASK:
Generate 3,800 words of polished narrative prose for:
- Chapter 3: "The Splintering"
- POV: Mara
- Act: Act I

SCENE DEVELOPMENT (CRITICAL - ACT-AWARE):
You have 9 key events to cover in 3,800 words.
This means AVERAGE of ~422 words per event.

NOTE: This chapter is in Act I.
- Act I chapters: Efficient setup (slightly faster pacing)

Vary depth based on dramatic importance:
• Setup/transition scenes (317-380 words)
• Standard dramatic scenes (380-485 words)
• Climactic/peak scenes (506-633 words)

GUIDELINES:
1. Use the metadata (tone, pacing, themes, narrative style)
2. Draw on character backgrounds and motivations
3. Use world-building details
4. Follow the chapter outline's key events
5. Perfect continuity from previous chapters
6. TARGET: 3,800 words total = 9 events × ~422 w/e average

Return ONLY the prose text.
```

---

## Experiments to Run

### Experiment 1: Baseline Replication

**Goal**: Verify that current system produces consistent results

**Method**:
1. Clone pechter to wordcount-test
2. Regenerate Chapter 3 using same outline
3. Compare word count and scene structure

**Expected Results**:
- 3,500-4,500 words (may vary ±15% from baseline)
- Similar micro-scene structure
- Event coverage should match outline

**Metrics to Track**:
- Total word count
- Number of distinct scenes
- Average words per scene
- Coverage of all 9 outline events

---

### Experiment 2: Scene-Based Outline

**Goal**: Test if reducing events and focusing on "scenes" improves depth

**Method**:
1. Rewrite Chapter 3 outline with 4 major scenes instead of 9 events:
   ```yaml
   major_scenes:
   - Scene: Fiction Clan's Fall
     Location: Fiction territory, server room
     POV: Mara witnessing destruction
     Goal: Survive and save Joaquin
     Conflict: Narrative loops trapping defenders, Burn's attack
     Outcome: Joaquin saved but Fiction destroyed
     Target: ~1,000 words

   - Scene: Betrayal Evidence
     Location: Periodicals section
     Goal: Find what happened
     Conflict: Security footage shows traitor in Reference robes
     Outcome: Suspicion falls on Chen, but evidence is manipulated
     Target: ~800 words

   - Scene: David's Breakdown
     Location: Periodicals map room
     Goal: Stabilize David
     Conflict: Conflicting data streams breaking his mind
     Outcome: SOPHIA intervention, brothers' backstory revealed
     Target: ~1,000 words

   - Scene: Unity or Death
     Location: Great Hall
     Goal: Unite the clans
     Conflict: Brothers reunite, trust is shattered, time runs out
     Outcome: Mara offers neural bridge solution
     Target: ~1,000 words
   ```

2. Modify prose prompt to emphasize full scene development
3. Generate and compare

**Expected Results**:
- Deeper development per scene (900-1,200 words each)
- Better narrative flow
- More sensory detail and dialogue
- Total: ~3,800-4,200 words

---

### Experiment 3: Explicit Scene Structure

**Goal**: Add scene beat structure to prompt

**Method**:
1. Use original 9-event outline
2. Modify prose prompt to include scene structure guidance:
   ```
   For each event, develop as a FULL SCENE with:
   - Setup (100-150 words): Establish location, atmosphere, POV state
   - Development (250-400 words): Dialogue, action, sensory details
   - Climax (100-200 words): Key revelation or turning point
   - Transition (50-100 words): Outcome and bridge to next scene

   Target per event: 500-850 words (not 422w minimum)
   ```

3. Generate and compare

**Expected Results**:
- More structured scenes within events
- Better pacing and rhythm
- Total: 4,500-7,000 words (may exceed target)

---

### Experiment 4: Act III Depth Test

**Goal**: Test if Act III multiplier (1.35x) produces actual depth

**Method**:
1. Find an Act III chapter from pechter (e.g., Chapter 12-14)
2. Note its specifications (e.g., 3 events × 1,080 w/e = 3,240 words)
3. Regenerate and measure actual w/e
4. Compare to Act I/II chapters

**Expected Results**:
- Act III should achieve higher w/e than Act I/II
- Hypothesis: Still only 60-70% of target, but absolutely more words than Act I

---

### Experiment 5: Hybrid Approach

**Goal**: Keep outline events but add scene annotations

**Method**:
1. Use 9-event outline
2. Add scene annotations to each event:
   ```yaml
   key_events:
   - event: Fiction Clan's desperate defense fails...
     scene_type: climactic
     target_words: 800
     elements: [dialogue, action, sensory_details, reactions]

   - event: Mara races through territories...
     scene_type: transition
     target_words: 400
     elements: [movement, internal_thoughts, atmosphere]
   ```

3. Modify chapter generation to include these annotations
4. Modify prose prompt to respect scene types

**Expected Results**:
- Variable scene lengths based on importance
- Better match to professional structure
- Total: should hit 3,800-4,000 words

---

## Success Metrics

For each experiment, evaluate:

1. **Word Count Accuracy**
   - Target: 3,800 words
   - Acceptable: 3,400-4,200 words (90-110%)
   - Good: 3,600-4,000 words (95-105%)

2. **Words Per Event/Scene**
   - Current baseline: ~459 w/e (achieved)
   - Target: 800-1,000 w/e for full scenes
   - Minimum: 600 w/e for acceptable depth

3. **Coverage**
   - All outline events/scenes must appear in prose
   - No major gaps or skipped beats
   - Narrative flow maintained

4. **Reading Quality** (Subjective)
   - Does it feel like a published novel chapter?
   - Are scenes fully developed or rushed?
   - Is dialogue realistic and revealing?
   - Are sensory details present?
   - Does pacing vary appropriately?

5. **Scene Structure**
   - Clear scene boundaries
   - Setup → Development → Climax → Transition pattern
   - Smooth transitions between scenes

---

## Testing Process

1. **Clone pechter project**
   ```bash
   agentic
   /open pechter
   /clone wordcount-test
   ```

2. **Run baseline test** (Experiment 1)
   - Regenerate Chapter 3 with current system
   - Document results

3. **Modify outlines/prompts** (Experiments 2-5)
   - Make changes to outline or prompt
   - Regenerate
   - Compare to baseline

4. **Document findings**
   - Update this file with results
   - Include actual prose samples
   - Note which approach works best

5. **Iterate**
   - Refine successful approaches
   - Test on different chapter types
   - Build recommendations for system changes

---

## Results Log

### Experiment 1: Baseline Replication
**Status**: Not yet run
**Date**:
**Model**:
**Results**:

---

### Experiment 2: Scene-Based Outline
**Status**: Not yet run
**Date**:
**Model**:
**Results**:

---

### Experiment 3: Explicit Scene Structure
**Status**: Not yet run
**Date**:
**Model**:
**Results**:

---

### Experiment 4: Act III Depth Test
**Status**: Not yet run
**Date**:
**Model**:
**Results**:

---

### Experiment 5: Hybrid Approach
**Status**: Not yet run
**Date**:
**Model**:
**Results**:

---

## Notes

- All tests should use the same model for consistency
- Consider testing multiple models (Opus 4.1, Sonnet 4.5, Gemini Pro 2.0)
- Document any streaming/timeout issues
- Track token usage for cost analysis
- Save all generated prose to wordcount-test/experiments/ directory

## Next Steps

1. ✅ Create wordcount-test project by cloning pechter
2. Run Experiment 1 (baseline replication)
3. Analyze results and decide which experiments to prioritize
4. Test most promising approach
5. Update main documentation with findings
6. Implement successful changes in system
