---
name: iterate
description: Refine content with natural language feedback.
argument-hint: "[target] [feedback]"
---

Refine content with feedback, maintaining consistency and quality.

## Self-Contained Stages Model

Each stage's output is self-contained — it carries forward all information needed by downstream stages. When you iterate on stage N:

- Stage N becomes the new source of truth for downstream stages
- Stage N-1 becomes "historical" (the seed that started things, not the contract)
- Downstream stages (N+1, N+2...) automatically see the changes because they only read stage N

**Example:** If you iterate on treatment to change the ending, you don't need to update premise. Structure-plan reads only treatment, so it sees the new ending automatically. No conflicts.

## Usage

```
/iterate [target] [feedback]
```

## Arguments

- `target` (optional): What to iterate on - `premise`, `treatment`, `plan`, `chapter-plan`, or `prose`
- `feedback` (optional): Natural language description of desired changes

## Instructions

### Step 0: Detect Current Project

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, fall back to directory detection:
   - Look for `project.yaml` in the current directory or parent directories under `books/`
   - If not found, ask the user which project to work on (or suggest `/select-book`)

### Step 1: Determine Target

If `target` not provided, ask the user:
- What would you like to iterate on?
  1. Premise - refine the core concept
  2. Treatment - adjust the story outline
  3. Plan - modify structure plan (scene/chapter breakdown)
  4. Chapter/story plan - adjust a generation plan (novella/novel/epic: specific chapter, flash/short/novelette: story plan)
  5. Prose - revise generated prose

For chapter/story plan:
- Novella/novel/epic: ask which chapter plan to revise
- Flash/short/novelette: there's only one plan (`short-story-plan.md`)

For prose, also ask which chapter(s) to revise, or "all" for the entire story.

### Step 2: Gather Feedback

If `feedback` not provided, ask the user:
- What changes would you like to make?

### Step 3: Confirm Understanding

**Before making any changes, restate what you understood:**

```
I understand you want me to:
- [Specific change 1]
- [Specific change 2]

This will affect: [areas/chapters impacted]

Proceed with these changes?
```

**If feedback is ambiguous, ask clarifying questions first:**
- "When you say 'darker', do you mean tone, violence, themes, or all three?"
- "Should this apply to the whole chapter or specific scenes?"
- "Do you want to keep [element X] or is that part of what should change?"

Do NOT proceed until you're confident you understand the request.

### Step 3.5: Enumerate Planned Changes

Before making any edits, list exactly what you will modify:

```
Planned modifications:
- [Section/paragraph 1] — [what will change]
- [Section/paragraph 2] — [what will change]

Sections preserved unchanged:
- [Section A]
- [Section B]
```

This ensures precision and allows the user to catch unintended changes before they happen.

### Step 4: Read Context

**Read only the immediately prior stage plus the target being iterated.**

Read `books/{project}/project.yaml` to get the genre for taxonomy lookup.

**For premise iteration:**
- `books/{project}/premise.md` - Current premise
- `taxonomies/base-taxonomy.json` - Universal properties
- `taxonomies/{genre}-taxonomy.json` - Genre-specific options
- `taxonomies/style-taxonomy.json` - Style options (if changing style)

**For treatment iteration:**
- `books/{project}/treatment.md` - Current treatment (already self-contained with frontmatter)
- Do NOT read premise.md — treatment is the authoritative document now
- Note: If iterating on treatment, ensure frontmatter stays accurate

**For plan iteration (structure-plan.md):**
- `books/{project}/structure-plan.md` - Current plan (already contains frontmatter + Characters)
- Do NOT read premise.md or treatment.md — structure-plan is self-contained

**For chapter plan iteration (novella/novel/epic):**
- `books/{project}/structure-plan.md` - For frontmatter and character reference
- `books/{project}/summaries.md` (if exists) - For continuity
- The specific chapter plan being revised
- `books/{project}/chapter-plans/chapter-{PP}-plan.md` (if exists) - Previous chapter plan (local continuity only)
- Do NOT read premise.md or treatment.md

**For story plan iteration (flash/short/novelette):**
- `books/{project}/structure-plan.md` - For frontmatter and character reference
- `books/{project}/short-story-plan.md` - The plan being revised
- Do NOT read premise.md or treatment.md

**For prose iteration (novella/novel/epic):**
- `books/{project}/chapter-plans/chapter-{NN}-plan.md` - The plan for the chapter being revised
- `books/{project}/summaries.md` (if exists) - Canon Facts + Open Threads continuity anchor
- `books/{project}/chapters/chapter-{NN}.md` - The chapter being revised
- Previous chapters for voice continuity (scaled by length):
  - Novella: all previous chapters
  - Novel: last 3 chapters
  - Epic: last 2 chapters
- `misc/prose-style-{prose_style_key}.md` - Style card matching the project's prose style
- Do NOT read premise.md, treatment.md, or structure-plan.md

If revising multiple chapters, do it sequentially (one chapter at a time). Update `summaries.md` (both Canon Facts master section and per-chapter data) as you go.

**For prose iteration (flash/short/novelette):**
- `books/{project}/short-story-plan.md` - The story plan
- `books/{project}/short-story.md` - The story being revised
- `misc/prose-style-{prose_style_key}.md` - Style card matching the project's prose style
- Do NOT read premise.md, treatment.md, or structure-plan.md

### Step 5: Apply Changes

Generate the revised content:

1. **Apply the confirmed changes** - Make the specific changes discussed
2. **Preserve everything else** - Don't change elements not mentioned in feedback
3. **Maintain consistency** - Ensure changes align with the current stage's context
4. **Follow frontmatter** - For prose, use the style from chapter-plan's frontmatter and Style Notes (originally from premise → treatment → structure-plan)

**Prose iteration principles:**
- Preserve the author's distinctive voice and style
- Keep strong emotional beats and character moments
- Maintain character-specific dialogue patterns
- Don't flatten literary prose into generic writing
- If cutting for pacing, preserve essential story information

### Step 6: Show Summary of Changes

Briefly summarize what changed:

```
Changes applied:
- {Change 1}
- {Change 2}

Preserved:
- {Key element kept intact}
- {Another preserved element}
```

### Step 7: Write and Commit

Write the revised file(s) to `books/{project}/` and commit:

```bash
cd books && git add {project}/{file(s)} && git commit -m "Iterate: {target} - {brief feedback summary}"
```

**For prose iteration:** Also update and commit `summaries.md` (Chapter Summaries + Canon Facts + Open Threads Ledger) to reflect any changes you made.

## Iteration Guidelines

### Minimal Edits Principle

- Prefer targeted changes over wholesale rewrites
- If feedback affects one paragraph, edit that paragraph—not the entire section
- If feedback is broad ("make it darker"), still identify the smallest set of changes that achieves the goal
- Only rewrite entire documents when explicitly requested ("rewrite this from scratch")

### Premise Iteration

- Preserve the core hook unless explicitly asked to change
- Maintain genre alignment
- Update taxonomy selections if tone/style changes significantly

### Treatment Iteration

- Keep the basic story arc unless restructuring is requested
- Ensure changes cascade properly (if Act I changes, Act II/III may need adjustment)
- Maintain character arc consistency

### Plan Iteration (structure-plan.md)

- Preserve chapter/scene count unless explicitly asked to add/remove
- Adjust pacing notes if content changes significantly
- Update continuity tracking table

### Chapter Plan Iteration

- Iterate on chapter plans **before** generating prose for that chapter
- Adjust scene breakdowns, character states, or style notes as needed
- If the chapter's prose already exists, note that prose may need regeneration
- For flash/short/novelette, iterate on `short-story-plan.md`

### Prose Iteration

**Most common iteration target.** Apply feedback while maintaining:
- The story's established voice and tone
- Character voice consistency
- Plot thread continuity
- Established world details

Use the chapter-plan's Style Notes as guidance, not rigid rules. If the existing prose has a distinctive style that works, preserve it. The matching style card (`misc/prose-style-{prose_style_key}.md`) provides detailed reference.

**After prose iteration, update `summaries.md`** to reflect any changes to:
- Chapter/scene summaries (if plot events changed)
- Open threads (if threads were resolved, added, or modified)
- Facts/continuity details (if world details or character states changed)

This keeps the continuity anchor in sync with actual prose content.

**What to preserve during prose iteration:**
- Distinctive atmosphere and world-building
- Strong emotional beats
- Character-specific dialogue patterns
- Effective metaphors and imagery

**What to improve when asked:**
- Overly complex sentences that slow reading
- Redundant descriptions or repetitive imagery
- Pacing issues (too slow/fast for the scene type)
- Unclear plot points or confusing passages

For chapter-specific feedback, only revise that chapter.
For global feedback ("make everything darker"), revise all chapters.

## Natural Language Feedback Examples

- "Make the protagonist more conflicted about their decision"
- "Add more sensory details to the forest scenes"
- "The pacing feels slow in chapter 3, tighten it up"
- "I want the antagonist to be more sympathetic"
- "Add more romantic tension between the leads"
- "The dialogue feels stilted, make it more natural"
- "This chapter needs a stronger hook at the end"

## Cascading Changes and the Self-Contained Model

Because each stage only reads the immediately prior stage, iteration automatically propagates forward.

### Before Making Changes

If the requested change will force cascading edits to other files or sections:

1. **Enumerate the cascade first:**
   ```
   This change will affect:
   - treatment.md: frontmatter (field X)
   - structure-plan.md: frontmatter would become stale (currently copies from treatment)
   - chapter-plans/: may need regeneration if structure changes significantly
   ```

2. **Ask user how to proceed:**
   - Proceed with change + inform about downstream staleness?
   - Proceed and cascade updates to downstream files?
   - Abort and reconsider?

### Cascade Rules by Stage

**Premise changes:**
- If downstream stages don't exist yet: no action needed — they'll read the updated premise
- If treatment already exists: treatment's frontmatter may be stale. Inform user they may want to regenerate treatment or update its frontmatter.

**Treatment changes:**
- Structure-plan reads only treatment, so it automatically sees changes when regenerated
- If structure-plan already exists: inform user the ending/arc changed and they may want to regenerate structure-plan
- Premise becomes "historical" — it's the seed, not the contract

**Structure plan changes → May require:**
- Chapter plan revisions for affected chapters
- Prose revision for affected chapters

**Chapter plan changes → May require:**
- Prose regeneration for that chapter (if prose exists)

After completing the iteration, inform the user if downstream stages may need updating.

## Version History

Each iteration creates a git commit. Users can:
- View history: `git log --oneline`
- Compare versions: `git diff HEAD~1`
- Revert changes: `git checkout HEAD~1 -- {file}`

Remind users of these options when they express uncertainty about changes.
