# Skill: /review

Analyze content against quality standards without making changes.

## Usage

```
/review [target]
```

## Arguments

- `target` (optional): What to review - `premise`, `treatment`, `plan`, `prose`, or `all`

## Instructions

### Step 1: Determine Target

If `target` not provided, ask the user:
- What would you like to review?
  1. Premise
  2. Treatment
  3. Plan (novels only)
  4. Prose (specific chapter or all)
  5. All - complete project review

### Step 2: Read Context

Read `books/{project}/project.yaml` to get the genre.

**For premise review:**
- `books/{project}/premise.md`
- `AgenticAuthor/taxonomies/base-taxonomy.json`
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json`

**For treatment review:**
- `books/{project}/premise.md`
- `books/{project}/treatment.md`

**For plan review:**
- `books/{project}/premise.md`
- `books/{project}/treatment.md`
- `books/{project}/structure-plan.md`

**For prose review:**
- All of the above
- `AgenticAuthor/misc/prose-style-card.md`
- `AgenticAuthor/misc/copy-edit.md` (detailed quality guidelines)
- Target chapter(s) from `books/{project}/chapters/`

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

### Plan Review (Novels)

```markdown
# Structure Plan Review: {project}

## Treatment Alignment
- **Coverage:** {Does plan cover all treatment beats?}
- **Gaps:** {Any treatment elements missing from chapters?}

## Chapter Balance
- **Word count distribution:** {Are chapters balanced?}
- **POV consistency:** {POV structure working?}
- **Pacing flow:** {Action vs reflection balance}

## Continuity Check
| Element | Introduced | Resolved | Status |
|---------|-----------|----------|--------|
| {Plot thread} | Ch {X} | Ch {Y} | ✓/⚠️ |

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for prose, or needs adjustment}
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
- **Plan alignment:** {Does prose follow structure plan?}
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
