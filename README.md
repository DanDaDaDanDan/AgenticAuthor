# AgenticAuthor

AI-powered iterative book generation using OpenRouter API and natural language feedback.

## Features

- **Natural Language Iteration**: Just describe what you want changed
- **Git-Based Version Control**: Every change is tracked automatically
- **Slash Commands**: Claude Code-style command interface with `/` prefix
- **Multiple AI Models**: Switch between models on the fly via OpenRouter
- **Level of Detail Approach**: Progressive refinement from premise → treatment → chapters → prose

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Set API Key

Create a `.env` file with your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
```

Get your API key at: https://openrouter.ai/keys

### 3. Start the REPL

```bash
agentic
```

## Commands

All commands start with `/`. Type `/` to see available commands with autocomplete.

### Basic Commands

- `/help` - Show available commands
- `/new [name]` - Create a new book project
- `/open [path]` - Open existing project
- `/status` - Show project status
- `/exit` or `/quit` - Exit the application

### Model Commands

- `/model [name]` - Change or show current AI model
- `/models [search]` - List available models from OpenRouter

### Generation Commands (Coming Soon)

- `/generate premise` - Generate story premise
- `/generate treatment` - Create story treatment
- `/generate chapters` - Generate chapter outlines
- `/generate prose [chapter]` - Write full prose

### Iteration

Simply type natural language feedback (no slash) to iterate:

```
> Add more dialogue to chapter 3
> Make the protagonist more conflicted
> Expand the world-building in the opening
```

### Git Integration

- `/git status` - Check git status
- `/git log` - View commit history
- `/git diff` - See changes
- Every change auto-commits with descriptive messages

## Project Structure

```
books/[project-name]/
├── .git/                    # Version control
├── premise.md              # Story premise (LOD3)
├── treatment.md            # Story treatment (LOD2)
├── chapters.yaml           # Chapter outlines (LOD2)
├── chapters/               # Full prose (LOD0)
│   └── chapter-*.md
├── analysis/               # Story analysis
│   ├── commercial.md
│   ├── plot.md
│   └── ...
└── project.yaml            # Project metadata
```

## Development Status

### ✅ Completed
- Core configuration system
- OpenRouter API client with streaming
- Project and story data models
- Interactive REPL with slash commands
- Git integration
- Basic test suite

### 🚧 In Progress
- Generation system (premise, treatment, chapters, prose)
- Natural language iteration with intent checking
- Story analysis system

### 📋 Planned
- Export to various formats (EPUB, PDF, etc.)
- Multi-model collaboration
- Advanced analysis features

## Testing

Run tests with coverage:

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

Current test coverage: ~49%

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[docs/README.md](docs/README.md)** - Documentation index
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and architecture
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete API reference
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development setup and guidelines
- **[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)** - Current implementation status
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Version history

For AI assistants: See **[CLAUDE.md](CLAUDE.md)** for instructions on working with this codebase.

## Architecture

- **Python 3.11+** with async/await
- **prompt_toolkit** for REPL interface
- **Rich** for beautiful terminal output
- **Pydantic** for data validation
- **aiohttp** for async API calls
- **Git** via subprocess for version control

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Contributing

This is an experimental project exploring AI-assisted creative writing. Issues and PRs welcome!

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development guidelines.

## License

MIT