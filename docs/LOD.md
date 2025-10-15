# Level of Detail (LOD) Story Generation System

This document provides a comprehensive overview of the multi-level story generation pipeline that transforms high-level premises into complete, professionally edited books.

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [LOD Hierarchy](#lod-hierarchy)
3. [Generation Pipeline](#generation-pipeline)
4. [Detailed Prompt Documentation](#detailed-prompt-documentation)
5. [Taxonomy Integration](#taxonomy-integration)
6. [Iteration and Enhancement](#iteration-and-enhancement)

## System Architecture Overview

The story generation system uses a progressive refinement approach, starting from abstract concepts (LOD3) and progressively adding detail until reaching full prose (LOD0). Each level serves as the foundation for the next, ensuring consistency while allowing creative expansion.

### Core Principles
- **Progressive Elaboration**: Each level adds detail while preserving the essence of previous levels
- **Structural Integrity**: Earlier decisions constrain later choices to maintain coherence
- **Creative Freedom Within Constraints**: The system provides structure while allowing artistic interpretation
- **Genre-Aware Generation**: All prompts adapt to the selected genre and taxonomy
- **Unified Context Architecture**: Files stay separate on disk, but LLM sees/edits unified YAML for consistency

### Unified LOD Context System

**Critical Architecture** - The system maintains separate files on disk for human readability, but presents a unified YAML context to the LLM for consistent generation and iteration.

#### File Storage (On Disk)
```
project/
├── premise_metadata.json   # LOD3 - Core concept + taxonomy selections
├── treatment.md            # LOD2 - Narrative arc
├── chapters.yaml           # LOD2 - Chapter outlines
└── prose/                  # LOD0 - Full prose
    ├── chapter-01.md
    ├── chapter-02.md
    └── ...
```

**Note:** Old projects may have `premise.md` for backward compatibility, but new projects use only `premise_metadata.json` as single source of truth.

#### LLM View (Unified YAML)
```yaml
premise:
  text: |
    [Premise content from premise_metadata.json]
  metadata:
    protagonist: "..."
    antagonist: "..."
    # ... from premise_metadata.json

treatment:
  text: |
    [Treatment content from treatment.md]

chapters:
  - number: 1
    title: "..."
    summary: "..."
    key_events: [...]
    # ... from chapters.yaml

prose:
  - chapter: 1
    text: |
      [Content from prose/chapter-01.md]
  - chapter: 2
    text: |
      [Content from prose/chapter-02.md]
```

#### Key Benefits

1. **Atomic Upward Sync**: When iterating chapters/prose, the LLM can update premise/treatment in the same operation
2. **Automatic Culling**: When upstream LODs change, downstream content is automatically deleted to maintain consistency
3. **Complete Context**: LLM always sees the full story context, ensuring better coherence
4. **Human-Readable Storage**: Separate markdown files remain easy to read and version control
5. **Validation**: System ensures LLM returns all required sections in correct YAML structure

#### Generation Flow

1. **Build Context**: LODContextBuilder assembles files into unified YAML
2. **Generate**: LLM receives YAML context, generates response in YAML format
3. **Parse**: LODResponseParser validates and splits YAML back to individual files
4. **Cull**: Downstream files deleted if upstream LODs were modified
5. **Save**: Each section saved to its corresponding file

#### Culling Rules

- Modify **premise** → Delete: treatment, chapters, prose
- Modify **treatment** → Delete: chapters, prose (keep premise)
- Modify **chapters** → Delete: prose for changed chapters only
- Modify **prose** → No culling (most detailed LOD)

## LOD Hierarchy

### LOD3: Premise & Taxonomy (Highest Abstraction)
- **Purpose**: Define the core concept and story parameters
- **Content**: 2-3 sentence premise + taxonomy selections (genre, themes, tropes, etc.)
- **Word Count**: 50-100 words
- **Function**: Seeds all subsequent generation

### LOD2: Story Treatment & Chapter Outlines (Structural Detail)
- **Story Treatment**: Professional synopsis with complete narrative arc
  - Word Count: 500-3000 words (dynamically scaled)
  - Format: Present tense, narrative distance
- **Chapter Outlines**: Beat sheets for each chapter
  - Structure: 7-10 beats per chapter
  - Format: Structural waypoints, not prose

### LOD1: Chapter Summaries (Bridge Level - Not Currently Used)
- *Note: The system currently jumps from LOD2 directly to LOD0*

### LOD0: Full Prose (Complete Detail)
- **Raw Book**: Complete prose for all chapters
  - Word Count: Varies by format (1,500-150,000+ words)
  - Style: Author voice, full sensory detail
- **Edited Book**: Professionally copy-edited version
  - Format: XHTML for e-reader compatibility
  - Enhancement: Grammar, pacing, engagement optimization

## Generation Pipeline

### Step 1: Premise Generation (LOD3)

For user-provided premises, the system analyzes and potentially expands them. For AI generation:

#### Bulk Premise Generation Prompt
```
Generate [X] unique and diverse fiction premises optimized for mass market appeal, with taxonomy selections that match each premise.

[If exploration pattern provided]:
EXPLORATION PATTERN: [User's variation guidance]
Your premises should follow this pattern, varying the elements as specified while maintaining consistency where indicated.

[If previous generations exist]:
PREVIOUS GENERATIONS IN THIS SESSION:
[List of previous premises with key elements]
IMPORTANT: Avoid duplicating these exact premises. Create fresh, unique premises that explore different creative territory.

[If specific genre]:
GENRE CONTEXT: You are generating for the [GENRE] genre. Ensure all selections are appropriate for this genre.

AVAILABLE OPTIONS BY CATEGORY (use these exact keys):
[Dynamic list of all taxonomy categories and their options]

REQUIREMENTS:
1. Each premise should be 2-3 sentences long
2. The premises should be compelling, market-ready, and suitable for fiction
3. For each premise, choose taxonomy values that align with and support that specific story's content, themes, and tone
4. YOU MUST SELECT AT LEAST ONE VALUE FROM EACH OF THE [X] CATEGORIES
5. [Length specification: fixed or varied]
6. Include 4-6 descriptive tags for easy filtering and discovery
7. Every single category must have a selection - no category should be left empty
8. BE CREATIVE: Explore unexplored combinations, avoid repeating previous concepts

Return a JSON array with exactly [X] objects:
[
  {
    "premise": "Your 2-3 sentence premise here",
    "taxonomySelections": {
      [category]: ["value 1", "value 2"],
      ...
    },
    "keyTags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
  }
]
```

### Step 2: Story Treatment Generation (LOD2)

The treatment generation adapts based on premise length and detail:

#### System Message for Story Treatment
```
You are a professional story development editor specializing in creating industry-standard story treatments. Your treatments serve as the architectural blueprint for novels, outlining the complete narrative structure with precision and clarity.

[If author style specified]:
IMPORTANT: Write in the distinctive writing style of [Author Name]. Focus ONLY on mimicking their prose style, voice, sentence structure, pacing, and narrative techniques. Do NOT adopt their typical themes, settings, or subject matter - stick to the story elements provided.

TREATMENT FORMAT REQUIREMENTS:
- Write in PRESENT TENSE throughout ("Maya discovers..." not "Maya will discover...")
- Maintain NARRATIVE DISTANCE ("The ship explodes" not "We see the ship explode")
- Focus on STORY BEATS and PLOT POINTS, not prose style
- Include CHARACTER ARCS explicitly (how characters change)
- Mark TURNING POINTS and REVERSALS clearly
- Describe CAUSE AND EFFECT relationships between events
- NO dialogue, NO detailed scene descriptions, NO purple prose
- Think architecturally: structure over style

STRUCTURAL REQUIREMENTS:
- Write in plain text only, no formatting marks
- Use paragraph breaks to separate major story beats
- Include clear act structure (beginning/middle/end)
- Show escalation of conflict and stakes
- Identify the INCITING INCIDENT, MIDPOINT, and CLIMAX
- Track subplot development alongside main plot
- Format response with TITLE: and TREATMENT: sections exactly

TITLE REQUIREMENTS:
- Create compelling, marketable titles
- Capture the essence of the story
- Be memorable and intriguing

PROFESSIONAL TREATMENT STANDARDS:
- Open with the ORDINARY WORLD and CHARACTER STATUS QUO
- Clearly mark the INCITING INCIDENT that launches the story
- Build through PROGRESSIVE COMPLICATIONS with rising tension
- Include a clear MIDPOINT REVERSAL or REVELATION
- Escalate to the CRISIS moment (darkest hour/point of no return)
- Drive to CLIMAX where protagonist must make crucial choice/action
- Provide RESOLUTION showing new equilibrium and character change
- Weave in SUBPLOTS and SECONDARY ARCS throughout
- End each act on a CLIFFHANGER or REVELATION

ENGAGEMENT PRINCIPLES:
- Pose intriguing questions early in the synopsis to create curiosity
- Focus on compelling characters that readers will want to follow
- Hint at future conflicts and tensions to maintain reader interest
- Use quicker pacing, especially in the opening 10-15% of the story
- Design strategic plot points that create anticipation and momentum
- Ensure each major story beat builds toward a compelling climax
- Craft endings that feel earned and satisfying while leaving lasting impact
```

#### User Prompt for Story Treatment

For comprehensive treatments (1000+ words provided):
```
The author has provided a comprehensive story treatment. Your task is to enhance and expand it into a more detailed treatment while preserving all content.

**Comprehensive Treatment Provided ([word count] words):**
[User's treatment]

[Genre context if applicable]
[Story elements from taxonomy]

ENHANCEMENT REQUIREMENTS:
1. PRESERVE every specific detail, character, plot point, and story element from the treatment
2. EXPAND to approximately [target words] words (currently [current words] words)
   - This is a [X]x enhancement
   - Add sensory details and scene development without altering plot structure
3. ENHANCE by:
   - Adding sensory and atmospheric details to scenes
   - Developing character moments and emotional beats
   - Expanding key dramatic scenes with moment-to-moment detail
   - Enriching world-building with vivid descriptions
   - Preserving all specific numbers, timelines, and technical elements exactly
4. MAINTAIN:
   - The treatment's structure if it has clear sections or organization
   - Any explicit themes or philosophical statements
   - All factual content, technical terminology, and world rules
   - The author's tone and narrative voice
5. Create a compelling, marketable title that captures the essence of the story

FORMAT YOUR RESPONSE EXACTLY AS:
TITLE: [Your creative title here]

TREATMENT:
[Your enhanced treatment in present tense, preserving all elements from the original...]
```

For standard premises (under 400 words):
```
Create a professional story treatment with clear narrative structure based on these elements:

**Core Premise:** [User's premise]
[Genre context if applicable]

[Story elements from taxonomy]

TREATMENT REQUIREMENTS:
1. Create a compelling, marketable title
2. Write a [target]-word treatment in PRESENT TENSE
3. Structure with clear story beats:
   - OPENING: Establish protagonist, world, and status quo
   - INCITING INCIDENT: The event that launches the story
   - RISING ACTION: Progressive complications and obstacles
   - MIDPOINT: Major reversal or revelation
   - CRISIS: Darkest hour/maximum pressure
   - CLIMAX: Decisive confrontation/choice
   - RESOLUTION: New equilibrium and character transformation
4. Track CHARACTER ARCS explicitly (internal change)
5. Include SUBPLOT development
6. Maintain NARRATIVE DISTANCE (no "we see" or "the reader")

FORMAT YOUR RESPONSE EXACTLY AS:
TITLE: [Your creative title here]

TREATMENT:
[Your structured treatment in present tense...]
```

### Step 3: Chapter Generation (LOD2)

Chapters are generated as beat sheets, not prose. The system adapts for single-chapter vs multi-chapter works:

#### Multi-Chapter Generation Prompt
```
Based on the following story treatment and elements, create a detailed chapter breakdown with [X] chapters.

STORY TREATMENT:
[Generated treatment]
[Genre context]

STORY ELEMENTS:
[Taxonomy selections formatted]

REQUIREMENTS:
1. Create approximately [X] chapters (you may adjust slightly for better pacing, but aim for [X])
2. Each chapter should have:
   - A compelling title that captures the essence of that chapter
   - A beat sheet outline with [Y] major story beats
   - Each beat should be approximately [Z] words
3. Ensure proper story arc progression across all chapters
4. Distribute plot points, character development, and thematic elements appropriately
5. Each chapter should serve a clear purpose in advancing the story
6. Maintain consistency with the tone, pacing, and style indicated in the story elements

BEAT SHEET FORMAT:
- Focus on STRUCTURE, not prose narration
- Each beat describes a major plot point, turning point, or story moment
- Use present tense and maintain narrative distance
- Include: character decisions, conflicts, revelations, and consequences
- Format: "Beat 1: [Action/Event] → [Result/Consequence]"
- Think like a screenwriter outlining scenes, not a novelist writing prose

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS (use these exact delimiters):
[CHAPTER_START]
[CHAPTER_NUMBER]1[/CHAPTER_NUMBER]
[CHAPTER_TITLE]Title Here[/CHAPTER_TITLE]
[CHAPTER_OUTLINE]
Beat 1: [Major story beat here - approximately [Z] words]

Beat 2: [Next major story beat - approximately [Z] words]

[Continue for all beats...]
[/CHAPTER_OUTLINE]
[CHAPTER_END]

[Repeat for all chapters]
```

#### Single Chapter/Short Form Prompt
```
Based on the following story treatment and elements, create a detailed story outline.

STORY SYNOPSIS:
[Generated treatment]
[Genre context]

STORY ELEMENTS:
[Taxonomy selections]

REQUIREMENTS:
1. Create a single, complete story structure
2. The story should have:
   - A compelling title
   - [Brief/detailed] outline of the complete narrative arc (approximately [X] words)
3. Ensure the story has a clear beginning, middle, and end
4. Include all key plot points and character development
5. Maintain consistency with the tone, pacing, and style indicated in the story elements

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS (use these exact delimiters):
[CHAPTER_START]
[CHAPTER_NUMBER]1[/CHAPTER_NUMBER]
[CHAPTER_TITLE]Title Here[/CHAPTER_TITLE]
[CHAPTER_OUTLINE]
Full story outline here...
[/CHAPTER_OUTLINE]
[CHAPTER_END]
```

### Step 4: Raw Book Generation (LOD0)

Each chapter is transformed from beats to full prose:

#### System Message for Prose Generation
```
You are a professional novelist transforming a beat sheet outline into compelling, literary prose.
[If author style specified]:
IMPORTANT: Write in the distinctive writing style of [Author Name]. Focus ONLY on mimicking their prose style, voice, sentence structure, pacing, and narrative techniques. Do NOT adopt their typical themes, settings, or subject matter - stick to the story elements provided.

CRITICAL UNDERSTANDING - BEAT SHEETS VS PROSE:
You're receiving a BEAT SHEET - a structural outline marking key story moments. Your task is NOT mechanical expansion but creative interpretation. Beat sheets show WHAT happens; you must show HOW it feels, WHY it matters, and WHO these people really are.

THE ART OF BEAT INTERPRETATION:
- Beats are destinations; you create the journey
- Each beat contains both external action and internal change
- The space BETWEEN beats is where characters breathe, think, and grow
- Some beats explode into full scenes; others whisper in a paragraph
- Add unexpected moments within the expected structure
- Find the human story inside the structural skeleton

CREATING STORY IMMERSION:
- Ground every beat in sensory reality (all five senses + temperature, texture)
- Show emotional truth through physical details
- Use subtext - characters rarely say what they really mean
- Create narrative tension through what you withhold
- Vary prose rhythm: short sentences for tension, long for contemplation
- Let dialogue reveal character through HOW people speak, not just what

FORMATTING REQUIREMENTS:
- Plain text only, no markdown or special formatting
- SINGLE line breaks between paragraphs
- New paragraph for each speaker's dialogue
- Scene breaks: * * * on its own line

PACING & EMOTIONAL ARCHITECTURE:
- Opening: Drop readers into immediate experience (sensory, emotional, or active)
- Build emotional intensity through escalating beats
- Create breathing spaces between intense moments
- Use sentence length and paragraph breaks to control reading speed
- Layer in backstory through action, never exposition dumps
- End on unresolved tension - emotional, physical, or revelatory

CHAPTER GOALS:
- Transform structural beats into emotional journey
- Create prose with rhythm, voice, and personality
- Make readers FEEL the story, not just understand it
- Build narrative momentum that demands the next chapter
- Find surprising truths within planned structure
```

#### User Prompt for Prose Generation
```
Write the prose for Chapter [X]: [Chapter Title]

CHAPTER BEAT SHEET:
[Chapter outline with beats]

FULL STORY CONTEXT:
[Complete treatment]
[Genre context]

STORY ELEMENTS:
[Taxonomy selections]

UNDERSTANDING YOUR BEAT SHEET:
The beats above are structural waypoints, not a restrictive outline. Each beat marks an important story moment that needs to be transformed into living, breathing prose. Think of beats as destinations - your job is to create the journey between them with rich character experience, sensory detail, and emotional truth.

BEAT INTERPRETATION GUIDE:
- Each beat represents both an external event AND an internal shift
- Some beats deserve full scene treatment (500-1000+ words)
- Others might be a powerful paragraph or brief transition
- Let dramatic weight, not beat count, determine space allocation
- The moments BETWEEN beats are where character growth happens
- Add scenes and moments not specified in beats when they serve the story

CREATING COMPELLING PROSE:
- Transform structural beats into emotional experiences
- Show through action, dialogue, and internal reflection
- Add sensory immersion: sight, sound, smell, taste, texture, temperature
- Create subtext - what's unsaid is as important as what's spoken
- Vary sentence rhythm to control pacing and mood
- Find unexpected details within expected structure
- Let characters discover things that surprise even you

REQUIREMENTS:
- Write [target] words (between [min]-[max] words)
- Cover ALL beats from the outline, but interpret them creatively
- Add connective scenes between major beats
- Include rich dialogue with subtext and conflict
- Create immersive sensory description
- Develop character through action and internal experience
- Build to the chapter's emotional climax
- End with unresolved tension that demands the next chapter

[Additional engagement requirements for early chapters]:
ENGAGEMENT & PACING TECHNIQUES:
- CRITICAL: If this is among the first 2-3 chapters, ensure exceptionally captivating and fast-paced content
- Open with immediate engagement: action, intrigue, or compelling character moment
- Pose questions early in the chapter to create curiosity
- Focus on compelling characters that readers actively want to follow
- Hint at future conflicts and tensions throughout the narrative
- End the chapter on a cliffhanger, revelation, or moment of high tension - NEVER end on resolution
- Use quicker pacing - avoid excessive exposition or slow moments
- Include strategic scene breaks to maintain momentum
- Every scene must either advance the plot or deepen character understanding
- Create a sense of forward movement throughout the chapter
- Build tension progressively toward the chapter's climactic moment
```

### Step 5: Copy Editing (LOD0 Enhancement)

The final step transforms raw prose into professionally edited, e-reader-ready content:

#### System Message for Copy Editing
```
You are "BookCopyEditorGPT," a senior trade‑publishing copy editor.
[Genre context if applicable]
[Story elements context]

────────────────────  1.  CONTEXT  ────────────────────
You are editing a complete book ONE CHAPTER AT A TIME. You have the full book for context to maintain consistency in style, terminology, and narrative flow.

────────────────────  2.  FULL BOOK CONTENT  ────────────────────
Here is the complete book with current edit status:

[All chapters with their content and edit status]

────────────────────  3.  YOUR TASK  ────────────────────
Copy-edit ONLY Chapter [X]: [Title]

IMPORTANT:
- Return ONLY the edited content for Chapter [X]
- Maintain consistency with any previously edited chapters
- Apply the same style decisions throughout
- Do NOT include content from other chapters
- Output format: Valid XHTML with ALL text wrapped in <p> tags
- Every paragraph must be wrapped in <p>...</p> tags
- No text should exist outside of <p> tags
- No nested <p> tags allowed
- All tags must be properly closed
- All ampersands must be escaped as &amp;
- All special characters must be properly escaped
- You may use: <p>, <em>, <strong>, <span>, <br>, <sub>, <sup> tags only
- Special classes allowed: <p class="scene-break"> for scene breaks
- <p class="first"> will be added automatically by the system
- No chapter heading needed (will be added by the system)

────────────────────  4.  EDITORIAL SCOPE  ────────────────────
Perform a comprehensive copy‑edit while preserving the author's voice:
• Clarity, concision, pacing, paragraphing
• Consistency of tense, POV, timeline, names, invented terms
• Grammar, spelling, punctuation (Chicago 17 & Merriam‑Webster default)
• Factual coherence (science, measurements, terminology)
• Inclusive, sensitive language; flag potential bias
• Eliminate echoes, tighten transitions, smooth exposition dumps

ENGAGEMENT & PACING ENHANCEMENT:
• Ensure early chapters (1-3) are exceptionally captivating with fast pacing
• Verify each chapter poses questions to create reader curiosity
• Strengthen character appeal to ensure readers want to follow them
• Enhance hints at future conflicts and tensions throughout
• Confirm chapter endings create cliffhangers, revelations, or high tension
• Eliminate slow pacing and excessive exposition, especially in early chapters
• Strengthen scene breaks to maintain narrative momentum
• Ensure every scene advances plot or deepens character understanding
• Enhance forward movement and tension building throughout

FORMATTING REQUIREMENTS for Kindle/eBook compatibility:
• Normalize all line breaks: remove single line breaks within paragraphs
• Convert double line breaks (or more) to proper paragraph breaks
• Each speaker's dialogue MUST start a new paragraph
• Scene breaks (like ***, ---, ~~~, or similar) should be converted to: <p class="scene-break">* * *</p>
• Remove excessive whitespace or blank lines between paragraphs
• Ensure consistent paragraph separation throughout

────────────────────  5.  OUTPUT FORMAT  ────────────────────
You MUST return your response as a valid JSON object with EXACTLY this structure:
{
  "edited_content": "<p>First paragraph of edited chapter...</p><p>Second paragraph...</p><p>Third paragraph...</p>",
  "editorial_notes": [
    "Note about any significant changes or issues addressed",
    "Consistency corrections made (e.g., character names, timeline)",
    "Style decisions applied (e.g., tense corrections, POV adjustments)",
    "Flagged concerns (bias, sensitivity, factual issues)",
    "Major structural improvements (transitions, pacing, exposition)",
    "Formatting changes (line break normalization, scene breaks, dialogue separation)"
  ]
}

CRITICAL: Return ONLY the JSON object. No text before {, no text after }. No markdown code blocks.
```

### Step 6: Book Summary Generation (Marketing Enhancement)

After editing, a professional book summary is generated for Amazon KDP:

#### Book Summary Generation Prompt

The system uses a comprehensive prompt (400+ lines) that includes:

1. **Genre-Specific Guidance** - Different approaches for thriller, romance, fantasy, sci-fi, horror, YA
2. **Amazon KDP Best Practices** - Hook in first 50 characters, movie trailer approach
3. **Structured Deliverables**:
   - Tagline (10-20 words)
   - Main Blurb (150-250 words, 4-paragraph structure)
   - Unique Selling Points (3-5 bullets)
   - Comparisons (optional)
   - HTML Formatted Version
   - KDP Keywords (exactly 7, following Amazon guidelines)
   - Categories (3 strategic picks)
   - Audience Metadata

Key sections include:
```
CRITICAL AMAZON KDP BEST PRACTICES:
1. HOOK READERS IN FIRST 2 LINES - Only ~50 characters show in mobile preview
2. Think "MOVIE TRAILER" not synopsis - Tease, don't tell
3. Stop at the story's first major turning point - NO SPOILERS
4. Use short paragraphs (1-4 sentences max) with line breaks
5. Focus on protagonist + stakes + what's in their way
6. Match successful books in this genre for tone and structure

[Detailed 4-paragraph structure guide]

AMAZON KDP KEYWORDS (exactly 7, based on official Amazon guidelines)
THINK LIKE A READER - How would customers search for this book?

Focus on these keyword types:
- SETTING: Where/when the story takes place
- CHARACTER TYPES: Protagonist traits
- CHARACTER ROLES: What they do
- PLOT THEMES: Core story elements
- STORY TONE: The feeling/mood

CRITICAL RULES from Amazon:
- Combine keywords in LOGICAL ORDER (how readers would naturally search)
- Do NOT repeat words already in your book title or author name
- Do NOT use quotation marks
- Do NOT include subjective claims (bestselling, page-turner, etc.)
- Do NOT use category names you've already selected
- Be SPECIFIC and ACCURATE to book content
```

## Taxonomy Integration

The system uses a sophisticated hierarchical taxonomy system stored in the `/public/taxonomies/` folder. This system enables dynamic, genre-aware story generation through inheritance and extension patterns.

### Taxonomy File Structure

The taxonomy system consists of:

1. **Base Taxonomy (`base-taxonomy.json`)**: Universal properties applicable to all genres
2. **Genre-Specific Taxonomies**: Extend the base taxonomy with genre-specific options
3. **Generic Taxonomy**: Fallback for custom/undefined genres

### Inheritance Mechanism

#### Base Taxonomy Foundation
The `base-taxonomy.json` defines universal story properties that every story needs:

```json
{
  "taxonomy_version": "1.0",
  "taxonomy_name": "Base Story Properties",
  "description": "Universal properties applicable to all genres",
  "categories": {
    "length_scope": {
      "category_name": "Story Length",
      "selection_rule": "select_one",
      "options": {
        "flash_fiction": { "name": "Flash Fiction", "word_range": "500-1,500" },
        "short_story": { "name": "Short Story", "word_range": "1,500-7,500" },
        "novelette": { "name": "Novelette", "word_range": "7,500-17,500" },
        "novella": { "name": "Novella", "word_range": "17,500-40,000" },
        "novel": { "name": "Novel", "word_range": "40,000-120,000" },
        "epic": { "name": "Epic", "word_range": "120,000+" }
      }
    },
    "target_audience": {
      "category_name": "Target Audience",
      "options": {
        "middle_grade": { "name": "Middle Grade", "typical_length": "20,000-50,000 words" },
        "young_adult": { "name": "Young Adult", "typical_length": "50,000-80,000 words" },
        "adult": { "name": "Adult", "typical_length": "70,000-120,000 words" }
      }
    },
    "content_rating": { /* Clean, Mild, Moderate, Mature, Explicit */ }
  }
}
```

#### Genre Extension Pattern
Each genre taxonomy extends the base by:
1. Declaring `"extends": "base-taxonomy"`
2. Adding genre-specific categories
3. Potentially overriding base categories with genre-appropriate options

Example - Fantasy Taxonomy:
```json
{
  "extends": "base-taxonomy",
  "genre": "fantasy",
  "categories": {
    "fantasy_subgenre": {
      "options": {
        "epic_fantasy": {
          "name": "Epic/High Fantasy",
          "key_features": ["secondary world", "complex magic", "multiple POVs"],
          "themes": ["good vs evil", "prophecy", "chosen one"]
        },
        "urban_fantasy": {
          "name": "Urban Fantasy",
          "key_features": ["hidden magic", "modern technology", "city as character"]
        }
      }
    },
    "magic_system": { /* Detailed magic system options */ },
    "world_type": { /* Secondary world, portal, hidden world, etc. */ }
  }
}
```

Example - Romance Taxonomy:
```json
{
  "extends": "base-taxonomy",
  "genre": "romance",
  "categories": {
    "romance_subgenre": {
      "options": {
        "contemporary": { "popular_settings": ["big city", "small town", "workplace"] },
        "historical": { "popular_periods": ["Regency", "Victorian", "Medieval"] }
      }
    },
    "heat_level": { /* Sweet, Sensual, Steamy, Erotic */ },
    "relationship_type": { /* M/F, M/M, F/F, Poly, etc. */ }
  }
}
```

### Loading and Merging Process

When a genre is selected, the system:

1. **Loads Base Taxonomy**: Always loaded first to provide foundation
```javascript
const baseResponse = await fetch('/taxonomies/base-taxonomy.json');
const baseTaxonomy = await baseResponse.json();
```

2. **Loads Genre-Specific Taxonomy**: Based on selected genre
```javascript
const genreFile = genre === 'custom' ? 'generic' : genre;
const genreResponse = await fetch(`/taxonomies/${genreFile}-taxonomy.json`);
const genreTaxonomy = await genreResponse.json();
```

3. **Merges Categories**: Base + Genre-specific
```javascript
const mergedTaxonomy = {
  ...genreTaxonomy,
  categories: {
    ...baseTaxonomy.categories,    // Universal properties
    ...genreTaxonomy.categories     // Genre-specific override/extend
  }
};
```

4. **Fallback to Generic**: If genre taxonomy not found
```javascript
// Falls back to generic-taxonomy.json if specific genre file missing
```

### Available Genre Taxonomies

Currently implemented genre taxonomies:
- `fantasy-taxonomy.json` - Epic fantasy, urban fantasy, dark fantasy, etc.
- `romance-taxonomy.json` - Contemporary, historical, romantic suspense, etc.
- `mystery-thriller-taxonomy.json` - Detective, cozy mystery, psychological thriller
- `science-fiction-taxonomy.json` - Space opera, cyberpunk, dystopian
- `horror-taxonomy.json` - Gothic, psychological, cosmic horror
- `young-adult-taxonomy.json` - YA-specific themes and content
- `historical-fiction-taxonomy.json` - Period settings and historical elements
- `contemporary-fiction-taxonomy.json` - Modern literary and commercial fiction
- `literary-fiction-taxonomy.json` - Literary themes and experimental structures
- `urban-fantasy-taxonomy.json` - Modern magic in city settings
- `romantasy-taxonomy.json` - Romance + Fantasy hybrid

### Category Structure

Each category in a taxonomy follows this structure:
```json
{
  "category_key": {
    "category_name": "Human Readable Name",
    "selection_rule": "select_one | select_multiple | select_primary_and_secondary",
    "description": "What this category represents",
    "required": true/false,
    "options": {
      "option_key": {
        "name": "Display Name",
        "description": "Description of this option",
        // Additional metadata specific to the category
        "key_features": [],
        "themes": [],
        "typical_length": "",
        // etc.
      }
    }
  }
}
```

### Core Categories (Inherited by All Genres)

From base taxonomy:
- **length_scope**: Story format (flash fiction to epic)
- **target_audience**: Reader demographics (MG, YA, Adult)
- **content_rating**: Clean to Explicit
- **perspective**: POV (first, third limited, omniscient)
- **pacing**: Slow burn to breakneck

Genre-specific additions:
- **[genre]_subgenre**: Specific subgenre classifications
- **themes**: Genre-appropriate thematic elements
- **mood_tone**: Genre-specific atmospheric options
- **tropes**: Common genre conventions
- **setting**: Genre-relevant locations/worlds
- **protagonist_types**: Genre-typical character archetypes

### Dynamic Prompt Integration

The taxonomy selections flow through the entire generation pipeline:

1. **AI Receives Snake_Case Keys**: Direct from taxonomy files
```javascript
"taxonomySelections": {
  "fantasy_subgenre": ["epic_fantasy"],
  "magic_system": ["hard_magic"],
  "world_type": ["secondary_world"]
}
```

2. **Prompts Include All Selections**: Formatted for context
```
STORY ELEMENTS:
Fantasy Subgenre: Epic/High Fantasy
Magic System: Hard Magic System
World Type: Secondary World
```

3. **Generation Adapts**: Each stage uses taxonomy to guide generation
- Premise incorporates selected themes and tropes
- Treatment follows genre structure conventions
- Chapters reflect pacing preferences
- Prose adopts appropriate tone and mood

### Dynamic Word Count and Structure Calculations

The system uses taxonomy selections to dynamically adjust story parameters:

```javascript
// Base values from length_scope
if (lengthScope.includes('novel')) {
  targetWords = 80000;
  baseChapters = 20;
}

// Genre modifiers
if (genres.includes('thriller')) {
  chapterModifier *= 1.3;  // More, shorter chapters
  wordModifier *= 0.8;     // Faster pacing
}

// Audience modifiers
if (targetAudience.includes('middle_grade')) {
  totalWords *= 0.6;       // Shorter overall
  chapterModifier *= 1.2;  // More chapters
  wordModifier *= 0.7;     // Shorter chapters
}
```

### Benefits of the Taxonomy System

1. **Consistency**: All story elements align with genre expectations
2. **Flexibility**: New genres easily added without code changes
3. **Discovery**: Users can explore genre-specific options
4. **Intelligence**: AI understands genre context at every stage
5. **Customization**: Each genre has tailored options
6. **Inheritance**: Common properties shared, unique properties extended
7. **Maintenance**: Single source of truth for genre definitions

### Adding New Genres

To add a new genre:
1. Create `new-genre-taxonomy.json` in `/public/taxonomies/`
2. Set `"extends": "base-taxonomy"`
3. Define genre-specific categories and options
4. Add to genre dropdown in UI
5. System automatically loads and merges with base

This hierarchical taxonomy system ensures that every generated story adheres to genre conventions while maintaining flexibility for creative variation within those constraints.

## Iteration and Enhancement

### Story Iteration
When users provide feedback, the system can regenerate any level while preserving downstream consistency:

1. **Treatment Iteration**: Incorporates feedback while maintaining core premise
2. **Chapter Reorganization**: Adjusts pacing and structure
3. **Prose Refinement**: Rewrites specific chapters
4. **Targeted Editing**: Applies specific editorial changes

### Analysis and Improvement
The system includes sophisticated analysis tools that evaluate:
- **Story Structure**: Plot coherence and pacing
- **Character Development**: Arc consistency and depth
- **Market Viability**: Genre expectations and commercial appeal
- **Technical Quality**: Prose quality and engagement factors

## Word Count Dynamics

The system uses intelligent word count scaling based on story format:

### Format Configurations
```
Flash Fiction: 500-1,000 words
Short Story: 1,500-7,500 words
Novelette: 7,500-17,500 words
Novella: 17,500-40,000 words
Novel: 40,000-100,000 words
Epic: 100,000+ words
```

### Dynamic Scaling
- **Treatment Length**: 1-6% of total book length
- **Chapter Count**: Adjusted by genre and audience
- **Chapter Length**: Varies by format and pacing requirements
- **Beat Density**: 7-10 beats per chapter, scaled by chapter length

### Genre/Audience Modifiers
- **Middle Grade**: 60% of standard length
- **Young Adult**: 75% of standard length
- **Epic Fantasy**: 130% of standard chapter count
- **Thriller**: 120% chapter count for faster pacing
- **Romance**: Standard pacing with emotional beats

### Act-Aware Depth Architecture

The system uses a sophisticated **act-aware depth architecture** that ensures climaxes have appropriate emotional weight and intensity. This addresses a critical issue where Act III chapters would feel rushed and underweight compared to setup chapters.

#### The Problem

With flat words-per-event calculations across all acts:
- Act III has **fewer events** (focused conflict) but **same depth** per event as Act I
- Result: Act III chapters are significantly **shorter** than Act I chapters
- Impact: Climaxes feel rushed, lack emotional intensity, fail to meet reader expectations

**Example (80K novel, flat calculation):**
- Act I: 5 events × 950 w/e = 4,750 words/chapter
- Act III: 3 events × 950 w/e = 2,850 words/chapter
- **Act III is 40% SHORTER** than Act I - climaxes feel rushed!

#### The Solution: Independent Complexity and Depth Axes

The system treats **event count** (complexity) and **words per event** (depth) as **independent variables**:

1. **Complexity Axis (Event Distribution)**
   - Controlled by `ACT_EVENT_MULTIPLIERS`
   - Act I: More events (setup, world-building, character intro)
   - Act II: Standard events (rising action)
   - Act III: Fewer events (focused conflict)

2. **Depth Axis (Words Per Event)**
   - Controlled by `ACT_WE_MULTIPLIERS`
   - Act I: Slightly more efficient (many events to cover)
   - Act II: Standard depth (baseline)
   - Act III: Much deeper (emotional intensity, detail, pacing)

**Formula:**
```
word_count_target = event_count × words_per_event
                  = (avg_events × act_event_mult) × (base_we × act_we_mult)
```

#### Act Multipliers by Form

**Novels (50,000-110,000 words):**
```python
ACT_EVENT_MULTIPLIERS = {
    'act1': 1.3,   # More events for setup
    'act2': 1.0,   # Standard events
    'act3': 0.7    # Fewer events, focused climax
}

ACT_WE_MULTIPLIERS = {
    'act1': 0.95,  # Efficient (many events to cover)
    'act2': 1.00,  # Standard depth (baseline)
    'act3': 1.35   # Much deeper (emotional intensity)
}
```

**Epics (110,000-200,000 words):**
```python
ACT_EVENT_MULTIPLIERS = {
    'act1': 1.4,   # Many events (complex world, multiple threads)
    'act2': 1.0,   # Standard
    'act3': 0.6    # Very focused climax
}

ACT_WE_MULTIPLIERS = {
    'act1': 0.93,  # Very efficient (massive world-building)
    'act2': 1.00,  # Standard
    'act3': 1.40   # Very deep (multiple threads converging)
}
```

**Novellas (20,000-50,000 words):**
```python
# Uniform distribution (no act variation)
ACT_EVENT_MULTIPLIERS = {'act1': 1.0, 'act2': 1.0, 'act3': 1.0}
ACT_WE_MULTIPLIERS = {'act1': 1.0, 'act2': 1.0, 'act3': 1.0}
```

#### Act Boundaries

Chapters are assigned to acts based on their position in the story:

**Standard Distribution (4+ chapters):**
- Act I: First 25% of chapters (minimum 1 chapter)
- Act II: Middle 50% of chapters
- Act III: Final 25% of chapters (minimum 1 chapter)

**Small Chapter Counts (≤3 chapters):**
- 1 chapter: Act I only
- 2 chapters: Act I, Act III (no Act II)
- 3 chapters: Act I, Act II, Act III (one chapter each)

This ensures proper act distribution even for short-form stories.

#### Concrete Example: 80K Novel

**Input Parameters:**
- Target: 80,000 words
- Form: Novel (auto-detected)
- Pacing: Moderate (base_we = 950 words/event)
- Chapters: 20

**Calculations:**

| Chapter | Act | Event Mult | Events | Depth Mult | W/E | Word Target |
|---------|-----|------------|--------|------------|-----|-------------|
| 1 | I | 1.3× | 5 | 0.95× | 902 | 4,510 |
| 5 | I | 1.3× | 5 | 0.95× | 902 | 4,510 |
| 10 | II | 1.0× | 4 | 1.00× | 950 | 3,800 |
| 15 | II | 1.0× | 4 | 1.00× | 950 | 3,800 |
| 18 | III | 0.7× | 3 | 1.35× | 1,282 | 3,846 |
| 20 | III | 0.7× | 3 | 1.35× | 1,282 | 3,846 |

**Results:**
- Total: ~84,900 words (+6.1% vs target)
- Act I avg: 4,510 words/chapter
- Act II avg: 3,800 words/chapter
- Act III avg: 3,846 words/chapter

**Before Fix:**
- Act III was 40% SHORTER than Act I (2,850 vs 4,750 words)
- Climaxes felt rushed

**After Fix:**
- Act III is now comparable to Act I (3,846 vs 4,510 words, only 15% shorter)
- Act III has appropriate emotional depth despite fewer events
- Climaxes feel substantial and satisfying

#### Net Effect on Chapter Length

The combined effect of both multipliers:

```
Chapter length = events × we
               = (avg × event_mult) × (base_we × we_mult)
               = avg × base_we × (event_mult × we_mult)

Act I:   avg × base_we × (1.3 × 0.95) = 1.235× → +23.5% vs Act II
Act II:  avg × base_we × (1.0 × 1.0)  = 1.000× → baseline
Act III: avg × base_we × (0.7 × 1.35) = 0.945× → -5.5% vs Act II
```

**Key Insight:** Act III is **slightly shorter overall** but **much more intense** per event. The reduced event count is compensated by increased depth, ensuring climaxes don't feel rushed.

#### Integration with Generation Pipeline

1. **Chapter Generation** (`/generate chapters`):
   - Calculates act-aware event distribution across all chapters
   - Each chapter gets events = avg_events × act_event_multiplier
   - Each chapter gets word_target = events × act_words_per_event
   - Prompt includes act context for LLM awareness

2. **Word Count Assignment** (`/wordcount`):
   - Recalculates word targets based on actual event counts
   - Uses act-aware words_per_event for each chapter's act
   - Shows act position in change log

3. **Prose Generation** (`/generate prose`):
   - Reminds LLM about act-specific depth expectations
   - Act I: "Efficient setup"
   - Act II: "Standard development"
   - Act III: "DEEPER, more emotional intensity per event"

#### Why Mathematical vs LLM?

The system uses **deterministic mathematical formulas** instead of LLM-based word count assignment:

**Benefits:**
- **Deterministic**: Same input → same output (predictable)
- **Free**: No API calls (cost-effective)
- **Transparent**: Users can see and understand the formula
- **Consistent**: No variation between runs
- **Sufficient**: Act multipliers provide the key insight (climaxes need depth)

**Trade-offs:**
- Can't assess complexity beyond event count
- No nuanced judgment of dramatic peaks

**Decision:** Mathematical is sufficient for 90% of cases. LLM refinement could be added as optional enhancement if needed.

#### Implementation

The act-aware architecture is implemented in `src/generation/depth_calculator.py`:

**Key Methods:**
```python
DepthCalculator.get_act_for_chapter(ch_num, total_chapters)
# Returns: 'act1', 'act2', or 'act3'

DepthCalculator.get_act_words_per_event(form, pacing, act)
# Returns: act-adjusted words per event (int)

DepthCalculator.calculate_chapter_word_target(ch_num, total_chapters, event_count, form, pacing)
# Returns: word_count_target for chapter (int)
```

**Forward-Looking Only:**
- This architecture affects NEW generations only
- Existing content is not modified
- Users can regenerate chapters to apply new calculations

## Quality Control

### Validation Points
1. **Premise Validation**: Ensures marketability and genre fit
2. **Structure Validation**: Checks for complete story arc
3. **Pacing Validation**: Ensures appropriate tension escalation
4. **Consistency Validation**: Cross-references all levels for continuity
5. **Format Validation**: Ensures technical compliance (XHTML, JSON)

### Error Recovery
- **Automatic Retries**: Network and parsing errors
- **Graceful Degradation**: Falls back to simpler formats
- **Manual Intervention**: User can retry/regenerate any step
- **State Preservation**: Saves progress between sessions

## Conclusion

This LOD system represents a sophisticated approach to AI-assisted creative writing, balancing structure with creativity, consistency with innovation, and automation with human control. The progressive refinement ensures that each story maintains its core vision while developing the depth and detail necessary for a complete, publishable work.

The key to the system's success lies in:
1. **Clear Hierarchical Structure**: Each level builds logically on the previous
2. **Flexible Interpretation**: Prompts guide without constraining creativity
3. **Genre Awareness**: All generation adapts to genre conventions
4. **Quality Focus**: Multiple validation and enhancement steps
5. **User Control**: Every step can be customized or regenerated

This architecture enables the creation of commercially viable, emotionally engaging fiction at scale while maintaining the unique voice and vision of each story.