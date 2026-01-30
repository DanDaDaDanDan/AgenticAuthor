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

**Sub-agent prompt template:**

~~~
You are the Polish Sub-Agent for AgenticAuthor.

## Task
Iteratively polish `books/{project}/06-story.md` using GPT-5.2 Pro critique.

## Context Reading

Read these files:
1. `books/{project}/06-story.md` — The prose to polish
2. `books/{project}/05-story-plan.md` — Extract `prose_style`, `prose_style_key`, and `prose_guidance` from frontmatter

## Polish Loop

Run up to 5 iterations. For each iteration:

### 1. Call GPT-5.2 Pro

Use `mcp__mcp-openai__generate_text` with:
- model: "gpt-5.2-pro"
- reasoning_effort: "xhigh"
- max_output_tokens: 65536
- prompt: Build from the template below, filling in {prose_style} and {story_content}

**GPT Prompt Template:**

You are a professional fiction editor polishing a {prose_style} story.

GUIDELINES:
- Preserve the author's voice — improve, don't homogenize
- Sometimes less is more — cutting can improve
- If something isn't clearly better, don't change it
- Avoid verschlimmbessern (making worse by over-improving)
- If the story is already excellent, say so and return it unchanged
{Include any relevant prose_guidance notes about what to preserve or avoid}

CURRENT STORY:

{story_content}

YOUR TASK:

1. Rate the draft (A+ to C)
2. If below A+: make improvements that genuinely raise quality
3. Return the result in this exact format:

GRADE: [A+, A, A-, B+, B, B-, C+, C, or C-]

CHANGE_MAGNITUDE: [NONE, TRIVIAL, MINOR, MODERATE, SIGNIFICANT]
- NONE = no changes made, story is A+
- TRIVIAL = only punctuation/typo fixes
- MINOR = small wording tweaks
- MODERATE = paragraph-level revisions
- SIGNIFICANT = substantial rewrites

CHANGES:
- [bullet point for each meaningful change, or "None needed"]

===STORY===
[Complete revised story starting with # Title]
===END===

### 2. Parse Response

Extract from GPT's response:
- GRADE
- CHANGE_MAGNITUDE
- CHANGES list
- Story content between ===STORY=== and ===END===

### 3. Check Termination

Stop the loop if ANY of these:
- CHANGE_MAGNITUDE is "NONE" (story is A+, no changes needed)
- CHANGE_MAGNITUDE is "TRIVIAL" (diminishing returns)
- Story text is identical to previous iteration
- Iteration count reaches 5

### 4. Continue or Finish

If continuing: update story content with the revised version, loop back.
If stopping: proceed to save.

## Save and Commit

Write final story to `books/{project}/06-story.md`.

Commit (PowerShell):
cd books; git add {project}/06-story.md; git commit -m "Polish: {N} iterations, grade {GRADE}"

## Return Summary

Return:
- Iterations completed: {N}
- Final grade: {GRADE}
- Key improvements: {summarize main changes across all iterations}
~~~

### Step 4: Report Result

When the sub-agent returns, display its summary to the user.

Add:
```
To compare with original: git diff HEAD~1 (in books/ directory)
To revert: git checkout HEAD~1 -- {project}/06-story.md
To check API costs: use mcp__mcp-openai__get_cost_summary
```

---

## Notes

- Uses GPT-5.2 Pro with extended thinking (reasoning_effort: xhigh)
- Each iteration costs API credits — capped at 5 iterations
- Run `/polish` again if you want additional passes
- Original version preserved in git history
