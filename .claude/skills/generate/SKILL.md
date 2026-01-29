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

## Note

Users can also invoke stage skills directly:
- `/generate-premise` (same as `/generate premise`)
- `/generate-treatment` (same as `/generate treatment`)
- `/generate-prose` (same as `/generate prose`)

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

Do NOT generate content directly. This skill is purely a router.
