---
name: generate-prose
description: Generate structure plans and prose (04-structure-plan.md → plans → prose).
argument-hint: ""
---

Generate story prose, including any needed planning documents.

Equivalent to:
- `/generate prose`

## Usage

```
/generate-prose
```

---

## Instructions

### Step 0: Detect Current Project

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value from the YAML block
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, fall back to directory detection:
   - Look for `project.yaml` in the current directory or parent directories under `books/`
   - If not found, ask the user which project to work on (or suggest `/select-book`)

Read `books/{project}/project.yaml` to get project metadata (genre, length, title, author).

---

## Stage: prose

Generate the actual story prose.

### Orchestration Flow

1. **Check what exists** — 04-structure-plan? 05-story-plan (flash/short/novelette)? 05-chapter-plans (novella/novel/epic)? prose?
2. **Ask clarifying questions** UPFRONT for any missing planning documents
3. **Spawn sub-agents** sequentially for each missing piece:
   - Structure-plan sub-agent (if missing) — macro plan for all formats
   - Story-plan sub-agent (if missing, flash/short/novelette only) — micro beat sheet used as the prose contract
   - Chapter-plan sub-agents (if missing, for novella/novel/epic only)
   - Prose sub-agent(s)
4. Report completion

### Context Rules

**Context loading:** Each sub-agent reads only its immediate predecessor. Stages are fully self-contained.

| Generating | Sub-agent Reads | Sub-agent Does NOT Read |
|------------|-----------------|-------------------------|
| structure-plan | 03-treatment.md only | 01-premise.md, 02-treatment-approach.md |
| story-plan (flash/short/novelette) | 04-structure-plan.md only | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, prose |
| chapter-plan N (novella/novel/epic) | 04-structure-plan.md + chapter-plans 1..N-1 | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, chapter prose |
| prose (flash/short/novelette) | 05-story-plan.md + prose-style-{prose_style_key}.md | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md |
| prose (novella/novel/epic) | all previous chapter prose + all chapter plans (current + future) + prose-style-{prose_style_key}.md | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md |

### Clarifying Questions

**For Novella/Novel/Epic (chaptered formats) — ask BEFORE spawning:**

1. **Target length:** (adjust options based on length_key from treatment)

   For novella:
   > How long should this novella be?
   > 1. Short novella (8-10 chapters, ~20,000 words)
   > 2. Standard novella (10-12 chapters, ~30,000 words)
   > 3. Long novella (12-15 chapters, ~40,000 words)
   > 4. Let me decide based on the treatment

   For novel:
   > How long should this novel be?
   > 1. Compact (15-20 chapters, ~50,000 words)
   > 2. Standard (20-30 chapters, ~80,000 words)
   > 3. Long (30-40 chapters, ~100,000 words)
   > 4. Let me decide based on the treatment

   For epic:
   > How long should this epic be?
   > 1. Standard epic (35-45 chapters, ~120,000 words)
   > 2. Extended epic (45-60 chapters, ~150,000 words)
   > 3. Massive (60+ chapters, ~200,000+ words)
   > 4. Let me decide based on the treatment

2. **Chapter length preference:**
   > What chapter length feels right?
   > 1. Short and punchy (2,000-3,000 words) - quick reads, frequent hooks
   > 2. Standard (3,000-4,500 words) - balanced pacing
   > 3. Long and immersive (4,500-6,000+ words) - deep scenes
   > 4. Variable - mix based on content

**For Flash Fiction/Short Story/Novelette (single-file formats) — ask BEFORE spawning:**

1. **Target length:**
   > How long should this story be?
   > 1. Flash fiction (under 1,500 words)
   > 2. Short-short (1,500-3,000 words)
   > 3. Standard short (3,000-7,500 words)
   > 4. Long short story / Novelette (7,500-17,500 words)
   > 5. Let me decide based on the treatment

2. **Scene structure:**
   > How should the story flow?
   > 1. Single continuous scene
   > 2. 2-3 scenes with clear breaks
   > 3. Multiple short scenes
   > 4. Let me decide based on the treatment

---

### Sub-Agent: Structure Plan

**Spawn when:** `04-structure-plan.md` doesn't exist

**Sub-agent prompt template:**

```
Write `books/{project}/04-structure-plan.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}
**User preferences:** Target length={...}; Chapter/scene structure={...}

**Read only:** `books/{project}/03-treatment.md` (treatment is authoritative)

Do NOT read 01-premise.md, 02-treatment-approach.md, or any other files.

**Output:** `books/{project}/04-structure-plan.md` (use the appropriate Structure Plan template from this skill)

**Requirements:**
- Copy frontmatter from `03-treatment.md` and include the template's **Downstream Contract** section.
- Preserve `prose_guidance` from treatment frontmatter (do not drop or rename it).
- Preserve `plausibility_key` from treatment frontmatter (do not drop or rename it). If missing (legacy), set it to `heightened` / `Heightened`. Calibrate domain detail to it.
- Allocate per scene/chapter word targets deliberately (not uniform) and ensure they approximately sum to the overall target.
- For flash/short/novelette: each planned scene must include explicit **Desire / Obstacle / Escalation / Turn / Cost** fields (see template).
- **CRITICAL: Include ALL template sections** — downstream stages (story-plan or chapter-plans) will copy from structure-plan to become self-contained:
  - Character States (detailed: arcs, voice notes, tells, functions)
  - Story Arc Mapping (opening hook through resolution)
  - Style Notes (pacing, tone, dialogue balance, sensory focus)
  - Length Strategy (word allocation guidance)
  - Potential Pitfalls (what to avoid)

**After (Bash):** `cd books && git add {project}/04-structure-plan.md && git commit -m "Add: Generate structure plan for {project}"`
**After (PowerShell):** `cd books; git add {project}/04-structure-plan.md; git commit -m "Add: Generate structure plan for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Story Plan (Flash/Short/Novelette)

**Spawn when:** `05-story-plan.md` doesn't exist (and structure-plan exists; flash/short/novelette only)

**Sub-agent prompt template:**

```
Write `books/{project}/05-story-plan.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette}

**Read only:**
1. `books/{project}/04-structure-plan.md` — Macro structure plan (authoritative)

Do NOT read 01-premise.md, 02-treatment-approach.md, 03-treatment.md, or any other files.

**Output:** `books/{project}/05-story-plan.md` (use the Story Plan template from this skill)

**Requirements:**
- Copy ALL frontmatter values from `04-structure-plan.md` (including `prose_guidance` and `plausibility_key`). If `plausibility_key` is missing (legacy), set it to `heightened` / `Heightened`.
- **CRITICAL: Copy these sections from structure-plan to make story-plan self-contained:**
  - Character States (full character info with arcs, voice notes, tells, functions)
  - Story Arc Mapping (opening hook, complication, climax, resolution)
  - Style Notes (pacing, tone, dialogue balance, sensory focus)
  - Length Strategy (how to allocate words)
  - Potential Pitfalls (what to avoid)
- Expand each scene into a micro plan that makes prose generation difficult to "hand-wave":
  - Explicit: Desire / Obstacle / Escalation / Turn / Cost
  - 2–4 micro-turns (state changes) per scene
  - Identify one "must dramatize" moment per scene that may NOT be summarized in prose
- Identify where the story will include **at least 1 meaningful disagreement between allies** (subtext engine), and what it changes.
- If the story is domain-heavy (tech/legal/medical/etc.), ensure the plan includes at least 1 meaningful constraint and consequence appropriate to `plausibility_key` (e.g., security: authentication/logging; legal: evidence/traces; medical: limits/triage).

**After (Bash):** `cd books && git add {project}/05-story-plan.md && git commit -m "Add: Story plan for {project}"`
**After (PowerShell):** `cd books; git add {project}/05-story-plan.md; git commit -m "Add: Story plan for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Prose Generation (Flash/Short/Novelette)

**Spawn when:** `06-story.md` doesn't exist (and story-plan exists)

**Sub-agent prompt template:**

```
Write complete prose for `{project}`.

**Target word count:** {from story-plan, e.g., ~14,000 words}

**Read only:**
1. `books/{project}/05-story-plan.md` — Story plan (authoritative prose contract)
2. `misc/prose-style-{prose_style_key}.md` — Style card matching the project's prose style (read `prose_style_key` from frontmatter)

Do NOT read 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md, or any other files. The story-plan is fully self-contained with all character info, style notes, and pitfalls you need.

**Output:** `books/{project}/06-story.md` — Complete prose

**Guidance:** Follow the story plan as the authoritative contract. The story-plan contains:
- **Character States:** Full character info with arcs, voice notes, tells
- **Style Notes:** Pacing, tone, dialogue balance, sensory focus
- **Potential Pitfalls:** What to avoid
- **Scene Micro Plans:** Desire/obstacle/turn/cost for each scene

Use the style card for prose technique. Keep prose publication-ready.

You must obey `prose_guidance` from the story-plan frontmatter (especially `avoid_overuse`, `pacing_notes`, and `preserve`).

You must obey `plausibility_key` from the story-plan frontmatter:
- `grounded`: assume competent systems/procedures where relevant; include realistic constraints and consequences; avoid implausible shortcuts unless explicitly justified.
- `heightened`: allow cinematic compression, but keep internal logic; when domain-heavy, include at least one constraint and a cost.
- `stylized`: keep mechanics light and non-technical; avoid overly specific claims; prioritize voice, theme, and mood.

**Required process (two-pass):**
1. **Draft pass:** write a complete draft that covers the plan (do not polish yet).
2. **Self-review pass:** run the checklist below (do not include the checklist in the prose file).
3. **Revise pass:** revise for clarity, tension, and polish; then output the final revised prose.

**Self-review checklist (required):**
- Each scene has a clear desire / obstacle / turn (and a cost).
- No "thesis paragraph" unless it is anchored to an immediate sensory stimulus AND a present-moment choice.
- Supporting-character introductions do not exceed 2 sentences of explicit backstory on first meeting.
- Include at least 1 meaningful disagreement between allies (subtext), and ensure it changes a choice/approach.
- If domain-heavy: include at least 1 meaningful constraint and consequence appropriate to `plausibility_key` (e.g., security: authentication/logging; legal: evidence/traces; medical: limits/triage).
- Confirm compliance with `prose_guidance` (avoid overuse phrases/tics; apply pacing notes; preserve what must be preserved).
- Check the **Potential Pitfalls** section in story-plan and verify you avoided each one.
- Follow **Style Notes** for pacing, tone, and sensory focus.
- Use **Character States** for voice notes, tells, and arc consistency.

**Prose format:**
- Start with: # {Story Title}
- Complete story prose follows
- Use: * * * (asterisks with spaces) for scene breaks
- No frontmatter in prose files

**After (Bash):** `cd books && git add {project}/06-story.md && git commit -m "Add: Generate prose for {project}"`
**After (PowerShell):** `cd books; git add {project}/06-story.md; git commit -m "Add: Generate prose for {project}"`

Generate publication-ready prose. Do not ask for approval.
```

---

### Sub-Agent: Chapter Plan (Novella/Novel/Epic)

**Spawn when:** A chapter needs planning (chapter-plan doesn't exist)

**Sub-agent prompt template:**

```
Generate `books/{project}/05-chapter-plans/chapter-{NN}-plan.md` for Chapter {N} of `{project}`.

**Chapter target:** ~{X} words

**Read only these files:**
1. `books/{project}/04-structure-plan.md` — Structure plan (characters, full chapter breakdown)
2. All previous chapter plans in `books/{project}/05-chapter-plans/` (chapters 1 through {N-1}) — For continuity of character states and plot threads

**Do NOT read:** 01-premise.md, 02-treatment-approach.md, 03-treatment.md, or chapter prose.

**Output:** `books/{project}/05-chapter-plans/chapter-{NN}-plan.md`

**Format:** Use the Chapter Plan template from this skill.

**Requirements:**
- Copy ALL frontmatter values from `04-structure-plan.md` (including `prose_guidance` and `plausibility_key`). If `plausibility_key` is missing (legacy), set it to `heightened` / `Heightened`.
- Use structure-plan as the source of truth for this chapter's high-level content, goals, and beats.
- Reference previous chapter plans for character states, established details, and open threads.
- **CRITICAL: Copy/adapt these sections from structure-plan to make chapter-plan self-contained for prose generation:**
  - Character States (for characters appearing in this chapter — include arcs, voice notes, tells)
  - Style Notes (pacing, tone, dialogue balance, sensory focus — adapt for this chapter)
  - Length Strategy (how to allocate words within this chapter)
  - Potential Pitfalls (what to avoid — both story-wide and chapter-specific)
- Include per-scene word targets and brief development notes (what fills the space: dialogue/interiority/action/description).
- Include a short **Downstream Contract** section stating what the prose must preserve from this plan.

**After:**
Create directory (Bash): `mkdir -p books/{project}/05-chapter-plans`
Create directory (PowerShell): `New-Item -ItemType Directory -Force -Path books/{project}/05-chapter-plans | Out-Null`
Then (Bash): `cd books && git add {project}/05-chapter-plans/chapter-{NN}-plan.md && git commit -m "Add: Chapter {N} plan for {project}"`
Then (PowerShell): `cd books; git add {project}/05-chapter-plans/chapter-{NN}-plan.md; git commit -m "Add: Chapter {N} plan for {project}"`

Generate complete content. Do not ask for approval.
```

---
### Sub-Agent: Chapter Prose (Novella/Novel/Epic)

**Spawn when:** A chapter needs prose (chapter-plan exists but prose doesn't)

**Sub-agent prompt template:**

```
Generate `books/{project}/06-chapters/chapter-{NN}.md` (Chapter {N}) for `{project}`.

**Chapter target:** ~{X} words
**Project length:** {novella|novel|epic}

**Read only these files:**
1. All previous chapter prose in `books/{project}/06-chapters/` — Source of truth for continuity
2. All chapter plans in `books/{project}/05-chapter-plans/` — Current chapter plan is authoritative; future plans provide foreshadowing context
3. `misc/prose-style-{prose_style_key}.md` — Style card (read `prose_style_key` from frontmatter)

**Do NOT read:** 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md. Each chapter-plan is self-contained with all character info, style notes, and pitfalls you need.

**Output:** `books/{project}/06-chapters/chapter-{NN}.md` — Chapter prose

**Guidance:** Follow this chapter's plan as the authoritative contract. The chapter-plan contains:
- **Character States:** Character info with arcs, voice notes, tells for characters in this chapter
- **Style Notes:** Pacing, tone, dialogue balance, sensory focus for this chapter
- **Potential Pitfalls:** What to avoid
- **Scene Breakdown:** Purpose, conflict, beats for each scene

Use previous chapter prose for continuity and future chapter plans for foreshadowing context. Keep prose publication-ready.

You must obey `prose_guidance` from the chapter-plan frontmatter (especially `avoid_overuse`, `pacing_notes`, and `preserve`).

You must obey `plausibility_key` from the chapter-plan frontmatter:
- `grounded`: assume competent systems/procedures where relevant; include realistic constraints and consequences; avoid implausible shortcuts unless explicitly justified.
- `heightened`: allow cinematic compression, but keep internal logic; when domain-heavy, include at least one constraint and a cost.
- `stylized`: keep mechanics light and non-technical; avoid overly specific claims; prioritize voice, theme, and mood.

**Self-review checklist (required):**
- Each scene has a clear desire / obstacle / turn (and a cost).
- No "thesis paragraph" unless it is anchored to an immediate sensory stimulus AND a present-moment choice.
- Supporting-character introductions do not exceed 2 sentences of explicit backstory on first meeting.
- If domain-heavy: include at least 1 meaningful constraint and consequence appropriate to `plausibility_key`.
- Confirm compliance with `prose_guidance` (avoid overuse phrases/tics; apply pacing notes; preserve what must be preserved).
- Check the **Potential Pitfalls** section in chapter-plan and verify you avoided each one.
- Follow **Style Notes** for pacing, tone, and sensory focus.
- Use **Character States** for voice notes, tells, and arc consistency.
- Verify continuity with previous chapters (character states, established facts, open threads).

**Chapter prose format:**

Use this template structure for all chapter files:

```markdown
# Chapter {N}: {Title}

{Optional epigraph — use sparingly, only when thematically resonant}
> "Quote text here."
> — Attribution

{Scene 1 prose begins immediately after the heading (or epigraph if present).
No blank line needed after the heading. Start with action, dialogue, or
sensory detail — never "Chapter X begins with..."}

{Continue Scene 1 prose...}

* * *

{Scene 2 prose begins after the scene break.
The asterisks with spaces (* * *) create a visual pause.
Each scene should open with a clear grounding in time/place/character.}

{Continue Scene 2 prose...}

* * *

{Scene 3 prose...}

{Final scene ends with prose, not a scene break.
End on a hook, revelation, or emotional beat that pulls readers forward.}
```

**Formatting rules:**
- **Chapter heading:** `# Chapter {N}: {Title}` — always include both number and title
- **Scene breaks:** `* * *` (asterisks with spaces) — centered, with blank lines before/after
- **Epigraphs:** Optional. Use `>` blockquote format. Only include when genuinely meaningful.
- **No frontmatter:** Prose files contain only prose. Metadata lives in chapter-plans.
- **No meta-commentary:** Never write "In this chapter..." or "The scene opens with..."

**After generating:**
Create directory (Bash): `mkdir -p books/{project}/06-chapters`
Create directory (PowerShell): `New-Item -ItemType Directory -Force -Path books/{project}/06-chapters | Out-Null`
Then (Bash): `cd books && git add {project}/06-chapters/chapter-{NN}.md && git commit -m "Add: Generate chapter {N} prose for {project}"`
Then (PowerShell): `cd books; git add {project}/06-chapters/chapter-{NN}.md; git commit -m "Add: Generate chapter {N} prose for {project}"`

Generate publication-ready prose. Do not ask for approval.
```

---

### Chaptered Format Generation Loop (Novella/Novel/Epic)

For novella/novel/epic, after structure-plan exists, loop through all chapters:

```
For chapter 1 to N:
  1. Check if chapter-plan exists → if not, spawn chapter-plan sub-agent
  2. Check if chapter prose exists → if not, spawn chapter-prose sub-agent
  3. Continue to next chapter

Report: "{Novella/Novel/Epic} complete. {N} chapters, ~{total} words."
```

Do NOT stop between chapters. Generate the entire book in one `/generate-prose` invocation.

---

## Structure Plan Templates

### Structure Plan Format (Novella/Novel/Epic)

```markdown
---
project: {project-name}
stage: structure-plan
# Copy ALL taxonomy keys and display names from treatment frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from treatment}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from treatment - copy entire object}
subgenres: {from treatment - copy entire object}
length_key: {from treatment: novella|novel|epic}
length_target_words: {number}
series_structure_key: {from treatment}
series_structure: "{from treatment}"
target_audience_key: {from treatment}
target_audience: "{from treatment}"
content_rating_key: {from treatment}
content_rating: "{from treatment}"
plausibility_key: {from treatment (or default to heightened if missing)}
plausibility: "{from treatment (or default to Heightened if missing)}"
prose_style_key: {from treatment}
prose_style: "{from treatment}"
dialogue_density_key: {from treatment}
dialogue_density: "{from treatment}"
pov_key: {from treatment}
pov: "{from treatment}"
tense: {from treatment}
tone: "{from treatment}"
mood: "{from treatment}"
# Multi-select: copy all genre-specific arrays/objects from treatment
# Examples (actual fields depend on genre):
magic_system_keys: {from treatment - copy array if present}
magic_systems: {from treatment - copy array if present}
fantasy_race_keys: {from treatment - copy array if present}
fantasy_races: {from treatment - copy array if present}
theme_keys: {from treatment - copy array if present}
themes: {from treatment - copy array if present}
quest_type_key: {from treatment - copy if present}
quest_type: "{from treatment - copy if present}"
world_type_key: {from treatment - copy if present}
world_type: "{from treatment - copy if present}"
worldbuilding_depth_key: {from treatment - copy if present}
worldbuilding_depth: "{from treatment - copy if present}"
tags:
  - {from treatment}
custom_style_notes: "{from treatment}"
prose_guidance: {from treatment - copy entire object}
---

Copy ALL frontmatter values from treatment, including multi-select arrays and objects. Do not modify unless user explicitly requested changes.

# Structure Plan

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {Single POV / Multiple POV / Alternating}

Note: Per-chapter word count targets below should approximately sum to the overall target.

## Downstream Contract

This file is the authoritative plan for all chapter plans.

- **Must preserve downstream:** chapter order, POV assignments, required reveals/turns, and chapter goals
- **Downstream changes:** only if the user explicitly requests them (otherwise treat this as the contract)

## Character States

### {Protagonist}
- **Starting emotional state:** {where they begin}
- **Goal:** {what they want}
- **Internal conflict:** {tension driving them}
- **Arc:** {starting state → ending state}
- **Voice notes:** {how to render their perspective}

### {Other Key Characters}
- **{Name}:**
  - **Role:** {their function in the story}
  - **Tells/Voice:** {distinctive traits, speech patterns}
  - **Key moments:** {where they matter most}

## Chapter Breakdown

### Chapter 1: {Title}

**POV:** {Character name}
**Setting:** {Location and time}
**Word count target:** {2,500-4,000}

**Treatment reference:** {Which act/scenes from treatment this covers}

**Summary:**
{2-3 sentences describing what happens in this chapter}

**Scene breakdown:**
1. {Scene 1 - brief description}
2. {Scene 2 - brief description}
3. {Scene 3 - brief description}

**Chapter goals:**
- {What this chapter must accomplish for plot}
- {What this chapter must accomplish for character}

**Ends with:** {Hook or turn that leads to next chapter}

---

{Repeat for each chapter}

## Pacing Notes

- **Action chapters:** {List chapter numbers}
- **Character/Reflection chapters:** {List chapter numbers}
- **Climax chapters:** {List chapter numbers}

## Story Arc Mapping

- **Opening hook:** Chapter {X} — {how it grabs the reader}
- **Rising action:** Chapters {X-Y} — {where tension builds}
- **Midpoint:** Chapter {X} — {the shift or revelation}
- **Climax:** Chapter {X} — {the peak moment}
- **Resolution:** Chapter {X} — {how it ends}

## Style Notes

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

{2-4 sentences analyzing how this story will achieve its word count target — which chapters deserve more space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls

- {Thing to avoid or be careful about}
- {Risk to watch for}
- {Continuity concern}

## Continuity Tracking

| Element | Introduced | Resolved |
|---------|-----------|----------|
| {Plot thread} | Ch {X} | Ch {Y} |
| {Character arc} | Ch {X} | Ch {Y} |
```

### Structure Plan Format (Flash/Short/Novelette)

```markdown
---
project: {project-name}
stage: structure-plan
# Copy ALL taxonomy keys and display names from treatment frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from treatment}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from treatment - copy entire object}
subgenres: {from treatment - copy entire object}
length_key: {from treatment: flash_fiction|short_story|novelette}
length_target_words: {number}
series_structure_key: {from treatment}
series_structure: "{from treatment}"
target_audience_key: {from treatment}
target_audience: "{from treatment}"
content_rating_key: {from treatment}
content_rating: "{from treatment}"
plausibility_key: {from treatment (or default to heightened if missing)}
plausibility: "{from treatment (or default to Heightened if missing)}"
prose_style_key: {from treatment}
prose_style: "{from treatment}"
dialogue_density_key: {from treatment}
dialogue_density: "{from treatment}"
pov_key: {from treatment}
pov: "{from treatment}"
tense: {from treatment}
tone: "{from treatment}"
mood: "{from treatment}"
# Multi-select: copy all genre-specific arrays/objects from treatment
# Examples (actual fields depend on genre):
magic_system_keys: {from treatment - copy array if present}
magic_systems: {from treatment - copy array if present}
fantasy_race_keys: {from treatment - copy array if present}
fantasy_races: {from treatment - copy array if present}
theme_keys: {from treatment - copy array if present}
themes: {from treatment - copy array if present}
quest_type_key: {from treatment - copy if present}
quest_type: "{from treatment - copy if present}"
world_type_key: {from treatment - copy if present}
world_type: "{from treatment - copy if present}"
worldbuilding_depth_key: {from treatment - copy if present}
worldbuilding_depth: "{from treatment - copy if present}"
tags:
  - {from treatment}
custom_style_notes: "{from treatment}"
prose_guidance: {from treatment - copy entire object}
---

Copy ALL frontmatter values from treatment, including multi-select arrays and objects. Do not modify unless user explicitly requested changes.

# Structure Plan

## Overview

- **Target word count:** {estimate}
- **Number of scenes:** {count}
- **POV:** {narrative perspective}
- **Timespan:** {how much time the story covers}

Note: Per-scene word count targets below should approximately sum to the overall target.

## Downstream Contract

This file is the authoritative macro plan for story-plan generation (`05-story-plan.md`).

- **Story plan must preserve:** scene order, key beats/turns, `prose_guidance`, and style notes (unless the user explicitly requests changes)
- **Prose contract:** `05-story-plan.md` becomes the authoritative contract for `06-story.md`

## Character States

### {Protagonist}
- **Starting emotional state:** {where they begin}
- **Goal:** {what they want}
- **Internal conflict:** {tension driving them}
- **Arc:** {starting state → ending state}
- **Voice notes:** {how to render their perspective}

### {Other Characters}
- **{Name}:** {role, function, and how they affect protagonist}

## Scene Breakdown

### Scene 1: {Title/Description}

**Setting:** {Where and when}
**Word count target:** {estimate}

**Purpose:** {What this scene accomplishes}

**Scene engine:**
- **Desire:** {what the protagonist wants right now}
- **Obstacle:** {what blocks it}
- **Escalation:** {what makes it worse}
- **Turn:** {what changes by the end}
- **Cost:** {what is paid (emotionally or materially)}

**Beat-by-beat:**
1. {Opening beat - how scene starts}
2. {Development - what happens}
3. {Turn/Hook - how scene ends or transitions}

**Character state at end:** {Where the protagonist is emotionally}

**Development notes:** {what fills the space — e.g., "dialogue exchange + internal monologue + setting details"}

---

{Repeat for each scene}

## Story Arc Mapping

- **Opening hook:** Scene {X} — {how it grabs the reader}
- **Complication:** Scene {X} — {where tension rises}
- **Climax:** Scene {X} — {the peak moment}
- **Resolution:** Scene {X} — {how it ends}

## Style Notes

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

{2-4 sentences analyzing how this story will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls

- {Thing to avoid or be careful about}
- {Risk to watch for}
```

---

## Story Plan Template (Flash/Short/Novelette Only)

### Story Plan Format

```markdown
---
project: {project-name}
stage: story-plan
# Copy ALL taxonomy keys and display names from structure-plan frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from structure-plan}
subgenre_keys: {from structure-plan - copy entire object}
subgenres: {from structure-plan - copy entire object}
length_key: {from structure-plan: flash_fiction|short_story|novelette}
length_target_words: {number}
series_structure_key: {from structure-plan}
series_structure: "{from structure-plan}"
target_audience_key: {from structure-plan}
target_audience: "{from structure-plan}"
content_rating_key: {from structure-plan}
content_rating: "{from structure-plan}"
plausibility_key: {from structure-plan (or default to heightened if missing)}
plausibility: "{from structure-plan (or default to Heightened if missing)}"
prose_style_key: {from structure-plan}
prose_style: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
# Multi-select: copy all genre-specific arrays/objects from structure-plan
magic_system_keys: {from structure-plan - copy array if present}
magic_systems: {from structure-plan - copy array if present}
fantasy_race_keys: {from structure-plan - copy array if present}
fantasy_races: {from structure-plan - copy array if present}
theme_keys: {from structure-plan - copy array if present}
themes: {from structure-plan - copy array if present}
quest_type_key: {from structure-plan - copy if present}
quest_type: "{from structure-plan - copy if present}"
world_type_key: {from structure-plan - copy if present}
world_type: "{from structure-plan - copy if present}"
worldbuilding_depth_key: {from structure-plan - copy if present}
worldbuilding_depth: "{from structure-plan - copy if present}"
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
prose_guidance: {from structure-plan - copy entire object}
---

Copy ALL frontmatter values from structure-plan, including `prose_guidance`. Do not modify.

# Story Plan: {Title}

## Story Overview

- **Target word count:** {from structure-plan overview}
- **Number of scenes:** {from structure-plan overview}
- **POV:** {from structure-plan}
- **Timespan:** {from structure-plan}

**Story arc:** {1-3 lines summarizing the arc from structure-plan}

## Character States

{Copy ALL character information from structure-plan to make this file self-contained}

### {Protagonist}
- **Starting emotional state:** {from structure-plan}
- **Goal:** {from structure-plan}
- **Internal conflict:** {from structure-plan}
- **Arc:** {from structure-plan: starting state → ending state}
- **Voice notes:** {from structure-plan}

### {Other Key Characters}
{For each character from structure-plan, include:}
- **{Name}:**
  - **Role:** {their function in the story}
  - **Tells/Voice:** {distinctive traits, speech patterns}
  - **Key moments:** {where they matter most}

## Voice Calibration

{Optional but recommended for voice-heavy stories: 200-400 words of in-voice sample narration OR a bullet list of “voice moves” and “don’ts.”}

## Story-wide Engines (Required)

- **Ally disagreement (required):** {Where it happens, what is at stake, and what it changes}
- **Domain constraint (if applicable):** {the relevant real-world/procedural constraint} + {the cost/consequence} (calibrate to `plausibility_key`)

## Scene-by-Scene Micro Plan

### Scene 1: {Title/Description}

**Setting:** {from structure-plan}
**Word count target:** {from structure-plan}

**Desire:** {what the protagonist wants right now}
**Obstacle:** {what blocks it}
**Escalation:** {what makes it worse}
**Turn:** {what changes by the end}
**Cost:** {what is paid (emotionally or materially)}

**Micro-turns (2-4):**
1. {state change}
2. {state change}

**Must dramatize moment:** {one specific beat that must be shown in-scene (not summarized)}
**Backstory constraint:** {ensure intros stay ≤2 sentences of explicit backstory on first meeting}

**Notes:** {how to spend words — dialogue/interiority/action/texture; where subtext lives; what to avoid per prose_guidance}
**Ends with:** {hook/turn}

---

{Repeat for each scene}

## Story Arc Mapping

{Copy from structure-plan}

- **Opening hook:** Scene {X} — {how it grabs the reader}
- **Complication:** Scene {X} — {where tension rises}
- **Climax:** Scene {X} — {the peak moment}
- **Resolution:** Scene {X} — {how it ends}

## Style Notes

{Copy from structure-plan}

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

{Copy from structure-plan: 2-4 sentences analyzing how this story will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls

{Copy from structure-plan}

- {Thing to avoid or be careful about}
- {Risk to watch for}
- {Continuity concern}

## Downstream Contract

This file is the authoritative plan for prose generation (`06-story.md`).

- **Prose must preserve:** scene order, key beats/turns, scene engines (desire/obstacle/escalation/turn/cost), the planned ally disagreement, and `prose_guidance`.
- **Theme delivery constraint:** no thesis-only paragraphs; any thematic statement must be anchored to immediate sensation + present-moment choice.
- **Character consistency:** use Character States section for arcs, voice notes, and tells.
- **Style compliance:** follow Style Notes and avoid Potential Pitfalls.
```

---

## Chapter Plan Template (Novella/Novel/Epic Only)

### Chapter Plan Format

```markdown
---
project: {project-name}
stage: chapter-plan
chapter: {N}
# Copy ALL taxonomy keys and display names from structure-plan frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from structure-plan}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from structure-plan - copy entire object}
subgenres: {from structure-plan - copy entire object}
length_key: {from structure-plan: novella|novel|epic}
length_target_words: {number}
series_structure_key: {from structure-plan}
series_structure: "{from structure-plan}"
target_audience_key: {from structure-plan}
target_audience: "{from structure-plan}"
content_rating_key: {from structure-plan}
content_rating: "{from structure-plan}"
plausibility_key: {from structure-plan (or default to heightened if missing)}
plausibility: "{from structure-plan (or default to Heightened if missing)}"
prose_style_key: {from structure-plan}
prose_style: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
# Multi-select: copy all genre-specific arrays/objects from structure-plan
# Examples (actual fields depend on genre):
magic_system_keys: {from structure-plan - copy array if present}
magic_systems: {from structure-plan - copy array if present}
fantasy_race_keys: {from structure-plan - copy array if present}
fantasy_races: {from structure-plan - copy array if present}
theme_keys: {from structure-plan - copy array if present}
themes: {from structure-plan - copy array if present}
quest_type_key: {from structure-plan - copy if present}
quest_type: "{from structure-plan - copy if present}"
world_type_key: {from structure-plan - copy if present}
world_type: "{from structure-plan - copy if present}"
worldbuilding_depth_key: {from structure-plan - copy if present}
worldbuilding_depth: "{from structure-plan - copy if present}"
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
prose_guidance: {from structure-plan - copy entire object}
---

Copy ALL frontmatter values from structure-plan, including multi-select arrays and objects. Do not modify.

# Chapter {N} Plan: {Title}

## Structure Plan Reference

**From 04-structure-plan.md:**
- Treatment reference: {which act/scenes this covers}
- Summary: {the planned summary}
- Chapter goals: {from structure plan}
- Ends with: {the planned hook/turn}

## Continuity from Previous Chapters

{For Chapter 1, write "First chapter - establishing baseline."}

**Carrying forward from previous chapter plans:**
- {Open thread 1 from previous plans - status}
- {Open thread 2 - status}
- {Character emotional state entering this chapter, based on where previous plan left them}
- {Key details/facts established that affect this chapter}

**Promises to readers:** {things set up in previous chapters that need attention}

## Downstream Contract

This plan is authoritative for the prose of Chapter {N}.

- **Prose must preserve:** POV, scene order, key beats/reveals, and the planned hook/turn (unless the user explicitly requests changes)
- **Canon source:** prose agent reads all previous chapter prose for continuity
- **Character consistency:** use Character States section for voice notes, tells, and arc position
- **Style compliance:** follow Style Notes and avoid Potential Pitfalls

## Character States

{Copy/adapt from structure-plan's Character States for characters appearing in this chapter}

### {POV Character}
- **Emotional state:** {where they are mentally/emotionally entering this chapter}
- **Goal this chapter:** {what they want}
- **Internal conflict:** {what's pulling them in different directions}
- **Arc position:** {where they are in their overall arc}
- **Voice notes:** {how their mental state affects prose voice — include distinctive patterns, tells}

### {Other Key Characters in This Chapter}
- **{Name}:**
  - **State this chapter:** {emotional/situational state}
  - **Role:** {function in this chapter}
  - **Tells/Voice:** {distinctive traits, speech patterns to preserve}

## Scene-by-Scene Breakdown

**Chapter word count target:** {from structure-plan, e.g., ~3,500 words}

### Scene 1: {Description}
- **Word count:** {portion of chapter target, e.g., ~1,200 words}
- **Purpose:** {why this scene exists}
- **Conflict/Tension:** {what drives the scene}
- **Key beats:** {1-3 specific moments}
- **Ends with:** {transition to next scene}
- **Development notes:** {what fills the space — dialogue, interiority, description, tension}

### Scene 2: {Description}
{Repeat for each scene, with word counts summing to chapter target}

## Style Notes

- **Pacing:** {fast/slow/mixed for this chapter}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance for this chapter}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

{2-4 sentences analyzing how this chapter will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls

- {Thing to avoid or be careful about}
- {Continuity risk}
```
