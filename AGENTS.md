# Repository Guidelines

Align every change with `CLAUDE.md`, which links to the authoritative docs in `docs/`. Reference those files when updating flows or architecture notes.

## Project Structure & Module Organization
`src/` houses the Typer CLI and generation pipeline; see `docs/DEVELOPER_GUIDE.md` for architecture specifics.
- `src/cli` runs the REPL commands; `src/generation/` covers premise→prose logic; `src/prompts/` stores Jinja templates; `src/storage/` manages the shared git history described in `CLAUDE.md`.
- Configuration defaults live in `src/config`; adapt via `config.yaml` or `.env`.
- Generated books and the shared repository sit in `books/` (auto-commits per `CLAUDE.md`); inspiration taxonomies live in `taxonomies/`; logs drop into `logs/`.
- Docs, diagrams, and status reports belong in `docs/`—update `docs/IMPLEMENTATION_STATUS.md` when features change.
- Mirror module layout under `tests/`; create `tests/fixtures/` for reusable data.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` to isolate dependencies.
- `pip install -e .[dev]` installs runtime plus dev tooling noted in `pyproject.toml`.
- `agentic` starts the workflow; `agentic repl <project>` resumes an existing book (see `docs/USER_GUIDE.md` for command details).
- `pytest` executes the suite; add `--cov=src --cov-report=term-missing` to mirror the coverage settings in `CLAUDE.md`.
- `ruff check src tests` and `black src tests` keep formatting tight; run `mypy src` before PRs.

## Coding Style & Naming Conventions
Follow Black (4 spaces, 100-char lines) and Ruff’s import sorting, as enforced by `pyproject.toml`. Use `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. Lean on Pydantic models or dataclasses for structured data and keep async flows non-blocking inside Typer commands. Store new prompt assets in `src/prompts` with descriptive filenames, and document behavior changes in `docs/DEVELOPER_GUIDE.md`.

## Testing Guidelines
Name files `test_<module>.py` and decorate async tests with `pytest.mark.asyncio`. Mock OpenRouter calls and persist fixtures under `tests/fixtures`. Exercise the generation pipeline (`src/generation`) and persistence layers (`src/storage`) to maintain coverage expectations noted in `CLAUDE.md`. If you add helpers, expose them via `tests/conftest.py` and record notable additions in `docs/IMPLEMENTATION_STATUS.md`.

## Commit & Pull Request Guidelines
Keep commits frequent and formatted as `<Type>: <summary>` (`Fix:`, `Add:`, `Docs:`) matching the history in `git log`. Summaries stay imperative and ≤72 characters; add context in the body when behavior shifts or data migrations occur. Pull requests must outline the purpose, verification steps (`pytest`, `ruff`, `mypy` outputs), affected docs (link to specific files like `docs/USER_GUIDE.md`), and any CLI examples. Ensure the verification checklist from `CLAUDE.md` is complete before requesting review.

Rule — Always Check In Your Work:
- Commit after each meaningful change; do not leave large uncommitted diffs. Keep the working tree clean before switching tasks or asking for review.
