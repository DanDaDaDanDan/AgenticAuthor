# Skill: /iterate

Refine content with feedback, maintaining consistency and quality.

## Usage

```
/iterate [target] [feedback]
```

## Arguments

- `target` (optional): What to iterate on - `premise`, `treatment`, `plan`, or `prose`
- `feedback` (optional): Natural language description of desired changes

## Instructions

### Step 1: Determine Target

If `target` not provided, ask the user:
- What would you like to iterate on?
  1. Premise - refine the core concept
  2. Treatment - adjust the story outline
  3. Plan - modify chapter structure (novels only)
  4. Prose - revise generated chapters

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

### Step 4: Read Full Context

**Always read the complete context for the target.**

Read `books/{project}/project.yaml` to get the genre for taxonomy lookup.

**For premise iteration:**
- `books/{project}/premise.md` - Current premise
- `AgenticAuthor/taxonomies/base-taxonomy.json` - Universal properties
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json` - Genre-specific options
- `AgenticAuthor/taxonomies/style-taxonomy.json` - Style options (if changing style)

**For treatment iteration:**
- `books/{project}/premise.md` (full)
- `books/{project}/treatment.md` - Current treatment

**For plan iteration:**
- `books/{project}/premise.md` (full)
- `books/{project}/treatment.md` (full)
- `books/{project}/structure-plan.md` - Current plan

**For prose iteration:**
- `books/{project}/premise.md` (full, includes prose style selections)
- `books/{project}/treatment.md` (full)
- `books/{project}/structure-plan.md` (full, if novel)
- All chapters from `books/{project}/chapters/` (full)
- The specific chapter(s) being revised
- `AgenticAuthor/misc/prose-style-card.md` - Optional reference if premise uses Commercial style

### Step 5: Apply Changes

Generate the revised content:

1. **Apply the confirmed changes** - Make the specific changes discussed
2. **Preserve everything else** - Don't change elements not mentioned in feedback
3. **Maintain consistency** - Ensure changes align with other project parts
4. **Follow style card** - For prose, maintain style guidelines

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

## Iteration Guidelines

### Premise Iteration

- Preserve the core hook unless explicitly asked to change
- Maintain genre alignment
- Update taxonomy selections if tone/style changes significantly

### Treatment Iteration

- Keep the basic story arc unless restructuring is requested
- Ensure changes cascade properly (if Act I changes, Act II/III may need adjustment)
- Maintain character arc consistency

### Plan Iteration

- Preserve chapter count unless explicitly asked to add/remove
- Adjust pacing notes if chapter content changes significantly
- Update continuity tracking table

### Prose Iteration

**Most common iteration target.** Apply feedback while maintaining:
- The story's established voice and tone
- Character voice consistency
- Plot thread continuity
- Established world details

Use the style card as guidance, not rigid rules. If the existing prose has a distinctive style that works, preserve it.

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

## Cascading Changes

When iteration on one stage affects others:

**Premise changes → May require:**
- Treatment revision to align with new premise
- Plan adjustment for structural changes
- Prose revision for new themes/tone

**Treatment changes → May require:**
- Plan revision for chapter structure
- Prose revision for plot changes

**Plan changes → May require:**
- Prose revision for affected chapters

After completing the iteration, inform the user if downstream stages may need updating.

## Version History

Each iteration creates a git commit. Users can:
- View history: `git log --oneline`
- Compare versions: `git diff HEAD~1`
- Revert changes: `git checkout HEAD~1 -- {file}`

Remind users of these options when they express uncertainty about changes.
