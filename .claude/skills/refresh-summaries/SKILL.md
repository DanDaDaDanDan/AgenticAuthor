---
name: refresh-summaries
description: Rebuild summaries from current prose.
argument-hint: ""
---

Rebuild `summaries.md` from the current prose files. Use this when summaries have drifted out of sync with prose (e.g., after manual edits or if iteration didn't update properly).

## Usage

```
/refresh-summaries
```

## Arguments

None. Operates on the active book.

## Instructions

### Step 0: Detect Current Project

**Check for active book first:**

1. Read `books/active-book.yaml` and extract the `project:` value
2. If `project:` is set (not `null`), use that project
3. If `project:` is `null` or file doesn't exist, fall back to directory detection:
   - Look for `project.yaml` in the current directory or parent directories under `books/`
   - If not found, ask the user which project to work on (or suggest `/select-book`)

### Step 1: Determine Format

Read `books/{project}/project.yaml` to get the `length` field:

- **Flash fiction / Short story / Novelette** (`flash_fiction`, `short_story`, `novelette`): Single-file format
- **Novella / Novel / Epic** (`novella`, `novel`, `epic`): Chaptered format

### Step 2: Verify Required Files Exist

**Check structure-plan.md exists:**
- Read `books/{project}/structure-plan.md`
- If not found, inform user: "No structure-plan found. Run `/generate prose` first (it creates structure-plan automatically)."

**For single-file format:**
- Check `books/{project}/short-story.md` exists
- If not, inform user: "No prose found. Run `/generate prose` first."

**For chaptered format:**
- Check `books/{project}/chapters/` directory has at least one chapter
- If empty, inform user: "No chapters found. Run `/generate prose` first."

### Step 3: Read Required Context

**Read these files:**
1. `books/{project}/structure-plan.md` — For frontmatter (taxonomy keys, characters)
2. All prose files:
   - Single-file: `books/{project}/short-story.md`
   - Chaptered: All `books/{project}/chapters/chapter-*.md` files (in order)

**Do NOT read:** premise.md, treatment.md, chapter-plans, or short-story-plan.

The goal is to rebuild summaries purely from the prose as it currently exists.

### Step 4: Generate Summaries

#### For Single-File Format (Flash/Short/Novelette)

Generate `summaries.md` with this structure:

```markdown
---
project: {project-name}
stage: summaries
# Copy ALL taxonomy keys and display names from structure-plan frontmatter verbatim
# Include all single-select (scalars), primary/secondary (objects), and multi-select (arrays)
{...copy all frontmatter from structure-plan...}
---

# Canon Facts (Continuity Anchor)

Keep this concise and canonical (spellings, relationships, rules).

- **Characters:** {names, roles, relationships}
- **Locations:** {place names}
- **World/System Rules:** {rules that must remain consistent}
- **Objects/Terms:** {important items/orgs/jargon}

# Open Threads Ledger (Post-Story)

Most stories should end with no open threads; if any remain, list them explicitly (and consider revising the prose).

| Thread | Introduced | Resolved | Status | Notes |
|--------|------------|----------|--------|------|
| {Question/setup} | Scene {X} | Scene {Y} | resolved/open | {optional} |

# Story Summary

**Summary:** {3-5 sentences covering the complete story arc — derived from actual prose}

**Key Beats:**
- **Opening:** {1 sentence describing how the story actually opens}
- **Complication:** {1 sentence on the main complication as written}
- **Climax:** {1 sentence on the climactic moment}
- **Resolution:** {1 sentence on how it resolves}

**Character Arc:**
- **{Protagonist name from prose}:** {starting state} → {ending state}

**Themes Delivered:**
- {How primary theme actually manifested in the prose}
- {How secondary theme actually manifested}
```

#### For Chaptered Format (Novella/Novel/Epic)

Generate `summaries.md` with this structure:

```markdown
---
project: {project-name}
stage: summaries
# Copy ALL taxonomy keys and display names from structure-plan frontmatter verbatim
# Include all single-select (scalars), primary/secondary (objects), and multi-select (arrays)
{...copy all frontmatter from structure-plan...}
---

# Canon Facts (Continuity Anchor)

Update this section after each chapter. Keep it concise, concrete, and canonical (spellings, relationships, rules).

- **Characters:** {names, roles, relationships, signature details}
- **Locations:** {place names, geography, key features}
- **World/System Rules:** {rules that must remain consistent}
- **Timeline:** {relative/absolute time markers}
- **Objects/Terms:** {important items, organizations, jargon}

# Open Threads Ledger

Update this table after each chapter. This is the main “what must be paid off” index downstream agents should rely on.

| Thread | Introduced | Last Touched | Status | Notes/Payoff |
|--------|------------|--------------|--------|--------------|
| {Question/setup} | Ch {X} | Ch {Y} | open/advancing/resolved | {optional} |

# Chapter Summaries

### Chapter 1: {Title from chapter heading}

**Summary:** {3-5 sentences covering key plot events as they actually occur in this chapter}

**Character States at End:**
- **{Protagonist}:** {emotional/mental state at chapter's end}
- **{Other key characters}:** {state if relevant}

**Threads Updated (this chapter):**
- {Thread introduced/advanced/resolved} — Status: {open/advancing/resolved}

**Canon Facts Added (this chapter):**
- {Names, locations, rules, objects, relationships established in this chapter (add to Canon Facts above)}

**Promises to Reader:**
- {Setups that need payoff — foreshadowing, questions raised, tensions unresolved}

---

### Chapter 2: {Title}

{Same format for each chapter...}

---

{Continue for all chapters...}
```

### Step 5: Extraction Guidelines

When reading prose to extract summaries:

**Summary:** Focus on what actually happens, not what was planned. If the prose diverged from plans, the summary reflects the prose.

**Character Arc (single-file) / Character States (chaptered):** Look at dialogue, internal monologue, and actions. For single-file, capture the full arc (start → end). For chaptered, capture state at each chapter's end.

**The following apply to chaptered format only:**

**Open Threads Ledger:** Track:
- Questions raised but not answered
- Conflicts introduced but not resolved
- Characters mentioned who haven't appeared yet
- Mysteries, secrets, or foreshadowing

Mark threads as:
- `open` — Just introduced
- `advancing` — Progressed but not resolved
- `resolved` — Paid off in this chapter

**Canon Facts:** Extract specifics that must stay consistent:
- Character names (including minor characters)
- Place names and geography
- Rules of magic/technology/world
- Relationships stated
- Physical descriptions given
- Timeline markers

**Promises to Reader:** Note setups that create reader expectations:
- Foreshadowing ("little did she know...")
- Chekhov's guns (objects/skills introduced)
- Questions posed directly or indirectly
- Tensions that need resolution

### Step 6: Write and Commit

Write the regenerated summaries:

```bash
cd books && git add {project}/summaries.md && git commit -m "Refresh: Rebuild summaries.md from current prose for {project}"
```

### Step 7: Report Changes

Summarize what was rebuilt:

**For single-file:**
```
Rebuilt summaries.md for {project}:
- Story summary updated from current prose
- Key beats extracted (opening, complication, climax, resolution)
- Character arc captured
- Themes delivered documented
```

**For chaptered:**
```
Rebuilt summaries.md for {project}:
- {N} chapter summaries regenerated
- {N} total continuity facts extracted
- {N} open threads tracked ({M} resolved, {K} still open)

Chapters processed:
- Chapter 1: {title}
- Chapter 2: {title}
- ...
```

## When to Use This Skill

- After manual edits to prose files
- When summaries.md seems out of sync with actual content
- After recovering from failed iteration
- Before continuing generation if you suspect drift
- To audit continuity before final review

## Notes

- This skill overwrites existing summaries.md entirely
- If you only need to update one chapter's summary, use `/iterate prose` instead
- The skill reads prose only — it does not validate against plans
- Use `/review` after refreshing to check for continuity issues
