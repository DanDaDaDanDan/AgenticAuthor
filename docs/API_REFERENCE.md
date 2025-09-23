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

#### `/model [name]`
Show or change the current AI model.
- **name** (optional): Model ID to switch to. If not provided, shows current model.
- Example: `/model openai/gpt-4`

#### `/models [search]`
List available models from OpenRouter.
- **search** (optional): Filter models by search term
- Shows pricing and context length
- Sorted by price

### Content Generation (Not Yet Implemented)

#### `/generate <type> [options]`
Generate content at specified LOD level.

Types:
- `premise` - Generate story premise (LOD3)
- `treatment` - Generate story treatment (LOD2)
- `chapters` - Generate chapter outlines (LOD2)
- `prose [chapter]` - Generate full prose (LOD0)

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
- Examples: `/git status`, `/git log`, `/git diff`

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

#### `/help [command]`
Show help information.
- No args: Show all commands
- With command: Show detailed help for specific command

#### `/exit` or `/quit`
Exit the application.

## Python API

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