---
name: generate
description: Generate content at any stage - premise, treatment, or prose.
argument-hint: "[stage]"
---

Generate content at any stage of the book creation process.

## Usage

```
/generate [stage]
```

## Arguments

- `stage`: One of `premise`, `treatment`, or `prose`

---

## Execution Model

**Use sub-agents for all generation work.**

This skill orchestrates generation by spawning sub-agents with carefully managed context. Each sub-agent:
- Receives ONLY the files it needs (per the self-contained stages principle)
- Runs autonomously to completion without asking for approval
- Commits its work before returning

**Why sub-agents?**
1. **Context isolation** — Prevents contamination from earlier stages
2. **Token efficiency** — Each generation uses minimal context
3. **Autonomy** — No stopping for approval at intermediate steps

**Orchestrator responsibilities (main agent):**
1. Detect project and read project.yaml
2. Ask any required clarifying questions UPFRONT (before spawning)
3. Spawn sub-agent(s) with precise context instructions
4. Report completion to user

**Do NOT:**
- Ask for approval between steps
- Read files that sub-agents will read (wastes context)
- Generate content directly in main context (except premise, which is interactive)

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

## Stage: premise

Generate the core concept and story foundation.

**Note:** Premise generation is interactive (requires user input for concept and style), so it runs in the main context, not as a sub-agent.

**Context to read:**
- `taxonomies/base-taxonomy.json` - Universal story properties
- `taxonomies/{genre}-taxonomy.json` - Genre-specific options
- `taxonomies/style-taxonomy.json` - Prose style options

**Genre to filename mapping:**
| Genre in project.yaml | Taxonomy file |
|----------------------|---------------|
| fantasy | fantasy-taxonomy.json |
| science-fiction | science-fiction-taxonomy.json |
| romance | romance-taxonomy.json |
| horror | horror-taxonomy.json |
| mystery-thriller | mystery-thriller-taxonomy.json |
| urban-fantasy | urban-fantasy-taxonomy.json |
| romantasy | romantasy-taxonomy.json |
| contemporary-fiction | contemporary-fiction-taxonomy.json |
| literary-fiction | literary-fiction-taxonomy.json |
| historical-fiction | historical-fiction-taxonomy.json |
| young-adult | young-adult-taxonomy.json |
| generic | generic-taxonomy.json |

**Using taxonomy data:**
1. Review the genre taxonomy's subgenres and present relevant options to the user
2. Use the selected subgenre's `key_features`, `themes`, and `tone` to guide the premise
3. Read `length` and `series_structure` from project.yaml (already collected by /new-book)
4. Ask the user about `target_audience` and `content_rating` from base-taxonomy options
5. Review style-taxonomy for prose style options appropriate to the genre
6. Include 2-3 taxonomy-derived tags in the final premise
7. Store both taxonomy keys and display names in the frontmatter for downstream tooling
8. **For multi-select categories, follow the taxonomy's `selection_rule`:**
   - `select_one`: Store as scalar (`category_key: value`, `category: "Display"`)
   - `select_primary_and_secondary`: Ask user for primary, then optionally secondary. Store as object:
     ```yaml
     category_keys:
       primary: key1
       secondary: key2  # omit if not chosen
     categories:
       primary: "Display 1"
       secondary: "Display 2"  # omit if not chosen
     ```
   - `select_one_or_two`, `select_up_to_three`, `select_all_that_apply`: Let user pick multiple. Store as array:
     ```yaml
     category_keys:
       - key1
       - key2
     categories:
       - "Display 1"
       - "Display 2"
     ```
   - `select_primary`: Same as `select_one` (just a primary, no secondary)

**Output file:** `01-01-premise.md`

**Generation instructions:**

1. Ask the user for a brief concept (1-3 sentences describing the story idea).

2. **Present subgenre options from the genre taxonomy:**
   Read the genre taxonomy and find the subgenre category (named `{genre}_subgenre`, e.g., `fantasy_subgenre`, `romance_subgenre`). Present options to the user:
   > What subgenre fits this story?
   > {List options from taxonomy with brief descriptions}

   Check the category's `selection_rule`:
   - If `select_primary_and_secondary`: Ask for primary choice, then offer optional secondary
   - If `select_one`: Just ask for one choice
   - If multi-select (`select_up_to_three`, etc.): Allow multiple selections

   Store the selection(s) in the appropriate frontmatter structure (object for primary/secondary, array for multi-select, scalar for single).

3. Ask about target audience:
   > Who is the target audience?
   > 1. Middle Grade (ages 8-12) - age-appropriate themes, no explicit content
   > 2. Young Adult (ages 13-17) - coming-of-age themes, limited mature content
   > 3. New Adult (ages 18-25) - mature themes, identity exploration
   > 4. Adult (ages 18+) - no restrictions, complex narratives

4. Ask about content rating:
   > What content rating fits this story?
   > 1. Clean/All Ages - no profanity, violence, or sexual content
   > 2. Mild/PG - minimal mature content, mild profanity, non-graphic violence
   > 3. Moderate/PG-13 - some mature content, action violence, suggestive content
   > 4. Mature/R - adult content, strong language, violence, sexual content
   > 5. Explicit/NC-17 - graphic adult content, no limits

5. Ask about prose style preference:
   > What prose style fits this story?
   > 1. Commercial/Accessible - clear, readable, mass-market appeal
   > 2. Literary - denser prose, rewards close reading
   > 3. Minimalist - spare, precise, subtext-heavy
   > 4. Pulp/Action - fast, punchy, momentum-driven
   > 5. Lyrical/Atmospheric - poetic, mood-focused, sensory-rich
   > 6. Conversational - strong narrative voice, personality-driven

   Note the genre's `best_for` suggestions in style-taxonomy.json but let the user choose freely.

6. Ask about dialogue density (optional):
   > How dialogue-heavy should the narrative be?
   > 1. High (40-60%) - dialogue-driven, scenes play out in conversation
   > 2. Moderate (25-40%) - balanced mix of dialogue and narrative
   > 3. Low (<25%) - narrative-driven, dialogue used sparingly for impact

   **Default:** If the user skips or says "you decide," use Moderate (works for most genres).

7. Ask about point of view:
   > What narrative POV works best?
   > 1. First Person - intimate, limited knowledge, "I/me" narration
   > 2. Third Person Limited (Single POV) - one character's thoughts, some distance
   > 3. Third Person Multiple - rotating POV between characters
   > 4. Third Person Omniscient - all-knowing narrator, can access any thoughts
   > 5. Second Person - "you" narration (uncommon, experimental)

   **Default:** If the user skips or says "you decide," use Third Person Limited for most genres, First Person for YA/Romance/Urban Fantasy.

8. Ask about tense:
   > What tense should the narrative use?
   > 1. Past tense - traditional storytelling ("She walked...")
   > 2. Present tense - immediate, cinematic ("She walks...")

   **Default:** If the user skips or says "you decide," use Past tense (the industry standard for most genres).

9. Generate a complete premise document with YAML frontmatter:

```markdown
---
project: {project-name}
stage: premise
# Genre taxonomy (keys for tooling, names for readability)
genre_key: {genre-key from project.yaml}
# Subgenre uses select_primary_and_secondary → object with primary/secondary
subgenre_keys:
  primary: {key, e.g., dark_fantasy}
  secondary: {key or omit if none, e.g., political_intrigue}
subgenres:
  primary: "{Display Name, e.g., Dark Fantasy}"
  secondary: "{Display Name or omit if none, e.g., Political Intrigue}"
# Base taxonomy - required categories (store both key and display name)
length_key: {from project.yaml: flash_fiction|short_story|novelette|novella|novel|epic}
length_target_words: {number}
series_structure_key: {from project.yaml: standalone|duology|trilogy|series|serial}
series_structure: "{Display Name, e.g., Standalone}"
target_audience_key: {middle_grade|young_adult|new_adult|adult}
target_audience: "{Display Name, e.g., Adult}"
content_rating_key: {clean|mild|moderate|mature|explicit}
content_rating: "{Display Name, e.g., Mature/R}"
# Style taxonomy (keys for tooling)
prose_style_key: {commercial|literary|minimalist|pulp|lyrical|conversational}
prose_style: "{Display Name, e.g., Pulp/Action}"
dialogue_density_key: {high|moderate|low}
dialogue_density: "{Display Name, e.g., High}"
pov_key: {first_person|third_limited|third_multiple|third_omniscient|second_person}
pov: "{Display Name, e.g., First Person}"
tense: {past|present}
# Themes and tone (free-form)
tone: "{free-form description}"
mood: "{free-form description}"
# Genre-specific multi-select fields (examples from fantasy - actual fields vary by genre)
# Magic system uses select_one_or_two → array
magic_system_keys:
  - {key, e.g., hard_magic_system}
  - {optional second key, e.g., elemental_magic}
magic_systems:
  - "{Display Name, e.g., Hard Magic System}"
  - "{optional second, e.g., Elemental Magic}"
# Fantasy races uses select_all_that_apply → array
fantasy_race_keys:
  - {key}
  - {key}
fantasy_races:
  - "{Display Name}"
  - "{Display Name}"
# Themes uses select_up_to_three → array
theme_keys:
  - {key, e.g., power_corruption}
  - {key, e.g., identity_belonging}
themes:
  - "{Display Name, e.g., Power and Corruption}"
  - "{Display Name, e.g., Identity and Belonging}"
# Quest type uses select_primary → scalar (like select_one)
quest_type_key: {key, e.g., political_intrigue}
quest_type: "{Display Name, e.g., Political Intrigue}"
# Other select_one categories as scalars
world_type_key: {key, e.g., secondary_world}
world_type: "{Display Name, e.g., Secondary World}"
worldbuilding_depth_key: {key, e.g., moderate}
worldbuilding_depth: "{Display Name, e.g., Moderate}"
# Tags and custom notes
tags:
  - {tag1}
  - {tag2}
custom_style_notes: "{any specific guidance from user - optional}"
---

# Premise

{Expand the concept into 2-3 paragraphs that capture the essence of the story}

## Core Elements

- **Protagonist:** {Name and key traits - who is the main character?}
- **Antagonist:** {The opposing force - person, society, nature, or self}
- **Central Conflict:** {What the protagonist wants vs what stands in their way}
- **Stakes:** {What happens if they fail?}
- **Hook:** {The unique element that makes this story compelling}

## Setting

{Describe the world/time/place where the story unfolds - 1-2 paragraphs}

## Themes

- {Primary theme}
- {Secondary theme}
- {Optional tertiary theme}

## Tone

- **Tone:** {e.g., Dark and brooding, Light and humorous, Tense and atmospheric}
- **Mood:** {The emotional atmosphere - e.g., Melancholic, Hopeful, Ominous}

## Prose Style

- **Approach:** {Display name from frontmatter, e.g., Pulp/Action}
- **Dialogue density:** {Display name from frontmatter}
- **POV:** {Display name from frontmatter}
- **Tense:** {from frontmatter}
- **Custom notes:** {Any specific style preferences from user - optional}
```

**Important:** The YAML frontmatter stores both taxonomy keys (for tooling/determinism) and display names (for readability). Downstream stages copy this frontmatter, ensuring consistent taxonomy data flows through the pipeline.

**After generation:**
```bash
cd books && git add {project}/01-premise.md && git commit -m "Add: Generate premise for {project}"
```

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
Write `books/{project}/02-02-treatment-approach.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}
**User preferences:** Ending={...}; Structure={... if applicable}; Specific elements={... if any}

**Read only:**
1. `books/{project}/01-01-premise.md`
2. `taxonomies/{genre}-taxonomy.json`

Premise is the authoritative source. Do NOT read any other files.

**Output:** `books/{project}/02-02-treatment-approach.md` (use the Treatment Approach template from this skill)

**Goal:** Analyze the premise and decide the best treatment structure + risks (conflict, arc, antagonist deployment, pacing challenges).

**After:** `cd books && git add {project}/02-treatment-approach.md && git commit -m "Add: Treatment approach for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Treatment

**Spawn after treatment-approach exists.** This generates the full treatment using the approach as guidance.

**Sub-agent prompt template:**

```
Write `books/{project}/03-03-treatment.md` for `{project}`.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}

**Read only:**
1. `books/{project}/02-02-treatment-approach.md` — Planning document with structure decisions
2. `books/{project}/01-01-premise.md` — Original premise for frontmatter values

Do NOT read any other files.

**Output:** `books/{project}/03-03-treatment.md` (use the appropriate Treatment template from this skill)

**Requirements:**
- Follow the decisions in `02-treatment-approach.md` (structure type, act logic, risks).
- Copy frontmatter values from `01-premise.md` (frontmatter is authoritative downstream).
- Include the **Downstream Contract** section from the template.

**After:** `cd books && git add {project}/03-treatment.md && git commit -m "Add: Generate treatment for {project}"`

Generate complete, publication-ready content. Do not ask for approval.
```

### Treatment Templates

#### Treatment Approach Format

```markdown
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
# Copy ALL taxonomy keys and display names from premise frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from premise}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from premise - copy entire object}
subgenres: {from premise - copy entire object}
length_key: {from premise: novella|novel|epic}
length_target_words: {number}
series_structure_key: {from premise}
series_structure: "{from premise}"
target_audience_key: {from premise}
target_audience: "{from premise}"
content_rating_key: {from premise}
content_rating: "{from premise}"
prose_style_key: {from premise}
prose_style: "{from premise}"
dialogue_density_key: {from premise}
dialogue_density: "{from premise}"
pov_key: {from premise}
pov: "{from premise}"
tense: {from premise}
tone: "{from premise}"
mood: "{from premise}"
# Multi-select: copy all genre-specific arrays/objects from premise
# Examples (actual fields depend on genre):
magic_system_keys: {from premise - copy array if present}
magic_systems: {from premise - copy array if present}
fantasy_race_keys: {from premise - copy array if present}
fantasy_races: {from premise - copy array if present}
theme_keys: {from premise - copy array if present}
themes: {from premise - copy array if present}
quest_type_key: {from premise - copy if present}
quest_type: "{from premise - copy if present}"
world_type_key: {from premise - copy if present}
world_type: "{from premise - copy if present}"
worldbuilding_depth_key: {from premise - copy if present}
worldbuilding_depth: "{from premise - copy if present}"
tags:
  - {from premise}
custom_style_notes: "{from premise}"
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
# Copy ALL taxonomy keys and display names from premise frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from premise}
# Multi-select: subgenre (primary/secondary object)
subgenre_keys: {from premise - copy entire object}
subgenres: {from premise - copy entire object}
length_key: {from premise: flash_fiction|short_story|novelette}
length_target_words: {number}
series_structure_key: {from premise}
series_structure: "{from premise}"
target_audience_key: {from premise}
target_audience: "{from premise}"
content_rating_key: {from premise}
content_rating: "{from premise}"
prose_style_key: {from premise}
prose_style: "{from premise}"
dialogue_density_key: {from premise}
dialogue_density: "{from premise}"
pov_key: {from premise}
pov: "{from premise}"
tense: {from premise}
tone: "{from premise}"
mood: "{from premise}"
# Multi-select: copy all genre-specific arrays/objects from premise
# Examples (actual fields depend on genre):
magic_system_keys: {from premise - copy array if present}
magic_systems: {from premise - copy array if present}
fantasy_race_keys: {from premise - copy array if present}
fantasy_races: {from premise - copy array if present}
theme_keys: {from premise - copy array if present}
themes: {from premise - copy array if present}
quest_type_key: {from premise - copy if present}
quest_type: "{from premise - copy if present}"
world_type_key: {from premise - copy if present}
world_type: "{from premise - copy if present}"
worldbuilding_depth_key: {from premise - copy if present}
worldbuilding_depth: "{from premise - copy if present}"
tags:
  - {from premise}
custom_style_notes: "{from premise}"
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

---

## Stage: prose

Generate the actual story prose.

### Orchestration Flow

1. **Check what exists** — structure-plan? short-story-plan/chapter-plans? prose?
2. **Ask clarifying questions** UPFRONT for any missing planning documents
3. **Spawn sub-agents** sequentially for each missing piece:
   - Structure-plan sub-agent (if missing)
   - Short-story-plan sub-agent (if missing, for flash/short/novelette)
   - Chapter-plan sub-agents (if missing, for novella/novel/epic)
   - Prose sub-agent(s)
4. Report completion

### Context Rules

**Context loading:** Each sub-agent reads its immediate predecessor **plus** the continuity anchor (`06-chapters/summaries.md`). For chaptered formats, load all previous chapters for voice and narrative continuity.

| Generating | Sub-agent Reads | Sub-agent Does NOT Read |
|------------|-----------------|-------------------------|
| structure-plan | 03-treatment.md only | 01-premise.md, 02-treatment-approach.md |
| short-story-plan | 04-structure-plan.md only | 01-premise.md, 02-treatment-approach.md, 03-treatment.md |
| chapter-plan (novella/novel/epic) | 04-structure-plan.md + 06-chapters/summaries.md + previous chapter plan (if exists) | 01-premise.md, 02-treatment-approach.md, 03-treatment.md |
| prose (flash/short/novelette) | 05-story-plan.md + prose-style-{prose_style_key}.md | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md |
| prose (novella/novel/epic) | chapter-plan + 06-chapters/summaries.md + all previous chapters + prose-style-{prose_style_key}.md | 01-premise.md, 02-treatment-approach.md, 03-treatment.md, 04-structure-plan.md |

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

**Read only:** `books/{project}/03-03-treatment.md` (treatment is authoritative)

Do NOT read 01-premise.md or any other files.

**Output:** `books/{project}/04-structure-plan.md` (use the appropriate Structure Plan template from this skill)

**Requirements:**
- Copy frontmatter from `03-treatment.md` and include the template’s **Downstream Contract** section.
- Allocate per scene/chapter word targets deliberately (not uniform) and ensure they approximately sum to the overall target.

**After:** `cd books && git add {project}/04-structure-plan.md && git commit -m "Add: Generate structure plan for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Story Plan (Flash/Short/Novelette)

**Spawn when:** `05-story-plan.md` doesn't exist (and structure-plan exists)

**Sub-agent prompt template:**

```
Write `books/{project}/05-story-plan.md` for `{project}`.

**Target word count:** {from structure-plan, e.g., ~14,000 words}

**Read only:** `books/{project}/04-structure-plan.md` (structure-plan is authoritative)

Do NOT read 01-premise.md, 03-treatment.md, or any other files.

**Output:** `books/{project}/05-story-plan.md` (use the Story Plan template from this skill)

**Requirements:**
- Carry forward per-scene word count targets (the prose agent will NOT see structure-plan).
- Include “Development notes” for each scene so the prose can hit the intended depth/length.
- Include the template’s **Downstream Contract** section (this plan is authoritative for prose).

**After:** `cd books && git add {project}/05-story-plan.md && git commit -m "Add: Story plan for {project}"`

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Prose Generation (Flash/Short/Novelette)

**Spawn when:** `06-story.md` doesn't exist (and short-story-plan exists)

**Sub-agent prompt template:**

```
Write complete prose for `{project}`.

**Target word count:** {from story-plan, e.g., ~14,000 words}

**Read only:**
1. `books/{project}/05-story-plan.md` — Complete story plan with scene breakdowns and style notes
2. `misc/prose-style-{prose_style_key}.md` — Style card matching the project's prose style (read `prose_style_key` from frontmatter)

Do NOT read 01-premise.md, 03-treatment.md, 04-structure-plan.md, or any other files.

**Output:** `books/{project}/06-story.md` — Complete prose

**Guidance:** Follow the story plan as the authoritative contract. Use the style card for technique. Keep prose publication-ready.

**Prose format:**
- Start with: # {Story Title}
- Complete story prose follows
- Use: * * * (asterisks with spaces) for scene breaks
- No frontmatter in prose files

**After:** `cd books && git add {project}/06-story.md && git commit -m "Add: Generate prose for {project}"`

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
1. `books/{project}/04-structure-plan.md` — Full structure plan
2. `books/{project}/06-chapters/summaries.md` — If it exists (canon + open threads)
3. `books/{project}/05-chapter-plans/chapter-{PP}-plan.md` — Previous chapter plan (if it exists)

**Do NOT read:** 01-premise.md, 03-treatment.md, or prose files.

**Output:** `books/{project}/05-chapter-plans/chapter-{NN}-plan.md`

**Format:** Use the Chapter Plan template from this skill.

**Requirements:**
- Use `06-chapters/summaries.md` as the source of canon for names/facts/open threads (if it exists).
- Include per-scene word targets and brief development notes (what fills the space: dialogue/interiority/action/description).
- Include a short **Downstream Contract** section stating what the prose must preserve from this plan.

**After:**
Run: `mkdir -p books/{project}/05-chapter-plans`
Then: `cd books && git add {project}/05-chapter-plans/chapter-{NN}-plan.md && git commit -m "Add: Chapter {N} plan for {project}"`

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
1. `books/{project}/05-chapter-plans/chapter-{NN}-plan.md` — This chapter's plan
2. `books/{project}/06-chapters/summaries.md` — Canon Facts + Open Threads (if it exists)
3. All previous chapter prose in `books/{project}/06-chapters/`
4. `misc/prose-style-{prose_style_key}.md` — Style card (read `prose_style_key` from frontmatter)

**Do NOT read:** 01-premise.md, 03-treatment.md, 04-structure-plan.md, or other chapter-plans.

**Output files:**
1. `books/{project}/06-chapters/chapter-{NN}.md` — Chapter prose
2. Update `books/{project}/06-chapters/summaries.md` — Create if missing. **IMPORTANT:** Update BOTH the master Canon Facts section at the top AND add this chapter's summary at the bottom. Do not just append per-chapter data without merging into the master sections.

**Guidance:** Follow the chapter plan as the authoritative contract. Use `06-chapters/summaries.md` Canon Facts as the source of truth for names/facts. Keep prose publication-ready.

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
Run: mkdir -p books/{project}/06-chapters
Then: cd books && git add {project}/06-chapters/chapter-{NN}.md {project}/06-chapters/summaries.md && git commit -m "Add: Generate chapter {N} prose and summary for {project}"

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

Do NOT stop between chapters. Generate the entire book in one `/generate prose` invocation.

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

## Characters

Brief reference for continuity (from treatment):

- **{Protagonist}:** {one-line arc summary: starting state → ending state}
- **{Antagonist/Key character}:** {one-line role summary}
- **{Other key characters}:** {brief notes}

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

This file is the authoritative plan for the story plan.

- **Must preserve downstream:** scene order, required reveals/turns, and scene purposes
- **Downstream changes:** only if the user explicitly requests them (otherwise treat this as the contract)

## Characters

Brief reference for continuity (from treatment):

- **{Protagonist}:** {one-line arc summary: starting state → ending state}
- **{Other key characters}:** {brief role notes}

## Scene Breakdown

### Scene 1: {Title/Description}

**Setting:** {Where and when}
**Word count target:** {estimate}

**Purpose:** {What this scene accomplishes}

**Beat-by-beat:**
1. {Opening beat - how scene starts}
2. {Development - what happens}
3. {Turn/Hook - how scene ends or transitions}

**Character state:** {Where the protagonist is emotionally at scene end}

---

{Repeat for each scene}

## Story Arc Mapping

- **Opening hook:** Scene {X} — {how it grabs the reader}
- **Complication:** Scene {X} — {where tension rises}
- **Climax:** Scene {X} — {the peak moment}
- **Resolution:** Scene {X} — {how it ends}

## Continuity Notes

{Brief notes on any details that must remain consistent across scenes}
```

---

## Chapter/Story Plan Templates

### Chapter Plan Format (Novella/Novel/Epic)

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
---

Copy ALL frontmatter values from structure-plan, including multi-select arrays and objects. Do not modify.

# Chapter {N} Plan: {Title}

## Structure Plan Reference

**From 04-structure-plan.md:**
- Treatment reference: {which act/scenes this covers}
- Summary: {the planned summary}
- Chapter goals: {from structure plan}
- Ends with: {the planned hook/turn}

## Downstream Contract

This plan is authoritative for the prose of Chapter {N}.

- **Prose must preserve:** POV, scene order, key beats/reveals, and the planned hook/turn (unless the user explicitly requests changes)
- **Canon source:** use `06-chapters/summaries.md` as the continuity anchor for names/facts/open threads

## Continuity Check

**Carrying forward from previous chapters:**
- {Open thread 1 - status}
- {Open thread 2 - status}
- {Character emotional state entering this chapter}
- {Key setting/world details established}

**Promises to readers:** {things set up that need payoff}

(For Chapter 1, note "First chapter - establishing baseline" for continuity)

## Character States

### {POV Character}
- **Emotional state:** {where they are mentally/emotionally}
- **Goal this chapter:** {what they want}
- **Internal conflict:** {what's pulling them in different directions}
- **Voice notes:** {how their mental state affects prose voice}

### {Other Key Characters}
- **{Name}:** {state and role this chapter}

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

### Story Plan Format (Flash/Short/Novelette)

```markdown
---
project: {project-name}
stage: story-plan
# Copy ALL taxonomy keys and display names from structure-plan frontmatter
# This includes single-select (scalars), primary/secondary (objects), and multi-select (arrays)
genre_key: {from structure-plan}
# Multi-select: subgenre (primary/secondary object)
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
---

Copy ALL frontmatter values from structure-plan, including multi-select arrays and objects. Do not modify.

# Story Plan: {Title}

## Structure Plan Reference

**From 04-structure-plan.md:**
- Story arc: {the planned arc}
- Scene count: {number of scenes}
- Target word count: {estimate}

## Downstream Contract

This plan is authoritative for the prose in `06-story.md`.

- **Prose must preserve:** scene order, key beats/turns, and style notes (unless the user explicitly requests changes)
- **Canon source:** if `06-chapters/summaries.md` exists, treat it as the continuity anchor for names/facts

## Character States

### {Protagonist}
- **Starting emotional state:** {where they begin}
- **Goal:** {what they want}
- **Internal conflict:** {tension driving them}
- **Voice notes:** {how to render their perspective}

### {Other Characters}
- **{Name}:** {role and function}

## Scene-by-Scene Breakdown

Copy per-scene word count targets from structure-plan. These guide prose generation.

### Scene 1: {Description}
- **Word count target:** {from structure-plan, e.g., ~900 words}
- **Purpose:** {why this scene exists}
- **Conflict/Tension:** {what drives the scene}
- **Key beats:** {1-3 specific moments}
- **Ends with:** {transition or turn}
- **Development notes:** {what will fill the space — e.g., "dialogue exchange + internal monologue + setting details"}

{Repeat for each scene, carrying forward word count targets from structure-plan}

## Style Notes

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

{2-4 sentences analyzing how this story will achieve its word count target — which moments deserve space, what naturally invites expansion, where to resist rushing}

## Potential Pitfalls

- {Thing to avoid}
- {Risk to watch for}
```

---

## Summaries Schema (Chaptered Formats Only)

### 06-chapters/summaries.md

For novella/novel/epic only. Append after each chapter is generated. This provides continuity context for subsequent chapters.

**Note:** Flash/short/novelette formats do not generate summaries.md — the entire story is generated in one pass.

```markdown
---
project: {project-name}
stage: summaries
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
---

Copy ALL frontmatter values from structure-plan, including multi-select arrays and objects. Do not modify.

# Canon Facts (Continuity Anchor)

Update this section after each chapter. Keep it concise, concrete, and canonical (spellings, relationships, rules).

- **Characters:** {names, roles, relationships, signature details}
- **Locations:** {place names, geography, key features}
- **World/System Rules:** {rules that must remain consistent}
- **Timeline:** {relative/absolute time markers}
- **Objects/Terms:** {important items, organizations, jargon}

# Open Threads Ledger

Update this table after each chapter. This is the main "what must be paid off" index downstream agents should rely on.

| Thread | Introduced | Status | Notes |
|--------|------------|--------|-------|
| {Question/setup} | Ch {X} | open/advancing/resolved | {optional: payoff location if resolved} |

# Chapter Summaries

### Chapter 1: {Title}

**Summary:** {3-5 sentences covering key plot events}

**Character States at End:**
- **{Protagonist}:** {emotional/mental state}
- **{Other key characters}:** {state if relevant}

**Threads Updated (this chapter):**
- {Thread introduced/advanced/resolved} — Status: {open/advancing/resolved}

**Canon Facts Added (this chapter):**
- {Names, locations, rules, objects, relationships established (add to Canon Facts above)}

**Promises to Reader:**
- {Setups that need payoff — foreshadowing, questions raised, tensions unresolved}

---

### Chapter 2: {Title}

{Same format — append after each chapter}
```

---

## Context Management Summary

**Context loading:** Each stage reads its immediate predecessor. For chaptered formats, use `06-chapters/summaries.md` as the continuity anchor and load all previous chapters.

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| 02-treatment-approach | 01-premise + taxonomies | — |
| 03-treatment | 02-treatment-approach + 01-premise | — |
| 04-structure-plan | 03-treatment only | 01-premise, 02-treatment-approach |
| chapter-plan (novella/novel/epic) | 04-structure-plan + 06-chapters/summaries.md + previous chapter plan (if exists) | 01-premise, 02-treatment-approach, 03-treatment |
| 05-story-plan (flash/short/novelette) | 04-structure-plan only | 01-premise, 02-treatment-approach, 03-treatment |
| prose (novella/novel/epic) | chapter-plan + 06-chapters/summaries.md + all previous chapters + prose-style-{prose_style_key} | 01-premise, 02-treatment-approach, 03-treatment, 04-structure-plan |
| prose (flash/short/novelette) | 05-story-plan + prose-style-{prose_style_key} | 01-premise, 02-treatment-approach, 03-treatment, 04-structure-plan |

**Path Notes:**
All paths are relative to the repository root:
- Book project files: `books/{project}/`
- Prose style cards: `misc/prose-style-{prose_style_key}.md` (commercial, literary, minimalist, pulp, lyrical, conversational)
- Taxonomies: `taxonomies/`

---

## Frontmatter Requirements

**Every generated stage file MUST begin with valid YAML frontmatter.** This is a strict requirement.

- Frontmatter must be enclosed in `---` delimiters
- All required keys must be present (see templates for each stage)
- Keys must use exact names as specified (e.g., `prose_style_key`, not `style_key`)
- Values must match taxonomy options exactly (no typos, correct case)

**Fail fast:** If a sub-agent generates a file without valid frontmatter, the generation has failed. Report the error and suggest regenerating that stage.

**Validation checklist for frontmatter:**
- [ ] Starts with `---` on first line
- [ ] Ends with `---` before content
- [ ] Contains `project:` matching the project name
- [ ] Contains `stage:` matching the stage type
- [ ] Contains all `*_key` fields with valid taxonomy values
- [ ] Contains corresponding display name fields

## Error Handling

- If a required file is missing, tell the user which stage to generate first
- If project.yaml is missing, prompt to run `/new-book` first
- Never generate placeholder or skeleton content - always generate complete, quality prose
- If a sub-agent fails, report the error and suggest `/iterate` to fix

---

## Multi-Select Frontmatter Reference

Taxonomy files define different selection rules for categories. This reference documents how each rule maps to YAML frontmatter structure.

### Selection Rules and YAML Patterns

| Selection Rule | Key Field | Display Field | YAML Structure |
|---------------|-----------|---------------|----------------|
| `select_one` | `{cat}_key` | `{cat}` | scalar |
| `select_primary` | `{cat}_key` | `{cat}` | scalar |
| `select_primary_and_secondary` | `{cat}_keys` | `{cat}s` | object with `primary`, `secondary?` |
| `select_one_or_two` | `{cat}_keys` | `{cat}s` | array |
| `select_up_to_three` | `{cat}_keys` | `{cat}s` | array |
| `select_all_that_apply` | `{cat}_keys` | `{cat}s` | array |

### Example: select_one (scalar)

```yaml
world_type_key: secondary_world
world_type: "Secondary World"
```

### Example: select_primary_and_secondary (object)

```yaml
subgenre_keys:
  primary: dark_fantasy
  secondary: political_intrigue  # omit if not chosen
subgenres:
  primary: "Dark Fantasy"
  secondary: "Political Intrigue"  # omit if not chosen
```

### Example: select_one_or_two (array)

```yaml
magic_system_keys:
  - hard_magic_system
  - elemental_magic
magic_systems:
  - "Hard Magic System"
  - "Elemental Magic"
```

### Example: select_up_to_three (array)

```yaml
theme_keys:
  - power_corruption
  - identity_belonging
  - destiny_free_will
themes:
  - "Power and Corruption"
  - "Identity and Belonging"
  - "Destiny vs Free Will"
```

### Example: select_all_that_apply (array)

```yaml
fantasy_race_keys:
  - elves
  - dwarves
  - dragons
  - fae_folk
fantasy_races:
  - "Elves"
  - "Dwarves"
  - "Dragons"
  - "Fae/Faeries"
```

### Rules

1. **Single-item arrays stay arrays** — never collapse to scalars
2. **Primary/secondary uses named object** — not array (preserves semantic distinction)
3. **Optional secondary omitted if not chosen** — standard YAML absence
4. **Plural naming for all multi-select** — `_keys` suffix, plural display name
5. **Copy verbatim between stages** — do not modify structure when propagating frontmatter

### Genre-Specific Categories

Different genres have different multi-select categories. Common examples:

**Fantasy:**
- `fantasy_subgenre` → `select_primary_and_secondary`
- `magic_system_type` → `select_one_or_two`
- `fantasy_races` → `select_all_that_apply`
- `fantasy_themes` → `select_up_to_three`
- `quest_type` → `select_primary`
- `world_type` → `select_one`
- `worldbuilding_depth` → `select_one`

**Other genres:** Check the specific genre taxonomy file for the exact selection rules. The premise stage reads the taxonomy and creates the initial frontmatter; all downstream stages copy it verbatim.
