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
- (User can provide natural language feedback like "make it darker", "add more tension", "develop the romance subplot more")

### Step 3: Read Full Context

**Always read the complete context for the target.**

Read `books/{project}/project.yaml` to get the genre for taxonomy lookup.

**For premise iteration:**
- `books/{project}/premise.md` - Current premise
- `AgenticAuthor/taxonomies/base-taxonomy.json` - Universal properties
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json` - Genre-specific options

**For treatment iteration:**
- `books/{project}/premise.md` (full)
- `books/{project}/treatment.md` - Current treatment

**For plan iteration:**
- `books/{project}/premise.md` (full)
- `books/{project}/treatment.md` (full)
- `books/{project}/structure-plan.md` - Current plan

**For prose iteration:**
- `books/{project}/premise.md` (full)
- `books/{project}/treatment.md` (full)
- `books/{project}/structure-plan.md` (full, if novel)
- `AgenticAuthor/misc/prose-style-card.md` (full) - at repo root
- All chapters from `books/{project}/chapters/` (full)
- The specific chapter(s) being revised

**Path Notes:**
- Book files are in `books/{project}/`
- Prose style card is at `AgenticAuthor/misc/` (repo root)
- Taxonomies are at `AgenticAuthor/taxonomies/` (repo root)

### Step 4: Apply Changes

Generate the revised content:

1. **Understand the feedback:** Interpret what the user wants changed
2. **Identify impacts:** Consider what else might need adjustment for consistency
3. **Generate revision:** Create the updated content maintaining:
   - All existing elements not mentioned in feedback
   - Consistency with other parts of the project
   - Quality standards from the style card (for prose)

### Step 5: Show Summary of Changes

Before writing, briefly summarize what changed:

```
Changes applied:
- {Change 1}
- {Change 2}
- {Change 3}

Elements preserved:
- {Maintained element 1}
- {Maintained element 2}
```

### Step 6: Write and Commit

Write the revised file(s) to `books/{project}/` and commit:

```bash
cd books && git add {project}/{file(s)} && git commit -m "Iterate: {target} - {brief feedback summary}"
```

Examples:
```bash
cd books && git add my-book/premise.md && git commit -m "Iterate: premise - add more conflict"
cd books && git add my-book/chapters/chapter-03.md && git commit -m "Iterate: chapter 3 - increase tension"
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

- **Most common iteration target**
- Apply feedback while maintaining:
  - Style card guidelines
  - Character voice consistency
  - Plot thread continuity
  - Established world details
- For chapter-specific feedback, only revise that chapter
- For global feedback ("make everything darker"), revise all chapters

## Natural Language Feedback Examples

The feedback can be conversational:

- "Make the protagonist more conflicted about their decision"
- "Add more sensory details to the forest scenes"
- "The pacing feels slow in chapter 3, tighten it up"
- "I want the antagonist to be more sympathetic"
- "Add more romantic tension between the leads"
- "Make the magic system feel more mysterious"
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

After completing the iteration, inform the user if downstream stages may need updating:

```
Iteration complete. Note: Since the treatment changed significantly,
you may want to:
- Review the structure plan for alignment
- Consider regenerating affected chapters
```

## Version History

Each iteration creates a git commit, so the user can:
- View history with `git log --oneline`
- Compare versions with `git diff HEAD~1`
- Revert changes with `git checkout HEAD~1 -- {file}`

Remind users of these options when they express uncertainty about changes.
