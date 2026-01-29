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

- `target` (optional): What to iterate on - `premise`, `treatment`, `plan`, `story-plan`, `chapter-plan`, or `prose`
- `feedback` (optional): Natural language description of desired changes

## Instructions

### Step 1: Detect Project (Main Context)

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, ask the user which project to work on (or suggest `/select-book`)

### Step 2: Determine Target (Main Context)

If `target` not provided, ask the user:
- What would you like to iterate on?
  1. Premise - refine the core concept
  2. Treatment - adjust the story outline
  3. Plan - modify structure plan (macro scene/chapter breakdown)
  4. Story plan - modify micro beat sheet (flash/short/novelette only)
  5. Chapter plan - adjust a chapter's generation plan (novella/novel/epic only)
  6. Prose - revise generated prose

For chapter plan (novella/novel/epic only):
- Ask which chapter plan to revise

For prose, also ask which chapter(s) to revise, or "all" for the entire story.

### Step 3: Gather Feedback (Main Context)

If `feedback` not provided, ask the user:
- What changes would you like to make?

### Step 4: Confirm Understanding (Main Context)

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

### Step 5: Enumerate Planned Changes (Main Context)

Before spawning the edit sub-agent, describe what will be modified:

```
Planned modifications:
- [Section/paragraph 1] — [what will change]
- [Section/paragraph 2] — [what will change]

Sections preserved unchanged:
- [Section A]
- [Section B]
```

**Ask for approval:**
```
Ready to apply these changes?
```

### Step 6: Check for Cascading Changes (Main Context)

If the requested change will force cascading edits to other files:

1. **Enumerate the cascade:**
   ```
   This change will affect:
   - 03-treatment.md: frontmatter (field X)
   - 04-structure-plan.md: frontmatter would become stale
   - 05-chapter-plans/: may need regeneration if structure changes significantly
   ```

2. **Ask user how to proceed:**
   - Proceed with change + inform about downstream staleness?
   - Proceed and cascade updates to downstream files?
   - Abort and reconsider?

### Step 7: Spawn Edit Sub-Agent

Once the user approves, use the Task tool to spawn an Edit Sub-Agent with subagent_type `general-purpose`.

**Sub-agent prompt template:**

```
You are the Edit Sub-Agent for AgenticAuthor.

## Task
Apply iteration changes to "{target}" for project "{project}".

## Approved Changes
{enumerated list of approved changes from Step 5}

## Context Reading

Read `books/{project}/project.yaml` to get the genre for taxonomy lookup.

**Read only the immediately prior stage plus the target being iterated:**

**For premise iteration:**
- `books/{project}/01-premise.md` - Current premise
- `taxonomies/base-taxonomy.json` - Universal properties
- `taxonomies/{genre}-taxonomy.json` - Genre-specific options
- `taxonomies/style-taxonomy.json` - Style options (if changing style)

**For treatment iteration:**
- `books/{project}/03-treatment.md` - Current treatment (already self-contained with frontmatter)
- Do NOT read 01-premise.md — treatment is the authoritative document now

**For plan iteration (04-structure-plan.md):**
- `books/{project}/04-structure-plan.md` - Current plan
- Do NOT read 01-premise.md, 02-treatment-approach.md, or 03-treatment.md

**For story-plan iteration (05-story-plan.md; flash/short/novelette only):**
- `books/{project}/05-story-plan.md` - Current story plan
- Do NOT read earlier stages

**For chapter plan iteration (novella/novel/epic only):**
- `books/{project}/04-structure-plan.md` - Structure plan (frontmatter, characters, chapter breakdown)
- All previous chapter plans in `books/{project}/05-chapter-plans/` (for continuity)
- The specific chapter plan being revised
- Do NOT read 01-premise.md, 02-treatment-approach.md, 03-treatment.md, or chapter prose

**For prose iteration (novella/novel/epic):**
- `books/{project}/06-chapters/chapter-{NN}.md` - The chapter being revised
- All previous chapters in `books/{project}/06-chapters/` for continuity
- All chapter plans in `books/{project}/05-chapter-plans/`
- `misc/prose-style-{prose_style_key}.md` - Style card
- Do NOT read 01-premise.md, 02-treatment-approach.md, 03-treatment.md, or 04-structure-plan.md

**For prose iteration (flash/short/novelette):**
- `books/{project}/05-story-plan.md` - Story plan (authoritative contract for prose)
- `books/{project}/06-story.md` - The story being revised
- `misc/prose-style-{prose_style_key}.md` - Style card
- Do NOT read earlier stages

## Apply Changes

1. **Apply the approved changes** - Make the specific changes discussed
2. **Preserve everything else** - Don't change elements not mentioned in feedback
3. **Maintain consistency** - Ensure changes align with the current stage's context
4. **Follow frontmatter** - For prose, use the style from the plan's frontmatter

**Prose iteration principles:**
- Preserve the author's distinctive voice and style
- Keep strong emotional beats and character moments
- Maintain character-specific dialogue patterns
- Don't flatten literary prose into generic writing
- If cutting for pacing, preserve essential story information

## Write and Commit

Write the revised file(s) to `books/{project}/` and commit:

**PowerShell:**
```powershell
cd books; git add {project}/{file(s)}; git commit -m "Iterate: {target} - {brief feedback summary}"
```

## Return Summary

Return a summary of what changed:

```
Changes applied:
- {Change 1}
- {Change 2}

Preserved:
- {Key element kept intact}
- {Another preserved element}

Committed: "Iterate: {target} - {brief summary}"
```
```

### Step 8: Report Result (Main Context)

When the sub-agent returns:

1. **Display the summary** of changes applied
2. **Inform about cascade implications** (if any):
   ```
   Note: Since you changed {X}, these downstream stages may need updating:
   - 04-structure-plan.md (currently reads from treatment)
   - Run /generate-prose to regenerate with the new treatment
   ```
3. **Remind about version history:**
   ```
   To view history: git log --oneline (in books/ directory)
   To compare: git diff HEAD~1
   To revert: git checkout HEAD~1 -- {file}
   ```

## Why Hybrid?

Iterate involves two distinct concerns:
1. **Understanding intent** — requires back-and-forth with the user
2. **Applying edits** — requires reading file content

**Main context handles:**
- Parsing target and feedback
- Asking clarifying questions
- Enumerating planned changes
- Getting user approval
- Explaining cascade implications

**Sub-agent handles:**
- Reading full file content
- Applying the approved changes
- Writing and committing

This preserves the interactive "show what will change" UX while keeping file content out of main context.

---

## Iteration Guidelines

### Minimal Edits Principle

- Prefer targeted changes over wholesale rewrites
- If feedback affects one paragraph, edit that paragraph—not the entire section
- If feedback is broad ("make it darker"), still identify the smallest set of changes that achieves the goal
- Only rewrite entire documents when explicitly requested ("rewrite this from scratch")

### Target-Specific Guidelines

**Premise Iteration:**
- Preserve the core hook unless explicitly asked to change
- Maintain genre alignment
- Update taxonomy selections if tone/style changes significantly

**Treatment Iteration:**
- Keep the basic story arc unless restructuring is requested
- Ensure changes cascade properly (if Act I changes, Act II/III may need adjustment)
- Maintain character arc consistency

**Plan Iteration (04-structure-plan.md):**
- Preserve chapter/scene count unless explicitly asked to add/remove
- Adjust pacing notes if content changes significantly
- Update continuity tracking table

**Chapter Plan Iteration (Novella/Novel/Epic Only):**
- Iterate on chapter plans **before** generating prose for that chapter
- Adjust scene breakdowns, character states, or style notes as needed
- If the chapter's prose already exists, note that prose may need regeneration

**Prose Iteration:**
- Apply feedback while maintaining:
  - The story's established voice and tone
  - Character voice consistency
  - Plot thread continuity
  - Established world details
- Use the plan's Style Notes as guidance, not rigid rules
- The matching style card (`misc/prose-style-{prose_style_key}.md`) provides detailed reference

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

## Cascade Rules by Stage

**Premise changes:**
- If downstream stages don't exist yet: no action needed
- If treatment-approach already exists: its frontmatter may be stale

**Treatment changes:**
- Structure-plan reads only treatment, so it automatically sees changes when regenerated
- If structure-plan already exists: inform user they may want to regenerate

**Structure plan changes:**
- May require chapter plan revisions for affected chapters
- May require prose revision for affected chapters

**Chapter plan changes:**
- May require prose regeneration for that chapter (if prose exists)

## Natural Language Feedback Examples

- "Make the protagonist more conflicted about their decision"
- "Add more sensory details to the forest scenes"
- "The pacing feels slow in chapter 3, tighten it up"
- "I want the antagonist to be more sympathetic"
- "Add more romantic tension between the leads"
- "The dialogue feels stilted, make it more natural"
- "This chapter needs a stronger hook at the end"

## Version History

Each iteration creates a git commit. Users can:
- View history: `git log --oneline`
- Compare versions: `git diff HEAD~1`
- Revert changes: `git checkout HEAD~1 -- {file}`

Remind users of these options when they express uncertainty about changes.
