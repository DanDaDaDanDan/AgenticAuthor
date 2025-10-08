# AgenticAuthor

AI-powered iterative book generation with natural language feedback and git-backed version control.

## Features

### 🚀 Core Functionality
- **Level of Detail (LOD) Generation**: Premise (LOD3) → Treatment (LOD2) → Chapters (LOD2) → Prose (LOD0)
- **Natural Language Iteration**: Simply describe what you want changed
- **Git Integration**: Shared repository with project-prefixed commits, every change tracked
- **Smart Genre System**: Genre-specific taxonomies and parameters
- **Model Flexibility**: Switch between AI models on the fly

### ✨ New Features (v0.3.0)
- **Interactive Editors**
  - Full-screen model selector with live fuzzy search
  - Interactive taxonomy editor with checkbox selection
  - Keyboard navigation (↑↓, SPACE, TAB, ENTER, ESC)
- **Automatic Genre Detection**
  - LLM auto-detects genre from concept
  - No manual selection needed
  - High accuracy with confidence scoring
- **Taxonomy Iteration**
  - Modify story parameters and regenerate premise
  - Natural language feedback for taxonomy changes
  - Interactive checkbox editor for precise control
- **Strict Model Enforcement**
  - Single user-selected model for ALL operations
  - No fallback models - clear error messages
  - Ensures consistent cost and quality
- **Multi-Model Competition Mode** 🏆
  - Run 3+ models in parallel (tournament mode)
  - Judge model evaluates and picks winner
  - See all candidates side-by-side
  - Full transparency with scores and reasoning
  - All candidates saved for review

### Previous Features (v0.2.0)
- **Enhanced Premise Generation**
  - Genre-specific taxonomy support
  - Smart input detection (brief premise vs full treatment)
  - History tracking to avoid repetition
- **Advanced Command Completion**
  - Tab completion for all commands
  - Genre autocomplete for `/generate premise`
  - Model fuzzy search and completion
- **Comprehensive Logging**
  - Debug logging to `./logs/`
  - `/logs` command to view recent entries
  - Full error tracking and debugging support

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

### Config File (`config.yaml`)

Project-local configuration in the project root directory:

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
books/                      # All projects root
├── .git/                    # Shared version control for all projects
├── [project-name-1]/
│   ├── .agentic/            # Project-local AgenticAuthor state
│   │   ├── logs/            # Session logs
│   │   │   ├── agentic_YYYYMMDD.log
│   │   │   └── session_*.jsonl
│   │   ├── history          # Command history
│   │   ├── premise_history.json # Generation history
│   │   └── debug/           # Debug output
│   ├── config.yaml          # Project configuration
│   ├── premise.md           # Story premise (LOD3)
│   ├── premise_metadata.json # Taxonomy selections
│   ├── treatment.md         # Story treatment (LOD2)
│   ├── chapters.yaml        # Self-contained chapter context (metadata, characters, world, outlines)
│   ├── chapters/            # Full prose (LOD0)
│   │   ├── chapter-01.md
│   │   ├── chapter-02.md
│   │   └── ...
│   ├── analysis/            # Story analysis
│   │   ├── commercial.md
│   │   ├── plot.md
│   │   └── characters.md
│   └── project.yaml         # Project metadata
└── [project-name-2]/
    └── ... (same structure)
```

### Git Architecture

All projects share a single git repository at `books/.git`. Each commit is prefixed with the project name:

```
[my-novel] Generate premise: fantasy
[my-novel] Generate treatment: 2500 words
[sci-fi-story] Generate premise: sci-fi
[my-novel] Iterate chapter 3: add dialogue
```

This allows for:
- Simple multi-project history tracking
- Easy comparison between projects
- Unified version control across all books

## Logging and Debugging

Logs are automatically saved to `.agentic/logs/agentic_YYYYMMDD.log`

View logs in the REPL:
```bash
/logs  # Shows log location and recent entries
```

View logs directly:
```bash
# Windows
type .agentic\logs\agentic_20251005.log

# Mac/Linux
cat .agentic/logs/agentic_20251005.log
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

#### `/clone [name]`
Clone current project to a new name.
- **name** (optional): New project name. If not provided, prompts for input.
- Creates complete copy of current project
- Initializes new git repository (fresh history)
- Preserves all content (premise, treatment, chapters, prose, analysis)
- Prompts to switch to cloned project after creation
- Useful for:
  - Experimenting with different story directions
  - Creating variations of the same story
  - Backing up before major changes

#### `/status`
Show current project status.
- Shows project metadata
- Lists completed/pending content
- Displays git status

### Model Management

#### `/model [search]`
Show or change the current AI model.
- **search** (optional): Model search term. If not provided, launches interactive selector.
- Features:
  - **Interactive mode** (no args): Full-screen model selector with:
    - Live fuzzy search - type to filter models instantly
    - Shows pricing and provider for each model
    - Keyboard navigation: ↑↓ to navigate, ENTER to select, ESC to cancel
    - Displays current model with "← current" marker
  - **Direct search**: `/model opus` finds `anthropic/claude-3-opus`
  - Tab completion: Type `/model ` then Tab to see available models
  - Shows model price and context size after selection
- Examples:
  - `/model` - Launch interactive selector (NEW)
  - `/model opus` - Direct fuzzy search
  - `/model gpt` - Shows all GPT models in selector
  - `/model anthropic/claude-3-opus` - Exact match

#### `/models [search]`
List available models from OpenRouter.
- **search** (optional): Filter models by search term
- Shows pricing and context length
- Sorted by price

### Multi-Model Competition Mode 🏆

#### `/multimodel`
Toggle multi-model competition mode on/off.
- When enabled, generation commands run 3+ models in parallel
- Judge model evaluates all outputs and picks winner
- Prompt shows `(MULTI-MODEL)` indicator when active
- All candidates saved to `multimodel/` folder for review
- Status shows all competition models and judge

#### `/multimodel config`
Show current multi-model configuration.
- Displays competition models and judge model
- Lists available actions

#### `/multimodel add <model>`
Add a model to competition lineup.
- Example: `/multimodel add anthropic/claude-opus-4`

#### `/multimodel remove <model>`
Remove a model from competition.
- Requires at least 2 models to remain

#### `/multimodel judge <model>`
Set the judge model.
- Example: `/multimodel judge google/gemini-2.5-pro`
- Judge should be different from competitors

#### `/multimodel reset`
Reset to default configuration.
- Competition: grok-4-fast, claude-sonnet-4.5, claude-opus-4.1
- Judge: gemini-2.5-pro

**How It Works:**
1. Enable mode: `/multimodel`
2. Run generation: `/generate treatment`
3. All competitors generate in parallel
4. See candidates side-by-side comparison
5. Judge evaluates with scoring criteria
6. Winner auto-saved, all candidates preserved
7. Git commit includes judging results

**Iteration Support (NEW):**
- Multi-model mode now works during iteration
- `/iterate chapters` runs competition with feedback incorporated
- All models receive same feedback context
- Judge evaluates how well each addressed feedback
- Example: "Add foreshadowing to chapters 4,8" → 3 models compete, best wins

**Judging Criteria:**
- Treatment: structure, pacing, character development, coherence, prose quality
- Chapters: detail, pacing, beats, tension, hooks
- Prose: writing quality, voice, dialogue, emotion, readability
- Iteration: feedback incorporation, quality improvement, consistency preservation

### Content Generation

#### `/generate premise [genre] [concept]`
Generate story premise (LOD3) with genre-specific support.
- **genre** (optional): Genre for the story (fantasy, sci-fi, romance, etc.)
  - **Auto-detection** (NEW): If concept provided without genre, LLM auto-detects it
  - Tab completion available: `/generate premise fan` → `fantasy`
  - Interactive selection if neither provided
  - Aliases supported: `sci-fi` → `science-fiction`, `ya` → `young-adult`
- **concept** (optional): Initial idea to build upon
  - Can be brief (< 20 words) for full generation
  - Standard (20-100 words) for enhancement
  - Detailed (100-200 words) for structuring
  - Treatment (200+ words) preserved with taxonomy extraction
- Features:
  - **Automatic genre detection** - no manual selection needed
  - Genre-specific taxonomies and parameters
  - Smart input detection (premise vs treatment)
  - History tracking to avoid repetition
  - Creates premise with metadata (protagonist, antagonist, stakes, themes)
  - Auto-commits to git
- Examples:
  - `/generate premise` - Interactive genre selection
  - `/generate premise fantasy` - Fantasy premise with random concept
  - `/generate premise fantasy "a world where magic is illegal"` - Specific concept
  - `/generate premise "a detective story"` - Auto-detects genre (NEW)

#### `/generate premises <count> [genre] [concept]`
Generate multiple premise options and select one (batch generation).
- **count** (required): Number of premises to generate (1-30)
- **genre** (optional): Genre for the stories (same as `/generate premise`)
  - Auto-detection works with concept
  - Interactive selection if neither provided
- **concept** (optional): Concept to incorporate into all premises
- Features:
  - **Single LLM call** generates all premises for efficiency
  - Each premise is unique and diverse
  - Interactive numbered selection after generation
  - All candidates saved to `premises_candidates.json` for reference
  - Selected premise saved to `premise.md`
  - Shows premise text (truncated) and hook for each option
  - Auto-commits to git with selection noted
- Examples:
  - `/generate premises 5` - Generate 5 premises with genre selection
  - `/generate premises 3 fantasy` - 3 fantasy premises
  - `/generate premises 5 fantasy "a magical library"` - 5 premises based on concept
  - `/generate premises 10 "space detective"` - Auto-detect genre, 10 premises
  - `/generate premises 30 fantasy` - Maximum 30 fantasy premises

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

#### `/iterate <target> [feedback]`
Apply natural language feedback to existing content or taxonomy.
- **target**: What to iterate on (premise, treatment, chapters, prose, taxonomy)
- **feedback** (optional): Natural language description of desired changes
  - For taxonomy: If no feedback provided, launches interactive checkbox editor
- Features:
  - **Smart patch vs regenerate detection** (NEW): System automatically chooses optimal method
    - Patch: Fast unified diffs for targeted edits (10-15x faster)
    - Regenerate: Full AI regeneration for structural changes
    - chapters.yaml supports both modes intelligently
  - **Multi-model iteration support** (NEW): Competition mode works during iteration
    - Feedback incorporated into all competing models
    - Judge evaluates how well feedback was addressed
  - **Interactive taxonomy editor** (NEW): Full-screen UI when `/iterate taxonomy` has no feedback
    - Checkbox interface for all taxonomy categories
    - Keyboard navigation: ↑↓ to move, SPACE to toggle, TAB to switch category
    - Visual indication of current selections
    - ENTER to save, ESC to cancel
  - **Natural language taxonomy changes** (NEW): Describe changes in plain English
  - Automatically determines intent and scale
  - Creates git commit with changes
- Examples:
  - `/iterate taxonomy` - Launch interactive editor (NEW)
  - `/iterate taxonomy make it standalone and change pacing to fast` - Natural language (NEW)
  - `/iterate premise add more tension`
  - `/iterate chapter 3 add more dialogue`
  - `/iterate chapters` → "Change chapter 3 title to 'Awakening'" - Patch (seconds)
  - `/iterate chapters` → "Add foreshadowing to chapters 4,8" - Regenerate (minutes)

#### `/analyze [type]`
Analyze story for quality and issues.

Types:
- `commercial` - Commercial viability (0-100%)
- `plot` - Plot hole detection
- `characters` - Character consistency
- `world` - World-building coherence
- `all` - Run all analyses

#### `/cull <target>`
Delete generated content with cascade deletion.

Targets:
- `prose` - Delete all chapter prose files (chapter-XX.md)
- `chapters` - Delete chapters.yaml + cascade to prose
- `treatment` - Delete treatment.md + cascade to chapters and prose
- `premise` - Delete premise.md, premise_metadata.json + cascade to all downstream content

Features:
- Confirmation prompt before deletion
- Cascade deletion (deleting treatment also deletes chapters and prose)
- Git commit after successful deletion
- Useful for:
  - Starting over with a different approach
  - Regenerating from a specific LOD level
  - Removing unwanted generated content

Examples:
- `/cull prose` - Remove all prose, keep chapter outlines
- `/cull chapters` - Remove chapters and prose, keep treatment
- `/cull treatment` - Remove treatment, chapters, and prose

### Utility Commands

#### `/git <command>`
Run git commands on the shared repository.

**Important:** All projects share a single git repository at `books/.git`. All commits are automatically prefixed with the project name:
```
[my-novel] Generate premise: fantasy
[sci-fi-story] Iterate chapter 3: add dialogue
```

**Supported commands:**
- `/git status` - Show working tree status
- `/git log [n]` - Show last n commits (default: 10)
- `/git diff` - Show unstaged changes
- `/git add` - Stage all changes
- `/git commit <message>` - Commit with project name prefix
- `/git branch [name]` - List branches or create new branch
- `/git rollback [n]` - Undo last n commits (default: 1)

**Note:** All generation commands auto-commit their changes with project name prefixes

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

## Interactive Editors (v0.3.0)

### Model Selector (`/model` with no arguments)

Full-screen model selection with live fuzzy search:

**Features:**
- Type to filter models instantly (fuzzy matching)
- Shows pricing and provider for each model
- Current model marked with "← current"
- Up to 15 models displayed at once

**Keyboard Controls:**
- `Type any character` - Add to search filter
- `Backspace` - Remove character from search
- `↑/↓` - Navigate through models
- `Enter` - Select highlighted model
- `Esc` - Cancel and keep current model

**Example:**
```
/model
[Full-screen selector appears]
Search: grok
→ x-ai/grok-4-fast [$0.0010/1M] ← current
  x-ai/grok-beta [$0.0020/1M]
```

### Taxonomy Editor (`/iterate taxonomy` with no feedback)

Full-screen checkbox interface for precise taxonomy control:

**Features:**
- All taxonomy categories in tabs (pacing, themes, POV, etc.)
- Multi-select checkboxes for each option
- Visual indication of current selections (✓)
- Navigate between categories with TAB

**Keyboard Controls:**
- `↑/↓` - Navigate options in current category
- `Space` - Toggle selected option
- `Tab` - Next category
- `Shift+Tab` - Previous category
- `Enter` - Save changes
- `Esc` - Cancel

**Example:**
```
/iterate taxonomy
[Full-screen editor appears]
═══════════════════════════════════════════
 [Pacing]  Themes  POV  Story Structure
═══════════════════════════════════════════
→ [✓] Fast-paced
  [ ] Medium-paced
  [✓] Slow-burn
```

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
