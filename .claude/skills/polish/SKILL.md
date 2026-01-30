---
name: polish
description: Polish prose via iterative GPT-5.2 Pro critique.
argument-hint: ""
---

Polish a completed story through iterative GPT-5.2 Pro critique.

## Usage

```
/polish
```

---

## Instructions

### Step 1: Detect Project

1. Read `books/active-book.yaml` to get `project:`
   - If null or missing: ask user to run `/select-book`
2. Read `books/{project}/project.yaml` — verify `length` is flash_fiction, short_story, or novelette
   - If chaptered format: inform user this skill only works on single-file stories
3. Check `books/{project}/06-story.md` exists
   - If missing: inform user to run `/generate-prose` first

### Step 2: Spawn Polish Sub-Agent

Use Task tool with `subagent_type: "general-purpose"`:

~~~
You are the Polish Sub-Agent.

## Task
Iteratively polish `books/{project}/06-story.md` using GPT-5.2 Pro.

## Read
`books/{project}/06-story.md`

## Loop (max 5 iterations)

For each iteration:

1. Call `mcp__mcp-openai__generate_text` with:
   - model: "gpt-5.2-pro"
   - reasoning_effort: "xhigh"
   - max_output_tokens: 65536
   - prompt: Build this prompt, replacing {story} with the current story content:

<<<PROMPT
Rate and critique the following story and incorporate feedback to get it to an A+ score. But only incorporate feedback that makes it better and avoid the tendency to verschlimmbessern. Sometimes you improve via subtraction. Return a self-contained markdown file with just the new story (starting with # and the title).

{story}
PROMPT>>>

2. Extract the revised story from GPT's response (from the first # heading to the end)

3. Compare to previous version. Stop if:
   - Text is identical
   - Only trivial changes (whitespace, minor punctuation) that don't warrant another pass

   Otherwise: update story content, continue to next iteration.

## After Loop

Write final story to `books/{project}/06-story.md`.

Commit (PowerShell):
cd books; git add {project}/06-story.md; git commit -m "Polish: {N} iterations"

Return: iteration count and whether it stabilized or hit max iterations.
~~~

### Step 3: Report

Display sub-agent's result. Remind user:
```
git diff HEAD~1 (in books/) to compare
git checkout HEAD~1 -- {project}/06-story.md to revert
```
