# Skill: /generate

Generate content at any stage of the book creation process.

## Usage

```
/generate [stage]
```

## Arguments

- `stage`: One of `premise`, `treatment`, `plan`, `prose`, or `all`

## Instructions

### Step 0: Detect Current Project

Check if the current working directory is inside a book project:
- Look for `project.yaml` in the current directory or parent directories under `books/`
- If not found, ask the user which project to work on

Read `project.yaml` to get project metadata (genre, length, title, author).

---

## Stage: premise

Generate the core concept and story foundation.

**Context to read:**
- `AgenticAuthor/taxonomies/base-taxonomy.json` - Universal story properties
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json` - Genre-specific options
- `AgenticAuthor/taxonomies/style-taxonomy.json` - Prose style options

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
3. Check base-taxonomy for `target_audience`, `content_rating`, and `pacing` options
4. Review style-taxonomy for prose style options appropriate to the genre
5. Include 2-3 taxonomy-derived tags in the final premise

**Output file:** `premise.md`

**Generation instructions:**

1. Ask the user for a brief concept (1-3 sentences describing the story idea).

2. Ask about prose style preference:
   > What prose style fits this story?
   > 1. Commercial/Accessible - clear, readable, mass-market appeal
   > 2. Literary - denser prose, rewards close reading
   > 3. Minimalist - spare, precise, subtext-heavy
   > 4. Pulp/Action - fast, punchy, momentum-driven
   > 5. Lyrical/Atmospheric - poetic, mood-focused, sensory-rich
   > 6. Conversational - strong narrative voice, personality-driven

   Note the genre's `best_for` suggestions in style-taxonomy.json but let the user choose freely.

3. Generate a complete premise document:

```markdown
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

- **Approach:** {Commercial/Literary/Minimalist/Pulp/Lyrical/Conversational}
- **Pacing:** {Fast/Measured/Slow-burn}
- **Dialogue density:** {High/Moderate/Low}
- **POV:** {First person, Third limited, Third omniscient, Multiple POV}
- **Custom notes:** {Any specific style preferences from user - optional}

## Taxonomy Selections

- **Subgenre:** {Selected from taxonomy}
- **Length:** {novel/short-story} ({estimated word count})
- **Target Audience:** {e.g., Adult, Young Adult}
- **Content Rating:** {from base-taxonomy}
- **Tags:** {2-3 relevant tags from taxonomy}
```

**After generation:**
```bash
cd books && git add {project}/premise.md && git commit -m "Add: Generate premise for {project}"
```

---

## Stage: treatment

Generate the story outline/treatment.

**Context to read:**
- `books/{project}/premise.md` - Full premise document
- `AgenticAuthor/taxonomies/{genre}-taxonomy.json` - For genre-specific structure

**Output file:** `treatment.md`

**Check project length:** Read `length` from project.yaml.

### Before generating, ask clarifying questions:

After reading the premise, ask the user about key story decisions:

1. **Ending direction:**
   > How should this story end?
   > 1. Triumphant - protagonist achieves their goal
   > 2. Bittersweet - victory with significant cost
   > 3. Tragic - protagonist fails or is destroyed
   > 4. Ambiguous - open to interpretation
   > 5. Let me decide based on the premise

2. **Structure preference:** (novels only)
   > What story structure fits best?
   > 1. Three-act (classic setup/confrontation/resolution)
   > 2. Four-act (extended middle with clear crisis point)
   > 3. Five-act (epic with distinct falling action)
   > 4. Episodic (connected adventures/events)
   > 5. Let me decide based on the premise

3. **Any specific elements?** (optional, free-form)
   > Are there any specific plot points, scenes, or story beats you definitely want included?

Use the answers to guide the treatment. If the user says "let me decide," make appropriate choices based on genre and premise.

---

### For Novels (length: novel)

Generate a detailed treatment using the structure the user selected (or chose based on premise):

**Common structures:**
- **Three-act** (Setup/Confrontation/Resolution) - most commercial fiction
- **Four-act** (Setup/Complication/Crisis/Resolution) - longer novels
- **Five-act** (Exposition/Rising Action/Climax/Falling Action/Denouement) - epic or literary
- **Episodic** - connected adventures or vignettes
- **Non-linear** - if the premise suggests it

Default to three-act for most stories, but adapt based on genre and premise.

```markdown
# Treatment

## Story Overview

{2-3 paragraph summary of the complete story arc}

## Act Structure

{Use the structure that best fits the story. The three-act example below is a starting point, not a requirement.}

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

### For Short Stories (length: short-story)

Generate a simplified treatment:

```markdown
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

**After generation:**
```bash
cd books && git add {project}/treatment.md && git commit -m "Add: Generate treatment for {project}"
```

---

## Stage: plan

Generate the structure plan. **Planning is required for ALL projects** — novels get chapter-by-chapter plans, short stories get scene-by-scene plans.

Research shows that explicit planning before prose generation significantly improves quality, even for short-form content (Gurung & Lapata, 2025).

**Context to read:**
- `books/{project}/premise.md` - Full premise
- `books/{project}/treatment.md` - Full treatment

**Output file:** `books/{project}/structure-plan.md`

---

### For Novels

#### Before generating, ask clarifying questions:

After reading the premise and treatment, ask:

1. **Target length:**
   > How long should this novel be?
   > 1. Compact (15-20 chapters, ~50,000 words)
   > 2. Standard (20-30 chapters, ~80,000 words)
   > 3. Epic (30-40+ chapters, ~120,000+ words)
   > 4. Let me decide based on the treatment

2. **Chapter length preference:**
   > What chapter length feels right?
   > 1. Short and punchy (2,000-3,000 words) - quick reads, frequent hooks
   > 2. Standard (3,000-4,500 words) - balanced pacing
   > 3. Long and immersive (4,500-6,000+ words) - deep scenes
   > 4. Variable - mix based on content

3. **POV structure:** (if not already clear from premise)
   > How should POV be handled?
   > 1. Single POV throughout
   > 2. Multiple POV - alternating chapters
   > 3. Multiple POV - within chapters
   > 4. Already specified in premise

Use answers to guide chapter count, length targets, and POV assignments.

#### Generation instructions (Novels):

Generate a detailed chapter-by-chapter plan. Reference treatment scenes in chapter breakdowns.

```markdown
# Structure Plan

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {Single POV / Multiple POV / Alternating}

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

### Chapter 2: {Title}

{Repeat structure for each chapter}

---

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

---

### For Short Stories

Short stories also require a structure plan, but in a lighter format focused on scenes rather than chapters.

#### Before generating, ask clarifying questions:

1. **Target length:**
   > How long should this story be?
   > 1. Flash fiction (under 1,500 words)
   > 2. Short-short (1,500-3,000 words)
   > 3. Standard short (3,000-7,500 words)
   > 4. Long short story (7,500-15,000 words)
   > 5. Let me decide based on the treatment

2. **Scene structure:**
   > How should the story flow?
   > 1. Single continuous scene
   > 2. 2-3 scenes with clear breaks
   > 3. Multiple short scenes
   > 4. Let me decide based on the treatment

#### Generation instructions (Short Stories):

Generate a scene-by-scene plan. Even short stories benefit from explicit planning.

```markdown
# Structure Plan

## Overview

- **Target word count:** {estimate}
- **Number of scenes:** {count}
- **POV:** {narrative perspective}
- **Timespan:** {how much time the story covers}

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

### Scene 2: {Title/Description}

{Repeat structure for each scene}

---

## Story Arc Mapping

- **Opening hook:** Scene {X} — {how it grabs the reader}
- **Complication:** Scene {X} — {where tension rises}
- **Climax:** Scene {X} — {the peak moment}
- **Resolution:** Scene {X} — {how it ends}

## Continuity Notes

{Brief notes on any details that must remain consistent across scenes}
```

---

**After generation (all project types):**
```bash
cd books && git add {project}/structure-plan.md && git commit -m "Add: Generate structure plan for {project}"
```

---

## Stage: prose

Generate the actual story prose.

**Context to read (ALL of these, in full):**
- `books/{project}/premise.md` - Full premise (includes prose style selections)
- `books/{project}/treatment.md` - Full treatment
- `books/{project}/structure-plan.md` - Scene/chapter plan (required for all project types)
- `books/{project}/summaries.md` - Chapter/scene summaries (if exists, for quick reference)
- `books/{project}/chapter-plans/` - All previous chapter plans (novels)
- All previously generated chapters in `books/{project}/chapters/` directory (novels)
- `AgenticAuthor/misc/prose-style-card.md` - Optional detailed reference (only if premise uses "Commercial" style or you need specific guidance)

### Continuation Logic

Before generating, check what already exists:

1. **For novels:** List files in `books/{project}/chapters/` and `books/{project}/chapter-plans/`
2. **For short stories:** Check if `books/{project}/short-story-plan.md` and `books/{project}/short-story.md` exist

**If some chapters exist (novels):**
```
Chapters 1-3 already exist (with plans).
Chapter 4 plan exists but no prose yet.

Options:
1. Generate chapter 4 prose (plan exists)
2. Generate chapter 5 (plan + prose)
3. Regenerate a specific chapter
4. Regenerate all chapters

Which would you like?
```

**If short story plan exists but no prose (short stories):**
```
Story plan exists. Ready to generate prose.

Options:
1. Generate prose from existing plan
2. Regenerate plan first
```

**If user specifies a chapter:** `/generate prose 5` → Generate chapter 5 (plan first, then prose)

### Output files

- **Novels:**
  - Plans: `chapter-plans/chapter-{NN}-plan.md` (one per chapter)
  - Prose: `chapters/chapter-{NN}.md` (one per chapter)
- **Short stories:**
  - Plan: `short-story-plan.md`
  - Prose: `short-story.md`

### Generation instructions

**Use the premise's Prose Style section as your primary guide.** The style selections there (approach, pacing, dialogue density, POV, custom notes) define how this story should be written.

**Style approach meanings:**
- **Commercial** - Clear, readable, efficient. Reference `misc/prose-style-card.md` for detailed guidance.
- **Literary** - Denser prose, longer sentences welcome, thematic resonance, deep interiority
- **Minimalist** - Spare and precise, short declarative sentences, subtext-heavy, Hemingway-esque
- **Pulp** - Fast and punchy, action verbs, short paragraphs, momentum over contemplation
- **Lyrical** - Poetic and atmospheric, flowing sentences, rich sensory detail, mood-focused
- **Conversational** - Strong narrative voice, personality in syntax, feels like being told a story

**For each chapter/story:**

#### Step 1: Generate Chapter/Story Plan (REQUIRED)

Before writing prose, generate an external plan document. This is saved to a file and can be reviewed/iterated before prose generation. Research shows explicit planning significantly improves long-form content quality.

**Plan file location:**
- Novels: `books/{project}/chapter-plans/chapter-{NN}-plan.md`
- Short stories: `books/{project}/short-story-plan.md`

**Plan format for NOVELS:**

```markdown
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

### Scene 1: {Description}
- **Purpose:** {why this scene exists}
- **Conflict/Tension:** {what drives the scene}
- **Key beats:** {1-3 specific moments}
- **Ends with:** {transition to next scene}

### Scene 2: {Description}
{Repeat for each scene}

## Style Notes

- **Pacing:** {fast/slow/mixed for this chapter}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance for this chapter}
- **Sensory focus:** {what senses to emphasize}

## Potential Pitfalls

- {Thing to avoid or be careful about}
- {Continuity risk}
```

**Plan format for SHORT STORIES:**

```markdown
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

### Scene 1: {Description}
- **Purpose:** {why this scene exists}
- **Conflict/Tension:** {what drives the scene}
- **Key beats:** {1-3 specific moments}
- **Ends with:** {transition or turn}

{Repeat for each scene from structure-plan.md}

## Style Notes

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Potential Pitfalls

- {Thing to avoid}
- {Risk to watch for}
```

**After generating plan:**

For novels (create directory if first chapter):
```bash
mkdir -p books/{project}/chapter-plans
cd books && git add {project}/chapter-plans/chapter-{NN}-plan.md && git commit -m "Add: Chapter {N} plan for {project}"
```

For short stories:
```bash
cd books && git add {project}/short-story-plan.md && git commit -m "Add: Story plan for {project}"
```

**Present plan to user for review.** Wait for approval or iteration requests before proceeding to prose.

---

#### Step 2: Generate Prose

After the plan is approved, generate prose that:
- Follows the chapter plan's scene breakdown
- Matches the premise's style approach and pacing
- Respects dialogue density preference (High/Moderate/Low)
- Maintains POV discipline as specified
- Honors any custom style notes from the user
- Maintains consistency with previous chapters
- Advances the plot according to the structure plan

The chapter plan guides generation but prose can deviate if better ideas emerge — note significant deviations.

**Word count approach:**
- Chapter targets in structure-plan are guidelines, not strict limits
- Focus on completing scenes properly
- If significantly over/under target (±30%), note it after generation
- Quality and completeness over hitting exact numbers

**Chapter format:**

```markdown
# Chapter {N}: {Title}

{Prose content - scenes flow naturally without explicit scene breaks unless dramatically appropriate}

{Use "* * *" for scene breaks when needed}

{Continue prose...}
```

**Short story format** (saved to `short-story.md`):

```markdown
# {Story Title}

{Complete story prose}
```

### Quality Considerations

After generating, consider these guidelines (not rigid requirements):

1. **Dialogue balance:** Appropriate for the scene type? (More in confrontations, less in introspection)
2. **Sentence variety:** Good mix of lengths? Any that lose the reader?
3. **Scene momentum:** Does each scene end with forward energy? (Quiet scenes may end softly)
4. **Sensory grounding:** Can the reader see/hear/feel the scene?
5. **POV discipline:** Staying in one head per scene?
6. **Plot advancement:** Chapter accomplishes its stated goals from the plan

**Deviation is allowed.** Literary fiction, atmospheric scenes, and distinctive authorial voices may warrant different approaches than the style card suggests. The guidelines serve the story, not the other way around.

If something feels wrong, revise. If deliberate choices deviate from guidelines, that's fine.

### After generation: Chapter Summary (REQUIRED)

After generating each chapter (or the complete story for short stories), immediately generate a summary and append it to `summaries.md`.

**Purpose:** Summaries provide compressed context for later chapters. The paper "Learning to Reason for Long-Form Story Generation" (Gurung & Lapata, 2025) shows that having both full chapters AND compressed summaries improves generation quality.

**For novels — after each chapter:**

1. Generate a 2-4 sentence summary capturing:
   - Key plot events
   - Character developments/emotional shifts
   - Any important reveals or changes
   - How it connects to the overall arc

2. For the **first chapter**, create `books/{project}/summaries.md` with header:

```markdown
# Chapter Summaries

### Chapter 1: {Title}

{2-4 sentence summary}

**Key events:** {bullet list of 2-3 major events}
**Character states:** {brief note on where main characters end emotionally}

---
```

   For **subsequent chapters**, append to existing `summaries.md`:

```markdown
### Chapter {N}: {Title}

{2-4 sentence summary}

**Key events:** {bullet list of 2-3 major events}
**Character states:** {brief note on where main characters end emotionally}

---
```

3. Git commit both files together:
```bash
cd books && git add {project}/chapters/chapter-{NN}.md {project}/summaries.md && git commit -m "Add: Generate chapter {N} prose and summary for {project}"
```

**For short stories — after short-story.md:**

1. Generate a brief summary capturing the complete arc
2. Create `books/{project}/summaries.md`:

```markdown
# Story Summary

{3-5 sentence summary of the complete story}

**Key beats:**
- Opening: {1 sentence}
- Complication: {1 sentence}
- Climax: {1 sentence}
- Resolution: {1 sentence}
```

3. Git commit (include plan file if not already committed):
```bash
cd books && git add {project}/short-story-plan.md {project}/short-story.md {project}/summaries.md && git commit -m "Add: Generate prose and summary for {project}"
```

**Using summaries and plans during generation:**

When generating chapter N, read:
- Full context (premise, treatment, structure-plan) — 100%
- `summaries.md` — 100% (quick reference)
- `chapter-plans/` — all previous chapter plans (shows reasoning)
- All previous chapters — 100% (authoritative detail)

The summaries and chapter plans help with continuity; full chapters remain the source of truth for prose.

---

## Stage: all

Generate all stages in sequence: premise → treatment → plan → prose

For each stage:
1. Check if it already exists
2. If exists, ask user if they want to regenerate
3. If not exists or user confirms, generate it
4. Wait for user to review before proceeding to next stage

---

## Context Management

**CRITICAL:** Always include full context from previous stages. Token cost is negligible compared to quality loss from missing context.

For prose generation, include:
- `books/{project}/premise.md` (100%)
- `books/{project}/treatment.md` (100%)
- `books/{project}/structure-plan.md` (100%) - all project types
- `books/{project}/summaries.md` (100%) - if exists, quick reference
- `books/{project}/chapter-plans/` (100%) - all chapter plans (novels)
- `books/{project}/short-story-plan.md` (100%) - story plan (short stories)
- Previous prose: chapters 1 through N-1 (novels) or n/a (short stories)
- `AgenticAuthor/misc/prose-style-card.md` (100%) - at repo root, for Commercial style

**Path Notes:**
- Book project files are in `books/{project}/`
- The prose style card is at `AgenticAuthor/misc/` (repo root), NOT inside the book project
- Taxonomies are at `AgenticAuthor/taxonomies/` (repo root)

Never truncate or summarize context. If the context is too large, ask the user rather than silently truncating.

## Error Handling

- If a required file is missing, tell the user which stage to generate first
- If project.yaml is missing, prompt to run `/new-book` first
- Never generate placeholder or skeleton content - always generate complete, quality prose
