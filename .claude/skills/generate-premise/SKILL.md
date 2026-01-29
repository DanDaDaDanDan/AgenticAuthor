---
name: generate-premise
description: Generate the core premise (01-premise.md).
argument-hint: ""
---

Generate the core concept and story foundation (premise stage).

Equivalent to:
- `/generate premise`

## Usage

```
/generate-premise
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
1. Review the genre taxonomy's subgenre/type category and present relevant options to the user
2. Use the selected subgenre's `key_features`, `themes`, and `tone` to guide the premise
3. Read `length` and `series_structure` from project.yaml (already collected by /new-book)
4. Ask the user about `target_audience`, `content_rating`, and `plausibility` from base-taxonomy options
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

**Output file:** `01-premise.md`

**Generation instructions:**

1. Ask the user for a brief concept (1-3 sentences describing the story idea).

2. **Present the story’s “subgenre/type” from the genre taxonomy:**
   Not all taxonomies name this category `{genre}_subgenre`. Determine the best-fit category in this order:
   1. Prefer a category key ending in `_subgenre` (e.g., `fantasy_subgenre`, `contemporary_subgenre`, `scifi_subgenre`, `mystery_subgenre`).
   2. Otherwise use a genre-specific fallback:
      - `urban-fantasy` → `urban_fantasy_type`
      - `romantasy` → `world_setting`
      - `literary-fiction` → `literary_style`
      - `historical-fiction` → `historical_period`
      - `young-adult` → `ya_genre`
      - `generic` → `genres`

   Present the chosen category’s options to the user:
   > What subgenre/type fits this story best?
   > {List options from taxonomy with brief descriptions}

   Map the category’s `selection_rule` into the standard frontmatter fields:
   - If `select_primary_and_secondary`: Ask for primary choice, then offer optional secondary; store into `subgenre_keys`/`subgenres` object.
   - If `select_primary` or `select_one`: Ask for one choice; store as `subgenre_keys.primary`/`subgenres.primary` and omit `secondary`.
   - If it’s a multi-select rule: Ask for **one primary** and optionally **one secondary** from the options; store into `subgenre_keys`/`subgenres` object (do not store more than two in `subgenre_keys`).

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

5. Ask about plausibility:
   > How grounded should the story's world and specialized details be (technology, law, medicine, etc.)?
   > 1. Grounded - real-world constraints, competent systems, meaningful consequences
   > 2. Heightened - cinematic realism; streamlined but internally consistent
   > 3. Stylized - impressionistic/allegorical; prioritize voice and theme over mechanics

   **Default:** If the user skips or says "you decide," use Heightened.

6. Ask about prose style preference:
   > What prose style fits this story?
   > 1. Commercial/Accessible - clear, readable, mass-market appeal
   > 2. Literary - denser prose, rewards close reading
   > 3. Minimalist - spare, precise, subtext-heavy
   > 4. Pulp/Action - fast, punchy, momentum-driven
   > 5. Lyrical/Atmospheric - poetic, mood-focused, sensory-rich
   > 6. Conversational - strong narrative voice, personality-driven

   Note the genre's `best_for` suggestions in style-taxonomy.json but let the user choose freely.

7. Ask about dialogue density (optional):
   > How dialogue-heavy should the narrative be?
   > 1. High (40-60%) - dialogue-driven, scenes play out in conversation
   > 2. Moderate (25-40%) - balanced mix of dialogue and narrative
   > 3. Low (<25%) - narrative-driven, dialogue used sparingly for impact

   **Default:** If the user skips or says "you decide," use Moderate (works for most genres).

8. Ask about point of view:
   > What narrative POV works best?
   > 1. First Person - intimate, limited knowledge, "I/me" narration
   > 2. Third Person Limited (Single POV) - one character's thoughts, some distance
   > 3. Third Person Multiple - rotating POV between characters
   > 4. Third Person Omniscient - all-knowing narrator, can access any thoughts
   > 5. Second Person - "you" narration (uncommon, experimental)

   **Default:** If the user skips or says "you decide," use Third Person Limited for most genres, First Person for YA/Romance/Urban Fantasy.

9. Ask about tense:
   > What tense should the narrative use?
   > 1. Past tense - traditional storytelling ("She walked...")
   > 2. Present tense - immediate, cinematic ("She walks...")

   **Default:** If the user skips or says "you decide," use Past tense (the industry standard for most genres).

10. Generate a complete premise document with YAML frontmatter:

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
# Base taxonomy - plausibility (how strictly to adhere to real-world constraints)
plausibility_key: {grounded|heightened|stylized}
plausibility: "{Display Name, e.g., Heightened}"
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
**Bash:**
```bash
cd books && git add {project}/01-premise.md && git commit -m "Add: Generate premise for {project}"
```

**PowerShell:**
```powershell
cd books; git add {project}/01-premise.md; git commit -m "Add: Generate premise for {project}"
```
