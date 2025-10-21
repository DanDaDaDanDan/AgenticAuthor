# Repository Guidelines

Keep this guide concise. Treat `CLAUDE.md` and `ARCHITECTURE.md` as the sources of truth. When you change how things are structured or interact, add a short note to `ARCHITECTURE.md` (key decisions, rationale, date).

## Project Structure
- See `ARCHITECTURE.md` for the complete layout and roles.
- In brief: `src/` holds CLI, generation, prompts, storage, utils; `books/` stores per‑project artifacts; `taxonomies/` configures genre/form; logs go to `logs/`.

## Build, Test, and Dev
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -e .[dev]`
- `agentic` to start; `agentic repl <project>` to resume (use `/help` and tab completion).
- `pytest` (add `--cov=src --cov-report=term-missing` for coverage)
- `ruff check src tests`, `black src tests`, `mypy src`

## Coding Style
- Black (4 spaces, 100‑char lines) + Ruff import sorting (see `pyproject.toml`).
- Naming: `snake_case` (modules/functions), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- Prefer Pydantic models/dataclasses for structured data; keep Typer commands non‑blocking.
- New prompts go in `src/prompts` with descriptive filenames; capture high‑level changes in `ARCHITECTURE.md`.

## Testing Guidelines
- Name tests `test_<module>.py`; use `pytest.mark.asyncio` for async.
- Mock network (OpenRouter) and add fixtures under `tests/fixtures`.
- Exercise generation (`src/generation`) and persistence (`src/storage`) paths; share helpers via `tests/conftest.py`.

## Commit & PR Guidelines
- Format: `<Type>: <summary>` (e.g., `Fix: ...`, `Add: ...`, `Docs: ...`), ≤72 chars, imperative mood.
- Include verification evidence (`pytest`, `ruff`, `mypy` outputs) and any CLI examples affected.
- Link `ARCHITECTURE.md` when architectural behavior changes; add a brief decision note (what/why).

Rule — Always Check In Your Work
- Commit after each meaningful change; avoid large uncommitted diffs. Keep the tree clean before switching tasks or requesting review.
