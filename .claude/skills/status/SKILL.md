---
name: status
description: Show project progress and statistics.
argument-hint: "[project-name]"
---

Show the current project progress and statistics.

## Usage

```
/status [project-name]
```

## Arguments

- `project-name` (optional): Specific project to check. If not provided, use current directory or list all projects.

## Instructions

### Step 1: Find Project(s)

**Check for active book first:**

1. If `project-name` argument provided, use that project
2. Otherwise, read `books/active-book.yaml` and extract the `project:` value
3. If `project:` is set (not `null`), use that project
4. If `project:` is `null` or file doesn't exist, fall back to:
   - If inside `books/{project}/`, use that project
   - Otherwise, list all projects in `books/` directory

### Step 2: Read Project Data

For the target project, check which files exist:

```
books/{project}/
├── project.yaml            [x]/[ ]
├── 01-premise.md           [x]/[ ]
├── 03-treatment.md         [x]/[ ]
├── 04-structure-plan.md    [x]/[ ] (all project types)
│
│   # For novella/novel/epic:
├── 05-chapter-plans/       (novella/novel/epic only)
│   ├── chapter-01-plan.md  [x]/[ ]
│   └── ...
├── 06-chapters/            (novella/novel/epic only)
│   ├── chapter-01.md       [x]/[ ]
│   └── ...
│
│   # For flash/short/novelette:
├── 05-story-plan.md        [x]/[ ] (flash/short/novelette only)
└── 06-story.md             [x]/[ ] (flash/short/novelette only)
```

### Step 3: Calculate Statistics

For each existing file, calculate:
- Word count
- Last modified date
- Git status (committed, modified, untracked)

### Step 4: Display Status

Output a formatted status report using plain ASCII characters for terminal compatibility:

```
PROJECT: {title}
  Author: {author}
  Genre: {genre}
  Type: {Flash Fiction/Short Story/Novelette/Novella/Novel/Epic}
  Created: {date}

------------------------------------------------------------------------

PROGRESS:
  [x] Premise          {word count} words
  [x] Treatment        {word count} words
  [x] Structure Plan   {chapter/scene count} planned
  [x] Generation Plans {X}/{Y} plans (novella/novel/epic) or [x]/[ ] story plan (flash/short/novelette)
  [ ] Prose            {X}/{Y} chapters (novella/novel/epic) or [x]/[ ] (flash/short/novelette)

WORD COUNT:
  Target: {length_target_words from frontmatter} words
  Actual: {total prose word count} words
  Status: {on track / under target / over target by X%}

------------------------------------------------------------------------

CHAPTERS (novella/novel/epic):
  Ch 1: {title}        Plan [x]  Prose [x]  {actual} / {target} words
  Ch 2: {title}        Plan [x]  Prose [x]  {actual} / {target} words
  Ch 3: {title}        Plan [x]  Prose [ ]  (ready to write)
  Ch 4: {title}        Plan [ ]  Prose [ ]  (not started)
  ...

FLASH/SHORT/NOVELETTE:
  Story Plan: [x]/[ ]
  Prose: [x]/[ ]  {actual} / {target} words

------------------------------------------------------------------------

COMPLETION: {X}% complete

------------------------------------------------------------------------

RECENT ACTIVITY:
  {commit 1 - date - message}
  {commit 2 - date - message}
  {commit 3 - date - message}

------------------------------------------------------------------------

NEXT STEPS:
  > {Recommended next action based on current progress}
```

**Word count sources:**
- Target: Read `length_target_words` from premise/treatment/structure-plan frontmatter
- Per-chapter targets: Read from structure-plan chapter breakdowns
- Actual: Count words in prose files

### Step 5: Git Commands for Statistics

Use these commands to gather information:

```bash
# Word count for a file
wc -w books/{project}/01-premise.md

# List chapters
ls books/{project}/06-chapters/

# Recent commits for project
cd books && git log --oneline -5 -- {project}/

# Check for uncommitted changes
cd books && git status --porcelain {project}/
```

**Note:** This skill uses plain ASCII characters ([x], [ ], dashes) for terminal compatibility. Avoid emoji and box-drawing characters.

## Progress Calculation

Calculate completion percentage based on stages:

| Stage | Weight (Novella/Novel/Epic) | Weight (Flash/Short/Novelette) |
|-------|------------------------------|-------------------------------|
| Premise | 10% | 10% |
| Treatment | 15% | 15% |
| Structure Plan | 10% | 10% |
| Generation Plans | 10% | 10% |
| Prose | 55% | 55% |

**Weight distribution within stages:**

For **novella/novel/epic**, generation plans and prose weights are distributed across chapters:
- Generation Plans: 10% × (completed plans / total chapters)
- Prose: 55% × (completed chapters / total chapters)

For **flash/short/novelette**, each stage is binary (complete or not):
- Generation Plan: 10% if `05-story-plan.md` exists
- Prose: 55% if `06-story.md` exists

## Multi-Project Summary

If listing all projects:

```
AGENTICAUTHOR PROJECTS
------------------------------------------------------------------------

  Project          Type          Progress    Actual / Target
  ----------------------------------------------------------------
  my-fantasy       Novel         45%         32,450 / 80,000 words
  quick-story      Short Story   100%        8,200 / 7,500 words
  new-project      Novel         10%         1,200 / 80,000 words

------------------------------------------------------------------------

Use /status {project-name} for details.
```

## Uncommitted Changes Warning

If there are uncommitted changes, show a warning:

```
WARNING: Uncommitted changes detected:
  - 01-premise.md (modified)
  - 06-chapters/chapter-03.md (new file)

Consider committing with: git add . && git commit -m "message"
```

## Next Steps Logic

Suggest next action based on current state:

| Current State | Suggested Next Step |
|--------------|---------------------|
| No premise | `/generate premise` |
| Premise only | `/generate treatment` |
| Treatment complete | `/generate prose` (creates structure plan automatically) |
| Some chapters done (novella/novel/epic) | `/generate prose` to continue |
| All complete | `/export` to create final document |
| Recent iteration | Review changes, continue writing |
