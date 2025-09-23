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
  - Debug logging to `~/.agentic/logs/`
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

## Command Reference

### Generation Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/generate premise [genre] ["concept"]` | Generate story premise | `/generate premise fantasy` |
| `/generate treatment [words]` | Generate story treatment | `/generate treatment 2500` |
| `/generate chapters [count]` | Generate chapter outlines | `/generate chapters 15` |
| `/generate prose <chapter>` | Generate full prose | `/generate prose 1` |

### Model Management

| Command | Description | Example |
|---------|-------------|---------|
| `/model [search]` | Show/change model | `/model claude` |
| `/models [filter]` | List available models | `/models gpt` |

### Project Management

| Command | Description | Example |
|---------|-------------|---------|
| `/new [name]` | Create new project | `/new my-book` |
| `/open [path]` | Open existing project | `/open books/my-book` |
| `/status` | Show project status | `/status` |

### Utility Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/git <command>` | Run git commands | `/git status` |
| `/logs` | View log file | `/logs` |
| `/config [key] [value]` | Manage configuration | `/config` |
| `/help [command]` | Show help | `/help generate` |

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
temperature:
  premise: 0.9
  treatment: 0.7
  chapters: 0.6
  prose: 0.8
```

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

Logs are automatically saved to `~/.agentic/logs/agentic_YYYYMMDD.log`

View logs in the REPL:
```bash
/logs  # Shows log location and recent entries
```

View logs directly:
```bash
# Windows
type %USERPROFILE%\.agentic\logs\agentic_20250923.log

# Mac/Linux
cat ~/.agentic/logs/agentic_20250923.log
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