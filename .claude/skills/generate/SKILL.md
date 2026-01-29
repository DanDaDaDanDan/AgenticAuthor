---
name: generate
description: Route to stage-specific generation (premise, treatment, prose).
argument-hint: "[stage]"
---

Route generation to a stage-specific skill.

## Usage

```
/generate [stage]
```

## Arguments

- `stage`: One of `premise`, `treatment`, or `prose`

---

## Routing

**Recommended:** Use the stage-specific skills directly:
- `/generate-premise` (same as `/generate premise`)
- `/generate-treatment` (same as `/generate treatment`)
- `/generate-prose` (same as `/generate prose`)

If invoked as `/generate` with no stage, infer the next stage from existing files:
1. If `books/{project}/01-premise.md` is missing → `premise`
2. Else if `books/{project}/03-treatment.md` is missing → `treatment`
3. Else → `prose`

**Dispatch rules:**
- `premise` → invoke the `/generate-premise` skill
- `treatment` → invoke the `/generate-treatment` skill
- `prose` → invoke the `/generate-prose` skill

Do NOT generate content directly in this skill. Always dispatch to the stage skills.

---

## Step 0: Detect Current Project

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value from the YAML block
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, fall back to directory detection:
   - Look for `project.yaml` in the current directory or parent directories under `books/`
   - If not found, ask the user which project to work on (or suggest `/select-book`)

Read `books/{project}/project.yaml` to get project metadata (genre, length, title, author).

---

## Execution

1. Detect the current project (Step 0 above)
2. Parse the `stage` argument (or infer from existing files if not provided)
3. Invoke the corresponding skill:
   - `premise` → `/generate-premise`
   - `treatment` → `/generate-treatment`
   - `prose` → `/generate-prose`

This skill is purely a router. All generation logic lives in the stage-specific skills.
