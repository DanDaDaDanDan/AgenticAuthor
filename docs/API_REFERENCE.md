# API Reference

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
- **path** (optional): Path to project. If not provided, shows list of available projects.

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
- Logs stored in `~/.agentic/logs/agentic_YYYYMMDD.log`
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
| `Ctrl+R` | Search history |

## Python API

### Taxonomy System

```python
from src.generation.taxonomies import (
    TaxonomyLoader,
    PremiseAnalyzer,
    PremiseHistory
)

# Load genre-specific taxonomy
loader = TaxonomyLoader()
taxonomy = loader.load_merged_taxonomy('fantasy')
options = loader.get_category_options(taxonomy)

# Analyze input to determine type
analysis = PremiseAnalyzer.analyze(user_input)
if analysis['is_treatment']:
    # Preserve as treatment, extract taxonomy
    pass
else:
    # Generate or enhance premise
    pass

# Track generation history
history = PremiseHistory()
history.add(premise, genre, selections)
if not history.should_regenerate(new_premise):
    # Avoid repetition
    pass
```

### Premise Generator

```python
from src.generation.premise import PremiseGenerator

generator = PremiseGenerator(client, project, model='x-ai/grok-4-fast')

# Generate with genre and concept
result = await generator.generate(
    genre='fantasy',
    user_input='a world where dreams are currency'
)

# Extract taxonomy from existing treatment
result = await generator.generate_taxonomy_only(
    treatment=existing_text,
    genre='fantasy'
)

# Iterate on existing premise
result = await generator.iterate(
    feedback='Make it darker and more mysterious'
)
```

### OpenRouter Client

```python
from src.api import OpenRouterClient

async with OpenRouterClient(api_key="sk-or-...") as client:
    # Discover available models
    models = await client.discover_models()

    # Simple completion
    response = await client.completion(
        model="anthropic/claude-opus-4.1",
        prompt="Write a story premise",
        temperature=0.9,
        max_tokens=2000
    )

    # Streaming completion
    result = await client.streaming_completion(
        model="anthropic/claude-opus-4.1",
        messages=[
            {"role": "system", "content": "You are a creative writer"},
            {"role": "user", "content": "Write a story"}
        ],
        on_token=lambda token, count: print(token, end=""),
        temperature=0.8
    )

    # JSON completion
    data = await client.json_completion(
        model="anthropic/claude-opus-4.1",
        prompt="Return a JSON object with title and genre",
        temperature=0.3
    )
```

### Project Management

```python
from src.models import Project

# Create new project
project = Project.create(
    path="books/my-story",
    name="My Story",
    genre="fantasy",
    author="John Doe"
)

# Load existing project
project = Project("books/my-story")

# Save content
project.save_premise("A hero's journey begins...")
project.save_treatment("Act 1: The ordinary world...")
project.save_chapter(1, "Chapter 1\n\nIt was a dark night...")

# Load content
premise = project.get_premise()
treatment = project.get_treatment()
chapter = project.get_chapter(1)
```

### Story Model

```python
from src.models import Story, Chapter, ChapterOutline

# Create story structure
story = Story()
story.premise = "A compelling premise"

# Add chapter outline
outline = ChapterOutline(
    number=1,
    title="The Beginning",
    summary="Introduction to the world",
    key_events=["Event 1", "Event 2"],
    word_count_target=3000
)
story.chapter_outlines.append(outline)

# Add full chapter
chapter = Chapter(
    number=1,
    title="Chapter One",
    content="Full prose content...",
    word_count=2847
)
story.add_chapter(chapter)

# Check completeness
if story.is_complete:
    print(f"Total words: {story.total_word_count}")
```

### Git Integration

```python
from src.storage import GitManager

git = GitManager(project_path)

# Initialize repository
git.init()

# Basic operations
git.add()  # Stage all changes
git.commit("Updated chapter 3")
git.status()
git.diff()
git.log(limit=10)

# Auto-commit with descriptive message
git.auto_commit("Generate premise", "Fantasy genre with hero's journey")

# Branch operations
git.create_branch("experiment")
git.checkout("main")
branches = git.list_branches()

# Rollback
git.rollback(steps=1)  # Undo last commit
```

### Configuration

```python
from src.config import get_settings

settings = get_settings()

# Access configuration
api_key = settings.openrouter_api_key
model = settings.active_model
temp = settings.get_temperature('prose')
max_tokens = settings.get_max_tokens('premise')

# Modify settings
settings.set_model('openai/gpt-4')
settings.auto_commit = False
settings.save_config_file(Path("config.yaml"))
```

## Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-your-key-here

# Optional
BOOKS_DIR=/path/to/books
TAXONOMIES_DIR=/path/to/taxonomies
DEFAULT_MODEL=anthropic/claude-opus-4.1

# Logging
LOG_LEVEL=INFO  # DEBUG for verbose output
LOG_FILE=/custom/path/to/logfile.log
```

## Configuration Files

### `.env` (Project root)
```env
OPENROUTER_API_KEY=sk-or-your-key
```

### `config.yaml` (Project or user directory)
```yaml
default_model: anthropic/claude-opus-4.1
auto_commit: true
show_token_usage: true
streaming_output: true
temperature:
  premise: 0.9
  treatment: 0.7
  chapters: 0.6
  prose: 0.8
  polish: 0.3
  iteration: 0.5
  analysis: 0.3
  intent: 0.1
```

### `project.yaml` (Book directory)
```yaml
name: My Fantasy Novel
created_at: 2024-01-23T10:00:00
updated_at: 2024-01-23T15:30:00
author: Jane Doe
genre: fantasy
taxonomy: fantasy-taxonomy
premise_metadata:
  selections:
    tone: dark
    pacing: fast-paced
    magic_system: hard
    world_type: secondary_world
model: anthropic/claude-opus-4.1
word_count: 45000
chapter_count: 15
status: draft
tags:
  - epic fantasy
  - magic system
  - hero's journey
```

## Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `InvalidAPIKey` | API key format invalid | Ensure key starts with 'sk-or-' |
| `ProjectNotFound` | Project doesn't exist | Check path or use `/new` |
| `NoProjectLoaded` | No active project | Use `/open` or `/new` first |
| `GenerationFailed` | API call failed | Check internet/API status |
| `GitError` | Git operation failed | Check git installation |
| `TaxonomyNotFound` | Genre taxonomy missing | Check taxonomies directory |
| `HistoryValidation` | Duplicate premise detected | Provide different input |