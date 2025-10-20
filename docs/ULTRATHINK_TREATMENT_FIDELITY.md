# ULTRATHINK: Treatment Fidelity Crisis

**STATUS: FIXED** ✅
- Treatment (premise + taxonomy + treatment text) now visible in all chapter generation prompts
- Temperature: 0.6 (balanced)
- System message: Professional and balanced
- Prompts: Simplified, keep treatment visible

---

## ROOT CAUSE IDENTIFIED 🎯

**The chapter generation prompt doesn't show the TREATMENT (premise + taxonomy + treatment) to the LLM!**

### Evidence

**File:** `src/generation/chapters.py`
**Method:** `_generate_single_chapter()` (line 454)

**Problem:**
```python
async def _generate_single_chapter(
    self,
    chapter_num: int,
    total_chapters: int,
    context_yaml: str,        # ← Contains premise + treatment (line 472 comment)
    foundation: Dict[str, Any],
    previous_chapters: List[Dict[str, Any]],
    ...
) -> Dict[str, Any]:
```

**The prompt (lines 511-555) shows:**
```
# STORY FOUNDATION
```yaml
{foundation_yaml}  ← Only metadata, characters, world
```

# PREVIOUS CHAPTERS
```yaml
{previous_yaml}
```

# YOUR TASK
Generate Chapter {chapter_num}...
```

**What's missing:** `context_yaml` (the treatment!) is **NEVER USED** in the prompt!

### Why This Causes Treatment Deviation

1. **Foundation contains:** Metadata, characters, world-building
2. **Foundation does NOT contain:** The actual PLOT from treatment
3. **Without plot context:** LLM invents new plot elements (antagonists, conspiracies, backstories)
4. **Result:** Treatment fidelity violations detected by validation

The LLM can't extract from a source it can't see!

---

## SECONDARY ISSUES

### 1. Wrong Framing
**Current:** "Generate Chapter N"
**Should be:** "Extract and structure Chapter N from the treatment"

The word "generate" implies creation, not extraction.

### 2. No Extraction Instructions
No explicit instructions to:
- Divide treatment into N chapters
- Identify which treatment sections belong in each chapter
- Extract scenes from treatment plot points
- Stay faithful to treatment plot

### 3. No Visual Treatment Reference
Even if we add context_yaml, the prompt structure doesn't highlight:
- "Here's the treatment plot"
- "Here's what happens in the story"
- "Extract chapter N's content from this plot"

### 4. Temperature Too High?
Current: `temperature=0.6` (line 570)

For **extraction** tasks, lower is better:
- 0.3-0.4: Faithful extraction
- 0.6: Some creativity (current - problematic)
- 0.8: High creativity (inappropriate for extraction)

---

## PROPOSED FIX: EXTRACTION-FIRST ARCHITECTURE

### Principle
**Chapter generation is EXTRACTION + STRUCTURING, not CREATIVE GENERATION**

### Changes Required

#### 1. Add Treatment to Prompt (CRITICAL)
```python
prompt = f"""# TREATMENT (SOURCE OF TRUTH - EXTRACT FROM HERE)
```
{context_yaml}  # ← ADD THIS! Shows premise + treatment
```

⚠️ CRITICAL INSTRUCTION:
You are EXTRACTING and STRUCTURING content FROM THE TREATMENT ABOVE.
Do NOT invent new plot elements, antagonists, conspiracies, or backstories.
The treatment contains the complete plot - your job is to divide and structure it.

# STORY FOUNDATION (extracted from treatment)
```yaml
{foundation_yaml}
```

# PREVIOUS CHAPTERS (already extracted)
```yaml
{previous_yaml}
```

# YOUR TASK
Extract and structure Chapter {chapter_num} of {total_chapters} from the treatment.

EXTRACTION PROCESS:
1. Review the treatment plot above
2. Identify which treatment events belong in chapter {chapter_num}
3. Divide those events into {scene_count} scenes
4. Structure each scene with beats
5. DO NOT add plot elements not in treatment

FORBIDDEN ADDITIONS:
❌ New antagonists or villains
❌ Secret organizations or conspiracies
❌ Character backstories not in treatment
❌ New plot threads or subplots
❌ Major revelations not in treatment

ALLOWED ELABORATIONS:
✅ Dialogue specifics (treatment has plot, you add dialogue)
✅ Sensory details (sight, sound, smell, etc.)
✅ Minor characters (servants, officials, background)
✅ Scene transitions and pacing
✅ Internal character thoughts

# OUTPUT
...
```

#### 2. Reframe Instructions
**Before:**
- "Generate chapter"
- "Create scenes"

**After:**
- "Extract chapter from treatment"
- "Identify treatment events for this chapter"
- "Structure treatment plot into scenes"

#### 3. Lower Temperature
```python
temperature=0.3,  # Faithful extraction, not creative generation
```

#### 4. Add Explicit Examples
Show the LLM examples of:
- ✅ Good: Extracting treatment plot point and structuring it
- ❌ Bad: Inventing new conspiracy not in treatment

#### 5. Add Pre-Validation Reminder
At the END of the prompt:
```
FINAL REMINDER: Review your chapter against the treatment above.
Every major plot element in your chapter must come from the treatment.
If you invented something not in the treatment, remove it.
```

---

## IMPLEMENTATION PLAN

### Phase 1: Critical Fix (Immediate)
1. ✅ Add `context_yaml` to chapter generation prompt
2. ✅ Add "EXTRACTION not GENERATION" instruction
3. ✅ Add forbidden/allowed lists
4. ✅ Lower temperature to 0.3
5. ✅ Reframe "Generate" → "Extract and structure"

### Phase 2: Enhanced Instructions
1. Add extraction process steps
2. Add examples (good vs bad)
3. Add pre-validation reminder
4. Update system message

### Phase 3: Foundation Generation Fix
The foundation generation prompt (line 270) says:
```
Generate foundation (metadata + characters + world) from the treatment.
```

This should also emphasize extraction:
```
Extract foundation (metadata + characters + world) from the treatment.
Do NOT invent major plot elements during extraction.
```

### Phase 4: Testing
1. Generate chapters with a known treatment
2. Verify no treatment fidelity violations
3. Verify chapters follow treatment plot faithfully

---

## CODE LOCATIONS TO MODIFY

### 1. `_generate_single_chapter()` (line 454)
**File:** `src/generation/chapters.py`

**Current prompt (line 511):**
```python
prompt = f"""# STORY FOUNDATION
```yaml
{foundation_yaml}
```

# PREVIOUS CHAPTERS
```yaml
{previous_yaml if previous_yaml else "# Chapter 1 - no previous chapters"}
```

**CRITICAL**: Review previous chapters carefully. Each scene must be NEW events and conflicts. Do NOT duplicate plot beats already covered.

# YOUR TASK
Generate Chapter {chapter_num} of {total_chapters} ({default_act}, {chapter_role} role)
```

**Should be:**
```python
prompt = f"""# TREATMENT (SOURCE OF TRUTH - EXTRACT FROM HERE)
```
{context_yaml}
```

⚠️ CRITICAL INSTRUCTION:
You are EXTRACTING and STRUCTURING content FROM THE TREATMENT ABOVE.
Do NOT invent new plot elements. The treatment contains the complete plot.
Your job is to divide it into chapters and structure it into scenes/beats.

# STORY FOUNDATION (extracted from treatment)
```yaml
{foundation_yaml}
```

# PREVIOUS CHAPTERS (already extracted and structured)
```yaml
{previous_yaml if previous_yaml else "# Chapter 1 - no previous chapters"}
```

**CRITICAL**: Review previous chapters carefully. Each scene must be NEW events from treatment. Do NOT duplicate plot beats already covered.

# YOUR TASK
Extract and structure Chapter {chapter_num} of {total_chapters} from the treatment above.

EXTRACTION PROCESS:
1. Review the treatment plot (shown above)
2. Identify which treatment sections/events belong in chapter {chapter_num}
3. Divide those treatment events into {scene_count} scenes
4. Structure each scene with beats showing HOW the treatment events unfold
5. DO NOT add plot elements not present in the treatment

FORBIDDEN (causes treatment drift):
❌ New antagonists or villains not in treatment
❌ Secret organizations or conspiracies not in treatment
❌ Character backstories not in treatment
❌ New plot threads or subplots not in treatment
❌ Major revelations not established in treatment

ALLOWED (scene-level elaboration):
✅ Dialogue specifics (treatment has plot, you add dialogue)
✅ Sensory details (sight, sound, smell, touch, taste)
✅ Minor characters (servants, officials, crowd, background)
✅ Scene transitions and connective tissue
✅ Internal character thoughts and reactions
✅ Action choreography (treatment says "fight", you show how)

EXAMPLES:

❌ BAD - Inventing new plot:
Treatment: "Dr. Lang is the antagonist who steals the formula"
Chapter: "Sarah discovers Dr. Lang is part of a secret government program called Project Chimera"
Problem: "Project Chimera" is NEW - not in treatment!

✅ GOOD - Extracting plot:
Treatment: "Dr. Lang is the antagonist who steals the formula"
Chapter: "Sarah confronts Dr. Lang in his laboratory and witnesses him taking the formula"
Correct: Extracted treatment plot, added scene details (laboratory, confrontation action)

Chapter {chapter_num} role: {chapter_role}
Act: {default_act}
Scenes: {scene_count}
Target: {words_total:,} words (~{words_scenes // scene_count}w per scene)

# OUTPUT
Return plain YAML starting with "number:" (DO NOT wrap in ```yaml or ``` fences):

number: {chapter_num}
title: "Chapter Title (reflecting treatment events)"
pov: "Character Name"
...

FINAL REMINDER: Review your chapter against the treatment shown at the top.
Every major plot element must come from the treatment. If you invented something
not in the treatment, remove it before returning your response.
```

### 2. Temperature Change (line 570)
```python
# BEFORE
temperature=0.6,  # Stricter adherence to treatment/foundation sources

# AFTER
temperature=0.3,  # Faithful extraction from treatment (not creative generation)
```

### 3. System Message (line 567)
```python
# BEFORE
{"role": "system", "content": "You are a professional story development assistant. You always return valid YAML without additional formatting."}

# AFTER
{"role": "system", "content": "You are a story structure extraction specialist. You extract plot from treatments and structure it into chapters with scenes and beats. You never invent new plot elements. You always return valid YAML without additional formatting."}
```

### 4. Foundation Generation (line 270)
```python
# BEFORE
Generate foundation (metadata + characters + world) from the treatment.

Note: Extract and structure what's in the treatment. Elaborate fully but don't invent major plot elements.

# AFTER
Extract and structure foundation (metadata + characters + world) from the treatment.

⚠️ CRITICAL: You are EXTRACTING from the treatment, not generating new content.
- Extract metadata that reflects treatment's scope
- Extract characters that are IN the treatment
- Extract world details that are IN the treatment
- Elaborate on details, but DO NOT invent new major plot elements, antagonists, or conspiracies
```

---

## WHY THIS HAPPENED

### Recent Simplification
The user and I recently simplified prompts from 133 lines to ~45 lines (66% reduction).

**What we removed:**
- Formulaic beat pattern explanations ✅ Good removal
- Over-prescriptive instructions ✅ Good removal
- Long examples ✅ Good removal

**What we accidentally removed:**
- Treatment fidelity guard rails ❌ BAD REMOVAL
- Extraction vs generation framing ❌ BAD REMOVAL
- Explicit "source of truth" references ❌ BAD REMOVAL

### Key Insight
**Simplification was correct, but we simplified the WRONG parts.**

We should have:
- ✅ Removed formulaic writing advice (LLM knows story structure)
- ❌ KEPT treatment fidelity instructions (LLM doesn't know to extract vs generate)

---

## EXPECTED IMPACT

### Before Fix
```
Treatment: "Dr. Lang is the antagonist"
↓
Chapter Generation: "Sarah discovers Project Chimera, a secret government program"
↓
Validation: ❌ CRITICAL ISSUE - invented "Project Chimera"
↓
User has to iterate/abort
```

### After Fix
```
Treatment: "Dr. Lang is the antagonist"
↓
Chapter Generation: "Sarah confronts Dr. Lang (treatment plot) in his lab (scene detail)"
↓
Validation: ✓ PASS - faithfully extracted from treatment
↓
No iteration needed
```

---

## IMPLEMENTATION ORDER

1. **CRITICAL (do first):** Add context_yaml to prompt + extraction instructions
2. **CRITICAL (do first):** Lower temperature to 0.3
3. **CRITICAL (do first):** Update system message
4. **Important:** Add forbidden/allowed lists
5. **Important:** Add examples
6. **Important:** Add final reminder
7. **Enhancement:** Update foundation generation similarly
8. **Testing:** Generate chapters and verify no violations

---

## VALIDATION

The validation system is working correctly - it's catching these issues. The problem is the generation is creating violations in the first place.

**Goal:** Reduce validation failures from ~50% to <5% by fixing generation fidelity.

---

## COMMIT MESSAGE

```
Fix: Chapter generation now extracts from treatment instead of inventing

CRITICAL BUG: Chapter generation prompt didn't show the treatment to LLM!
The context_yaml parameter (containing treatment) was passed but never used
in the prompt. This forced the LLM to invent plot elements instead of
extracting from the treatment, causing treatment fidelity violations.

Root Cause:
- _generate_single_chapter() receives context_yaml (premise + treatment)
- Prompt only showed foundation (metadata/characters/world)
- Treatment plot was never shown to LLM
- LLM invented new plot elements (antagonists, conspiracies, etc.)
- Validation correctly flagged these as treatment violations

Changes:
1. Add treatment (context_yaml) to chapter generation prompt
2. Reframe from "Generate" to "Extract and structure"
3. Add explicit extraction instructions
4. Add forbidden/allowed lists (no new antagonists, etc.)
5. Lower temperature from 0.6 to 0.3 (extraction not creativity)
6. Update system message to emphasize extraction
7. Add examples of good vs bad extraction
8. Add final pre-validation reminder

Architecture Change:
Chapter generation is now clearly framed as EXTRACTION + STRUCTURING
rather than CREATIVE GENERATION. The treatment is the source of truth,
and chapters extract/structure its plot into scenes and beats.

Expected Impact:
- Reduce treatment fidelity violations from ~50% to <5%
- Fewer iteration cycles needed
- Faithful adaptation of treatment plot
- Auto-fix mode will rarely trigger

Files:
- src/generation/chapters.py: _generate_single_chapter() prompt
```
