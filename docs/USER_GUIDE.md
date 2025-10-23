# AgenticAuthor User Guide

**Version:** 0.4.0 (Unreleased)
**Last Updated:** 2025-10-23

Complete guide to using AgenticAuthor for AI-powered book generation with natural language iteration.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Management](#project-management)
3. [Generation Workflow](#generation-workflow)
4. [Natural Language Iteration](#natural-language-iteration)
5. [Model Selection](#model-selection)
6. [Taxonomy Editing](#taxonomy-editing)
7. [Analysis and Quality](#analysis-and-quality)
8. [Export and Publishing](#export-and-publishing)
9. [Git Integration](#git-integration)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd AgenticAuthor

# Install dependencies
pip install -e .

# Set API key
export OPENROUTER_API_KEY="sk-or-your-key-here"

# Start REPL
agentic
```

### First Book in 5 Commands

```bash
/new my-first-book
/model grok-4-fast
/generate premise "a wizard discovers magic is breaking"
/generate treatment
/generate chapters
/finalize chapters
/generate prose all
```

---

## Project Management

### Creating Projects

```bash
# Create new project
/new my-novel

# Create with specific name
/new steampunk-adventure
```

### Opening Projects

```bash
# Interactive selection (shows all projects)
/open

# Direct open
/open my-novel
```

### Cloning Projects

**CRITICAL for iteration testing:**

```bash
# Clone current project to new name
/clone my-novel-v2

# Why clone?
# - Iteration is destructive (replaces content)
# - Always test on clones, never production books
# - Git commits allow rollback but cloning is safer
```

### Project Status

```bash
/status

# Output:
# Project: my-novel
# Model: x-ai/grok-4-fast
# Premise: ✓
# Treatment: ✓ (2,500 words)
# Chapters: ✓ (11 chapters from 4 variants)
# Prose: ✓ (35,234 words across 11 chapters)
# Iteration: premise (ready for feedback)
```

---

## Generation Workflow

### Premise Generation

**Auto-Detection with Single Premise:**

```bash
/generate premise "a magical library where books come alive"

# System auto-detects genre: fantasy
# Generates single premise with taxonomy
# Sets iteration target to 'premise'
```

**Batch Generation (Multiple Options):**

```bash
/generate premises 5 fantasy "a magical library"

# Generates 5 premise options
# Shows numbered list to choose from
# Selected premise becomes active
```

**With Explicit Genre:**

```bash
/generate premise fantasy "a wizard discovers magic is breaking"
```

### Treatment Generation

```bash
/generate treatment

# Requires: premise exists
# Generates: 2,500-word treatment with structure
# Sets iteration target to 'treatment'
```

### Chapter Generation (Multi-Variant)

**Generate Variants:**

```bash
/generate chapters

# Generates 4 variants in parallel:
# - Variant 1: temp=0.65 (Conservative)
# - Variant 2: temp=0.70 (Balanced-Conservative)
# - Variant 3: temp=0.75 (Balanced-Creative)
# - Variant 4: temp=0.80 (Creative)
#
# Saves to: chapter-beats-variants/
```

**Finalize with LLM Judge:**

```bash
/finalize chapters

# LLM evaluates all 4 variants
# Selects winner based on quality criteria
# Copies winner to chapter-beats/
# Saves decision to decision.json
# Sets iteration target to 'chapters'
```

### Prose Generation

**All Chapters:**

```bash
/generate prose all

# Generates prose for all chapters
# Uses winner from /finalize chapters
# Saves to chapters/chapter-NN.md
# Sets iteration target to 'prose'
```

**Single Chapter:**

```bash
/generate prose 3

# Generates only chapter 3
# Requires chapters 1-2 already exist (for context)
```

**Range of Chapters:**

```bash
/generate prose 5-8

# Generates chapters 5 through 8
```

### Short Story Workflow

For stories ≤7,500 words (flash fiction, short stories, novelettes):

```bash
/new my-short-story
/model grok-4-fast
/generate premise "a brief concept"
/iterate taxonomy  # Select "short_story" in length_scope

# Generate treatment
/generate treatment

# Generate complete story (single file)
/generate prose
# Creates: story.md (NOT chapters/)

# Status shows:
# Type: Short Story (~3,500 words target)
# Story: ✓ (3,200 words)
```

---

## Natural Language Iteration

**NEW in v0.4.0:** Always-on iteration mode for natural language feedback on generated content.

### Overview

When an iteration target is set, any non-command text becomes iteration feedback. The system:

1. Regenerates content based on your feedback
2. Validates with LLM judge (matches your request?)
3. Shows semantic diff (human-readable change summary)
4. Asks for approval
5. Auto-commits to git on approval

### Setting Iteration Target

**Automatic (after generation):**

```bash
/generate premise "concept"
# Iteration target auto-set to: premise

/generate treatment
# Iteration target auto-set to: treatment

/finalize chapters
# Iteration target auto-set to: chapters

/generate prose all
# Iteration target auto-set to: prose
```

**Manual:**

```bash
# Set target
/iterate premise
/iterate treatment
/iterate chapters
/iterate prose

# Show current target
/iterate

# Output: Current iteration target: premise
```

### Iteration Examples

#### Premise Iteration

```bash
/generate premise "a wizard discovers magic is breaking"
# Target auto-set to: premise

# Now just type feedback (no command needed):
make it darker and add more mystery

# System:
# 1. Regenerates premise with your feedback
# 2. Judge validates (does it address feedback?)
# 3. Shows semantic diff
# 4. Asks approval
# 5. Commits: [my-novel] Iterate premise: make it darker and add more mystery
```

#### Treatment Iteration

```bash
/iterate treatment

# Provide feedback:
add a subplot about the protagonist's mentor betraying them

# System iterates on treatment with full context
```

#### Chapter Iteration

```bash
/iterate chapters

# Provide feedback:
chapter 5 feels rushed, expand the confrontation scene

# System regenerates ALL chapters (holistic approach)
# Maintains consistency across all chapters
# Shows semantic diff of changes
```

#### Prose Iteration

```bash
/iterate prose

# Provide feedback:
add more dialogue in chapter 3 and make the ending more ambiguous

# System regenerates ALL prose (holistic approach)
# Uses chapters.yaml for structure consistency
# Shows semantic diff of changes across all chapters
```

### Judge Validation Loop

The LLM judge validates generated content before showing you:

**Approval (automatic):**
```
Judge verdict: ✓ Approved
Reasoning: The revision successfully addresses the feedback by adding mystery
elements and darkening the tone while maintaining story coherence.

Generating semantic diff...
```

**Needs Revision (retries automatically):**
```
Judge verdict: ⚠ Needs Revision
Issues:
- Feedback requested more mystery but changes are superficial
- Dark tone added but mystery elements not developed

Attempt 2 of 3...
```

**Max Attempts Reached (asks user):**
```
Judge rejected after 3 attempts.

Last reasoning: The revision still doesn't fully capture the requested mystery
elements, though the dark tone is improved.

Options:
1. Accept anyway (might be good enough)
2. Retry with clarified feedback
3. Cancel iteration

Your choice:
```

### Semantic Diff Display

Human-readable change summary (not raw git diff):

```markdown
# Iteration Summary: premise

## User Request
Make it darker and add more mystery

## Changes Made

### Major Changes
- Added mystery subplot: Ancient conspiracy controlling magic system
- Darkened protagonist's backstory: Lost family to magical corruption
- Introduced ominous foreshadowing: Recurring symbol in failures

### Moderate Changes
- Changed tone: Hopeful optimism → Desperate urgency
- Modified ending: Clear resolution → Open questions

### Minor Changes
- Updated character name: Aric → Kael (darker sound)
- Adjusted pacing: Gradual discovery → Shocking revelation

## Before/After Comparison

**Before:**
> Aric discovers magic is fading and embarks on a quest to restore it.

**After:**
> Kael, haunted by his family's death from magical corruption, uncovers a
> conspiracy that suggests the failures aren't random—they're orchestrated.

## Verdict
Changes successfully address feedback: darker tone ✓, added mystery ✓
```

### Downstream Cascade

When iterating on upstream content (premise, treatment), downstream content becomes stale:

```bash
/iterate premise

# After semantic diff approval:
Downstream content affected:
- Treatment (2,500 words)
- Chapters (11 chapters)
- Prose (35,234 words)

These will be out of sync with the new premise.

Options:
1. cull-all: Delete all downstream content (start fresh)
2. keep-all: Keep downstream content (might be inconsistent)
3. cancel: Don't proceed with iteration

Your choice: 1

# System deletes treatment, chapters, prose
# Commits iteration
# You regenerate from scratch with new premise
```

### Iteration History

Every iteration is tracked in `{lod-folder}/iteration_history.json`:

```json
[
  {
    "timestamp": "2025-10-23T18:30:45Z",
    "feedback": "make it darker and add more mystery",
    "judge_attempts": 2,
    "judge_verdict": "approved",
    "judge_reasoning": "Successfully addresses feedback...",
    "semantic_summary": "Added mystery subplot and darkened tone...",
    "commit_sha": "a1b2c3d4",
    "files_changed": 1,
    "lines_changed": 45
  }
]
```

**Purpose:**
- Provides context for future iterations
- Tracks decision history
- Helps LLM understand cumulative changes

### Safety Features

**First Iteration Warning:**

```bash
# First time you iterate on a project:

⚠️  WARNING: Iteration replaces content permanently!

Always test on cloned projects first (use /clone).
Git commits are created automatically for easy rollback.

Continue with iteration? (yes/no):
```

**Debug Storage:**

All generation attempts saved to `.agentic/debug/iteration/`:

```
.agentic/debug/iteration/
├── premise_attempt_1_rejected.txt
├── premise_attempt_2_rejected.txt
├── premise_attempt_3_approved.txt
└── judge_verdicts.json
```

**Git Commits:**

Every iteration creates a commit:

```bash
git log

# Output:
# [my-novel] Iterate premise: make it darker and add more mystery
# [my-novel] Iterate treatment: add mentor betrayal subplot
# [my-novel] Iterate chapters: expand chapter 5 confrontation
```

**Rollback if needed:**

```bash
/git log
# Shows recent commits

/git diff HEAD~1
# Shows changes in last commit

# Rollback (if you made a mistake):
git reset --hard HEAD~1
```

---

## Model Selection

### Interactive Selector

```bash
/model

# Launches full-screen interactive selector:
# - Live fuzzy search (type to filter)
# - Arrow keys to navigate
# - Enter to select
# - Escape to cancel
# - Shows provider, context length, pricing
```

### Direct Search

```bash
/model grok
# Fuzzy matches: x-ai/grok-4-fast, x-ai/grok-beta, etc.
# Selects first match

/model claude
# Fuzzy matches: anthropic/claude-3.5-sonnet, etc.
```

### List Models

```bash
/models
# Shows all available models with metadata

/models grok
# Filters list by search term
```

### Model Policy

**CRITICAL:** One model for ALL operations. No fallbacks.

```bash
# Selected model used for:
# - Premise generation
# - Treatment generation
# - Chapter generation
# - Prose generation
# - Iteration (all targets)
# - Judge validation
# - Semantic diff generation
# - Intent analysis
# - All other LLM calls

# Why? Cost control and predictable behavior
```

---

## Taxonomy Editing

### Interactive Editor

```bash
/iterate taxonomy

# Launches full-screen checkbox UI:
# - Categories: length_scope, pacing, complexity, etc.
# - Checkboxes for multi-select categories
# - Radio buttons for single-select categories
# - Space to toggle, Enter to save
# - Escape to cancel
```

**Example:**

```
Taxonomy Editor - fantasy

┌─ length_scope ─────────────────┐
│ [ ] flash_fiction (≤1k words)  │
│ [ ] short_story (1k-7.5k)      │
│ [✓] standalone (30k-60k)       │  ← Currently selected
│ [ ] series_book_1 (60k-120k)   │
│ [ ] epic (120k-200k+)          │
└────────────────────────────────┘

Space: Toggle  Enter: Save  Esc: Cancel
```

### Natural Language Updates

```bash
/iterate taxonomy

# Then type feedback:
change to short story and make pacing fast

# System updates taxonomy fields
# Optionally regenerates premise with new parameters
```

---

## Analysis and Quality

### Analyze Content

```bash
# Analyze premise
/analyze premise

# Analyze treatment
/analyze treatment

# Analyze chapters
/analyze chapters

# Analyze specific chapter
/analyze chapters 3

# Analyze prose
/analyze prose

# Analyze specific prose chapter
/analyze prose 5
```

**Output:**

```markdown
# Chapter Analysis

## Quality Score: 78/100

## Strengths
- Strong character development
- Clear plot progression
- Effective use of conflict

## Issues

### Critical
- Plot hole: Chapter 5 contradicts Chapter 2 regarding magic rules

### Major
- Character inconsistency: Protagonist's motivation shifts unexpectedly

### Minor
- Pacing slightly rushed in climax

## Recommendations
1. Revise Chapter 5 to align with established magic rules
2. Add transition scene to justify motivation shift
3. Consider expanding climax by 500-1000 words
```

### Copy Editing

```bash
# Interactive copy edit (review each change)
/copyedit

# Auto copy edit (apply all changes)
/copyedit --auto
```

**Process:**
1. Loads chapters.yaml + all prose (full context)
2. LLM identifies grammar, style, consistency issues
3. Shows each change with before/after
4. You approve or reject each change
5. Saves edited prose
6. Commits changes

---

## Export and Publishing

### Export to RTF

```bash
/export rtf

# Generates: exports/[project-name].rtf
# Includes: frontmatter, dedication, all chapters
# Compatible with most word processors
```

### Export to Markdown

```bash
/export markdown

# Generates: exports/[project-name].md
# Includes: all chapters with markdown formatting
```

### Metadata for Publishing

```bash
# Set metadata
/metadata title "The Unforged Sky"
/metadata author "Sloane Grey"
/metadata copyright "2025 Sloane Grey"

# View all metadata
/metadata

# Output:
# title: The Unforged Sky
# author: Sloane Grey
# copyright: 2025 Sloane Grey
# publisher: (not set)
# isbn: (not set)
```

### Generate Marketing Materials

```bash
# KDP description
/generate marketing description

# Keywords
/generate marketing keywords

# Author bio
/generate marketing bio
```

---

## Git Integration

### View Status

```bash
/git status

# Output:
# On branch main
# Changes not staged for commit:
#   modified: chapters/chapter-03.md
```

### View History

```bash
/git log

# Output (recent commits):
# a1b2c3d [my-novel] Iterate prose: add more dialogue
# b2c3d4e [my-novel] Generate prose: all chapters
# c3d4e5f [my-novel] Finalize chapters: variant 3 selected
```

### View Changes

```bash
/git diff

# Shows unstaged changes in unified diff format
```

### Commit Manual Changes

```bash
# If you manually edited files outside AgenticAuthor:

/git commit "Manual edits to chapter 3"

# Creates commit:
# [my-novel] Manual edits to chapter 3
```

**Note:** All AgenticAuthor operations auto-commit. Manual commits only needed for external edits.

---

## Content Management

### Delete Content (Cull)

```bash
# Delete prose (keeps chapters)
/cull prose

# Delete chapters (cascades to prose)
/cull chapters
# Warning: This will also delete prose. Continue? (yes/no)

# Delete treatment (cascades to chapters + prose)
/cull treatment
# Warning: This will also delete chapters and prose. Continue? (yes/no)

# Delete premise (cascades to everything)
/cull premise
# Warning: This will delete ALL generated content. Continue? (yes/no)

# Delete debug files
/cull debug
```

**Cascade Rules:**
- Deleting upstream content requires deleting downstream content
- Ensures no stale content remains
- Git commits allow rollback if needed

---

## Troubleshooting

### No Model Selected

```
Error: No model selected. Use /model <model-name> to select a model.

Solution:
/model grok-4-fast
```

### No Premise Found

```
Error: No premise found. Generate premise first with /generate premise

Solution:
/generate premise "your concept here"
```

### Iteration Target Not Set

```
Error: No iteration target set

Solution:
/iterate premise  # or treatment, chapters, prose
```

### JSON Parsing Error (Premise Iteration)

```
Error: Failed to parse premise JSON: Expecting ',' delimiter: line 5 column 3

LLM Response:
{
  "text": "A wizard discovers magic is breaking"
  "taxonomy": { ... }
}

Solution:
- Check .agentic/debug/iteration/ for full LLM response
- Try iteration again (might be transient LLM error)
- If persistent, report issue
```

### Judge Keeps Rejecting

```
Judge rejected after 3 attempts.

Options:
1. Accept anyway - Content might be good enough, judge is overly strict
2. Retry with clarified feedback - Provide more specific instructions
3. Cancel - Abandon this iteration

Solution:
- Option 1: If changes look reasonable, accept
- Option 2: Clarify your feedback (e.g., "make it darker" → "add grief and loss themes, remove optimistic elements")
- Option 3: Cancel and try different feedback
```

### Git Commit Failed

```
Error: Git commit failed: nothing to commit, working tree clean

Solution:
- This usually means no content actually changed
- Check .agentic/debug/iteration/ to see what LLM generated
- Try iteration again with more specific feedback
```

### Iteration Taking Too Long

**Normal iteration times:**
- Premise: 30-60 seconds
- Treatment: 60-120 seconds
- Chapters: 120-180 seconds
- Prose: 180-300 seconds (depends on chapter count)

**If much longer:**
- Check console for progress updates
- Might be in judge validation loop (shows "Attempt X of 3")
- Large prose regenerations can take 5-10 minutes
- Press Ctrl+C to cancel if needed

### Out of API Credits

```
Error: OpenRouter API error: Insufficient credits

Solution:
- Visit https://openrouter.ai/credits
- Add credits to your account
- Retry operation
```

---

## Best Practices

### 1. Always Clone Before Iteration

```bash
# WRONG:
/open my-precious-novel
/iterate prose
# Risk: Permanent changes to production book

# RIGHT:
/open my-precious-novel
/clone my-precious-novel-test
/iterate prose
# Safe: Testing on clone
```

### 2. Use Specific Feedback

```bash
# VAGUE:
make it better

# SPECIFIC:
add more sensory details in the opening scene and change the protagonist's motivation from revenge to redemption
```

### 3. Review Semantic Diff

Always read the semantic diff before approving:
- Confirms changes match your intent
- Catches unintended changes
- Helps you learn how the system interprets feedback

### 4. Start with Small Iterations

```bash
# WRONG (too many changes at once):
change the protagonist, add subplot, revise ending, adjust pacing, add mystery

# RIGHT (one focused change):
add a subplot about the mentor's secret past

# Then after reviewing:
adjust pacing in act 2 to be faster

# Then:
revise ending to be more ambiguous
```

### 5. Use Judge Feedback

When judge rejects:
- Read the reasoning carefully
- Clarify your feedback
- Be more specific about what you want

### 6. Leverage Iteration History

The system remembers all previous iterations:
- Each iteration builds on previous changes
- No need to repeat earlier feedback
- Can reference earlier changes: "keep the mystery from last iteration but lighten the tone"

### 7. Git is Your Safety Net

```bash
# Before risky iteration:
/git log  # Note current commit SHA

# After iteration you don't like:
git reset --hard <previous-sha>

# Or just:
git reset --hard HEAD~1  # Undo last commit
```

### 8. Model Selection Matters

**Fast iteration (cheaper):**
- x-ai/grok-4-fast
- anthropic/claude-3-haiku

**Quality iteration (more expensive):**
- anthropic/claude-opus-4
- anthropic/claude-3.5-sonnet

**Recommendation:** Use fast model for exploration, quality model for final iterations

---

## Keyboard Shortcuts

**In REPL:**
- `Tab`: Autocomplete commands, genres, models
- `Ctrl+C`: Cancel current operation
- `Ctrl+D`: Exit application
- `↑/↓`: Navigate command history

**In Interactive Model Selector:**
- `Type`: Live fuzzy search
- `↑/↓`: Navigate results
- `Enter`: Select model
- `Esc`: Cancel

**In Interactive Taxonomy Editor:**
- `↑/↓`: Navigate options
- `Space`: Toggle selection
- `Enter`: Save changes
- `Esc`: Cancel

---

## File Structure Reference

```
books/
├── .git/                       # Shared git repo for all projects
├── [project-name]/
│   ├── .agentic/
│   │   ├── logs/              # Session logs
│   │   ├── history            # Command history
│   │   ├── premise_history.json
│   │   └── debug/
│   │       └── iteration/     # Debug output for iterations
│   ├── config.yaml            # Project configuration
│   ├── premise/
│   │   ├── premise_metadata.json  # Single source of truth
│   │   └── iteration_history.json
│   ├── treatment/
│   │   ├── treatment.md
│   │   └── iteration_history.json
│   ├── chapter-beats-variants/
│   │   ├── foundation.yaml
│   │   ├── variant-1/
│   │   ├── variant-2/
│   │   ├── variant-3/
│   │   ├── variant-4/
│   │   └── decision.json
│   ├── chapter-beats/
│   │   ├── foundation.yaml
│   │   ├── chapter-01.yaml
│   │   ├── ...
│   │   └── iteration_history.json
│   ├── chapters/
│   │   ├── chapter-01.md
│   │   ├── ...
│   │   └── iteration_history.json
│   ├── analysis/
│   ├── exports/
│   └── project.yaml
```

---

## FAQ

**Q: Can I iterate on only part of the prose (e.g., chapter 3)?**

A: Not currently. Prose iteration regenerates all prose to maintain consistency. Use targeted feedback like "improve dialogue in chapter 3" to focus changes.

**Q: What happens if I cancel during iteration?**

A: Safe to cancel anytime. No changes committed until you approve semantic diff.

**Q: Can I iterate multiple times in a row?**

A: Yes! Each iteration builds on previous changes. History is tracked.

**Q: How do I undo an iteration?**

A: `git reset --hard HEAD~1` (or use specific commit SHA from `/git log`)

**Q: Does iteration work with short stories?**

A: Yes! Set iteration target to `prose` and provide feedback. Single story.md file is regenerated.

**Q: Can I edit files manually and then iterate?**

A: Not recommended. Iteration regenerates content, overwriting manual edits. Use iteration for all changes or commit manual edits separately.

**Q: Why does judge keep rejecting my iterations?**

A: Try more specific feedback. Judge validates that changes match your request. Vague feedback = vague changes = rejection.

**Q: How much does iteration cost?**

A: Depends on model and content size. Typical costs (grok-4-fast):
- Premise: $0.02-0.05
- Treatment: $0.10-0.20
- Chapters: $0.30-0.50
- Prose: $1.00-3.00 (depends on chapter count)

**Q: Can I iterate on cloned projects without affecting original?**

A: YES! This is the recommended workflow. Clone, iterate on clone, then copy winning content back to original if desired.

---

## Additional Resources

- [CHANGELOG.md](CHANGELOG.md) - Version history and recent changes
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Feature tracking and known issues
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - For developers extending AgenticAuthor
- [CLAUDE.md](../CLAUDE.md) - AI assistant instructions for working with codebase

---

**For issues and feedback:** https://github.com/anthropics/claude-code/issues
