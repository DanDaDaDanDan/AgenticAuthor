---
name: generate-treatment
description: Generate treatment planning and treatment (02-treatment-approach.md → 03-treatment.md).
argument-hint: ""
---

Generate the outline/treatment stages for the active project.

Equivalent to:
- `/generate treatment`

## Usage

```
/generate-treatment
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

## Stage: treatment

Generate the story outline/treatment.

### Orchestration Flow

1. **Read premise** to understand the story (main context)
2. **Ask clarifying questions** about ending, structure, specific elements
3. **Spawn sub-agent** to generate 02-treatment-approach.md (planning document)
4. **Spawn sub-agent** to generate 03-treatment.md (reads treatment-approach for guidance)
5. Report completion

### Clarifying Questions (ask BEFORE spawning)

After reading the premise, ask the user about key story decisions:

1. **Ending direction:**
   > How should this story end?
   > 1. Triumphant - protagonist achieves their goal
   > 2. Bittersweet - victory with significant cost
   > 3. Tragic - protagonist fails or is destroyed
   > 4. Ambiguous - open to interpretation
   > 5. Let me decide based on the premise

2. **Structure preference:** (novella/novel/epic only)
   > What story structure fits best?
   > 1. Three-act (classic setup/confrontation/resolution)
   > 2. Four-act (extended middle with clear crisis point)
   > 3. Five-act (epic with distinct falling action)
   > 4. Episodic (connected adventures/events)
   > 5. Let me decide based on the premise

3. **Any specific elements?** (optional, free-form)
   > Are there any specific plot points, scenes, or story beats you definitely want included?

### Sub-Agent: Treatment Approach

**Spawn first.** This planning document reasons through how to structure the treatment.

**Sub-agent prompt template:**

```
Write `books/{project}/02-treatment-approach.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}
**User preferences:** Ending={...}; Structure={... if applicable}; Specific elements={... if any}

**Read only:**
1. `books/{project}/01-premise.md`
2. `taxonomies/{genre}-taxonomy.json`

Premise is the authoritative source. Do NOT read any other files.

**Output:** `books/{project}/02-treatment-approach.md` (use the Treatment Approach template from this skill)

**Goal:** Analyze the premise and decide the best treatment structure + risks (conflict, arc, antagonist deployment, pacing challenges).

**After (Bash):** `cd books && git add {project}/02-treatment-approach.md && git commit -m "Add: Treatment approach for {project}"`
**After (PowerShell):** `cd books; git add {project}/02-treatment-approach.md; git commit -m "Add: Treatment approach for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Treatment

**Spawn after treatment-approach exists.** This generates the full treatment using the approach as guidance.

**Sub-agent prompt template:**

```
Write `books/{project}/03-treatment.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}

**Read only:** `books/{project}/02-treatment-approach.md` — Self-contained planning document (includes frontmatter values from premise)

Do NOT read 01-premise.md or any other files.

**Output:** `books/{project}/03-treatment.md` (use the appropriate Treatment template from this skill)

**Requirements:**
- Follow the decisions in `02-treatment-approach.md` (structure type, act logic, risks).
- Copy frontmatter values from `02-treatment-approach.md` (treatment-approach has all values from premise).
- Add a `prose_guidance` block in frontmatter with actionable, project-specific guidance:
  - `avoid_overuse`: phrases/tics to watch for (keep entries as plain phrases whenever possible)
  - `techniques`: specific craft techniques to apply (e.g., “replace thesis paragraphs with dramatized friction”)
  - `pacing_notes`: where to tighten/expand and why
  - `preserve`: what is working and must not be lost downstream
- Include the **Downstream Contract** section from the template.

**After (Bash):** `cd books && git add {project}/03-treatment.md && git commit -m "Add: Generate treatment for {project}"`
**After (PowerShell):** `cd books; git add {project}/03-treatment.md; git commit -m "Add: Generate treatment for {project}"`

Generate complete, publication-ready content. Do not ask for approval.
```

### Treatment Templates

#### Treatment Approach Format

```markdown
---
project: {project-name}
stage: treatment-approach
# Copy ALL taxonomy keys and display names from premise frontmatter
# This makes treatment-approach self-contained so treatment doesn't need to read premise
genre_key: {from premise}
subgenre_keys: {from premise - copy entire object}
subgenres: {from premise - copy entire object}
length_key: {from premise}
length_target_words: {from premise}
series_structure_key: {from premise}
series_structure: "{from premise}"
target_audience_key: {from premise}
target_audience: "{from premise}"
content_rating_key: {from premise}
content_rating: "{from premise}"
plausibility_key: {from premise (or default to heightened if missing)}
plausibility: "{from premise (or default to Heightened if missing)}"
prose_style_key: {from premise}
prose_style: "{from premise}"
dialogue_density_key: {from premise}
dialogue_density: "{from premise}"
pov_key: {from premise}
pov: "{from premise}"
tense: {from premise}
tone: "{from premise}"
mood: "{from premise}"
# Copy all genre-specific arrays/objects from premise
# (actual fields depend on genre - copy whatever exists in premise)
tags: {from premise}
custom_style_notes: "{from premise}"
---

# Treatment Approach

## Premise Analysis

**Core conflict:** {How the central conflict will drive the story structure}
**Protagonist arc:** {Starting state → transformation → ending state}
**Antagonist role:** {How the opposing force will be deployed across the narrative}
**Stakes escalation:** {How stakes will build throughout the story}

## Theme Integration

- **{Primary theme}:** {How it will manifest in plot/character choices}
- **{Secondary theme}:** {Where it will appear}

## Proposed Structure

**Structure type:** {Three-act / Four-act / Five-act / Episodic / Other}
**Reasoning:** {Why this structure fits the premise}

**Act overview:**
- Act I: {One sentence on setup approach}
- Act II: {One sentence on confrontation/complication approach}
- Act III: {One sentence on resolution approach}
{Add acts if using four/five-act structure}

## Subplots

- **{Subplot 1}:** {Brief description and connection to main plot}
- **{Subplot 2}:** {Brief description}

## Potential Challenges

- {Any gaps in the premise that need resolution}
- {Structural tensions to navigate}
- {Pacing considerations}

## Style Considerations

**Prose style impact:** {How the selected prose style affects treatment choices, including implied pacing}
```

#### Treatment Format (Novella/Novel/Epic)

```markdown
---
project: {project-name}
stage: treatment
# Copy ALL taxonomy keys and display names from treatment-approach frontmatter
# Treatment-approach is self-contained (already has all values from premise)
genre_key: {from treatment-approach}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from treatment-approach - copy entire object}
subgenres: {from treatment-approach - copy entire object}
length_key: {from treatment-approach: novella|novel|epic}
length_target_words: {number}
series_structure_key: {from treatment-approach}
series_structure: "{from treatment-approach}"
target_audience_key: {from treatment-approach}
target_audience: "{from treatment-approach}"
content_rating_key: {from treatment-approach}
content_rating: "{from treatment-approach}"
plausibility_key: {from treatment-approach (or default to heightened if missing)}
plausibility: "{from treatment-approach (or default to Heightened if missing)}"
prose_style_key: {from treatment-approach}
prose_style: "{from treatment-approach}"
dialogue_density_key: {from treatment-approach}
dialogue_density: "{from treatment-approach}"
pov_key: {from treatment-approach}
pov: "{from treatment-approach}"
tense: {from treatment-approach}
tone: "{from treatment-approach}"
mood: "{from treatment-approach}"
# Multi-select: copy all genre-specific arrays/objects from treatment-approach
# Examples (actual fields depend on genre):
magic_system_keys: {from treatment-approach - copy array if present}
magic_systems: {from treatment-approach - copy array if present}
fantasy_race_keys: {from treatment-approach - copy array if present}
fantasy_races: {from treatment-approach - copy array if present}
theme_keys: {from treatment-approach - copy array if present}
themes: {from treatment-approach - copy array if present}
quest_type_key: {from treatment-approach - copy if present}
quest_type: "{from treatment-approach - copy if present}"
world_type_key: {from treatment-approach - copy if present}
world_type: "{from treatment-approach - copy if present}"
worldbuilding_depth_key: {from treatment-approach - copy if present}
worldbuilding_depth: "{from treatment-approach - copy if present}"
tags:
  - {from treatment-approach}
custom_style_notes: "{from treatment-approach}"
prose_guidance:
  # Required. Keep `avoid_overuse` entries as plain phrases/tics whenever possible.
  avoid_overuse:
    - {phrase or tic to watch for}
  techniques:
    - {specific craft technique to apply}
  pacing_notes:
    - {pacing note (where to tighten/expand and why)}
  preserve:
    - {element that must be preserved downstream}
---

# Treatment

## Downstream Contract

- **Authoritative for:** `04-structure-plan.md`
- **Must preserve downstream:** ending, major beats/reveals, character arcs, and frontmatter constraints (POV/tense/tone/content rating)
- **Downstream changes:** only if the user explicitly requests them (otherwise treat this as the contract)

## Story Overview

{2-3 paragraph summary of the complete story arc}

## Act Structure

{Use the structure that best fits the story.}

### Act I: {Title} (Setup)

{Describe the opening situation, character introductions, inciting incident, and first plot point}

**Key scenes:**
{List the essential scenes - may be 3-6 depending on story needs}

### Act II: {Title} (Confrontation)

{Describe the rising action, complications, midpoint, and escalating conflict}

**Key scenes:**
{List essential scenes - this act is often longest}

### Act III: {Title} (Resolution)

{Describe the climax, resolution, and ending}

**Key scenes:**
{List essential scenes}

## Character Arcs

### {Protagonist Name}
- **Starting state:** {How they begin}
- **Key transformation:** {What changes them}
- **Ending state:** {Who they become}

### {Antagonist/Key Character}
- **Role in story:** {Their function}
- **Arc:** {How they develop or remain static}

## Subplots

1. **{Subplot name}:** {Brief description and how it connects to main plot}
2. **{Subplot name}:** {Brief description}

## World Elements

{Any important world-building details needed for the story}
```

#### Treatment Format (Flash/Short/Novelette)

```markdown
---
project: {project-name}
stage: treatment
# Copy ALL taxonomy keys and display names from treatment-approach frontmatter
# Treatment-approach is self-contained (already has all values from premise)
genre_key: {from treatment-approach}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from treatment-approach - copy entire object}
subgenres: {from treatment-approach - copy entire object}
length_key: {from treatment-approach: flash_fiction|short_story|novelette}
length_target_words: {number}
series_structure_key: {from treatment-approach}
series_structure: "{from treatment-approach}"
target_audience_key: {from treatment-approach}
target_audience: "{from treatment-approach}"
content_rating_key: {from treatment-approach}
content_rating: "{from treatment-approach}"
plausibility_key: {from treatment-approach (or default to heightened if missing)}
plausibility: "{from treatment-approach (or default to Heightened if missing)}"
prose_style_key: {from treatment-approach}
prose_style: "{from treatment-approach}"
dialogue_density_key: {from treatment-approach}
dialogue_density: "{from treatment-approach}"
pov_key: {from treatment-approach}
pov: "{from treatment-approach}"
tense: {from treatment-approach}
tone: "{from treatment-approach}"
mood: "{from treatment-approach}"
# Multi-select: copy all genre-specific arrays/objects from treatment-approach
# Examples (actual fields depend on genre):
magic_system_keys: {from treatment-approach - copy array if present}
magic_systems: {from treatment-approach - copy array if present}
fantasy_race_keys: {from treatment-approach - copy array if present}
fantasy_races: {from treatment-approach - copy array if present}
theme_keys: {from treatment-approach - copy array if present}
themes: {from treatment-approach - copy array if present}
quest_type_key: {from treatment-approach - copy if present}
quest_type: "{from treatment-approach - copy if present}"
world_type_key: {from treatment-approach - copy if present}
world_type: "{from treatment-approach - copy if present}"
worldbuilding_depth_key: {from treatment-approach - copy if present}
worldbuilding_depth: "{from treatment-approach - copy if present}"
tags:
  - {from treatment-approach}
custom_style_notes: "{from treatment-approach}"
prose_guidance:
  # Required. Keep `avoid_overuse` entries as plain phrases/tics whenever possible.
  avoid_overuse:
    - {phrase or tic to watch for}
  techniques:
    - {specific craft technique to apply}
  pacing_notes:
    - {pacing note (where to tighten/expand and why)}
  preserve:
    - {element that must be preserved downstream}
---

# Treatment

## Downstream Contract

- **Authoritative for:** `04-structure-plan.md`
- **Must preserve downstream:** ending, key beats, and frontmatter constraints (POV/tense/tone/content rating)
- **Downstream changes:** only if the user explicitly requests them (otherwise treat this as the contract)

## Story Arc

{Single paragraph: opening situation → complication → climax → resolution}

## Key Beats

1. **Opening hook:** {How the story grabs attention}
2. **Complication:** {The central problem or conflict}
3. **Turning point:** {The moment everything changes}
4. **Resolution:** {How it ends}

## Character

- **Protagonist:** {Name} — {Starting state → ending state in one sentence}
- **Other characters:** {Brief notes on any supporting characters}

## Core Scene

{The most important scene - describe in 2-3 sentences}
```
