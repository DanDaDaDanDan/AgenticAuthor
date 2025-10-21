# AgenticAuthor — High‑Level Architecture (Codex Overview v2)

This document is a self‑contained tour of AgenticAuthor’s architecture: how the codebase is organized, the design philosophies that guide it, the data formats in play, and the end‑to‑end flow from a blank idea to a finished manuscript and exportable assets.

## Design Philosophies
- Full‑Context First: Always provide the LLMs with the fullest useful context (premise, treatment, foundation, prior prose). Quality beats token thrift.
- Fail Fast, No Fallbacks: If required inputs or a selected model are missing or incompatible, stop immediately with actionable errors.
- Single‑Model Policy: Respect the user’s selected model across operations; never silently substitute.
- Quality Over Word Counts: Targets are guidance, not quotas. Scenes breathe; validation checks fidelity, not length.
- Global Plan, Local Fidelity: Plan chapters globally in one pass to prevent duplication, then write prose sequentially with prior prose as authority.
- Deterministic Interfaces: Prompts demand structured outputs (YAML/JSON) to allow robust parsing and safe iteration.
- Traceability by Default: Projects live in `books/<name>/` with auto‑commits to a shared repo; analysis reports and debug dumps are written to disk.
- Prompt Discipline: Jinja templates separate [SYSTEM]/[USER] text; strict YAML/JSON rules avoid parsing errors and hallucinated wrappers.

## Data & File Types (Why these formats)
- Markdown (`.md`): Human‑readable prose chapters and documentation; easy diffing and editing.
- YAML (`.yaml`): Hierarchical story structure (foundation and chapter outlines) with readable multi‑line blocks.
- JSON (`.json`): Machine‑consumable metadata (premise metadata, taxonomy selections, model lists, analysis outputs).
- RTF (`.rtf`): Publishing‑friendly export for word processors.

## File Hierarchy (key files and roles)
- Top‑level
  - `README.md`: Quick start and feature overview.
  - `CLAUDE.md`: Operating principles, verification checklist, core flow, and command cheatsheet.
  - `AGENTS.md`: Contributor guide and workflow rules (commit discipline).
  - `pyproject.toml`: Python 3.11 project; tooling (Black, Ruff, MyPy, PyTest, Coverage) and CLI entrypoint `agentic`.
  - `config.yaml`: Default runtime settings; user‑level overrides come from environment or project config.
  - `docs/`: Deep dives (architecture experiments, changelogs, user/dev guides, verification reports).
  - `books/`: All user projects (each is a self‑contained workspace with versioned artifacts).
  - `taxonomies/`: Genre and form taxonomies used to seed consistent parameters.
  - `logs/`: Session and operational logs.

- `src/` (application code)
  - `cli/`
    - `main.py`: Typer app entry; exposes commands (`agentic`, `repl`, `new`).
    - `interactive.py`: REPL loop, command routing (`/generate`, `/analyze`, `/model`, etc.).
    - `command_completer.py`, `auto_suggest.py`: CLI UX helpers.
    - `model_selector.py`, `taxonomy_editor.py`: Interactive selection tools.
  - `api/`
    - `openrouter.py`: Async client with streaming, token budgeting, retries, and model discovery.
    - `streaming.py`: Stream handlers (incremental display, token counters).
    - `models.py`: Model metadata and utilities (context/output capacities, pricing).
    - `auth.py`: API key validation (must start with `sk-or-`).
  - `config/`
    - `settings.py`, `constants.py`: App settings (base URL, dirs, defaults) loaded via `get_settings()`.
  - `models/`
    - `project.py`: Project layout, file IO (foundation, beats, prose), migration, counters, paths.
    - `story.py`, `taxonomy.py`: Structured story entities and taxonomy helpers.
  - `prompts/`
    - `__init__.py`: `PromptLoader` (Jinja environment, [SYSTEM]/[USER] parsing, template metadata).
    - `config.yaml`: Prompt‑level settings (format, temperature, etc.).
    - `generation/`: LOD prompts for foundation, chapters, prose, treatment.
    - `editing/`: Copy edit prompts.
    - `kdp/`: Author bio, description, keywords prompt templates.
  - `generation/`
    - `premise.py`, `treatment.py`: Premise/treatment generation with taxonomy integration.
    - `chapters.py`: Chapter foundation + single‑shot chapter outlines with anti‑duplication guardrails; validation and YAML robustness; writes `chapter-beats/`.
    - `variants.py`, `judging.py`: Multi‑variant chapter generation and LLM judging → selects best outline.
    - `prose.py`: Sequential prose generator (respects prior prose, validates fidelity, iterates surgically when needed).
    - `lod_context.py`, `depth_calculator.py`: LOD scaffolding and structural sizing (acts/chapters).
    - `copy_editor.py`, `kdp_metadata.py`, `cull.py`, `short_story.py`, `taxonomies.py`: Polishing, metadata, utilities, and short‑form flow.
  - `storage/`
    - `git_manager.py`: Shared repo integration at `books/` root; init, add, commit, log, and safeguards.
  - `export/`
    - `md_exporter.py`, `rtf_exporter.py`, `dedication_generator.py`: Publishing artifacts.
  - `utils/`
    - `tokens.py`: Token estimation and headroom planning.
    - `yaml_utils.py`, `markdown_extractors.py`: Robust parsing/formatting between YAML/Markdown.
    - `session_logger.py`, `logging.py`: Turnkey logging, LLM call capture, debug artifacts.

## Project Layout on Disk (`books/<project>/`)
- `project.yaml`: Project metadata (name, model, counts, timestamps).
- `premise/`: `premise_metadata.json`, candidate premises.
- `treatment/`: `treatment.md`, `treatment_metadata.json`.
- `chapter-beats/`: `foundation.yaml` (metadata, characters, world) + `chapter-XX.yaml` files.
- `chapter-beats-variants/`: variant runs with per‑variant chapter files + `decision.json`.
- `chapters/`: Prose chapters `chapter-XX.md` with headers.
- `analysis/`: Markdown reports from analyzers.
- `exports/`: Frontmatter, KDP metadata, and RTF/Markdown exports.

## Runtime Flow (New Book → Finished Book)
1. Initialize
   - Configure API key (`OPENROUTER_API_KEY`). Launch `agentic`.
   - `/new <name>` creates `books/<name>/`, initializes shared Git at `books/` if needed.
2. Premise & Taxonomy
   - Generate/select a premise; capture taxonomy selections (genre, length scope, tone).
3. Treatment (LOD2 prose plan)
   - Expand premise into a structured treatment (acts, turning points, arcs).
4. Foundation (metadata/characters/world)
   - Extract structured foundation from treatment into `foundation.yaml` (strict YAML, robust parsing).
5. Chapters (single‑shot global plan)
   - Generate all chapter outlines in one pass to prevent duplicate events; anti‑redundancy rules for Act II; save `chapter-XX.yaml` files.
   - Optionally generate multiple variants and judge to select the best arc.
6. Prose (sequential, full context)
   - Write chapters in order, including prior FULL prose as authoritative context; validate against outline and iterate surgically on issues.
7. Copy Edit & Polish
   - Run editing passes and KDP metadata generation as needed.
8. Export & Deliver
   - Export to Markdown/RTF and generate publishing metadata.
9. Analyze & Iterate
   - Use unified analysis and treatment‑deviation checks; act on priority issues and regenerate slices.

## Subsystems in Context
- Prompt System
  - Templates live in `src/prompts/...` with [SYSTEM]/[USER] sections; `PromptLoader` injects variables and splits rendered content to enforce format.
  - Strict YAML/JSON and quoting rules reduce parse errors and enable robust fallbacks when sanitizing.
- Generation Pipeline
  - Chapters: global single‑shot generation with per‑chapter beats; variants + judging ensure the best arc; saved as discrete YAML for better diffs.
  - Prose: sequential generation uses previous chapters’ FULL prose to avoid restaging; validation (`prose_fidelity`) flags summary‑only output or missing moments.
- Analysis & Validation
  - `UnifiedAnalyzer`: JSON‑structured scoring, strengths, and actionable feedback with duplicate‑beat detection.
  - `TreatmentDeviationAnalyzer`: Ensures foundation aligns with treatment; critical issues prompt fix or abort.
  - Reports are saved as Markdown under `analysis/` with grades, issues, and next steps.
- Storage & Git
  - `Project` abstracts pathing and IO; `GitManager` consolidates commits at the shared `books/` root so related works share history while staying project‑scoped.
- Observability
  - `SessionLogger` intercepts console and LLM calls, saving prompts/responses and debug files for failed parses or validation.

## Error Handling & Guardrails
- Hard validation of API keys and required inputs (premise, treatment, chapters) prevents partial pipelines.
- YAML/JSON strictness in prompts and parsers; graceful degradation (extracting chapters by pattern if YAML parsing fails) with explicit warnings.
- Analysis‑driven iteration: show critical issues, allow targeted regeneration with a cap on attempts; abort over unsafe states.

## Extensibility Guidelines
- New prompts: add `src/prompts/<area>/file.j2`, wire variables clearly, and document system/user sections; add metadata in `src/prompts/config.yaml` if needed.
- New generators/analyzers: implement self‑contained modules in `src/generation/` or `src/generation/analysis/` and integrate them via the REPL in `cli/interactive.py`.
- New output targets: add exporters in `src/export/` and reference them from CLI flows.
- Taxonomies: place genre/base taxonomies in `taxonomies/` and integrate via `generation/taxonomies.py`.

## Why This Architecture Works
- Separating foundation (YAML) from prose (Markdown) lets planning be structured and writing be freeform, while enabling objective validation.
- Single‑shot global chapter planning plus sequential prose mitigates “accordion” summaries and beat duplication.
- Disk‑first persistence with Git integration guarantees traceability and easy manual intervention.
- Strict prompt contracts and robust parsers reduce brittle failure modes while keeping high creative quality.

This overview stands alone to onboard new contributors and inform design decisions without requiring cross‑references.
