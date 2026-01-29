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

- `target` (optional): What to review - `premise`, `treatment`, `plan`, `story-plan`, `chapter-plan`, `prose`, or `all`

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
  3. Plan (04-structure-plan.md - macro plan; all project types)
  4. Story plan (05-story-plan.md - micro beat sheet; flash/short/novelette only)
  5. Chapter plan (novella/novel/epic only: specific chapter plan)
  6. Prose (specific chapter or all)
  7. All - complete project review

### Step 2: Read Context

Read `books/{project}/project.yaml` to get the genre.

**Note:** Unlike generation (which uses the self-contained model), review intentionally reads multiple stages to check alignment and consistency between them.

**For premise review:**
- `books/{project}/01-premise.md`
- `taxonomies/base-taxonomy.json`
- `taxonomies/{genre}-taxonomy.json`

**For treatment review:**
- `books/{project}/01-premise.md`
- `books/{project}/02-treatment-approach.md`
- `books/{project}/03-treatment.md`

**For plan review (04-structure-plan.md):**
- `books/{project}/01-premise.md`
- `books/{project}/02-treatment-approach.md`
- `books/{project}/03-treatment.md`
- `books/{project}/04-structure-plan.md`

**For story plan review (05-story-plan.md; flash/short/novelette only):**
- `books/{project}/01-premise.md`
- `books/{project}/02-treatment-approach.md`
- `books/{project}/03-treatment.md`
- `books/{project}/04-structure-plan.md`
- `books/{project}/05-story-plan.md`

**For chapter plan review (novella/novel/epic only):**
- `books/{project}/01-premise.md`
- `books/{project}/02-treatment-approach.md`
- `books/{project}/03-treatment.md`
- `books/{project}/04-structure-plan.md`
- Target chapter plan from `books/{project}/05-chapter-plans/`

**For prose review:**
- All of the above (premise includes prose style selections)
- For novella/novel/epic: all chapter plans in `books/{project}/05-chapter-plans/`
- For novella/novel/epic: all chapter prose in `books/{project}/06-chapters/`
- For flash/short/novelette: `books/{project}/04-structure-plan.md`, `books/{project}/05-story-plan.md` (if present), and `books/{project}/06-story.md`
- `misc/prose-style-{prose_style_key}.md` - Style card matching the project's prose style

### Step 3: Analyze Content

Generate a review report. **Do NOT make any changes to files.**

### Prose Lint (Required for Prose Review)

For `prose` reviews, include a short **Prose Lint** section with lightweight, measurable signals:

- Estimated **Flesch Reading Ease** (compare to the style card target range)
- **Dialogue ratio proxy** (quote-line ratio)
- **Scene break count** vs. planned scene count
- **Repeated phrase counts** for phrases listed in `prose_guidance.avoid_overuse` (from the plan frontmatter)

Recommended approach (Python, no external dependencies):

```bash
python - <<'PY'
import re
from pathlib import Path

def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")

def frontmatter_block(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return ""

def extract_avoid_overuse(frontmatter):
    phrases = []
    lines = frontmatter.splitlines()
    in_pg = False
    in_ao = False
    for line in lines:
        if re.match(r"^prose_guidance:\\s*$", line):
            in_pg, in_ao = True, False
            continue
        if in_pg and re.match(r"^\\S", line):  # back to top-level
            in_pg, in_ao = False, False
        if in_pg and re.match(r"^\\s{2}avoid_overuse:\\s*$", line):
            in_ao = True
            continue
        if in_ao:
            m = re.match(r"^\\s{4}-\\s*(.+?)\\s*$", line)
            if m:
                raw = m.group(1).strip().strip('\"').strip(\"'\")
                # Skip template placeholders
                if raw and not raw.startswith(\"{\") and not raw.endswith(\"}\"):
                    phrases.append(raw)
                continue
            # end avoid_overuse block if indentation changes
            if re.match(r\"^\\s{0,2}\\S\", line):
                in_ao = False
    # de-dupe while preserving order
    seen = set()
    out = []
    for p in phrases:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out

def syllables(word):
    w = re.sub(r\"[^a-z]\", \"\", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    if w.endswith(\"e\"):
        w = w[:-1]
    groups = re.findall(r\"[aeiouy]+\", w)
    return max(1, len(groups))

def flesch_reading_ease(text):
    plain = re.sub(r\"^#.*$\", \"\", text, flags=re.M)
    words = re.findall(r\"[A-Za-z0-9’']+\", plain)
    sents = [s for s in re.split(r\"(?<=[.!?])\\s+\", plain.strip()) if re.search(r\"[A-Za-z]\", s)]
    if not words or not sents:
        return None
    syll = sum(syllables(w) for w in words)
    wps = len(words) / len(sents)
    spw = syll / len(words)
    return 206.835 - 1.015 * wps - 84.6 * spw

def extract_planned_scene_count(text):
    m = re.search(r\"\\*\\*Number of scenes:\\*\\*\\s*(\\d+)\", text)
    return int(m.group(1)) if m else None

project = \"{project}\"
story = read(f\"books/{project}/06-story.md\")
plan_path = Path(f\"books/{project}/05-story-plan.md\")
plan_text = read(plan_path) if plan_path.exists() else read(f\"books/{project}/04-structure-plan.md\")

fm = frontmatter_block(plan_text)
avoid = extract_avoid_overuse(fm)

flesch = flesch_reading_ease(story)
lines = story.splitlines()
quote_lines = sum(1 for l in lines if '\"' in l)
scene_breaks = sum(1 for l in lines if l.strip() == \"* * *\")
planned_scenes = extract_planned_scene_count(plan_text)

print(\"flesch_est\", None if flesch is None else round(flesch, 1))
print(\"quote_line_ratio\", f\"{quote_lines}/{len(lines)}\")
print(\"scene_breaks\", scene_breaks)
print(\"planned_scenes\", planned_scenes)
for p in avoid:
    print(\"phrase\", p, story.lower().count(p.lower()))
PY
```

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
- **Gaps:** {Any treatment elements missing from the planned chapters/scenes?}

## Chapter/Scene Balance
- **Word count distribution:** {Are chapters/scenes balanced?}
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

### Story Plan Review (Flash/Short/Novelette Only)

```markdown
# Story Plan Review: {project}

## Structure Plan Alignment
- **Matches 04-structure-plan.md:** {Does story-plan preserve scene order, beats, and style notes?}
- **Scene engines present:** {Does every scene include desire/obstacle/escalation/turn/cost?}
- **Micro-turns present:** {2-4 state changes per scene?}
- **Must-dramatize moments:** {One per scene, concrete and non-summary?}

## Subtext & Friction
- **Ally disagreement (required):** {Is there at least one meaningful disagreement that changes a choice/approach?}
- **Not “thesis-y”:** {Does the plan force dramatized moments instead of manifesto paragraphs?}

## Prose Guidance Quality
- **avoid_overuse:** {Actionable phrase/tic list (prefer plain phrases)?}
- **pacing_notes:** {Specific and stage-appropriate?}
- **preserve:** {Clear “do not lose” items for the prose agent?}

## Suggestions
1. {Specific improvement suggestion}
2. {Another suggestion}

**Overall:** {Ready for prose generation, or iterate story-plan first}
```

### Chapter Plan Review (Novella/Novel/Epic Only)

For novella/novel/epic, review specific chapter plans. For flash/short/novelette, use "Story Plan Review" (`05-story-plan.md`) as the micro generation plan (structure-plan is macro).

```markdown
# Chapter Plan Review: {project} - Chapter {N}

## Structure Plan Alignment
- **Matches structure-plan:** {Does plan align with 04-structure-plan.md?}
- **Goals addressed:** {Will this plan achieve the stated goals?}

## Continuity Check
- **Previous content threads:** {Properly picked up from earlier chapters? (N/A for first chapter)}
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

## Prose Lint (metrics)
- **Estimated Flesch Reading Ease:** {value} (compare to style card target)
- **Dialogue ratio proxy:** {quote lines}/{total lines} ({interpretation})
- **Scene breaks:** {actual scene breaks} (planned scenes: {planned count}; expected breaks ≈ planned-1)
- **Repeated phrases (from `prose_guidance.avoid_overuse`):**
  - {phrase}: {count}

## Strengths to Preserve

- {What's working well - voice, atmosphere, moments}
- {Strong passages or techniques}
- {Effective character work}

## Areas to Consider

- {Potential issue and location - frame as observation, not error}
- {Another area that might benefit from revision}

## Plot/Continuity
- **Structure plan alignment:** {Does prose follow structure plan?}
- **Story plan alignment (flash/short/novelette):** {Does prose follow `05-story-plan.md` micro beats and constraints?}
- **Chapter plan alignment (novella/novel/epic):** {Does prose follow the chapter plan's scene breakdown?}
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
- [ ] Frontmatter values match across stages (premise → treatment-approach → treatment → structure-plan)
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
