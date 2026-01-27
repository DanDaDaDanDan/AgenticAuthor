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

### Step 1: Determine Target

If `target` not provided, ask the user:
- What would you like to review?
  1. Premise
  2. Treatment
  3. Plan (structure plan - all project types)
  4. Chapter/story plan (novels: specific chapter plan, short stories: story plan)
  5. Prose (specific chapter or all)
  6. All - complete project review

### Step 2: Read Context

Read `books/{project}/project.yaml` to get the genre.

**Note:** Unlike generation (which uses the self-contained model), review intentionally reads multiple stages to check alignment and consistency between them.

**For premise review:**
- `books/{project}/premise.md`
- `AgenticAuthor/taxonomies/base-taxonomy.json`
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json`

**For treatment review:**
- `books/{project}/premise.md`
- `books/{project}/treatment.md`

**For plan review (structure-plan.md):**
- `books/{project}/premise.md`
- `books/{project}/treatment.md`
- `books/{project}/structure-plan.md`

**For chapter plan review:**
- `books/{project}/premise.md`
- `books/{project}/treatment.md`
- `books/{project}/structure-plan.md`
- Target chapter plan from `books/{project}/chapter-plans/` or `books/{project}/short-story-plan.md`
- `books/{project}/summaries.md` (if exists)

**For prose review:**
- All of the above (premise includes prose style selections)
- For novels: `books/{project}/chapter-plans/` (relevant chapter plans)
- For novels: target chapter(s) from `books/{project}/chapters/`
- For short stories: `books/{project}/short-story-plan.md` and `books/{project}/short-story.md`
- `AgenticAuthor/misc/prose-style-card.md` - Reference if premise uses Commercial style

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
- **Gaps:** {Any treatment elements missing from chapters/scenes?}

## Chapter/Scene Balance
- **Word count distribution:** {Are chapters/scenes balanced?}
- **POV consistency:** {POV structure working?}
- **Pacing flow:** {Action vs reflection balance}

## Continuity Check
| Element | Introduced | Resolved | Status |
|---------|-----------|----------|--------|
| {Plot thread} | Ch/Scene {X} | Ch/Scene {Y} | ✓/⚠️ |

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for prose, or needs adjustment}
```

### Chapter/Story Plan Review

For novels, review specific chapter plans. For short stories, review the story plan.

```markdown
# Plan Review: {project} - {Chapter N / Story Plan}

## Structure Plan Alignment
- **Matches structure-plan:** {Does plan align with structure-plan.md?}
- **Goals addressed:** {Will this plan achieve the stated goals?}

## Continuity Check
- **Previous content threads:** {Properly picked up? (N/A for first chapter or short stories)}
- **Character states:** {Consistent with where they should be?}
- **World details:** {No contradictions?}

## Scene Breakdown Quality
- **Scene purposes clear:** {Each scene has a reason?}
- **Conflict/tension present:** {Scenes have drivers?}
- **Transitions logical:** {Scenes connect well?}

## Style Notes Assessment
- **Appropriate for content:** {Pacing/tone fit?}
- **Consistent with story style:** {Matches the style in structure-plan's Story Configuration?}

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
