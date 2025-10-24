# AgenticAuthor — High-Level Architecture (Codex Overview v2)

This document is a self-contained overview of AgenticAuthor's architecture: how the codebase is organized, the guiding philosophies, data formats chosen, and the end-to-end flow from a blank idea to completed prose and exports.

## Development Philosophies
- Full-Context First: Provide LLMs with all relevant context (premise, treatment, foundation, prior prose). Quality over token thrift.
- Fail Fast, No Fallbacks: If a required artifact or model selection is missing, abort with a clear message. Never silently substitute models or defaults.
- Single-Model Policy: Respect the user's selected model for all operations.
- Global Plan, Local Fidelity: Plan the book's chapter arc in a single call; write prose sequentially with prior prose as authoritative context.
- Deterministic Interfaces: Prompts require strict YAML/JSON/Markdown shapes so the app can parse and validate reliably.
- Traceability by Default: Every project lives under `books/<name>/` with auto-commits to a shared repo; analysis and debug artifacts are saved to disk.
- Quality Over Word Counts: Targets guide breadth; chapters "breathe" to serve the story.
- Creative vs. Mathematical Separation: Foundation stores LLM-generated creative content (genre, themes, characters, world); structure values (word count, chapter count) are always calculated from taxonomy via DepthCalculator, never stored in foundation.

## File Types and Rationale
- Markdown (`.md`): Prose chapters and human-readable documentation. Great for diffs and editors.
- YAML (`.yaml`): Structured planning (foundation, chapter beats) with readable multi-line content. IMPORTANT: YAML files are GENERATED from LLM markdown output via MarkdownExtractor (see "Markdown-First Storage" section).
- JSON (`.json`): Machine-readable metadata (premise metadata, taxonomy selections, models, analysis results).
- Jinja2 (`.j2`): LLM prompt templates with variable substitution and logic.
- RTF (`.rtf`): Publishing-friendly export format.

## Repository Layout (What each file/folder does)
- ARCHITECTURE.md — This file: high-level architecture and design documentation.
- CLAUDE.md — Contributor guidance for Claude Code (commit discipline, verification checklist, operating principles).
- AGENTS.md — Repository guidelines (structure, commands, style, testing, PR rules).
- config.yaml — User-side defaults (paths, runtime preferences).
- books/ — All user projects (each is a working tree with versioned outputs; shared .git at this level).
- .agentic/ — Global debug/logs directory at repository root (NOT in books/).
  - logs/ — Session logs (agentic_YYYYMMDD.log).
  - debug/ — Debug artifacts organized by project name.
  - history — REPL command history.
  - backups/ — Automated backups (e.g., copy_edit originals).
- misc/ — Miscellaneous support assets (example backmatter, dedications).
- pyproject.toml — Project definition, Python >=3.11, dependencies, tools (Black/Ruff/MyPy/PyTest/Coverage), CLI entry `agentic`.
- taxonomies/ — Genre/form taxonomies (JSON files: fantasy, romance, sci-fi, horror, contemporary, historical, literary, young-adult, urban-fantasy, romantasy, etc.) used to seed consistent parameters.
- tests/ — Test harness (needs rebuilding for v0.3.0+).
- src/ — Application code (see below).

### src/ (Application Code)
- src/__init__.py — Package marker.

- src/api/
  - __init__.py — API package marker.
  - auth.py — API key validation (must start with `sk-or-`).
  - models.py — Model metadata (context length, pricing, selection helpers).
  - openrouter.py — Async OpenRouter client (model discovery, completion, streaming, retry, token budgeting).
  - streaming.py — Stream handling and token counters for incremental output.

- src/cli/
  - __init__.py — CLI package marker.
  - main.py — Typer entry (`agentic`, `repl`, `new`).
  - interactive.py — REPL: routes `/generate`, `/analyze`, `/model`, `/iterate`, etc.; orchestrates flows and logging.
  - command_completer.py — Command metadata and tab-completion.
  - model_selector.py — Interactive model selection.
  - taxonomy_editor.py — Interactive taxonomy editing.
  - auto_suggest.py — Input assistance utilities.

- src/config/
  - __init__.py — Config package marker.
  - constants.py — App constants.
  - settings.py — Settings loader (`get_settings()`), environment/config resolution.

- src/export/
  - __init__.py — Export package marker.
  - md_exporter.py — Markdown export helpers.
  - rtf_exporter.py — RTF export for word processors.
  - dedication_generator.py — Dedication text generation.

- src/generation/
  - __init__.py — Generation package marker.
  - premise.py — Premise generation and taxonomy integration.
  - treatment.py — Treatment (LOD2) generation from premise.
  - chapters.py — Foundation extraction and single-shot chapter outline generation; saves `chapter-beats/`.
  - variants.py — Multi-variant chapter generation (temperature fan-out).
  - judging.py — LLM judging across variants to pick the winner.
  - prose.py — Sequential prose generation with fidelity validation and surgical iteration.
  - short_story.py — Short-form flow (≤2 chapters).
  - depth_calculator.py — Structural sizing (acts, chapter count, targets).
  - lod_context.py — Context assembly for LOD prompts.
  - copy_editor.py — Copy-editing pass utilities.
  - kdp_metadata.py — Publishing metadata generation.
  - taxonomies.py — Taxonomy loading and management for genre-specific generation.
  - cull.py — Content deletion system for pruning generated artifacts at various LOD levels.
  - analysis/
    - base.py — Analysis interfaces and data types.
    - unified_analyzer.py — Single-pass, JSON-structured editorial analysis (duplicates, strengths, next steps).
    - treatment_deviation_analyzer.py — Checks foundation against treatment for contradictions.
    - analyzer.py — Coordinator that collects content/context and renders reports to `analysis/`.
  - iteration/ (v0.4.0) — Natural language iteration system (1119 total lines)
    - iterator.py — Main coordinator for holistic regeneration with judge validation loop (795 lines).
    - history.py — Iteration history tracking per LOD level (feedback + semantic summaries for context) (117 lines).
    - judge.py — LLM judge validation (validates generated content matches feedback before showing user) (116 lines).
    - semantic_diff.py — Human-readable change summaries (not raw git diffs) (85 lines).

- src/models/
  - __init__.py — Models package marker.
  - project.py — Project abstraction: paths, IO for premise/treatment/foundation/beats/prose; migrations; word counts; analysis paths.
  - story.py — Story structures and helpers.
  - taxonomy.py — Taxonomy models and formatting utilities.

- src/prompts/
  - __init__.py — `PromptLoader` (Jinja environment, [SYSTEM]/[USER] parsing, metadata access).
  - config.yaml — Prompt metadata (format, temperature, token hints).
  - generation/ — Core LOD generation prompts:
    - premise_main.j2, premise_with_taxonomy.j2 — Premise generation.
    - treatment_generation.j2 — Treatment expansion from premise.
    - chapter_foundation.j2 — Extract structured foundation (metadata/characters/world) from treatment.
    - chapter_single_shot.j2 — Plan all chapters in one pass (anti-redundancy guardrails, act anchors).
    - prose_generation.j2 — Write chapters as dramatized scenes from beats with prior prose context.
    - prose_iteration.j2 — Surgical rewrite for validation fixes (legacy/validation-focused).
    - dedication_generation.j2 — Book dedication generation.
    - premise_iteration.j2, treatment_iteration.j2, chapter_iteration.j2 — Full LOD level regeneration with feedback and history context.
    - prose_full_iteration.j2 — Full prose regeneration with feedback (distinct from surgical prose_iteration.j2).
  - editing/ — Editing prompts:
    - copy_edit.j2 — Copy editing pass.
  - kdp/ — Publishing metadata prompts:
    - author_bio.j2, description.j2, keywords.j2 — KDP publishing assets.
  - analysis/ — Analysis and evaluation prompts:
    - chapter_judging.j2 — Multi-variant chapter evaluation.
    - semantic_diff.j2 — Human-readable change summary generation.
    - unified_analysis.j2 — Editorial analysis (duplicates, strengths, next steps).
    - treatment_deviation.j2 — Foundation vs treatment consistency check.
    - genre_detection.j2 — Automatic genre identification.
    - taxonomy_extraction.j2 — Extract taxonomy from existing content.
  - validation/ — Validation prompts:
    - iteration_fidelity.j2 — Judge validation for iteration system.
    - prose_fidelity.j2 — Prose validation against beats.
    - treatment_fidelity.j2 — Treatment validation against premise.
  - iteration/ — Iteration-specific utility prompts:
    - premise_revision.j2 — Premise revision utilities.
    - taxonomy_update.j2 — Taxonomy update utilities.

- src/storage/
  - __init__.py — Storage package marker.
  - git_manager.py — Shared repo management under `books/` (init, add, commit, log, rollback).

- src/utils/
  - __init__.py — Utils package marker.
  - tokens.py — Token estimation and headroom planning for prompts/responses.
  - yaml_utils.py — Robust YAML parsing and sanitization for LLM outputs.
  - markdown_extractors.py — Extracts structured beats from Markdown chapter summaries (MarkdownExtractor).
  - session_logger.py — Intercepts console/LLM I/O to logs and `.agentic/debug`.
  - logging.py — Log setup, rotation, and cleanup helpers.

## Project Layout on Disk (`books/<project>/`)
- project.yaml — Project metadata (name, model, counts, timestamps).
- premise/ — Premise directory:
  - premise_metadata.json — Selected premise and taxonomy metadata.
  - premises_candidates.json — Batch-generated premise candidates.
  - iteration_history.json — Premise iteration history (feedback + semantic summaries).
- treatment/ — Treatment directory:
  - treatment.md — Main treatment document.
  - treatment_metadata.json — Treatment metadata.
  - iteration_history.json — Treatment iteration history.
  - combined.md — Snapshot (when requested).
- chapter-beats/ — Chapter structure directory:
  - foundation.yaml — Structured foundation (metadata, characters, world).
  - foundation.md — Foundation in markdown format.
  - chapter-NN.md — Per-chapter beat sheets (markdown).
  - iteration_history.json — Chapter structure iteration history.
  - combined.md — Snapshot of foundation + all chapter beats.
- chapter-beats-variants/ — Multi-variant generation artifacts:
  - foundation.yaml, foundation.md — Shared foundation.
  - variant-N/ — Per-variant chapter structures.
  - decision.json — Variant selection decision.
  - combined.md — Snapshot of all variants with foundation.
- chapters/ — Final prose chapters:
  - chapter-NN.md — Individual chapter prose files.
  - iteration_history.json — Prose iteration history.
  - combined.md — Optional full prose snapshot (when requested).
- analysis/ — Editorial analysis reports as Markdown.
- exports/ — Publishing artifacts (frontmatter, RTF/MD exports).

NOTE: Iteration debug storage is at repository root: `.agentic/debug/<project-name>/iteration/` (all attempts, judge verdicts).

## Runtime Flow (New Book → Finished Book)
1. Initialize
   - Set `OPENROUTER_API_KEY` (must start with `sk-or-`).
   - Run `agentic` and `/new <name>` to create `books/<name>/` (shared Git initialized at `books/` if needed).
2. Premise & Taxonomy
   - Generate or select a premise; choose taxonomy options (genre, length scope, tone). Persist to `premise/premise_metadata.json`.
3. Treatment (LOD2)
   - Expand premise into a structured treatment prose document (`treatment/treatment.md`).
4. Foundation
   - Extract structured foundation (metadata, characters, world) from treatment (`chapter-beats/foundation.yaml` or `foundation.md`).
5. Chapters (Global Plan)
   - Generate all chapter outlines in one call (`chapter_single_shot.j2`) with act anchors and anti-redundancy guardrails; save per-chapter beats to `chapter-beats/chapter-NN.md`.
   - `--auto` mode lets the LLM pick an appropriate chapter count (act weights passed); no target word counts shown.
   - Optionally generate multiple variants; `chapter-beats-variants/combined.md` consolidates foundation and all variant beats.
6. Prose (Sequential, strict)
   - Write chapters in order using prior chapters' FULL prose as authoritative context.
   - Prompt includes fenced sections and requires current/future beat files; missing beats or files are treated as errors (no silent fallbacks).
   - Save `chapters/chapter-NN.md` and update `chapters/combined.md` when requested.
7. Copy Edit & Polish
   - Run copy editing and generate KDP metadata as needed.
8. Export & Deliver
   - Export to Markdown/RTF; assemble publishing metadata.
9. Analyze & Iterate
   - Use unified/treatment-deviation analysis to identify issues and guide targeted revisions.
10. Natural Language Iteration (v0.4.0)
    - Set iteration target (`/iterate premise|treatment|chapters|prose`) or auto-set after generation.
    - Provide natural language feedback (no `/` prefix): "make it darker", "add more dialogue in chapter 3".
    - System regenerates content holistically with full context (premise, treatment, existing chapters/prose).
    - LLM judge validates changes match feedback (up to 3 attempts with retry logic).
    - Human-readable semantic diff displayed for approval (not raw git diff).
    - Auto-commit to git on approval with project-prefixed message: `[project-name] Iterate target: feedback`.
    - Iteration history tracked per LOD level (`iteration_history.json`) for cumulative context.
    - Downstream cascade handling: editing premise prompts to cull or keep treatment/chapters/prose.
    - Debug storage: all attempts saved to `.agentic/debug/<project-name>/iteration/` with judge verdicts.
    - Safety warning on first iteration (test on cloned projects only).

## How Components Fit Together
- CLI orchestrates flows, displays streaming output, and records logs.
- Generation modules render Jinja prompts via `PromptLoader` and call OpenRouter through the async API client. Prompts use hard fences to avoid source bleed (e.g., TREATMENT, FOUNDATION, TAXONOMY, CHAPTER OUTLINE, PREVIOUS PROSE).
- Planning artifacts (YAML/Markdown) and prose (Markdown) are persisted per project, enabling repeatable runs and manual edits.
- Validators and analyzers provide structured feedback used for surgical iterations.
- Git integration at `books/` ensures a traceable, shared history across projects.

## Error Handling & Guardrails
- Early checks for missing artifacts (premise, treatment, beats) and invalid API keys.
- Strict prompt contracts (YAML/JSON/Markdown) and fenced context; robust parsing where applicable. Prose generation enforces presence of real beat files (current + future) and beats/key_events are required.
- Analysis-driven iteration loops with caps and user choice to continue, fix, or abort.

## Extending the System
- New prompts: add under `src/prompts/<area>/` and wire in via the relevant generator.
- New analyzers: implement under `src/generation/analysis/` and route through the coordinator.
- New exporters: add under `src/export/` and expose via CLI.
- New taxonomy sets: place in `taxonomies/` and integrate in `generation/taxonomies.py`.

This overview is self-contained and reflects the current source tree and on-disk behavior to onboard contributors and guide design decisions.

## Markdown-First Storage and Optional Extraction

Core Philosophy: LLMs produce higher quality outputs in markdown. We store raw LLM markdown (foundation.md, chapter-NN.md) and extract structure as needed.

Layers:
1. Prompt (`.j2`) → LLM generates markdown with clear headings/fields and fences.
2. Raw storage (`.md`) for foundation/beat sheets; prose is always `.md`.
3. Optional extraction (`MarkdownExtractor`) to dicts/YAML for validation/analysis.

Why:
- Creative fidelity and fewer formatting failures.
- Easy human review and diffs.
- Structure still available when needed for validation or downstream tools.

File Type Summary:
- `.j2` — Jinja2 prompt templates
- `.json` — Metadata/decisions
- `.md` — Canonical storage for foundation, beats, variants, and prose
- `.yaml` — Optional/legacy structured artifacts (extracted when necessary)

Implementation: See `src/utils/markdown_extractors.py` (MarkdownExtractor) and callers in generation modules.

## Architecture Decision Records (ADR)

### ADR-001: Shared Git Repository at books/ Level
**Decision:** Single shared git repository at `books/.git` instead of per-project repos.
**Rationale:** Simplifies management, enables cross-project history, reduces overhead.
**Impact:** All projects commit to shared repo with project-prefixed commit messages.

### ADR-002: Markdown-First with Optional YAML Extraction
**Decision:** Store foundation and beats as `.md` files, extract to YAML only when needed.
**Rationale:** LLMs produce higher quality markdown; YAML extraction is brittle.
**Impact:** Better creative fidelity, easier diffs, backward compatible with legacy YAML.

### ADR-003: Global .agentic Directory
**Decision:** Single `.agentic/` directory at repository root (not per-project).
**Rationale:** Centralized debugging, shared logs, simpler cleanup.
**Impact:** Debug artifacts organized by project name within shared structure.

### ADR-004: Iteration System Judge Validation
**Decision:** LLM judge validates regenerated content before showing to user.
**Rationale:** Prevents wasted iterations from hallucination or misunderstood feedback.
**Impact:** Higher success rate, better UX, but adds token cost per iteration.

### ADR-005: No Default/Fallback Models
**Decision:** Fail early if no model selected; never substitute defaults.
**Rationale:** Respect user choice, prevent unexpected costs/quality issues.
**Impact:** Users must explicitly select model via `/model` command.
