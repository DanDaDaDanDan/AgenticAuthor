# Skill: /status

Show the current project progress and statistics.

## Usage

```
/status [project-name]
```

## Arguments

- `project-name` (optional): Specific project to check. If not provided, use current directory or list all projects.

## Instructions

### Step 1: Find Project(s)

Check the current working directory:
- If inside `books/{project}/`, use that project
- If in repository root, check if `project-name` argument provided
- If no argument, list all projects in `books/` directory

### Step 2: Read Project Data

For the target project, check which files exist:

```
books/{project}/
├── project.yaml      ✓/✗
├── premise.md        ✓/✗
├── treatment.md      ✓/✗
├── structure-plan.md ✓/✗ (novels only)
├── chapters/
│   ├── chapter-01.md ✓/✗
│   ├── chapter-02.md ✓/✗
│   └── ...
└── story.md          ✓/✗ (short stories only)
```

### Step 3: Calculate Statistics

For each existing file, calculate:
- Word count
- Last modified date
- Git status (committed, modified, untracked)

### Step 4: Display Status

Output a formatted status report:

```
📚 Project: {title}
   Author: {author}
   Genre: {genre}
   Type: {novel/short-story}
   Created: {date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Progress:
  [✓] Premise          {word count} words
  [✓] Treatment        {word count} words
  [✓] Structure Plan   {chapter count} chapters planned
  [ ] Prose            {X}/{Y} chapters complete

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chapters:
  Ch 1: {title}        ✓ {word count} words
  Ch 2: {title}        ✓ {word count} words
  Ch 3: {title}        ○ Not started
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Progress: {X}% complete
Total Words: {total word count}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recent Activity:
  {commit 1 - date - message}
  {commit 2 - date - message}
  {commit 3 - date - message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next Steps:
  → {Recommended next action based on current progress}
```

### Step 5: Git Commands for Statistics

Use these commands to gather information:

```bash
# Word count for a file
wc -w books/{project}/premise.md

# List chapters
ls books/{project}/chapters/

# Recent commits for project
cd books && git log --oneline -5 -- {project}/

# Check for uncommitted changes
cd books && git status --porcelain {project}/
```

**Note:** This skill uses visual indicators (checkmarks, circles) for status display to improve readability.

## Progress Calculation

Calculate completion percentage based on stages:

| Stage | Weight (Novel) | Weight (Short Story) |
|-------|---------------|---------------------|
| Premise | 10% | 15% |
| Treatment | 20% | 25% |
| Structure Plan | 10% | N/A |
| Prose | 60% | 60% |

For prose, weight is distributed across chapters:
- Novel: 60% / number of chapters
- Short story: 60% for story.md

## Multi-Project Summary

If listing all projects:

```
📚 AgenticAuthor Projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Project          Type          Progress    Words
  ─────────────────────────────────────────────────
  my-fantasy       Novel         45%         32,450
  quick-story      Short Story   100%        8,200
  new-project      Novel         10%         1,200

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use /status {project-name} for details.
```

## Uncommitted Changes Warning

If there are uncommitted changes, show a warning:

```
⚠️  Uncommitted changes detected:
    - premise.md (modified)
    - chapters/chapter-03.md (new file)

    Consider committing with: git add . && git commit -m "message"
```

## Next Steps Logic

Suggest next action based on current state:

| Current State | Suggested Next Step |
|--------------|---------------------|
| No premise | `/generate premise` |
| Premise only | `/generate treatment` |
| Treatment, no plan (novel) | `/generate plan` |
| Plan complete, no prose | `/generate prose` |
| Some chapters done | `/generate prose` to continue |
| All complete | `/export` to create final document |
| Recent iteration | Review changes, continue writing |
