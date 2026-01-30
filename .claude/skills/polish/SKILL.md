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
2. Read `books/{project}/project.yaml` — verify it's flash_fiction, short_story, or novelette
3. Verify `books/{project}/06-story.md` exists

### Step 2: Spawn Polish Sub-Agent

Use Task tool with `subagent_type: "general-purpose"`:

~~~
You are the Polish Sub-Agent.

## Task
Iteratively polish `books/{project}/06-story.md` using GPT-5.2 Pro.

## Read
- `books/{project}/06-story.md`

## Loop (max 5 iterations)

For each iteration:

1. Call `mcp__mcp-openai__generate_text` with:
   - model: "gpt-5.2-pro"
   - reasoning_effort: "xhigh"
   - max_output_tokens: 65536
   - prompt: (use this exact prompt, with {story} replaced by current story content)

---
Rate and critique the following story and incorporate feedback to get it to an A+ score. But only incorporate feedback that makes it better and avoid the tendency to verschlimmbessern. Sometimes you improve via subtraction. Return a self-contained markdown file with just the new story (starting with # Title).

{story}
---

2. Extract the story from GPT's response (everything from # Title onward)

3. Compare new story to previous version:
   - If identical or nearly identical (trivial whitespace/punctuation only): stop loop
   - Otherwise: update story, continue

## After Loop

Write final story to `books/{project}/06-story.md`.

Commit:
cd books; git add {project}/06-story.md; git commit -m "Polish: {N} iterations"

Return: iteration count and brief note on whether it stabilized or hit max.
~~~

### Step 3: Report

Display sub-agent's result. Remind user:
```
git diff HEAD~1 (in books/) to compare
git checkout HEAD~1 -- {project}/06-story.md to revert
```
