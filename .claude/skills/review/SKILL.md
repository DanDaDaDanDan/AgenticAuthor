---
name: review
description: Analyze content against quality standards without making changes.
argument-hint: "[target]"
---

Analyze content against quality standards without making changes.

## Usage

```
/review [target]
```

## Arguments

- `target` (optional): What to review - `premise`, `treatment`, `plan`, `chapter-plan`, `prose`, or `all`

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
- What would you like to review?
  1. Premise
  2. Treatment
  3. Plan (structure plan - all project types)
  4. Chapter/story plan (novella/novel/epic: specific chapter plan, flash/short/novelette: story plan)
  5. Prose (specific chapter or all)
  6. All - complete project review

### Step 2: Read Context

Read `books/{project}/project.yaml` to get the genre.

**Note:** Unlike generation (which uses the self-contained model), review intentionally reads multiple stages to check alignment and consistency between them.

**For premise review:**
- `books/{project}/01-premise.md`
- `taxonomies/base-taxonomy.json`
- `taxonomies/{genre}-taxonomy.json`

**For treatment review:**
- `books/{project}/01-premise.md`
- `books/{project}/03-treatment.md`

**For plan review (04-structure-plan.md):**
- `books/{project}/01-premise.md`
- `books/{project}/03-treatment.md`
- `books/{project}/04-structure-plan.md`

**For chapter plan review:**
- `books/{project}/01-premise.md`
- `books/{project}/03-treatment.md`
- `books/{project}/04-structure-plan.md`
- Target chapter plan from `books/{project}/05-chapter-plans/` or `books/{project}/05-story-plan.md`
- `books/{project}/06-06-chapters/summaries.md` (if exists)

**For prose review:**
- All of the above (premise includes prose style selections)
- For novella/novel/epic: `books/{project}/05-chapter-plans/` (relevant chapter plans)
- For novella/novel/epic: target chapter(s) from `books/{project}/06-chapters/`
- For flash/short/novelette: `books/{project}/05-story-plan.md` and `books/{project}/06-story.md`
- `misc/prose-style-{prose_style_key}.md` - Style card matching the project's prose style

### Step 3: Analyze Content

Generate a review report. **Do NOT make any changes to files.**

---

## Review Reports by Target

### Premise Review

```markdown
# Premise Review: {project}

## Taxonomy Alignment
- **Genre fit:** {How well does the premise fit the selected genre/subgenre?}
- **Missing elements:** {Any expected genre elements not present?}

## Core Elements Check
- [ ] Protagonist clearly defined
- [ ] Antagonist/opposition established
- [ ] Central conflict articulated
- [ ] Stakes specified
- [ ] Hook is compelling and unique

## Themes Assessment
- **Clarity:** {Are themes clear but not heavy-handed?}
- **Genre appropriateness:** {Do themes fit the genre?}

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Brief assessment - ready for treatment, or needs work}
```

### Treatment Review

```markdown
# Treatment Review: {project}

## Premise Alignment
- **Consistency:** {Does treatment follow from premise?}
- **Gaps:** {Any premise elements not addressed?}

## Structure Analysis
- **Act I:** {Setup effectiveness, inciting incident clarity}
- **Act II:** {Rising action, midpoint strength, complications}
- **Act III:** {Climax setup, resolution satisfaction}

## Character Arcs
- **Protagonist:** {Arc clarity and transformation}
- **Supporting characters:** {Development and purpose}

## Pacing Notes
- {Observations about story rhythm}

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for plan/prose, or needs iteration}
```

### Plan Review (Structure Plan)

```markdown
# Structure Plan Review: {project}

## Treatment Alignment
- **Coverage:** {Does plan cover all treatment beats?}
- **Gaps:** {Any treatment elements missing from 06-chapters/scenes?}

## Chapter/Scene Balance
- **Word count distribution:** {Are 06-chapters/scenes balanced?}
- **POV consistency:** {POV structure working?}
- **Pacing flow:** {Action vs reflection balance}

## Continuity Check
| Element | Introduced | Resolved | Status |
|---------|-----------|----------|--------|
| {Plot thread} | Ch/Scene {X} | Ch/Scene {Y} | OK/WARN |

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for prose, or needs adjustment}
```

### Chapter/Story Plan Review

For novella/novel/epic, review specific chapter plans. For flash/short/novelette, review the story plan.

```markdown
# Plan Review: {project} - {Chapter N / Story Plan}

## Structure Plan Alignment
- **Matches structure-plan:** {Does plan align with 04-structure-plan.md?}
- **Goals addressed:** {Will this plan achieve the stated goals?}

## Continuity Check
- **Previous content threads:** {Properly picked up? (N/A for first chapter, or N/A for flash/short/novelette)}
- **Character states:** {Consistent with where they should be?}
- **World details:** {No contradictions?}

## Scene Breakdown Quality
- **Scene purposes clear:** {Each scene has a reason?}
- **Conflict/tension present:** {Scenes have drivers?}
- **Transitions logical:** {Scenes connect well?}

## Style Notes Assessment
- **Appropriate for content:** {Pacing/tone fit?}
- **Consistent with story style:** {Matches the style in structure-plan's frontmatter?}

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for prose generation, or iterate first}
```

### Prose Review

```markdown
# Prose Review: {project} - {Chapter/All}

## Style Observations

{Note: These are observations, not pass/fail criteria. Deviations may be intentional and effective.}

### Readability
- **Sentence length feel:** {Flows well? Any passages that drag or rush?}
- **Dense passages:** {Any sections that might lose readers? Are they justified?}

### Dialogue
- **Balance:** {Feels right for the scene types? Too sparse/heavy anywhere?}
- **Voice distinction:** {Do characters sound different?}
- **Tag usage:** {Clean and unobtrusive?}

### Scene Structure
- **Purpose:** {Does each scene earn its place?}
- **Momentum:** {Do scenes end with energy? Note: quiet endings are valid for reflective scenes}
- **Pacing variety:** {Good mix of tension and breathing room?}

### POV Discipline
- **Consistency:** {Single POV per scene?}
- **Any drift:** {Unintentional perspective shifts?}

## Strengths to Preserve

- {What's working well - voice, atmosphere, moments}
- {Strong passages or techniques}
- {Effective character work}

## Areas to Consider

- {Potential issue and location - frame as observation, not error}
- {Another area that might benefit from revision}

## Plot/Continuity
- **Structure plan alignment:** {Does prose follow structure plan?}
- **Chapter plan alignment:** {Does prose follow the chapter plan's scene breakdown?}
- **Consistency notes:** {Any contradictions or continuity gaps?}

## Suggestions
1. {Specific improvement idea with location}
2. {Another suggestion}

**Overall:** {Assessment noting both strengths and priority areas. Acknowledge intentional style choices.}
```

### Full Project Review

When reviewing `all`, generate a combined report:

```markdown
# Project Review: {project}

## Summary
- **Stage:** {Current project stage}
- **Word count:** {Total if prose exists}
- **Overall assessment:** {Brief summary}

## Stage Reviews

{Include abbreviated versions of each applicable review}

## Priority Improvements
1. {Most important fix}
2. {Second priority}
3. {Third priority}

## Ready for Next Step?
{Yes/No with explanation}
```

### Frontmatter Integrity Check

**Include in every review.** Check all stage files for frontmatter issues:

```markdown
## Frontmatter Integrity

### {filename}
- [ ] Valid YAML structure (opens and closes with `---`)
- [ ] `project:` matches project name
- [ ] `stage:` matches file type
- [ ] All `*_key` fields present and valid
- [ ] Display name fields match keys
- [ ] No unknown/misspelled keys

**Issues found:**
- {List any problems: missing keys, invalid values, typos}

**Cross-stage consistency:**
- [ ] Frontmatter values match across stages (premise → treatment → structure-plan)
- [ ] No conflicting taxonomy selections
```

If frontmatter is invalid or inconsistent, flag it as a priority fix — downstream stages depend on accurate frontmatter.

### Drift Detector

**Include for prose reviews.** Check where prose deviates from its plan:

```markdown
## Plan vs Prose Drift

### Chapter {N}

**Planned scenes:**
1. {Scene from plan}
2. {Scene from plan}

**Actual scenes in prose:**
1. {What actually appears}
2. {What actually appears}

**Drift analysis:**
- [ ] Scene count matches plan
- [ ] Scene purposes achieved
- [ ] Character states match plan expectations
- [ ] Key beats present

**Deviations found:**
| Planned | Actual | Assessment |
|---------|--------|------------|
| {planned element} | {what happened} | Intentional improvement / Needs plan update / Needs prose fix |

**Recommendation:**
- Update plan to match prose (if prose is better)
- Regenerate prose (if plan should be authoritative)
- No action (deviation is minor/intentional)
```

Drift is not always bad — sometimes prose improves on the plan. The review identifies drift and recommends whether to update the plan or the prose.

---

## Output Guidelines

- **Be specific:** Reference exact locations (chapter, paragraph, line when possible)
- **Be constructive:** Frame observations as opportunities, not failures
- **Be balanced:** Note strengths first, then areas for consideration
- **Be actionable:** Suggestions should be clear enough to implement via `/iterate`
- **Respect intentional choices:** If something deviates from guidelines but works, acknowledge it as a valid stylistic choice rather than an error
- **Avoid mechanical judgments:** Don't reduce prose quality to ratios and word counts—assess how it *reads*

## After Review

Inform the user:
```
Review complete. To address any suggestions:
  /iterate {target} "{specific feedback}"

To see version history:
  git log --oneline (in books/ directory)
```

**Do NOT automatically apply changes.** The review is advisory only.
