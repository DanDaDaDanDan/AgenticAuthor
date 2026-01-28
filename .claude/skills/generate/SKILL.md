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

Check if the current working directory is inside a book project:
- Look for `project.yaml` in the current directory or parent directories under `books/`
- If not found, ask the user which project to work on

Read `project.yaml` to get project metadata (genre, length, title, author).

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

**Output file:** `premise.md`

**Generation instructions:**

1. Ask the user for a brief concept (1-3 sentences describing the story idea).

2. Ask about target audience:
   > Who is the target audience?
   > 1. Middle Grade (ages 8-12) - age-appropriate themes, no explicit content
   > 2. Young Adult (ages 13-17) - coming-of-age themes, limited mature content
   > 3. New Adult (ages 18-25) - mature themes, identity exploration
   > 4. Adult (ages 18+) - no restrictions, complex narratives

3. Ask about content rating:
   > What content rating fits this story?
   > 1. Clean/All Ages - no profanity, violence, or sexual content
   > 2. Mild/PG - minimal mature content, mild profanity, non-graphic violence
   > 3. Moderate/PG-13 - some mature content, action violence, suggestive content
   > 4. Mature/R - adult content, strong language, violence, sexual content
   > 5. Explicit/NC-17 - graphic adult content, no limits

4. Ask about prose style preference:
   > What prose style fits this story?
   > 1. Commercial/Accessible - clear, readable, mass-market appeal
   > 2. Literary - denser prose, rewards close reading
   > 3. Minimalist - spare, precise, subtext-heavy
   > 4. Pulp/Action - fast, punchy, momentum-driven
   > 5. Lyrical/Atmospheric - poetic, mood-focused, sensory-rich
   > 6. Conversational - strong narrative voice, personality-driven

   Note the genre's `best_for` suggestions in style-taxonomy.json but let the user choose freely.

5. Generate a complete premise document with YAML frontmatter:

```markdown
---
project: {project-name}
stage: premise
# Genre taxonomy (keys for tooling, names for readability)
genre_key: {genre-key from project.yaml}
subgenre_key: {taxonomy key, e.g., social_issue, workplace_drama}
subgenre: "{Display Name, e.g., Social Issue Fiction / Workplace Drama}"
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
prose_pacing_key: {fast|measured|slow-burn}
prose_pacing: "{Display Name, e.g., Fast}"
dialogue_density_key: {high|moderate|low}
dialogue_density: "{Display Name, e.g., High}"
pov_key: {first_person|third_limited|third_multiple|third_omniscient|second_person}
pov: "{Display Name, e.g., First Person}"
tense: {past|present}
# Themes and tone
tone: "{free-form description}"
mood: "{free-form description}"
themes:
  - {primary theme}
  - {secondary theme}
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

- **Approach:** {Display name from frontmatter}
- **Pacing:** {Display name from frontmatter}
- **Dialogue density:** {Display name from frontmatter}
- **POV:** {Display name from frontmatter}
- **Tense:** {from frontmatter}
- **Custom notes:** {Any specific style preferences from user - optional}
```

**Important:** The YAML frontmatter stores both taxonomy keys (for tooling/determinism) and display names (for readability). Downstream stages copy this frontmatter, ensuring consistent taxonomy data flows through the pipeline.

**After generation:**
```bash
cd books && git add {project}/premise.md && git commit -m "Add: Generate premise for {project}"
```

---

## Stage: treatment

Generate the story outline/treatment.

### Orchestration Flow

1. **Read premise** to understand the story (main context)
2. **Ask clarifying questions** about ending, structure, specific elements
3. **Spawn sub-agent** to generate treatment-approach.md (planning document)
4. **Spawn sub-agent** to generate treatment.md (reads treatment-approach for guidance)
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
Generate treatment-approach.md for the {project} project.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}
**User preferences:**
- Ending: {user's choice}
- Structure: {user's choice, if novella/novel/epic}
- Specific elements: {user's input, if any}

**Context to read:**
1. `books/{project}/premise.md` — Full premise
2. `taxonomies/{genre}-taxonomy.json` — Genre structure

**Do NOT read:** Any other files. Premise is the authoritative source.

**Output file:** `books/{project}/treatment-approach.md`

**Format:**
[Include the treatment-approach template from this skill]

**Purpose:**
This document analyzes the premise and plans the treatment structure. Think through:
- How the central conflict drives story structure
- The protagonist's arc (starting state → transformation → ending state)
- How to deploy the antagonist across the narrative
- Which structure type fits best and why
- Potential challenges to navigate

**After generating:**
```bash
cd books && git add {project}/treatment-approach.md && git commit -m "Add: Treatment approach for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Treatment

**Spawn after treatment-approach exists.** This generates the full treatment using the approach as guidance.

**Sub-agent prompt template:**

```
Generate treatment.md for the {project} project.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}

**Context to read:**
1. `books/{project}/treatment-approach.md` — Planning document with structure decisions
2. `books/{project}/premise.md` — Original premise for frontmatter values

**Do NOT read:** Any other files.

**Output file:** `books/{project}/treatment.md`

**Format (novella/novel/epic):**
[Include the Novella/Novel/Epic treatment template from this skill]

**Format (flash/short/novelette):**
[Include the Flash/Short/Novelette treatment template from this skill]

**Guidance:**
Follow the decisions made in treatment-approach.md:
- Use the structure type it selected
- Follow the act overview it outlined
- Address the potential challenges it identified
- Carry forward frontmatter from premise (the frontmatter is authoritative for downstream stages)

**After generating:**
```bash
cd books && git add {project}/treatment.md && git commit -m "Add: Generate treatment for {project}"
```

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

**Prose approach impact:** {How the selected style affects treatment choices}
**Pacing implications:** {How pacing preference shapes scene density}
```

#### Treatment Format (Novella/Novel/Epic)

```markdown
---
project: {project-name}
stage: treatment
# Copy all taxonomy keys and display names from premise frontmatter
genre_key: {from premise}
subgenre_key: {from premise}
subgenre: "{from premise}"
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
prose_pacing_key: {from premise}
prose_pacing: "{from premise}"
dialogue_density_key: {from premise}
dialogue_density: "{from premise}"
pov_key: {from premise}
pov: "{from premise}"
tense: {from premise}
tone: "{from premise}"
mood: "{from premise}"
themes:
  - {from premise}
  - {from premise}
tags:
  - {from premise}
custom_style_notes: "{from premise}"
---

# Treatment

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
# Copy all taxonomy keys and display names from premise frontmatter
genre_key: {from premise}
subgenre_key: {from premise}
subgenre: "{from premise}"
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
prose_pacing_key: {from premise}
prose_pacing: "{from premise}"
dialogue_density_key: {from premise}
dialogue_density: "{from premise}"
pov_key: {from premise}
pov: "{from premise}"
tense: {from premise}
tone: "{from premise}"
mood: "{from premise}"
themes:
  - {from premise}
  - {from premise}
tags:
  - {from premise}
custom_style_notes: "{from premise}"
---

# Treatment

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

**Self-contained stages principle:** Each sub-agent reads ONLY its immediate predecessor.

| Generating | Sub-agent Reads | Sub-agent Does NOT Read |
|------------|-----------------|-------------------------|
| structure-plan | treatment.md only | premise.md, treatment-approach.md |
| short-story-plan | structure-plan.md only | premise.md, treatment-approach.md, treatment.md |
| chapter-plan (novella/novel/epic) | structure-plan.md + summaries.md + prev chapter-plans | premise.md, treatment-approach.md, treatment.md |
| prose (flash/short/novelette) | short-story-plan.md + prose-style-card.md | premise.md, treatment-approach.md, treatment.md, structure-plan.md |
| prose (novella/novel/epic) | chapter-plan + summaries.md + prev chapters + prose-style-card.md | premise.md, treatment-approach.md, treatment.md, structure-plan.md |

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

**Spawn when:** `structure-plan.md` doesn't exist

**Sub-agent prompt template:**

```
Generate structure-plan.md for the {project} project.

**Project type:** {flash_fiction|short_story|novelette|novella|novel|epic}
**User preferences:**
- Target length: {user's choice}
- Chapter/scene structure: {user's choice}

**Context to read:**
1. `books/{project}/treatment.md` — Full treatment with frontmatter

**Do NOT read:** premise.md or any other files. Treatment is the authoritative source.

**Output file:** `books/{project}/structure-plan.md`

**Format:**
[Include appropriate structure-plan template based on project type]

**Word count allocation:**
The overall target is {X} words across {N} scenes/chapters. Before writing the structure-plan, reason through how to allocate this budget:

- Which scenes carry the most narrative weight? (These need more words)
- Which scenes are transitional or momentum-focused? (These can be leaner)
- Where does the story need room to breathe — emotional beats, character development, world-building?
- Where should pacing be tight — action sequences, tension, reveals?

Distribute word counts so they sum to the overall target. A heist scene might need 1,200 words; a quick transition might need 600. The distribution should reflect the story's needs, not be uniform.

**After generating:**
```bash
cd books && git add {project}/structure-plan.md && git commit -m "Add: Generate structure plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Story Plan (Flash/Short/Novelette)

**Spawn when:** `short-story-plan.md` doesn't exist (and structure-plan exists)

**Sub-agent prompt template:**

```
Generate short-story-plan.md for the {project} project.

**Target word count:** {from structure-plan, e.g., ~14,000 words}

**Context to read:**
1. `books/{project}/structure-plan.md` — Full structure plan with scenes and frontmatter

**Do NOT read:** premise.md, treatment.md, or any other files. Structure-plan is self-contained.

**Output file:** `books/{project}/short-story-plan.md`

**Format:**
[Include story plan template]

**Per-scene word counts:**
The structure-plan includes word count targets for each scene. Carry these forward into the story-plan — they guide prose generation. The prose sub-agent won't have access to structure-plan, so the story-plan must be self-contained.

**Planning for length:**
For each scene, think through how the prose will achieve its word count target:

- A 900-word scene might have 3-4 beats with modest development
- A 1,200-word scene needs more: extended dialogue exchanges, deeper interiority, richer sensory detail, or more beats
- Consider what THIS scene specifically offers for development — character moments? tension building? atmosphere? dialogue?

Add a "Development notes" field to each scene in your plan, briefly noting what elements will fill the space (e.g., "Extended dialogue between Dex and Throttle; Dex's internal justification monologue; sensory details of the base").

**After generating:**
```bash
cd books && git add {project}/short-story-plan.md && git commit -m "Add: Story plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Prose Generation (Flash/Short/Novelette)

**Spawn when:** `short-story.md` doesn't exist (and short-story-plan exists)

**Sub-agent prompt template:**

```
Generate complete prose for the {project} novelette/short story.

**Target word count:** {from story-plan, e.g., ~14,000 words}

**Context to read:**
1. `books/{project}/short-story-plan.md` — Complete story plan with scene breakdowns and style notes
2. `misc/prose-style-card.md` — Reference for prose style (use as loose guidance)

**Do NOT read:** premise.md, treatment.md, structure-plan.md, or any other files. The story-plan is self-contained.

**Output files:**
1. `books/{project}/short-story.md` — Complete prose
2. `books/{project}/summaries.md` — Story summary

**Style guidance:**
Follow the frontmatter for core style settings (POV, tense, tone, prose style, content rating). Use the Style Notes section for scene-specific guidance on:
- Pacing (fast/slow/mixed)
- Dialogue vs narration balance
- Sensory focus

**Scene length guidance:**
The story-plan includes per-scene word count targets. Use these as guidance for how much space each scene should occupy. Scenes can run shorter or longer if the prose calls for it, but the targets help ensure proper development — a scene targeted at 1,200 words needs more beats, dialogue, and interiority than one targeted at 600 words.

**Prose format:**
```markdown
# {Story Title}

{Complete story prose}

{Use "* * *" for scene breaks}
```

**Summary format:**
Use the summaries.md (Flash/Short/Novelette) format from the Summaries Schema section below.

**After generating:**
```bash
cd books && git add {project}/short-story.md {project}/summaries.md && git commit -m "Add: Generate prose and summary for {project}"
```

Generate publication-ready prose. Do not ask for approval.
```

---

### Sub-Agent: Chapter Plan (Novella/Novel/Epic)

**Spawn when:** A chapter needs planning (chapter-plan doesn't exist)

**Sub-agent prompt template:**

```
Generate chapter plan for Chapter {N} of {project}.

**Chapter target:** ~{X} words

**Context to read:**
1. `books/{project}/structure-plan.md` — Full structure plan
2. `books/{project}/summaries.md` — If exists, for continuity
3. `books/{project}/chapter-plans/chapter-*.md` — All previous chapter plans

**Do NOT read:** premise.md, treatment.md, or prose files.

**Output file:** `books/{project}/chapter-plans/chapter-{NN}-plan.md`

**Format:**
[Include chapter plan template]

**Planning for length:**
This chapter targets ~{X} words. Think through how the prose will achieve this:

- How many scenes does this chapter contain? How should word count distribute across them?
- Which moments in this chapter need room to breathe — emotional beats, reveals, confrontations?
- Where should pacing be tight — action, transitions, momentum?
- What specific elements will develop each scene — dialogue, interiority, description, tension-building?

Include these considerations in the chapter plan so the prose sub-agent has concrete guidance.

**After generating:**
```bash
mkdir -p books/{project}/chapter-plans
cd books && git add {project}/chapter-plans/chapter-{NN}-plan.md && git commit -m "Add: Chapter {N} plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Chapter Prose (Novella/Novel/Epic)

**Spawn when:** A chapter needs prose (chapter-plan exists but prose doesn't)

**Sub-agent prompt template:**

```
Generate prose for Chapter {N} of {project}.

**Chapter target:** ~{X} words

**Context to read:**
1. `books/{project}/chapter-plans/chapter-{NN}-plan.md` — This chapter's plan
2. `books/{project}/summaries.md` — For continuity
3. `books/{project}/chapters/chapter-*.md` — All previous chapters
4. `misc/prose-style-card.md` — Style reference

**Do NOT read:** premise.md, treatment.md, structure-plan.md, or other chapter-plans.

**Output files:**
1. `books/{project}/chapters/chapter-{NN}.md` — Chapter prose
2. Append to `books/{project}/summaries.md` — Chapter summary

**Style guidance:**
Follow the frontmatter in the chapter-plan for core style settings (POV, tense, tone, prose style, content rating). Use the Style Notes section for chapter-specific guidance on pacing, dialogue balance, and sensory focus.

**Scene length guidance:**
The chapter-plan includes per-scene word count targets and development notes. Use these as guidance for how much space each scene should occupy. Scenes can run shorter or longer if the prose calls for it, but the targets help ensure proper development.

**After generating:**
```bash
mkdir -p books/{project}/chapters
cd books && git add {project}/chapters/chapter-{NN}.md {project}/summaries.md && git commit -m "Add: Generate chapter {N} prose and summary for {project}"
```

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
# Copy all taxonomy keys and display names from treatment frontmatter
genre_key: {from treatment}
subgenre_key: {from treatment}
subgenre: "{from treatment}"
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
prose_pacing_key: {from treatment}
prose_pacing: "{from treatment}"
dialogue_density_key: {from treatment}
dialogue_density: "{from treatment}"
pov_key: {from treatment}
pov: "{from treatment}"
tense: {from treatment}
tone: "{from treatment}"
mood: "{from treatment}"
themes:
  - {from treatment}
  - {from treatment}
tags:
  - {from treatment}
custom_style_notes: "{from treatment}"
---

Copy all frontmatter values from treatment. Do not modify unless user explicitly requested changes.

# Structure Plan

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {Single POV / Multiple POV / Alternating}

Note: Per-chapter word count targets below should approximately sum to the overall target.

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
# Copy all taxonomy keys and display names from treatment frontmatter
genre_key: {from treatment}
subgenre_key: {from treatment}
subgenre: "{from treatment}"
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
prose_pacing_key: {from treatment}
prose_pacing: "{from treatment}"
dialogue_density_key: {from treatment}
dialogue_density: "{from treatment}"
pov_key: {from treatment}
pov: "{from treatment}"
tense: {from treatment}
tone: "{from treatment}"
mood: "{from treatment}"
themes:
  - {from treatment}
  - {from treatment}
tags:
  - {from treatment}
custom_style_notes: "{from treatment}"
---

Copy all frontmatter values from treatment. Do not modify unless user explicitly requested changes.

# Structure Plan

## Overview

- **Target word count:** {estimate}
- **Number of scenes:** {count}
- **POV:** {narrative perspective}
- **Timespan:** {how much time the story covers}

Note: Per-scene word count targets below should approximately sum to the overall target.

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
# Copy all taxonomy keys and display names from structure-plan frontmatter
genre_key: {from structure-plan}
subgenre_key: {from structure-plan}
subgenre: "{from structure-plan}"
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
prose_pacing_key: {from structure-plan}
prose_pacing: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
themes:
  - {from structure-plan}
  - {from structure-plan}
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
---

Copy all frontmatter values from structure-plan. Do not modify.

# Chapter {N} Plan: {Title}

## Structure Plan Reference

**From structure-plan.md:**
- Treatment reference: {which act/scenes this covers}
- Summary: {the planned summary}
- Chapter goals: {from structure plan}
- Ends with: {the planned hook/turn}

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
# Copy all taxonomy keys and display names from structure-plan frontmatter
genre_key: {from structure-plan}
subgenre_key: {from structure-plan}
subgenre: "{from structure-plan}"
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
prose_pacing_key: {from structure-plan}
prose_pacing: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
themes:
  - {from structure-plan}
  - {from structure-plan}
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
---

Copy all frontmatter values from structure-plan. Do not modify.

# Story Plan: {Title}

## Structure Plan Reference

**From structure-plan.md:**
- Story arc: {the planned arc}
- Scene count: {number of scenes}
- Target word count: {estimate}

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

## Summaries Schema

### summaries.md (Novella/Novel/Epic)

Append after each chapter is generated. This provides continuity context for subsequent chapters.

```markdown
---
project: {project-name}
stage: summaries
# Copy all taxonomy keys and display names from structure-plan frontmatter
genre_key: {from structure-plan}
subgenre_key: {from structure-plan}
subgenre: "{from structure-plan}"
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
prose_pacing_key: {from structure-plan}
prose_pacing: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
themes:
  - {from structure-plan}
  - {from structure-plan}
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
---

Copy all frontmatter values from structure-plan. Do not modify.

# Chapter Summaries

### Chapter 1: {Title}

**Summary:** {3-5 sentences covering key plot events}

**Character States at End:**
- **{Protagonist}:** {emotional/mental state}
- **{Other key characters}:** {state if relevant}

**Open Threads:**
- {Thread introduced or advanced} — Status: {open/advancing/resolved}

**Continuity Facts Introduced:**
- {Names, locations, rules, objects, relationships established}

**Promises to Reader:**
- {Setups that need payoff — foreshadowing, questions raised, tensions unresolved}

---

### Chapter 2: {Title}

{Same format — append after each chapter}
```

### summaries.md (Flash/Short/Novelette)

Generated once after prose is complete.

```markdown
---
project: {project-name}
stage: summaries
# Copy all taxonomy keys and display names from structure-plan frontmatter
genre_key: {from structure-plan}
subgenre_key: {from structure-plan}
subgenre: "{from structure-plan}"
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
prose_pacing_key: {from structure-plan}
prose_pacing: "{from structure-plan}"
dialogue_density_key: {from structure-plan}
dialogue_density: "{from structure-plan}"
pov_key: {from structure-plan}
pov: "{from structure-plan}"
tense: {from structure-plan}
tone: "{from structure-plan}"
mood: "{from structure-plan}"
themes:
  - {from structure-plan}
  - {from structure-plan}
tags:
  - {from structure-plan}
custom_style_notes: "{from structure-plan}"
---

Copy all frontmatter values from structure-plan. Do not modify.

# Story Summary

**Summary:** {3-5 sentences covering the complete story arc}

**Key Beats:**
- **Opening:** {1 sentence}
- **Complication:** {1 sentence}
- **Climax:** {1 sentence}
- **Resolution:** {1 sentence}

**Character Arc:**
- **{Protagonist}:** {starting state} → {ending state}

**Themes Delivered:**
- {How primary theme manifested}
- {How secondary theme manifested}
```

---

## Context Management Summary

**Self-contained stages principle:** Each stage reads only the immediately prior stage. This prevents conflicts when earlier stages are iterated.

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| treatment-approach | premise + taxonomies | — |
| treatment | treatment-approach + premise | — |
| structure-plan | treatment only | premise, treatment-approach |
| chapter-plan (novella/novel/epic) | structure-plan + summaries + prev chapter-plans | premise, treatment-approach, treatment |
| short-story-plan (flash/short/novelette) | structure-plan only | premise, treatment-approach, treatment |
| prose (novella/novel/epic) | chapter-plan + summaries + prev chapters + prose-style-card | premise, treatment-approach, treatment, structure-plan |
| prose (flash/short/novelette) | short-story-plan + prose-style-card | premise, treatment-approach, treatment, structure-plan |

**Path Notes:**
All paths are relative to the repository root:
- Book project files: `books/{project}/`
- Prose style card: `misc/prose-style-card.md`
- Taxonomies: `taxonomies/`

---

## Error Handling

- If a required file is missing, tell the user which stage to generate first
- If project.yaml is missing, prompt to run `/new-book` first
- Never generate placeholder or skeleton content - always generate complete, quality prose
- If a sub-agent fails, report the error and suggest `/iterate` to fix
