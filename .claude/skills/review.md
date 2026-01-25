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

## Style Card Compliance

### Readability
- **Flesch Reading Ease:** {Estimated range}
- **Average sentence length:** {Estimate - target 12-16 words}
- **Long sentences (>35 words):** {Count and locations}

### Dialogue
- **Ratio:** {Estimated % - target 35-50% in character scenes}
- **Voice distinction:** {Do characters sound different?}
- **Tag variety:** {Appropriate mix?}

### Structure (POISE)
- [ ] Purpose - Each scene has clear purpose
- [ ] Obstacle - Conflicts present and engaging
- [ ] Interaction - Characters actively engaged
- [ ] Stakes - Tension maintained
- [ ] End-turn - Scenes end with momentum

### POV Discipline
- **Consistency:** {Single POV per scene?}
- **Head-hopping:** {Any violations?}

## Copy-Edit Observations

### Preserve (Strengths)
- {Strong element to keep}
- {Another strength}

### Consider Revising
- {Issue and location}
- {Another issue}

## Plot/Continuity
- **Plan alignment:** {Does prose follow structure plan?}
- **Consistency issues:** {Any contradictions?}

## Suggestions
1. {Specific improvement with location}
2. {Another suggestion}

**Overall:** {Assessment and priority areas for iteration}
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
- **Be constructive:** Frame issues as opportunities, not failures
- **Be balanced:** Note strengths alongside areas for improvement
- **Be actionable:** Suggestions should be clear enough to implement via `/iterate`

## After Review

Inform the user:
```
Review complete. To address any suggestions:
  /iterate {target} "{specific feedback}"

To see version history:
  git log --oneline (in books/ directory)
```

**Do NOT automatically apply changes.** The review is advisory only.
