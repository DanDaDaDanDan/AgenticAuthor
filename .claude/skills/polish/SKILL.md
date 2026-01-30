---
name: polish
description: Polish prose via iterative GPT-5.2 Pro critique.
argument-hint: ""
---

Polish a completed story through iterative GPT-5.2 Pro critique and revision.

## Usage

```
/polish
```

## When to Use

After `/generate-prose` has created `06-story.md` for flash fiction, short stories, or novelettes.

---

## Instructions

### Step 1: Detect Project

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is `null` or file doesn't exist, ask user to run `/select-book`
3. Read `books/{project}/project.yaml` to get `length`
4. Verify it's a single-file format (flash_fiction, short_story, or novelette). If chaptered, inform user this skill only works on single-file stories.

### Step 2: Verify Story Exists

Check that `books/{project}/06-story.md` exists. If not, inform user to run `/generate-prose` first.

### Step 3: Spawn Polish Sub-Agent

Use the Task tool to spawn a sub-agent with `subagent_type: "general-purpose"`.

**Sub-agent prompt:**

```
You are the Polish Sub-Agent for AgenticAuthor.

## Task
Iteratively polish `books/{project}/06-story.md` using GPT-5.2 Pro critique.

## Context Reading

Read these files:
1. `books/{project}/06-story.md` — The prose to polish
2. `books/{project}/05-story-plan.md` — Extract `prose_style` and `prose_guidance` from frontmatter

## Polish Loop

Run up to 5 iterations. For each iteration:

### 1. Call GPT-5.2 Pro

Use `mcp__mcp-openai__generate_text` with:
- `model`: "gpt-5.2-pro"
- `reasoning_effort`: "high"
- `max_output_tokens`: 65536
- `prompt`: (see below)

**GPT Prompt Template:**

```
You are a professional fiction editor polishing a {prose_style} story.

## Guidelines
- Preserve the author's voice — improve, don't homogenize
- Sometimes less is more — cutting can improve
- If something isn't clearly better, don't change it
- Avoid verschlimmbessern (making worse by over-improving)
- If the story is already excellent, say so

## Current Story

{full story content}

## Your Task

1. Rate the draft (A+ to C)
2. If below A+: make improvements that genuinely raise quality
3. Return the result in this exact format:

GRADE: [A+, A, A-, B+, B, B-, C+, C, or C-]

CHANGE_MAGNITUDE: [NONE, TRIVIAL, MINOR, MODERATE, SIGNIFICANT]
- NONE = no changes made, story is A+
- TRIVIAL = only punctuation/typo fixes
- MINOR = small wording tweaks, no structural changes
- MODERATE = paragraph-level revisions
- SIGNIFICANT = substantial rewrites

CHANGES:
- [bullet point describing each meaningful change, or "None needed"]

---STORY---
[Complete revised story starting with # Title]
---END---
```

### 2. Parse Response

Extract:
- GRADE
- CHANGE_MAGNITUDE
- CHANGES list
- Story content between ---STORY--- and ---END---

### 3. Check Termination

Stop the loop if ANY of these:
- GRADE is "A+" and CHANGE_MAGNITUDE is "NONE"
- CHANGE_MAGNITUDE is "TRIVIAL" (not worth another pass)
- Story text is identical to previous iteration
- Iteration count reaches 5

### 4. Continue or Finish

If continuing: update story content, increment iteration, loop back.
If stopping: proceed to save.

## Save and Commit

Write final story to `books/{project}/06-story.md`.

Commit (PowerShell):
```powershell
cd books; git add {project}/06-story.md; git commit -m "Polish: {N} iterations, grade {GRADE}"
```

## Return Summary

Return:
```
Polishing complete.
- Iterations: {N}
- Final grade: {GRADE}
- Key improvements:
  - {summarize main changes across iterations}
```
```

### Step 4: Report Result

When the sub-agent returns, display its summary to the user.

Add reminder:
```
To compare with original: git diff HEAD~1 (in books/ directory)
To revert: git checkout HEAD~1 -- {project}/06-story.md
```

---

## Notes

- Uses GPT-5.2 Pro extended thinking via MCP-OpenAI
- Each iteration costs API credits — capped at 5 iterations
- Run `/polish` again if you want additional passes
- Original version preserved in git history
