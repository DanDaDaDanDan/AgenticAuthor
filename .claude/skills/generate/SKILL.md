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

**CRITICAL: Use sub-agents for all generation work.**

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
- **Length:** {novel/novelette/short-story} ({estimated word count})
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

### Orchestration Flow

1. **Read premise** to understand the story (main context)
2. **Ask clarifying questions** about ending, structure, specific elements
3. **Spawn sub-agent** to generate treatment-approach.md
4. **Spawn sub-agent** to generate treatment.md
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

2. **Structure preference:** (novels only)
   > What story structure fits best?
   > 1. Three-act (classic setup/confrontation/resolution)
   > 2. Four-act (extended middle with clear crisis point)
   > 3. Five-act (epic with distinct falling action)
   > 4. Episodic (connected adventures/events)
   > 5. Let me decide based on the premise

3. **Any specific elements?** (optional, free-form)
   > Are there any specific plot points, scenes, or story beats you definitely want included?

### Sub-Agent: Treatment Generation

After collecting user preferences, spawn a single sub-agent to generate both treatment-approach.md and treatment.md.

**Sub-agent prompt template:**

```
Generate treatment documents for the {project} project.

**Project type:** {novel/novelette/short-story}
**User preferences:**
- Ending: {user's choice}
- Structure: {user's choice, if novel}
- Specific elements: {user's input, if any}

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\premise.md` — Full premise
2. `D:\Personal\AgenticAuthor\taxonomies\{genre}-taxonomy.json` — Genre structure

**Do NOT read:** Any other files. Premise is the authoritative source.

**Output files:**
1. `D:\Personal\AgenticAuthor\books\{project}\treatment-approach.md` — Planning document
2. `D:\Personal\AgenticAuthor\books\{project}\treatment.md` — Full treatment

**Treatment-approach format:**
[Include the treatment-approach template from this skill]

**Treatment format (novels):**
[Include the novel treatment template from this skill]

**Treatment format (short stories/novelettes):**
[Include the short story treatment template from this skill]

**After generating:**
```bash
cd /d/Personal/AgenticAuthor/books && git add {project}/treatment-approach.md {project}/treatment.md && git commit -m "Add: Generate treatment for {project}"
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

#### Treatment Format (Novels)

```markdown
# Treatment

## Story Configuration

Carried forward from premise (authoritative for all downstream stages):

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Length:** {novel/novelette/short-story} (~{target word count} words)
- **Genre:** {genre/subgenre from premise}
- **Target Audience:** {demographic}
- **Content Rating:** {rating}
- **Tone:** {emotional quality}
- **Themes:** {primary theme}, {secondary theme}

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

#### Treatment Format (Short Stories/Novelettes)

```markdown
# Treatment

## Story Configuration

Carried forward from premise (authoritative for all downstream stages):

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Length:** {short-story/novelette} (~{target word count} words)
- **Genre:** {genre/subgenre from premise}
- **Target Audience:** {demographic}
- **Content Rating:** {rating}
- **Tone:** {emotional quality}
- **Themes:** {primary theme}, {secondary theme}

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

1. **Check what exists** — structure-plan? story-plan/chapter-plans? prose?
2. **Ask clarifying questions** UPFRONT for any missing planning documents
3. **Spawn sub-agents** sequentially for each missing piece:
   - Structure-plan sub-agent (if missing)
   - Story-plan sub-agent (if missing, for short stories)
   - Chapter-plan sub-agents (if missing, for novels)
   - Prose sub-agent(s)
4. Report completion

### Context Rules (CRITICAL)

**Self-contained stages principle:** Each sub-agent reads ONLY its immediate predecessor.

| Generating | Sub-agent Reads | Sub-agent Does NOT Read |
|------------|-----------------|-------------------------|
| structure-plan | treatment.md only | premise.md |
| story-plan (short) | structure-plan.md only | premise.md, treatment.md |
| chapter-plan (novel) | structure-plan.md + summaries.md + prev chapter-plans | premise.md, treatment.md |
| prose (short) | short-story-plan.md + prose-style-card.md | premise.md, treatment.md, structure-plan.md |
| prose (novel) | chapter-plan + summaries.md + prev chapters + prose-style-card.md | premise.md, treatment.md, structure-plan.md |

### Clarifying Questions

**For Novels — ask BEFORE spawning:**

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

**For Short Stories/Novelettes — ask BEFORE spawning:**

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

**Project type:** {novel/novelette/short-story}
**User preferences:**
- Target length: {user's choice}
- Chapter/scene structure: {user's choice}

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\treatment.md` — Full treatment with Story Configuration

**Do NOT read:** premise.md or any other files. Treatment is the authoritative source.

**Output file:** `D:\Personal\AgenticAuthor\books\{project}\structure-plan.md`

**Format for {novels/short stories}:**
[Include appropriate structure-plan template]

**After generating:**
```bash
cd /d/Personal/AgenticAuthor/books && git add {project}/structure-plan.md && git commit -m "Add: Generate structure plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Story Plan (Short Stories/Novelettes)

**Spawn when:** `short-story-plan.md` doesn't exist (and structure-plan exists)

**Sub-agent prompt template:**

```
Generate short-story-plan.md for the {project} project.

**Target word count:** {from structure-plan, e.g., ~14,000 words}

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\structure-plan.md` — Full structure plan with scenes and style config

**Do NOT read:** premise.md, treatment.md, or any other files. Structure-plan is self-contained.

**Output file:** `D:\Personal\AgenticAuthor\books\{project}\short-story-plan.md`

**Format:**
[Include story plan template]

**CRITICAL — Length Strategy section:**
The structure-plan specifies a target word count. Your Length Strategy must genuinely analyze how each scene will achieve its portion of that target. Do not write generic advice — think specifically about THIS story's scenes and what they need.

**After generating:**
```bash
cd /d/Personal/AgenticAuthor/books && git add {project}/short-story-plan.md && git commit -m "Add: Story plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Prose Generation (Short Stories/Novelettes)

**Spawn when:** `short-story.md` doesn't exist (and story-plan exists)

**Sub-agent prompt template:**

```
Generate complete prose for the {project} novelette/short story.

**Target word count:** {from story-plan, e.g., ~14,000 words}

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\short-story-plan.md` — Complete story plan with scene breakdowns and style notes
2. `D:\Personal\AgenticAuthor\misc\prose-style-card.md` — Reference for prose style (use as loose guidance)

**Do NOT read:** premise.md, treatment.md, structure-plan.md, or any other files. The story-plan is self-contained.

**Output files:**
1. `D:\Personal\AgenticAuthor\books\{project}\short-story.md` — Complete prose
2. `D:\Personal\AgenticAuthor\books\{project}\summaries.md` — Story summary

**Style guidance:**
Follow the Style Notes section in the story-plan. Key elements:
- POV and voice characteristics
- Pacing (fast/slow/mixed)
- Dialogue vs narration balance
- Sensory focus
- Tone

**Prose format:**
```markdown
# {Story Title}

{Complete story prose}

{Use "* * *" for scene breaks}
```

**Summary format:**
```markdown
# Story Summary

{3-5 sentence summary of the complete story}

**Key beats:**
- Opening: {1 sentence}
- Complication: {1 sentence}
- Climax: {1 sentence}
- Resolution: {1 sentence}
```

**After generating:**
```bash
cd /d/Personal/AgenticAuthor/books && git add {project}/short-story.md {project}/summaries.md && git commit -m "Add: Generate prose and summary for {project}"
```

Generate publication-ready prose. Do not ask for approval.
```

---

### Sub-Agent: Chapter Plan (Novels)

**Spawn when:** A chapter needs planning (chapter-plan doesn't exist)

**Sub-agent prompt template:**

```
Generate chapter plan for Chapter {N} of {project}.

**Chapter target:** ~{X} words

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\structure-plan.md` — Full structure plan
2. `D:\Personal\AgenticAuthor\books\{project}\summaries.md` — If exists, for continuity
3. `D:\Personal\AgenticAuthor\books\{project}\chapter-plans\chapter-*.md` — All previous chapter plans

**Do NOT read:** premise.md, treatment.md, or prose files.

**Output file:** `D:\Personal\AgenticAuthor\books\{project}\chapter-plans\chapter-{NN}-plan.md`

**Format:**
[Include chapter plan template]

**After generating:**
```bash
mkdir -p /d/Personal/AgenticAuthor/books/{project}/chapter-plans
cd /d/Personal/AgenticAuthor/books && git add {project}/chapter-plans/chapter-{NN}-plan.md && git commit -m "Add: Chapter {N} plan for {project}"
```

Generate complete content. Do not ask for approval.
```

---

### Sub-Agent: Chapter Prose (Novels)

**Spawn when:** A chapter needs prose (chapter-plan exists but prose doesn't)

**Sub-agent prompt template:**

```
Generate prose for Chapter {N} of {project}.

**Chapter target:** ~{X} words

**Context to read:**
1. `D:\Personal\AgenticAuthor\books\{project}\chapter-plans\chapter-{NN}-plan.md` — This chapter's plan
2. `D:\Personal\AgenticAuthor\books\{project}\summaries.md` — For continuity
3. `D:\Personal\AgenticAuthor\books\{project}\chapters\chapter-*.md` — All previous chapters
4. `D:\Personal\AgenticAuthor\misc\prose-style-card.md` — Style reference

**Do NOT read:** premise.md, treatment.md, structure-plan.md, or other chapter-plans.

**Output files:**
1. `D:\Personal\AgenticAuthor\books\{project}\chapters\chapter-{NN}.md` — Chapter prose
2. Append to `D:\Personal\AgenticAuthor\books\{project}\summaries.md` — Chapter summary

**After generating:**
```bash
mkdir -p /d/Personal/AgenticAuthor/books/{project}/chapters
cd /d/Personal/AgenticAuthor/books && git add {project}/chapters/chapter-{NN}.md {project}/summaries.md && git commit -m "Add: Generate chapter {N} prose and summary for {project}"
```

Generate publication-ready prose. Do not ask for approval.
```

---

### Novel Generation Loop

For novels, after structure-plan exists, loop through all chapters:

```
For chapter 1 to N:
  1. Check if chapter-plan exists → if not, spawn chapter-plan sub-agent
  2. Check if chapter prose exists → if not, spawn chapter-prose sub-agent
  3. Continue to next chapter

Report: "Novel complete. {N} chapters, ~{total} words."
```

Do NOT stop between chapters. Generate the entire novel in one `/generate prose` invocation.

---

## Structure Plan Templates

### Structure Plan Format (Novels)

```markdown
# Structure Plan

## Story Configuration

Carried forward from treatment:

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Tone:** {emotional quality}
- **Content Rating:** {rating}

## Overview

- **Total chapters:** {number}
- **Estimated word count:** {total}
- **POV structure:** {Single POV / Multiple POV / Alternating}

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

### Structure Plan Format (Short Stories/Novelettes)

```markdown
# Structure Plan

## Story Configuration

Carried forward from treatment:

- **Prose Style:** {approach} — {pacing}, {dialogue density}
- **POV:** {narrative perspective}
- **Tone:** {emotional quality}
- **Content Rating:** {rating}

## Overview

- **Target word count:** {estimate}
- **Number of scenes:** {count}
- **POV:** {narrative perspective}
- **Timespan:** {how much time the story covers}

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

### Chapter Plan Format (Novels)

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

## Length Strategy

Think through how this chapter will achieve its target word count (~{X} words). Consider:
- How do the scenes in this chapter relate to the target length?
- Which moments deserve room to breathe?
- What aspects naturally invite expansion?
- Where might you be tempted to rush?

{Write 2-4 sentences of genuine analysis about how this specific chapter will achieve its length target.}

## Potential Pitfalls

- {Thing to avoid or be careful about}
- {Continuity risk}
```

### Story Plan Format (Short Stories/Novelettes)

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
- **Word count target:** {estimate}

{Repeat for each scene from structure-plan.md}

## Style Notes

- **Pacing:** {overall rhythm}
- **Tone:** {emotional quality}
- **Dialogue vs narration:** {balance}
- **Sensory focus:** {what senses to emphasize}

## Length Strategy

Think through how this story will achieve its target word count (~{X} words). Consider:
- How does the scene count relate to the target length?
- Which moments deserve room to breathe?
- What aspects naturally invite expansion?
- Where might you be tempted to rush?

{Write 2-4 sentences of genuine analysis about how this specific story will achieve its length target.}

## Potential Pitfalls

- {Thing to avoid}
- {Risk to watch for}
```

---

## Context Management Summary

**Self-contained stages principle:** Each stage reads only the immediately prior stage. This prevents conflicts when earlier stages are iterated.

| Generating | Reads | Does NOT Read |
|------------|-------|---------------|
| treatment | premise + taxonomies | — |
| structure-plan | treatment only | premise |
| chapter-plan | structure-plan + summaries + prev chapter-plans | premise, treatment |
| story-plan | structure-plan only | premise, treatment |
| prose (novel) | chapter-plan + summaries + prev chapters | premise, treatment, structure-plan |
| prose (short) | story-plan only | premise, treatment, structure-plan |

**Path Notes:**
- Book project files are in `books/{project}/`
- The prose style card is at `AgenticAuthor/misc/` (repo root), NOT inside the book project
- Taxonomies are at `AgenticAuthor/taxonomies/` (repo root)

---

## Error Handling

- If a required file is missing, tell the user which stage to generate first
- If project.yaml is missing, prompt to run `/new-book` first
- Never generate placeholder or skeleton content - always generate complete, quality prose
- If a sub-agent fails, report the error and suggest `/iterate` to fix
