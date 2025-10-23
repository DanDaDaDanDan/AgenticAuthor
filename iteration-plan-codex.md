# Iteration Plan Codex

This document proposes a general, LLM‑assisted system to iteratively improve premise, treatment, and chapter beats. It balances creative freedom with structural safety, produces minimal diffs, and keeps every step traceable in Git and folder‑level combined.md snapshots.

## Goals
- Human‑in‑the‑loop iteration across targets: premise, treatment, chapter beats (and eventually prose).
- Small, surgical changes with explicit intent and measurable improvement.
- Deterministic context packaging (fenced blocks) to avoid source bleed.
- Clear rollback, audit trail, and per‑folder combined.md snapshots.

## Principles
- Intent → Plan → Patch → Validate → Present → Apply → Commit.
- Minimal change, maximal clarity: small patches over full rewrites.
- Preservation of invariants: required sections/fields must remain intact.
- Markdown‑first: patch sections/headings/fields, not free‑form blobs.
- Fenced context only; never mix sources.

## Scope & Targets
- premise (premise_metadata.json: premise text + fields)
- treatment (`treatment/treatment.md`)
- chapter beats (`chapter-beats/foundation.md`, `chapter-beats/chapter-NN.md`)

Out‑of‑scope (v1): automatic chapter‑prose iteration (keep manual for now). The same pattern can extend to prose later.

## Iteration Types (LLM‑recognized)
- modify: change a specific section/beat (e.g., “raise stakes in midpoint”).
- add: add missing section/beat (e.g., “add Act I reversal pre‑midpoint”).
- remove: remove redundant/duplicated beats.
- reorder: move beats/sections to improve pacing.
- regenerate: carefully rebuild a bounded section (e.g., Act II summary only).
- clarify: minor rewording for clarity/consistency.

## Context Packaging (Fenced)
Pass ONLY what’s needed, with hard fences:
- <<<PREMISE START/END>>>
- <<<TAXONOMY (CONSTRAINTS) START/END>>>
- <<<TREATMENT START/END>>>
- <<<FOUNDATION START/END>>>
- <<<CHAPTER OUTLINES START/END>>>
For chapter‑level iteration, also fence a concise Chapter Index and the specific chapter(s) to touch as <<<CURRENT CHAPTER OUTLINE>>>.

## Patch DSL (JSON)
The LLM outputs a minimal patch plan, not full text. We apply locally.

Structure:
```
{
  "target": "treatment|chapter_beats|premise",
  "scope": "global|act|chapter|section",
  "edits": [
    {
      "op": "replace|insert_after|insert_before|remove|move|rename",
      "selector": {
        "type": "heading|chapter|field|beat",
        "value": "Act II" | 5 | "Themes" | "Beat: ‘interrogation → confession’"
      },
      "payload": {
        "text": "markdown snippet (for replace/insert)",
        "to": {"type": "chapter", "value": 7}   // for move
      },
      "rationale": "why this improves pacing/clarity"
    }
  ],
  "invariants": [
    "Keep all required sections (Metadata/Characters/World)",
    "Avoid duplicate beats; each chapter must add new information"
  ]
}
```

Selectors (examples):
- treatment: {type:"heading", value:"Act II"}
- chapter: {type:"chapter", value: N}
- field: {type:"field", value:"Themes"}
- beat: {type:"beat", value:"…"} (exact match in chapter outline)

Patch Application Order:
1) validate selectors exist, 2) apply ops in order, 3) re‑validate structure, 4) write file(s), 5) re‑run analyzers.

## Prompts (Outline)
SYSTEM: “You are a surgical editor. Return ONLY valid JSON patch per schema. Do not rewrite full text.”

USER:
- Fenced CURRENT state (only the parts to change) and TAXONOMY constraints.
- High‑level goal (human intent) + optional analysis findings.
- Explicit schema reminder + invariants.

## Validation & Measurement
- Run analyzers before/after and show delta: duplicate reduction, pacing notes, key event uniqueness.
- Structural checks:
  - Treatment must retain 3‑act sections if they existed.
  - Foundation must preserve metadata/characters/world headings.
  - Chapters must retain: Act, POV, Operation Type, Key Events, Character Development, Emotional Beat, New Information, Hook Type.
- If invariants violated, reject patch and show reasons.

## UX & CLI (Proposed)
- /iterate <premise|treatment|chapter N|chapters> <instruction>
  - Example: `/iterate treatment "raise midpoint stakes and reduce Act II repetition"`
- Flow:
  1) Capture intent string
  2) Build context bundle (fenced)
  3) LLM → JSON patch plan
  4) Dry‑run apply; show human diff (side‑by‑side or unified)
  5) Approve → write files + update folder‑level combined.md
  6) Re‑analyze and display improvements
  7) Git commit: `Iterate: <target> – <summary>`
- Flags:
  - `--dry-run` (default on): preview only
  - `--apply` (apply immediately)
  - `--limit` (acts/chapters to touch)
  - `--revert N` (quick rollback)

## Storage & Traceability
- Every applied iteration writes a Git commit with target + summary.
- Folder‑level combined.md updated after each successful iteration:
  - treatment/combined.md (premise + taxonomy + treatment)
  - chapter-beats/combined.md (adds foundation + beats)
- Keep patch plan files under `.agentic/patches/<timestamp>_<target>.json` for audit.

## Safety Rails
- Hard stop if target files missing (e.g., current/future chapter beats must exist).
- No deletion of required sections; minimal textual span for replacements.
- Auto‑reject patches that introduce duplicate beats or regress analyzer scores significantly.

## Open Questions
1) Review vs. auto‑apply: default preview is safer; should we allow `--apply` for small/low‑risk edits?
2) Patch DSL richness: do we need more ops (e.g., split/merge beats), or is the initial set sufficient?
3) Iteration scope limits: should we cap edits per run (e.g., <= 5 ops) to keep diffs human‑readable?
4) Analyzer gates: what minimum improvement threshold should gate acceptance (e.g., remove ≥1 duplicate, no new high/critical issues)?
5) Variant-aware iteration: do we want “iterate on variants” (e.g., produce 2 alternative patch plans and pick one)?
6) Prose iteration: do we apply the same patch‑plan approach to prose later, or keep chapter iteration feeding into prose regeneration?

## Next Steps (Implementation Sketch)
- Add: `IterationCoordinator` with phases (intent → plan → patch → validate → present → apply → commit).
- Add: Patch applicators for treatment.md and chapter‑beats/*.md (heading/beat aware).
- Add: Prompt templates for iteration targets returning JSON per schema.
- Add: CLI `/iterate` with dry‑run UI and diff display; write patch files under `.agentic/patches/` and update folder combined.md.
- Wire: Analyzer comparison before/after; show deltas; gate acceptance when configured.

---
If these principles align, I’ll scaffold the coordinator, patch DSL schema, and initial templates next. Please confirm preferences on review vs. auto‑apply, gating thresholds, and whether to include “variant‑aware iteration” in v1.

