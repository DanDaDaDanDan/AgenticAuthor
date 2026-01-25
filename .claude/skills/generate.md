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
4. Include 2-3 taxonomy-derived tags in the final premise

**Output file:** `premise.md`

**Generation instructions:**

Ask the user for a brief concept (1-3 sentences describing the story idea).

Then generate a complete premise document:

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

## Tone and Style

- **Tone:** {e.g., Dark and brooding, Light and humorous, Tense and atmospheric}
- **Pacing:** {e.g., Fast-paced thriller, Slow-burn character study}
- **Voice:** {e.g., First person intimate, Third person limited, Multiple POV}

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

### For Novels (length: novel)

Generate a detailed treatment:

```markdown
# Treatment

## Story Overview

{2-3 paragraph summary of the complete story arc}

## Act Structure

### Act I: {Title} (Setup)

{Describe the opening situation, character introductions, inciting incident, and first plot point}

**Key scenes:**
1. {Opening scene description}
2. {Character establishment}
3. {Inciting incident}
4. {First plot point / point of no return}

### Act II: {Title} (Confrontation)

{Describe the rising action, complications, midpoint, and escalating conflict}

**Key scenes:**
1. {First major complication}
2. {Midpoint reversal or revelation}
3. {Protagonist's darkest moment}
4. {Second plot point}

### Act III: {Title} (Resolution)

{Describe the climax, resolution, and ending}

**Key scenes:**
1. {Final approach to climax}
2. {Climax scene}
3. {Resolution and aftermath}
4. {Final image/closing}

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

Generate the chapter structure plan (novels only).

**If project is a short story, skip this stage.**

**Context to read:**
- `books/{project}/premise.md` - Full premise
- `books/{project}/treatment.md` - Full treatment

**Output file:** `books/{project}/structure-plan.md`

**Generation instructions:**

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

**After generation:**
```bash
cd books && git add {project}/structure-plan.md && git commit -m "Add: Generate structure plan for {project}"
```

---

## Stage: prose

Generate the actual story prose.

**Context to read (ALL of these, in full):**
- `books/{project}/premise.md` - Full premise
- `books/{project}/treatment.md` - Full treatment
- `books/{project}/structure-plan.md` - Chapter plan (novels only)
- `AgenticAuthor/misc/prose-style-card.md` - Style guidelines (at repo root)
- All previously generated chapters in `books/{project}/chapters/` directory

### Continuation Logic

Before generating, check what already exists:

1. **For novels:** List files in `books/{project}/chapters/`
2. **For short stories:** Check if `books/{project}/story.md` exists

**If some chapters exist:**
```
Chapters 1-3 already exist.

Options:
1. Generate chapter 4 (continue)
2. Regenerate a specific chapter
3. Regenerate all chapters

Which would you like?
```

**If user specifies a chapter:** `/generate prose 5` → Generate chapter 5

### Output files

- Novels: `chapters/chapter-{NN}.md` (one per chapter)
- Short stories: `story.md` (single file)

### Generation instructions

Read the prose style card carefully and apply all its guidelines.

**For each chapter/story:**

1. Review the full context (premise, treatment, plan, previous chapters)
2. Generate prose that:
   - Follows the style card guidelines (sentence length, dialogue ratio, etc.)
   - Maintains consistency with previous chapters
   - Advances the plot according to the plan
   - Develops characters as outlined
3. Do NOT include chapter planning notes in the output - only the prose itself

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

**Short story format:**

```markdown
# {Story Title}

{Complete story prose}
```

### Quality Self-Check

After generating each chapter, verify:

1. **Dialogue ratio:** Approximately 35-50% in character-heavy scenes
2. **Sentence length:** No sentences over 35 words without rhythmic justification
3. **Scene endings:** Each scene ends with a turn (POISE structure)
4. **Sensory details:** At least 2 per 200 words
5. **POV consistency:** No head-hopping within scenes
6. **Plot advancement:** Chapter accomplishes its stated goals from the plan

If any check fails, revise before committing.

### After generation

**After each chapter (novels):**
```bash
cd books && git add {project}/chapters/chapter-{NN}.md && git commit -m "Add: Generate chapter {N} prose for {project}"
```

**After story.md (short stories):**
```bash
cd books && git add {project}/story.md && git commit -m "Add: Generate prose for {project}"
```

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

For prose generation of chapter N, include:
- `books/{project}/premise.md` (100%)
- `books/{project}/treatment.md` (100%)
- `books/{project}/structure-plan.md` (100%) - novels only
- Chapters 1 through N-1 from `books/{project}/chapters/` (100% of each)
- `AgenticAuthor/misc/prose-style-card.md` (100%) - at repo root

**Path Notes:**
- Book project files are in `books/{project}/`
- The prose style card is at `AgenticAuthor/misc/` (repo root), NOT inside the book project
- Taxonomies are at `AgenticAuthor/taxonomies/` (repo root)

Never truncate or summarize context. If the context is too large, ask the user rather than silently truncating.

## Error Handling

- If a required file is missing, tell the user which stage to generate first
- If project.yaml is missing, prompt to run `/new-book` first
- Never generate placeholder or skeleton content - always generate complete, quality prose
