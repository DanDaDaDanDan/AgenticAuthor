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

## Execution

1. **Detect the current project:**
   - Read `books/active-book.yaml` and extract the `project:` value
   - If `project:` is `null` or file doesn't exist, ask user to run `/select-book`

2. **Determine the stage** (from argument or infer from files):
   - If `stage` argument provided → use it
   - Else if `books/{project}/01-premise.md` missing → `premise`
   - Else if `books/{project}/03-treatment.md` missing → `treatment`
   - Else → `prose`

3. **Invoke the stage skill** using the Skill tool:
   - `premise` → `Skill(skill: "generate-premise")`
   - `treatment` → `Skill(skill: "generate-treatment")`
   - `prose` → `Skill(skill: "generate-prose")`

This skill is purely a router. All generation logic lives in the stage-specific skills.
