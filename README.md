# AgenticAuthor

**AI-powered book generation using natural language and git-backed version control.**

AgenticAuthor is a Python CLI tool that leverages Large Language Models to help you write complete books through a structured, iterative process. It uses a "Level of Detail" approach, starting from a premise and progressively building up to full prose.

## Features

- **Structured Generation Pipeline**: premise → treatment → chapters → prose
- **Natural Language Iteration**: Give feedback in plain English to refine your content
- **Multi-Variant Generation**: Generate multiple chapter variants and select the best
- **Git-Backed Version Control**: Every change is automatically committed
- **Quality-First Approach**: No artificial word count pressure
- **Style Cards**: Define and maintain consistent prose style across your book
- **Short Story Support**: Optimized handling for stories with ≤2 chapters
- **OpenRouter Integration**: Access to multiple LLM providers through a single API

## Prerequisites

- Python 3.8+
- OpenRouter API key (get one at [openrouter.ai](https://openrouter.ai))

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd AgenticAuthor
   ```

2. **Install the package:**
   ```bash
   pip install -e .
   ```

3. **Set your API key:**
   ```bash
   export OPENROUTER_API_KEY="sk-or-your-key-here"
   ```

   Or on Windows (PowerShell):
   ```powershell
   $env:OPENROUTER_API_KEY="sk-or-your-key-here"
   ```

## Quick Start

1. **Launch the REPL:**
   ```bash
   agentic
   ```

2. **Create a new project:**
   ```
   /new my-first-book
   ```

3. **Select your AI model:**
   ```
   /model
   ```
   Choose from the interactive list of available models.

4. **Generate your book step by step:**
   ```
   /generate premise
   /generate treatment
   /generate chapters
   /finalize chapters
   /generate prose all
   ```

## Core Workflow

### 1. Premise Generation
The starting point - a high-level concept for your book.
```
/generate premise
```

### 2. Treatment
Expands the premise into a detailed outline with character arcs and plot structure.
```
/generate treatment
```

### 3. Chapter Generation
Generates multiple variants of chapter plans. You'll review and select the best.
```
/generate chapters
/finalize chapters
```

### 4. Prose Generation
Writes the actual prose for your chapters. Uses style cards by default for consistency.
```
/generate prose all           # Generate all chapters
/generate prose 1             # Generate specific chapter
/generate prose 1-3           # Generate range of chapters
/generate prose --no-style-card  # Skip style card if needed
```

## Natural Language Iteration

Once content is generated, you can refine it using natural language feedback:

```
/iterate prose
make it darker and more suspenseful
add more internal dialogue
focus more on the character's backstory
```

The system validates changes with an AI judge, shows semantic diffs, and commits approved changes to git.

## Key Commands

### Project Management
- `/new <name>` - Create a new book project
- `/list` - List all projects
- `/switch <name>` - Switch to a different project
- `/clone <name>` - Clone existing project for safe experimentation

### Model Selection
- `/model` - Interactively select AI model
- `/model <name>` - Set model directly

### Generation
- `/generate premise` - Generate book premise
- `/generate treatment` - Generate detailed treatment
- `/generate chapters` - Generate chapter variants
- `/finalize chapters` - Select best chapter variant
- `/generate prose <target>` - Generate prose (all, chapter #, or range)

### Iteration
- `/iterate prose` - Enter iteration mode for prose refinement
- Provide natural language feedback (no `/` prefix)
- System validates, diffs, and commits changes

### Utilities
- `/help` - Show all available commands
- `/quit` or `/exit` - Exit the REPL

## Project Structure

Generated projects are stored in the `books/` directory:

```
books/
├── .git/                      # Shared git repository
└── my-book/
    ├── premise.md             # Book premise
    ├── treatment.md           # Detailed treatment
    ├── chapters.yaml          # Chapter plans (finalized)
    ├── prose/                 # Generated prose chapters
    │   ├── chapter_01.md
    │   ├── chapter_02.md
    │   └── ...
    └── misc/
        └── prose-style-card.md  # Style guide for prose
```

## Style Cards

Style cards define the prose style for your book and are used by default during generation. They include:

- Narrative voice and POV
- Tone and pacing
- Dialogue style
- Descriptive focus
- Technical elements

Generated automatically during prose generation, stored in `books/project/misc/prose-style-card.md`.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - High-level architecture and design decisions
- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** - Comprehensive user guide
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Version history and changes
- **[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)** - Feature tracking
- **[CLAUDE.md](CLAUDE.md)** - Development guidance for AI assistants

## Core Principles

1. **Natural Language First** - Iterate using plain English feedback
2. **Single Model Policy** - One model for all operations, no fallbacks
3. **Fail Early** - Clear errors instead of silent failures
4. **Context is King** - Complete context over token savings
5. **Quality First** - No artificial constraints on generation

## Tips

- Use tab-completion in the REPL for command hints
- All operations automatically commit to git
- Use `/clone` before experimenting with iteration
- Check `.agentic/logs/` for detailed operation logs
- Debug files are stored in `.agentic/debug/`

## Requirements

- OpenRouter API key must start with `sk-or-`
- Generation must follow the pipeline: premise → treatment → chapters → prose
- Each step builds on the previous one

## Getting Help

- Use `/help` in the REPL for command reference
- Check documentation in the `docs/` directory
- Review `ARCHITECTURE.md` for system design details

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
