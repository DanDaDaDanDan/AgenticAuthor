# AgenticAuthor

AI-powered iterative book generation with natural language feedback and git-backed version control.

## Features

### 🚀 Core Functionality
- **Level of Detail (LOD) Generation**: Premise (LOD3) → Treatment (LOD2) → Chapters (LOD2) → Prose (LOD0)
- **Natural Language Iteration**: Simply describe what you want changed
- **Git Integration**: Every book is a git repo, every change is a commit
- **Smart Genre System**: Genre-specific taxonomies and parameters
- **Model Flexibility**: Switch between AI models on the fly

### ✨ New Features (v0.2.0)
- **Enhanced Premise Generation**
  - Genre-specific taxonomy support
  - Smart input detection (brief premise vs full treatment)
  - History tracking to avoid repetition
  - Interactive genre selection
- **Advanced Command Completion**
  - Tab completion for all commands
  - Genre autocomplete for `/generate premise`
  - Model fuzzy search and completion
- **Comprehensive Logging**
  - Debug logging to `./logs/`
  - `/logs` command to view recent entries
  - Full error tracking and debugging support
- **Improved User Experience**
  - Better error messages
  - Mouse support for text selection
  - Command history with smart suggestions

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/AgenticAuthor.git
cd AgenticAuthor

# Install in development mode
pip install -e .

# Set your OpenRouter API key
export OPENROUTER_API_KEY="sk-or-your-key-here"
```

## Quick Start

```bash
# Start the REPL
agentic

# Create a new book
/new my-fantasy-novel

# Generate content with genre support
/generate premise fantasy "a world where magic is illegal"
/generate treatment
/generate chapters
/generate prose 1

# Use natural language iteration
Add more dialogue to chapter 1
Make the protagonist more complex
The ending needs more tension
```


## Advanced Features

### Genre-Specific Generation

The system now supports genre-specific taxonomies for these genres:
- Fantasy, Science Fiction, Mystery/Thriller
- Romance, Horror, Contemporary
- Historical, Literary, Young Adult
- Urban Fantasy, Romantasy

Each genre has specific parameters for:
- Tone, pacing, themes
- World-building elements
- Character archetypes
- Plot structures

### Smart Input Analysis

The premise generator automatically detects:
- **Brief concepts** (< 20 words) → Full premise generation
- **Standard premises** (20-100 words) → Enhancement and expansion
- **Detailed premises** (100-200 words) → Structure and refinement
- **Full treatments** (200+ words) → Preservation with taxonomy extraction

### Tab Completion

Press Tab to complete:
- Commands: `/gen` → `/generate`
- Subcommands: `/generate pr` → `/generate premise`
- Genres: `/generate premise fan` → `/generate premise fantasy`
- Models: `/model clau` → `/model anthropic/claude-3-opus`

**Behavior:**
- Single match: Completes immediately when Tab is pressed
- Multiple matches: Shows selection menu to choose from
- Example: `/op` + Tab → `/open` (instant completion)

## Configuration

### Environment Variables

```bash
OPENROUTER_API_KEY=sk-or-your-key-here
BOOKS_DIR=/path/to/books  # Optional, defaults to ~/books
DEFAULT_MODEL=x-ai/grok-4-fast  # Optional
```

### Config File (`~/.agentic/config.yaml`)

```yaml
default_model: anthropic/claude-3-opus
auto_commit: true
show_token_usage: true
streaming_output: true
streaming_display_mode: status  # Options: status, live, simple
temperature:
  premise: 0.9
  treatment: 0.7
  chapters: 0.6
  prose: 0.8
```

#### Streaming Display Modes

The `streaming_display_mode` setting controls how content is displayed during generation:

- **`status`** (default): Fixed status bar at bottom with scrollable content. Best for long generations where you want to scroll up to read earlier content while generation continues.
- **`live`**: Original in-place updating display. More visually dynamic but may have issues when scrolling with mouse during generation.
- **`simple`**: Plain text output without status display. Most compatible but less informative.

## Project Structure

```
books/[project-name]/
├── .git/                    # Version control
├── premise.md              # Story premise (LOD3)
├── premise_metadata.json   # Taxonomy selections
├── treatment.md            # Story treatment (LOD2)
├── chapters.yaml           # Chapter outlines (LOD2)
├── chapters/               # Full prose (LOD0)
│   ├── chapter-01.md
│   ├── chapter-02.md
│   └── ...
├── analysis/               # Story analysis
│   ├── commercial.md
│   ├── plot.md
│   └── characters.md
└── project.yaml            # Project metadata
```

## Logging and Debugging

Logs are automatically saved to `./logs/agentic_YYYYMMDD.log`

View logs in the REPL:
```bash
/logs  # Shows log location and recent entries
```

View logs directly:
```bash
# Windows
type %USERPROFILE%\.agentic\logs\agentic_20250923.log

# Mac/Linux
cat ./logs/agentic_20250923.log
```

## Testing

The project includes comprehensive test coverage:

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# Run integration tests (requires API key)
OPENROUTER_API_KEY=sk-or-your-key pytest tests/integration/
```

Test Statistics:
- 187 total tests (171 unit, 16 integration)
- 100% pass rate for core modules
- Comprehensive coverage for all new features

## Development

### Adding New Genres

1. Create taxonomy file in `docs/taxonomies/[genre]-taxonomy.json`
2. Add mapping in `src/generation/taxonomies.py`
3. Genre will auto-appear in autocomplete

### Custom Prompts

Create custom generation templates:
```python
from src.generation.premise import PremiseGenerator

generator = PremiseGenerator(client, project)
result = await generator.generate(
    template="Your custom template here",
    genre="fantasy"
)
```

## Troubleshooting

### Mouse Selection Not Working
- Windows Terminal: Hold Shift while dragging
- Other terminals: Check terminal settings for mouse mode

### Tab Completion Not Working
- Ensure you're using a compatible terminal
- Try pressing Tab twice for suggestions
- Check `/help` for command syntax

### API Errors
- Verify API key: `echo $OPENROUTER_API_KEY`
- Check model availability: `/models`
- Review logs: `/logs`

## Contributing

Contributions are welcome! Please ensure:
- All tests pass: `pytest tests/`
- Code is formatted: `black src/ tests/`
- Documentation is updated

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built on [OpenRouter](https://openrouter.ai) for model flexibility
- Inspired by [dv-story-generator](https://github.com/danielvschoor/dv-story-generator) for taxonomy system
- Uses [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) for REPL interface

## Command Reference

## Slash Commands

All commands in the REPL start with `/`. Type `/` to see auto-complete menu.

### Project Management

#### `/new [name]`
Create a new book project.
- **name** (optional): Project name. If not provided, prompts for input.
- Creates git repository automatically
- Initializes project structure

#### `/open [path]`
Open an existing project.
- **path** (optional): Path to project. If not provided, shows numbered list for selection.
- Features:
  - Inline numbered list selection (no popup)
  - Shows project metadata (genre, word count, last updated)
  - Type number to select, Enter to cancel
  - Can also type project name directly as argument

#### `/status`
Show current project status.
- Shows project metadata
- Lists completed/pending content
- Displays git status

### Model Management

#### `/model [search]`
Show or change the current AI model.
- **search** (optional): Model search term. If not provided, shows current model.
- Features:
  - Fuzzy search: `/model opus` finds `anthropic/claude-3-opus`
  - Interactive selection when multiple matches found
  - Tab completion: Type `/model ` then Tab to see available models
  - Shows model price and context size after selection
- Examples:
  - `/model` - Show current model
  - `/model opus` - Switch to Claude Opus
  - `/model gpt` - Shows selection menu for GPT models
  - `/model anthropic/claude-3-opus` - Exact match

#### `/models [search]`
List available models from OpenRouter.
- **search** (optional): Filter models by search term
- Shows pricing and context length
- Sorted by price

### Content Generation

#### `/generate premise [genre] [concept]`
Generate story premise (LOD3) with genre-specific support.
- **genre** (optional): Genre for the story (fantasy, sci-fi, romance, etc.)
  - Tab completion available: `/generate premise fan` → `fantasy`
  - Interactive selection if not provided
  - Aliases supported: `sci-fi` → `science-fiction`, `ya` → `young-adult`
- **concept** (optional): Initial idea to build upon
  - Can be brief (< 20 words) for full generation
  - Standard (20-100 words) for enhancement
  - Detailed (100-200 words) for structuring
  - Treatment (200+ words) preserved with taxonomy extraction
- Features:
  - Genre-specific taxonomies and parameters
  - Smart input detection (premise vs treatment)
  - History tracking to avoid repetition
  - Creates premise with metadata (protagonist, antagonist, stakes, themes)
  - Auto-commits to git
- Examples:
  - `/generate premise` - Interactive genre selection
  - `/generate premise fantasy` - Fantasy premise with random concept
  - `/generate premise fantasy "a world where magic is illegal"` - Specific concept
  - `/generate premise "a detective story"` - Auto-detects genre from concept

#### `/generate treatment [words]`
Generate story treatment from premise (LOD2).
- **words** (optional): Target word count (default: 2500)
- Expands premise into three-act structure
- Auto-generates premise if missing

#### `/generate chapters [count]`
Generate chapter outlines from treatment (LOD2).
- **count** (optional): Number of chapters (auto-calculated if not specified)
- Creates detailed beats for each chapter
- Saves to chapters.yaml

#### `/generate prose <chapter>`
Generate full prose for a chapter (LOD0).
- **chapter**: Chapter number to generate (required)
- Uses chapter outline as blueprint
- Maintains continuity with previous chapters
- Saves to chapters/chapter-NN.md

#### `/iterate <feedback>`
Apply natural language feedback to existing content.
- Automatically determines intent
- Creates git commit with changes

#### `/analyze [type]`
Analyze story for quality and issues.

Types:
- `commercial` - Commercial viability (0-100%)
- `plot` - Plot hole detection
- `characters` - Character consistency
- `world` - World-building coherence
- `all` - Run all analyses

### Utility Commands

#### `/git <command>`
Run git commands on the project repository.

**Supported commands:**
- `/git status` - Show working tree status
- `/git log [n]` - Show last n commits (default: 10)
- `/git diff` - Show unstaged changes
- `/git add` - Stage all changes
- `/git commit <message>` - Commit staged changes
- `/git branch [name]` - List branches or create new branch
- `/git rollback [n]` - Undo last n commits (default: 1)

**Note:** All generation commands auto-commit their changes

#### `/config [key] [value]`
Show or set configuration values.
- No args: Show all config
- With key: Show specific value
- With key and value: Set configuration

#### `/export [format]`
Export story to different formats (not yet implemented).
- Formats: `md`, `html`, `epub`, `pdf`

#### `/clear`
Clear the terminal screen.

#### `/logs`
View recent log entries.
- Shows log file location
- Displays last 20 lines of current log
- Logs stored in `./logs/agentic_YYYYMMDD.log`
- Automatic rotation daily

#### `/help [command]`
Show help information.
- No args: Show all commands
- With command: Show detailed help for specific command

#### `/exit` or `/quit`
Exit the application.

## Keybindings (REPL)

| Key | Action |
|-----|--------|
| `Enter` | Submit input |
| `Shift+Enter` | New line in multi-line input |
| `Escape` | Stop current generation |
| `Ctrl+C` | Exit application (with confirmation) |
| `Ctrl+L` | Clear screen |
| `Up/Down` | Navigate command history |
| `Tab` | Auto-complete commands, genres, and models |
