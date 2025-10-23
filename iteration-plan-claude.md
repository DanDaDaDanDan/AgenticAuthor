# Iteration System Design

**Status:** Design Document
**Date:** 2025-10-23
**Purpose:** Unified natural language iteration system for all generated content (premise, treatment, chapters, prose)

---

## Core Philosophy

**Always-on iteration mode:** The entire REPL operates as an iteration system. Any text that isn't a command is treated as iteration feedback for the current target.

**Key principles:**
1. **Natural language only** - Users provide freeform feedback, LLM handles the details
2. **Judge-validated** - Every iteration is validated by LLM judge before user review
3. **Context-aware** - Full context (upstream content + iteration history) provided
4. **Holistic regeneration** - Entire LOD level regenerated to maintain consistency
5. **Human-in-the-loop** - User approves all changes after seeing semantic diff
6. **Git-tracked** - Every iteration creates a git commit for easy rollback

---

## Iteration Targets

### Supported LOD Levels

| Target | Content | Context Provided | Downstream |
|--------|---------|------------------|------------|
| `premise` | premise_metadata.json | taxonomy | treatment, chapters, prose |
| `treatment` | treatment.md | premise, taxonomy | chapters, prose |
| `chapters` | chapter-beats/*.md | premise, treatment, taxonomy, foundation, chapters | prose |
| `prose` | chapters/*.md | premise, treatment, chapters (full structure) | none |

### Target Auto-Setting

**Rule:** Iteration target auto-sets to the most recent generation command.

```bash
/generate premise
[Iteration target: premise]

/generate treatment
[Iteration target: treatment]

/generate chapters
[Iteration target: chapters]
```

**Manual override:**
```bash
/iterate treatment
[Iteration target: treatment]
```

**Query current target:**
```bash
/iterate
[Current iteration target: chapters]
[Iteration history: 3 iterations]
```

**Error handling:**
```bash
# If no content generated yet
> Make this darker
[Error: No iteration target set. Generate content first with /generate]

# If trying to set invalid target
/iterate foo
[Error: Invalid target. Valid targets: premise, treatment, chapters, prose]

# If target content doesn't exist
/iterate chapters
[Error: No chapters found. Generate chapters first with /generate chapters]
```

---

## Iteration Workflow

### 1. User Provides Feedback

```bash
# Single line (most common)
> Make chapter 3 darker with more internal conflict

# Multi-line paste (from external editor)
> Make chapter 3 darker with nightmarish imagery.
> Add three internal conflict scenes where protagonist questions their morality.
> Ensure changes fit with the redemption arc we added previously.
[Enter submits immediately - no special delimiter needed]
```

**Input handling:**
- Enter always submits (no multi-line input mode)
- Multi-line paste is supported (line breaks preserved)
- Feedback can be any length
- Empty input is ignored (no operation)

### 2. Downstream Check

Before generation, check if downstream content exists:

```bash
⚠️  Downstream content will be affected:
  • Prose (8 chapters generated from current chapters)
  • Analysis (3 analysis reports)

Action: (cull-all/keep-all/cancel): _
```

**Options:**
- `cull-all`: Delete all downstream content (clean slate for regeneration)
- `keep-all`: Mark downstream as potentially stale, keep files
- `cancel`: Abort iteration

**No partial culling** - it's all or nothing to avoid complexity.

### 3. Generation Loop (with Judge Validation)

```bash
[Generating chapters... Attempt 1]
  • Context: taxonomy, treatment, foundation, 15 chapters, 3 previous iterations
  • Feedback: "Make chapter 3 darker with more internal conflict"

[████████████████████████] 100%
✓ Generated (saved to debug/)

[Running validation judge...]
Judge verdict: ✗ NEEDS REVISION

Judge feedback:
  "Chapter 3 tone is still optimistic. The added conflict scenes are present
   but don't convey darkness. Needs nightmarish imagery and moral ambiguity.
   Protagonist still makes heroic choices without internal struggle."

Continue with judge feedback? (yes/no/view-partial): yes

[Generating chapters... Attempt 2]
  • Context: Same as attempt 1
  • Feedback: Original + Judge feedback

[████████████████████████] 100%
✓ Generated (saved to debug/)

[Running validation judge...]
Judge verdict: ✗ NEEDS REVISION

Judge feedback:
  "Improvement - darker imagery present. However, internal conflict feels
   superficial. Protagonist needs to genuinely question their methods and
   face morally gray decisions where there's no clear right answer."

Continue with judge feedback? (yes/no/view-partial): yes

[Generating chapters... Attempt 3]
  • Context: Same as attempt 1
  • Feedback: Original + Judge feedback (cumulative)

[████████████████████████] 100%
✓ Generated (saved to debug/)

[Running validation judge...]
Judge verdict: ✓ APPROVED

Judge reasoning:
  "Chapter 3 successfully darkened. Nightmare opening establishes tone.
   Three internal conflict scenes show genuine moral struggle. Protagonist
   makes morally ambiguous choice that will haunt them. Tone shift is
   consistent with redemption arc - makes eventual redemption harder-earned
   and more meaningful. Changes well-integrated across all chapters."
```

**Key behaviors:**
- **No max attempts** - Human decides when to stop
- **Judge feedback accumulates** - Each attempt gets original + all judge feedback
- **All attempts saved to debug** - For post-mortem analysis
- **Human options at each failure:**
  - `yes`: Continue with judge feedback (regenerate)
  - `no`: Stop loop, accept current result anyway
  - `view-partial`: Show semantic diff of current attempt, then decide

### 4. Semantic Diff (via LLM)

After judge approval (or user accepts partial result):

```bash
[Generating semantic diff...]
  • Comparing: Old vs New content
  • Context: User feedback + iteration history
  • Analysis: What changed and why

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITERATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User feedback:
  "Make chapter 3 darker with more internal conflict"

Judge attempts: 3 (approved on attempt 3)

CHANGES TO CHAPTERS:

Foundation (metadata, characters, world):
  ✓ Themes: Added "moral ambiguity" to existing [redemption, sacrifice, duty]
  ✓ Protagonist archetype: hero → anti-hero
  ✓ Chapter 3 tone metadata: "hopeful" → "dark, introspective"

Chapter Structure:

  Major changes (★★★):
    • Chapter 3: COMPLETE REWRITE for darker tone

      Opening:
        Before: Protagonist wakes refreshed, ready to face challenges
        After:  Protagonist wakes from nightmare of victims they couldn't save

      New scenes added:
        - Scene 2: Internal conflict - questions if ends justify means
        - Scene 4: Moral dilemma - must choose between two bad options
        - Scene 6: Dark reflection - realizes they're becoming what they fought

      Ending:
        Before: Clear victory, protagonist feels justified
        After:  Pyrrhic victory, protagonist makes morally gray choice that haunts them

      Tone shift: Heroic → Morally complex
      Word count: +15% (added internal monologue)

  Moderate changes (★★):
    • Chapter 2: Foreshadowing adjustments
      - Added nightmare imagery in final scene
      - Protagonist shows first signs of moral doubt

    • Chapter 4: Consequence ripples
      - Other characters react to protagonist's chapter 3 choice
      - Trust issues emerge

  Minor changes (★):
    • Chapters 1, 5-7: Tone calibration for consistency
      - Subtle foreshadowing of darkness to come
      - Character dialogue references moral ambiguity

    • Chapters 8-15: No structural changes
      - Minor tone adjustments only

Overall impact:
  • Files changed: 8 of 16 (foundation + 7 chapters)
  • Lines changed: ±187 across all files
  • Arc impact: Redemption now harder-earned, more meaningful
  • Tone: Shifted from heroic to morally complex
  • Consistency: Maintained with established redemption arc

Why these changes work:
  The darkness in chapter 3 creates a low point that makes the redemption
  arc more powerful. By showing the protagonist at their worst - morally
  compromised and questioning themselves - we set up a more satisfying
  journey back to the light. The changes ripple forward naturally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View detailed text diff? (foundation/chapter-3/all/skip): _
```

**Semantic diff features:**
- **LLM-generated** - Human-readable summary, not raw git diff
- **Hierarchical** - Foundation → Major → Moderate → Minor changes
- **Before/After** - Shows key scene changes in plain English
- **Context-aware** - Explains why changes work (references iteration history)
- **Selective drill-down** - Option to see detailed text diffs for specific files

**"Details" option shows actual text diffs:**
```bash
View detailed text diff? (foundation/chapter-3/all/skip): chapter-3

━━━ Chapter 3: Detailed Changes ━━━

Opening Scene (Lines 1-45):

  OLD:
    Marcus woke as the first rays of sunlight streamed through the window.
    He felt refreshed, ready to face whatever challenges the day might bring.
    Today was the day he'd finally confront the corrupt magistrate.

  NEW:
    Marcus woke in darkness, heart pounding. The nightmare again—faces of
    those he'd failed to save, their accusing eyes following him even in
    sleep. He sat up, drenched in sweat. Three months since the warehouse
    fire. Three months of those faces haunting him. Was he saving people,
    or just delaying the inevitable? The thought made him sick.

[... continues with detailed line-by-line comparison ...]

Press Enter for next section, 'q' to return to summary: _
```

### 5. User Approval

```bash
Accept these changes? (yes/no/diff): _
```

**Options:**
- `yes`: Accept all changes, finalize iteration
- `no`: Reject, rollback to previous version
- `diff`: Re-show semantic summary (or detailed diff)

### 6. Finalization

```bash
[Finalizing iteration...]
  ✓ Chapter beats saved (16 files)
  ✓ Iteration history updated (4 total iterations)
  ✓ Prose culled (8 chapters deleted)
  ✓ Git commit: "[chapters] Make chapter 3 darker with more internal conflict"

✓ Iteration complete (3 judge attempts, approved)

To review full diff: git diff HEAD~1
To undo iteration: git reset --hard HEAD~1

[Iteration target: chapters]
Ready for next iteration.
```

---

## Iteration History

### Storage Format

**Location:** `{lod-folder}/iteration_history.json`

Examples:
- `premise/iteration_history.json`
- `treatment/iteration_history.json`
- `chapter-beats/iteration_history.json`
- `chapters/iteration_history.json`

**Schema:**
```json
{
  "iterations": [
    {
      "timestamp": "2025-10-23T19:30:00Z",
      "feedback": "Make chapter 3 darker with more internal conflict",
      "judge_attempts": 3,
      "judge_verdict": "approved",
      "judge_reasoning": "Chapter 3 successfully darkened. Nightmare opening...",
      "semantic_summary": "Major changes to chapter 3: complete rewrite for darker tone...",
      "commit_sha": "abc123f",
      "files_changed": 8,
      "lines_changed": 187
    },
    {
      "timestamp": "2025-10-23T19:15:00Z",
      "feedback": "Add redemption arc in act 3",
      "judge_attempts": 1,
      "judge_verdict": "approved",
      "judge_reasoning": "Redemption arc well-integrated...",
      "semantic_summary": "Added redemption arc: chapters 11-15 modified...",
      "commit_sha": "def456a",
      "files_changed": 6,
      "lines_changed": 94
    },
    {
      "timestamp": "2025-10-23T19:00:00Z",
      "feedback": "Make protagonist more flawed",
      "judge_attempts": 2,
      "judge_verdict": "approved",
      "judge_reasoning": "Protagonist flaws well-developed...",
      "semantic_summary": "Protagonist changes: added hubris and self-doubt...",
      "commit_sha": "ghi789b",
      "files_changed": 12,
      "lines_changed": 143
    }
  ]
}
```

### Context Usage

**Iteration history is included in every generation:**

```python
# Prompt context for iteration
context = {
    'taxonomy': {...},              # Latest version
    'treatment': "...",             # Latest version
    'foundation': {...},            # Latest version
    'chapters': [...],              # Latest version
    'iteration_history': [          # FULL history of feedback
        {
            'feedback': "Make protagonist more flawed",
            'semantic_summary': "Protagonist changes: added hubris..."
        },
        {
            'feedback': "Add redemption arc in act 3",
            'semantic_summary': "Added redemption arc: chapters 11-15..."
        },
        {
            'feedback': "Make chapter 3 darker with more internal conflict",
            'semantic_summary': "Major changes to chapter 3: complete rewrite..."
        }
    ]
}
```

**Why include semantic summaries?**
- Provides **what changed** not just **why**
- Helps LLM understand cumulative effect of iterations
- Prevents "forgetting" previous changes

**Token management:**
- Modern models (200k+ context) can handle full history
- If history grows very long (50+ iterations), consider summarization
- For now: include everything, optimize later if needed

---

## Debug Storage

### Automatic Debug Saves

**Every generation attempt is saved for debugging:**

```
.agentic/debug/{project-name}/iteration_{target}_{timestamp}/
  attempt_1_raw.md                    # Raw LLM output
  attempt_1_judge_verdict.json        # Judge analysis
  attempt_2_raw.md
  attempt_2_judge_verdict.json
  attempt_3_raw.md                    # (approved)
  attempt_3_judge_verdict.json
  final_semantic_diff.md              # Semantic diff shown to user
  user_decision.txt                   # "accepted" or "rejected"
```

**Judge verdict format:**
```json
{
  "verdict": "needs_revision",
  "reasoning": "Chapter 3 tone is still optimistic. The added conflict scenes are present but don't convey darkness. Needs nightmarish imagery and moral ambiguity.",
  "specific_issues": [
    "Opening scene lacks darkness",
    "Internal conflict feels superficial",
    "Protagonist makes heroic choices without struggle"
  ],
  "suggestions": [
    "Add nightmare or flashback opening",
    "Show genuine moral dilemmas with no clear answer",
    "Make protagonist question their methods"
  ]
}
```

**Purpose:**
- Post-mortem analysis when iterations don't work as expected
- Training data for improving judge prompts
- Understanding LLM behavior patterns
- User can review attempts if they're unsure about accepting

---

## Implementation Details

### Judge Prompt

**Location:** `src/prompts/validation/iteration_fidelity.j2`

**Purpose:** Validate that generated content matches user feedback + context

**Input:**
- User feedback (original)
- Iteration history (all previous feedback + summaries)
- Old content (before iteration)
- New content (generated)
- Context (upstream content: premise, treatment, etc.)

**Output:**
```json
{
  "verdict": "approved" | "needs_revision",
  "reasoning": "Detailed explanation of why approved or what's missing",
  "specific_issues": ["Issue 1", "Issue 2", ...],  // If needs_revision
  "suggestions": ["Suggestion 1", "Suggestion 2", ...]  // If needs_revision
}
```

**Temperature:** 0.1 (consistent, strict evaluation)

**Validation criteria:**
1. Does new content address user feedback?
2. Are changes consistent with iteration history?
3. Is quality maintained (no degradation)?
4. Are changes appropriate in scope?
5. Does it maintain consistency with upstream context?

### Semantic Diff Prompt

**Location:** `src/prompts/analysis/semantic_diff.j2`

**Purpose:** Generate human-readable summary of what changed and why

**Input:**
- User feedback
- Iteration history
- Old content
- New content
- Judge verdict + reasoning

**Output:** Markdown-formatted semantic diff (see example in workflow section)

**Temperature:** 0.3 (creative but consistent)

**Analysis requirements:**
1. Categorize changes by magnitude (major/moderate/minor)
2. Before/After comparisons for key changes
3. Explain **why** changes work (reference feedback + history)
4. Quantify impact (files changed, lines changed, tone shifts)
5. Highlight risks or inconsistencies

### Architecture Components

**New files needed:**
```
src/generation/iteration/
├── __init__.py
├── iterator.py              # Main iteration coordinator
├── judge.py                 # Judge validation
├── semantic_diff.py         # Semantic diff generator
└── history.py               # Iteration history management

src/prompts/validation/
└── iteration_fidelity.j2    # Judge prompt

src/prompts/analysis/
└── semantic_diff.j2         # Semantic diff prompt
```

**Iterator coordinator (`iterator.py`):**
```python
class Iterator:
    """Coordinates iteration workflow."""

    async def iterate(
        self,
        target: str,              # "chapters", "treatment", etc.
        feedback: str,            # User feedback
        cull_downstream: bool     # User choice
    ) -> IterationResult:
        """
        Execute iteration workflow:
        1. Load context + history
        2. Generation loop (with judge validation)
        3. Generate semantic diff
        4. Get user approval
        5. Finalize (save + commit)
        """
        pass
```

### Integration Points

**Changes to `src/cli/interactive.py`:**

1. **Track iteration target in session:**
```python
class InteractiveSession:
    def __init__(self):
        self.iteration_target: Optional[str] = None
        # ... existing code
```

2. **Auto-set target after generation:**
```python
async def generate_premise(self, args: str):
    # ... existing generation code
    self.iteration_target = "premise"
    self.console.print("[dim]Iteration target set: premise[/dim]")
```

3. **Handle non-command input as iteration:**
```python
async def process_input(self, user_input: str):
    # Check if it's a command
    if user_input.startswith('/'):
        await self.execute_command(user_input)
    else:
        # It's iteration feedback
        await self.handle_iteration_feedback(user_input)
```

4. **New iteration command:**
```python
async def cmd_iterate(self, args: str):
    """
    Set or query iteration target.

    Usage:
        /iterate chapters    # Set target to chapters
        /iterate             # Show current target + history
    """
    if not args:
        # Show current target
        self.show_iteration_status()
    else:
        # Set new target
        self.set_iteration_target(args)
```

---

## Example Sessions

### Session 1: Iterating on Chapters

```bash
$ agentic
> /open my-novel
Project: my-novel (fantasy, 80k words, 15 chapters)

> /generate chapters
[Generates 15 chapters...]
✓ Chapters generated
[Iteration target: chapters]

> Make chapter 3 darker and add internal conflict

⚠️ Prose exists (8 chapters)
   Cull all downstream? (yes/no/cancel): yes

[Generating chapters... Attempt 1]
✓ Generated
[Judge: ✗ "Tone still optimistic"]

[Generating chapters... Attempt 2]
✓ Generated
[Judge: ✓ "Approved"]

[Semantic diff...]
Major changes: Chapter 3 rewritten with darker tone
Accept? (yes/no/diff): yes

✓ Iteration complete
[Iteration target: chapters]

> Also make chapter 7 reflect the consequences of chapter 3

[Generating chapters... Attempt 1]
✓ Generated
[Judge: ✓ "Approved"]

[Semantic diff...]
Moderate changes: Chapter 7 shows consequences
Accept? (yes/no/diff): yes

✓ Iteration complete

> /status
Project: my-novel
Iteration target: chapters
Iterations: 2 on chapters
```

### Session 2: Switching Targets

```bash
> /iterate treatment
[Iteration target: treatment]
[Loaded: premise, treatment, taxonomy]
[History: 1 previous iteration]

> Add a betrayal subplot in act 2

⚠️ Downstream: chapters (15), prose (8)
   Cull all? (yes/no/cancel): yes

[Generating treatment... Attempt 1]
✓ Generated
[Judge: ✓ "Approved"]

[Semantic diff...]
Major changes: New betrayal subplot added to Act 2
Accept? (yes/no/diff): yes

✓ Iteration complete
[Iteration target: treatment]

> /iterate chapters
[Iteration target: chapters]
[Error: No chapters found. Generate first with /generate chapters]

> /generate chapters
[Generates from new treatment with betrayal subplot...]
✓ Chapters generated
[Iteration target: chapters]
```

### Session 3: Judge Loop with Human Decision

```bash
> Make the ending more ambiguous

[Generating chapters... Attempt 1]
✓ Generated
[Judge: ✗ "Ending is still conclusive, not ambiguous"]

Continue? (yes/no/view-partial): view-partial

[Semantic diff for attempt 1...]
Changes: Final chapter has open-ended questions but still resolves main plot
View full? (yes/no): no

Continue with judge feedback? (yes/no): yes

[Generating chapters... Attempt 2]
✓ Generated
[Judge: ✗ "Better but protagonist's fate too clear"]

Continue? (yes/no/view-partial): yes

[Generating chapters... Attempt 3]
✓ Generated
[Judge: ✓ "Approved - ambiguous ending achieved"]

[Semantic diff...]
Major changes: Chapter 15 rewritten with ambiguous ending
Accept? (yes/no/diff): yes

✓ Iteration complete (3 attempts)
```

---

## Success Criteria

An iteration is successful when:

1. ✅ **Judge approves** - Changes match user feedback
2. ✅ **User approves** - Semantic diff looks good
3. ✅ **Context maintained** - Consistency with upstream content
4. ✅ **History preserved** - Iteration logged with semantic summary
5. ✅ **Git committed** - Changes are tracked and reversible

---

## Future Enhancements

### Phase 2 (Post-MVP)
- **Iteration templates**: Common patterns like "make darker", "add subplot", etc.
- **Batch iterations**: Multiple feedback items in one iteration
- **Conditional iterations**: "If X then Y" logic
- **A/B testing**: Generate multiple variations, let user choose
- **Smart context pruning**: Summarize very long iteration histories

### Phase 3 (Advanced)
- **Cross-LOD iteration**: "Change protagonist age" affects premise → treatment → chapters
- **Incremental iteration**: Only regenerate affected chapters, not all
- **Iteration analytics**: Which types of feedback work best
- **Learning system**: Improve judge based on user accept/reject patterns

---

## Open Questions

1. **Token costs**: Full iteration history could be expensive. Monitor and optimize?
2. **Judge quality**: Will single judge model work or need ensemble?
3. **Diff granularity**: Is chapter-level diff enough or need scene-level?
4. **Undo complexity**: Git rollback is simple, but what about partial rollback?
5. **Performance**: Multiple judge attempts could be slow. Acceptable?

---

## Implementation Priority

### Phase 1 (MVP) - Essential Features
1. ✅ Iteration target tracking
2. ✅ Context loading (upstream + history)
3. ✅ Generation loop with judge validation
4. ✅ Semantic diff generation
5. ✅ User approval flow
6. ✅ Iteration history storage
7. ✅ Debug file storage

### Phase 2 - Polish
1. ⏳ Detailed text diff viewer (for "details" option)
2. ⏳ Better error handling (network failures, etc.)
3. ⏳ Progress indicators (better UX during long generations)
4. ⏳ Iteration statistics (success rate, common patterns)

### Phase 3 - Advanced
1. ⏳ Context optimization (smart history summarization)
2. ⏳ Judge improvements (multiple validation passes)
3. ⏳ Incremental iteration (chapter-level precision)
4. ⏳ Cross-LOD cascade handling

---

## Conclusion

This iteration system provides:
- **Natural workflow**: Always-on iteration mode, no mode switching
- **Quality assurance**: Judge validation ensures changes match intent
- **Transparency**: Semantic diffs show exactly what changed and why
- **Safety**: Git tracking + debug storage for every attempt
- **Flexibility**: Works across all LOD levels with same interface
- **Context preservation**: Full iteration history prevents "forgetting"

The system is designed to feel **conversational** (like talking to an editor) while maintaining **technical rigor** (validation, version control, debugging).
