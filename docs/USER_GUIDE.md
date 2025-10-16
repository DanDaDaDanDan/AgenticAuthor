# AgenticAuthor

AI-powered iterative book generation with natural language feedback and git-backed version control.

## Features

### 🚀 Core Functionality
- **Level of Detail (LOD) Generation**: Premise (LOD3) → Treatment (LOD2) → Chapters (LOD2) → Prose (LOD0)
- **Natural Language Iteration**: Simply describe what you want changed
- **Git Integration**: Shared repository with project-prefixed commits, every change tracked
- **Smart Genre System**: Genre-specific taxonomies and parameters
- **Model Flexibility**: Switch between AI models on the fly

### ✨ New Features (v0.3.0+)
- **Short Story Workflow** 📖
  - Auto-detection for stories ≤7,500 words (flash fiction, short stories)
  - Single file generation (story.md) instead of chapters/
  - Optimized prompts for short-form (unity of effect, single-sitting experience)
  - Direct iteration on complete story
  - Export works seamlessly for both short and long form

- **Sequential Chapter Generation** 🔄
  - Zero information loss (each chapter sees 100% of previous chapters)
  - Three phases: Foundation → Sequential Chapters → Assembly
  - User-controlled resume capability (continue/regenerate/abort)
  - Incremental saves (inspect partial results anytime)
  - Foundation loaded on resume (saves ~2,000 tokens + 30-45s)
  - Short consistent streams (30-60s per chapter)

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

- **Book Metadata and Export** 📚
  - Set title, author, copyright, ISBN, and other metadata
  - Professional RTF export for Kindle/ebook publishing
  - Combined Markdown export
  - Frontmatter template system (title page, copyright, dedication, acknowledgments)
  - Variable replacement in templates ({{title}}, {{author}}, etc.)

- **Professional Copy Editing** ✏️
  - Comprehensive copy editing pass for all chapter prose
  - Sequential processing with full story context
  - Pronoun consistency detection (especially unisex names)
  - Continuity checking across all chapters
  - Forward reference support (later chapters visible during editing)
  - Quality verification with preview before applying
  - Timestamped backups and checkpoint saving
  - Temperature 0.3 for precision

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
│   ├── config.yaml          # Project configuration (including book_metadata)
│   ├── frontmatter.md       # Frontmatter template (title page, copyright, dedication, etc.)
│   ├── premise_metadata.json # Story premise (LOD3) + taxonomy - Single source of truth
│   ├── treatment.md         # Story treatment (LOD2)
│   ├── chapters.yaml        # Self-contained chapter context (metadata, characters, world, outlines)
│   ├── chapters/            # Full prose (LOD0)
│   │   ├── chapter-01.md
│   │   ├── chapter-02.md
│   │   └── ...
│   ├── exports/             # Export outputs (RTF, Markdown, etc.)
│   │   ├── my-book-title.rtf
│   │   └── my-book-title.md
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

### Session Logs

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

### LLM Call Debug Files

Every LLM call is automatically saved to an individual text file for debugging. This is especially helpful when:
- Generation produces unexpected results
- You want to understand what prompt was used
- You need to inspect exact token usage
- You're troubleshooting issues

**Location:** `.agentic/debug/llm-calls/`

**Filename Format:** `YYYYMMDD_HHMMSS_{model}_{operation}.txt`

**Example:**
```
.agentic/debug/llm-calls/
├── 20250116_143022_x-ai_grok-4-fast_premise-generation.txt
├── 20250116_143530_anthropic_claude-sonnet-4_chapter-3.txt
└── 20250116_144105_google_gemini-2-5-pro_treatment-generation.txt
```

Each file contains:
- Timestamp and model name
- All request parameters (temperature, max_tokens, etc.)
- Complete prompt/messages sent to the LLM
- Full response received
- Token usage and response length

**To inspect a specific LLM call:**
```bash
# Windows
type .agentic\debug\llm-calls\20250116_143530_anthropic_claude-sonnet-4_chapter-3.txt

# Mac/Linux
cat .agentic/debug/llm-calls/20250116_143530_anthropic_claude-sonnet-4_chapter-3.txt
```

**Benefits:**
- Debug unexpected generation results
- Optimize prompts by comparing successful vs failed attempts
- Understand token usage patterns
- Share specific LLM calls when reporting issues

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

### Mouse Selection
- Text selection with mouse is fully supported (click and drag to select)
- Copy selected text with Cmd+C (Mac) or Ctrl+C (Windows/Linux)

### Tab Completion Not Working
- Ensure you're using a compatible terminal
- Try pressing Tab twice for suggestions
- Check `/help` for command syntax

### API Errors
- Verify API key: `echo $OPENROUTER_API_KEY`
- Check model availability: `/models`
- Review logs: `/logs`

### Network Errors and Automatic Retry (v0.3.1+)

**What Happens:** During chapter generation, network interruptions can cause incomplete YAML documents. The system automatically detects this and retries.

**What You'll See:**

**Scenario 1: Automatic Recovery (Most Common)**
```
✓ Generating chapter 2...
✗ YAML truncated (network error)
Retrying chapter 2 generation (1/2)...
✓ Generated chapter 2 (4,200 words)
```

The system detected the truncation, regenerated the chapter, and continued normally. No action needed!

**Scenario 2: Persistent Network Issues**
```
✓ Generating chapter 2...
✗ YAML truncated (network error)
Retrying chapter 2 generation (1/2)...
✗ YAML truncated (network error)
Retrying chapter 2 generation (2/2)...
✗ YAML truncation persists after 2 retries

This looks like a network truncation (automatic retries exhausted).
This can happen with unstable connections or slow models.

Failed to generate chapter 2: Failed to parse chapter 2 YAML: [error details]
```

**What to Do:**
1. **Check your internet connection** - Ensure stable connectivity
2. **Try a faster model** - Use `/model` to switch to a model with better streaming reliability
3. **Check OpenRouter status** - Visit openrouter.ai/status for service status
4. **Try again** - Often network issues are transient
5. **View logs** - Use `/logs` to see detailed error information

**Technical Details:**
- System attempts up to 2 automatic retries
- Each retry regenerates the chapter from scratch
- Uses same prompt/temperature as original attempt
- Saves ~2-5 minutes of user intervention on success

**Why This Happens:**
- Network drops during streaming API calls
- Connection timeouts on slower models
- Temporary service interruptions
- Unstable internet connection

**Prevention:**
- Use a stable internet connection (wired preferred over WiFi)
- Select faster models when on unstable connections
- Avoid very slow models (>60s generation time)

### Treatment Fidelity Validation (v0.3.1+)

**What It Does:** Prevents LLMs from inventing major plot elements beyond your treatment, while allowing scene-level elaboration.

**Why It Matters:** Without validation, LLMs may invent secret organizations, government conspiracies, or additional antagonists not in your treatment. This causes story drift and compounds errors in future chapters.

**How It Works - Three-Layer Defense:**

#### 1. Foundation Validation

After generating foundation (metadata + characters + world), the system validates it against your treatment:

**What You'll See (If Issues Found):**
```
═══════════════════════════════════════════════════════════════════
✗ CRITICAL ISSUE DETECTED in Foundation
═══════════════════════════════════════════════════════════════════

Issue Type: character_contradiction
Element: Detective Elias Crowe background

Problem:
  Treatment describes Elias as veteran detective. Foundation contradicts
  this by making him a rookie officer.

Recommendation:
  Update foundation to match treatment's character description.

⚠️  Foundation contradicts the treatment.
Continuing may cause story drift and compound errors in chapters.

What would you like to do?
  1. Abort generation (recommended) - fix treatment or regenerate foundation
  2. Regenerate foundation with stricter enforcement
  3. Ignore and continue (NOT recommended) - may cause story drift
```

**What To Do:**
- **Option 1 (Recommended)**: Abort generation and clarify your treatment
  - Update treatment to be more explicit about character details
  - Or verify that foundation interpretation is actually correct
- **Option 2**: Regenerate foundation with stricter enforcement
  - System retries with additional guardrails
  - Works well for minor misunderstandings
- **Option 3 (Not Recommended)**: Ignore and continue
  - Only use if you're sure the issue is minor
  - May cause compounding problems later

#### 2. Prompt Guardrails

Every chapter generation includes guidelines to keep LLMs faithful to your sources:
- Foundation + Treatment are **dual sources of truth**
- Elaboration welcomed for scene-level details (dialogue, props, gestures)
- Major plot elements must come from your sources
- Clear examples of allowed vs forbidden elaboration

#### 3. Chapter Validation

After generating each chapter, the system validates it against your treatment:

**What You'll See (If Issues Found):**
```
═══════════════════════════════════════════════════════════════════
✗ CRITICAL ISSUE DETECTED in Chapter 3
═══════════════════════════════════════════════════════════════════

Issue Type: major_plot_invention
Location: Scene 2: The Discovery
Element: Secret government program 'Project Chimera'

Problem:
  Treatment describes ONE antagonist (Dr. Victor Lang). This chapter invents
  a NEW conspiracy involving government experiments not mentioned in treatment.

Recommendation:
  Remove this plot thread or verify it exists in treatment.

⚠️  This chapter invents major plot elements not in the treatment.
Continuing may cause story drift and compound errors in future chapters.

What would you like to do?
  1. Abort generation (recommended) - fix treatment or regenerate chapter
  2. Regenerate chapter with stricter enforcement
  3. Ignore and continue (NOT recommended) - may cause story drift
```

**What To Do:**
- **Option 1 (Recommended)**: Abort and update treatment
  - If you want that plot element, add it to your treatment first
  - Or verify your treatment already has it and clarify the description
- **Option 2**: Regenerate chapter with stricter enforcement
  - System retries with additional guardrails
  - Good for LLMs that slightly exceeded bounds
- **Option 3 (Not Recommended)**: Ignore and continue
  - Only use if you actually WANT this new plot element
  - Consider adding it to treatment retroactively to maintain consistency

**Allowed Elaboration (NOT Violations):**
- Dialogue specifics ("Lang confronts Elias" → specific words, tone, gestures)
- Props and details (chess symbolism → specific chess pieces, board details)
- Location specifics (warehouse → rust on pipes, broken windows, smell of oil)
- Minor characters (servants, officials, background people)
- Sensory details (sounds, smells, textures, colors)

**Forbidden Invention (VIOLATIONS):**
- New antagonists not in treatment
- Secret organizations or conspiracies not in treatment
- Major backstories not in treatment
- New plot threads or subplots
- Character role changes
- World-building contradictions (realistic → supernatural, etc.)

**Best Practices:**

**Writing Better Treatments:**
1. **Be Explicit About Major Elements**: List all antagonists, plot threads, and conspiracies
2. **Include Character Backgrounds**: Key motivations, histories, and roles
3. **Describe World Rules**: Realistic vs supernatural, magic systems, tech level
4. **Set Tone and Pacing**: Fast-paced thriller vs slow-burn literary

**When Validation Triggers:**
1. **Review Carefully**: Read the issue description and understand the concern
2. **Check Your Treatment**: Is the element actually missing or just unclear?
3. **Regenerate First**: Try option 2 (regenerate) before giving up
4. **Update Treatment**: If you want the element, add it explicitly first
5. **Don't Ignore**: Ignoring issues compounds errors in future chapters

**Why Validation Happens AFTER Saving:**
- Failed generations are preserved in `chapter-beats/` for debugging
- You can inspect what the LLM generated and understand the problem
- Foundation and chapters are saved even when issues are detected
- Helps you improve your treatment for better results

**Temperature Settings:**
- Generation: 0.6 (stricter adherence to sources)
- Validation: 0.1 (consistent evaluation)
- Lower temperature = better fidelity, slightly less creativity

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

**🌟 NEW: Interactive Guided Mode** - Run `/generate premise` with no arguments:
1. **Story Concept** - Enter your story idea
2. **Genre** - Select from list or choose "Auto-detect"
3. **Story Length** - Choose target length (flash fiction → epic)

**Length Options:**
- Flash Fiction: 500-1,500 words (~5 min read)
- Short Story: 1,500-7,500 words (~15-30 min read)
- Novelette: 7,500-17,500 words (~45-90 min read)
- Novella: 17,500-40,000 words (~2-4 hours)
- Novel: 40,000-120,000 words (~6-12 hours)
- Epic: 120,000+ words (~12+ hours)

**Traditional Command-Line Mode** - Provide arguments directly:
- **genre** (optional): Genre for the story (fantasy, sci-fi, romance, etc.)
  - **Auto-detection**: If concept provided without genre, LLM auto-detects it
  - Tab completion available: `/generate premise fan` → `fantasy`
  - Interactive selection if neither provided
  - Aliases supported: `sci-fi` → `science-fiction`, `ya` → `young-adult`
- **concept** (optional): Initial idea to build upon
  - Can be brief (< 20 words) for full generation
  - Standard (20-100 words) for enhancement
  - Detailed (100-200 words) for structuring
  - Treatment (200+ words) preserved with taxonomy extraction

Features:
- **Interactive guided flow** - asks upfront questions for better premises
- **Length-aware generation** - premise scope matches target length
- **Automatic genre detection** - no manual selection needed
- Genre-specific taxonomies and parameters
- Smart input detection (premise vs treatment)
- History tracking to avoid repetition
- Creates premise with metadata (protagonist, antagonist, stakes, themes)
- Length automatically saved to taxonomy for treatment/chapters
- Auto-commits to git

Examples:
- `/generate premise` - Interactive guided mode (RECOMMENDED)
- `/generate premise fantasy` - Fantasy premise with random concept
- `/generate premise fantasy "a world where magic is illegal"` - Specific concept
- `/generate premise "a detective story"` - Auto-detects genre

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
  - Selected premise saved to `premise_metadata.json`
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

**Treatment Analysis (Initial Generation):**
When generating chapters for the first time, the LLM analyzes your treatment to determine an organic word count instead of using rigid genre defaults:

**Analysis Factors:**
1. **Story Complexity**: Number of major plot threads
2. **Character Count**: How many characters have significant arcs
3. **World-Building Needs**: Alternate history, magic systems, extensive setting
4. **Subplot Density**: Number of parallel storylines
5. **Natural Pacing**: Fast-paced action vs deliberate literary exploration
6. **Timeline Span**: Events spanning days/weeks (shorter) vs months/years (longer)

**Example:**
```
📊 Treatment Analysis Results
═══════════════════════════════════════════════════════════

  Word Count: 92,000 → 75,000 ↘ -18.5% (-17,000 words)

  Average chapter length: 4,000 → 3,260 words

═══════════════════════════════════════════════════════════
```

**Why This Matters:**
- Tight thriller with 3 characters → 60K words (not genre default 92K)
- Epic with extensive world-building → 105K words (not genre default 92K)
- Still respects form ranges (novel: 50k-120k)

**Note:** Treatment analysis only runs during initial generation. Iteration uses stored targets and adjusts based on feedback.

#### `/generate prose <chapter>`
Generate full prose for a chapter (LOD0).
- **chapter**: Chapter number to generate (required)
- Uses chapter outline as blueprint
- Maintains continuity with previous chapters
- Saves to chapters/chapter-NN.md

#### `/generate marketing [components]`
Generate Amazon KDP marketing metadata using LLM.
- **components** (optional): Specific metadata to generate
  - `all` (default): Generate description and keywords
  - `description`: Book description only (100-150 words, HTML formatted)
  - `keywords`: 7 keyword boxes only (50 characters each)
- Prerequisites:
  - Title and author must be set (`/metadata title` and `/metadata author`)
  - Premise must exist (generates from all available content)
- Features:
  - **Book Description**: Compelling 100-150 word pitch with HTML formatting
  - **Keywords**: 7 optimized keyword boxes for Amazon search
  - Builds context from premise, treatment, chapters.yaml, and first chapter prose
  - Saves to `publishing-metadata.md` file
  - Progress spinners and formatted display
- Examples:
  - `/generate marketing` - Generate description and keywords
  - `/generate marketing description` - Only book description
  - `/generate marketing keywords` - Only keywords
- See also: `docs/EXPORT_AND_PUBLISHING_GUIDE.md` for complete publishing workflow

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
Get honest, free-form feedback on your story without rigid categorization.

**Types:**
- `premise` - Analyze premise quality
- `treatment` - Analyze treatment structure
- `chapters` - Analyze chapter outlines
- `prose` - Analyze chapter prose (specify chapter number)
- `all` - Run comprehensive analysis

**Philosophy:**
- **Simplified Prompt**: "Rate the quality and provide constructive criticism. Focus on what matters most."
- **Free-Form Feedback**: LLM identifies what actually matters instead of being forced into rigid dimensions
- **Authentic Analysis**: No prescribed categories means more honest, organic observations
- **Fast & Simple**: Shorter prompt = faster, cheaper analysis

**Examples:**
```bash
/analyze premise              # Analyze premise quality
/analyze treatment            # Analyze treatment structure
/analyze prose 1              # Analyze chapter 1 prose
/analyze chapters             # Analyze all chapter outlines
```

**Output Format:**
```
📊 Analysis: Chapters

Grade: B+ (Very Good)
Strong plotting but pacing issues in Act II

The chapters demonstrate solid three-act structure with clear character arcs.
World-building is rich and immersive. However, Act II suffers from pacing
problems that slow momentum.

📝 Feedback:
  • Act II drags - consolidate chapters 9-11 to maintain momentum
  • Protagonist's motivation unclear in chapter 5 - needs stronger setup
  • Subplot with minor character feels disconnected from main plot

✓ Strengths:
  • Excellent world-building with vivid atmospheric descriptions
  • Strong character voice consistency throughout
  • Natural dialogue that reveals character

🎯 Next Steps:
  Consolidate middle chapters to tighten pacing and clarify protagonist
  motivation in Act I
```

**Report Includes:**
- Letter Grade (A+ through F) with justification
- Overall assessment (2-3 sentences)
- Specific feedback points with concrete suggestions
- Story strengths
- Single most impactful next step
- Saved to `analysis/[type]-[timestamp].md`

#### `/cull <target>`
Delete generated content with cascade deletion.

Targets:
- `prose` - Delete all chapter prose files (chapter-XX.md)
- `chapters` - Delete chapters.yaml + cascade to prose
- `treatment` - Delete treatment.md + cascade to chapters and prose
- `premise` - Delete premise_metadata.json + cascade to all downstream content

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

#### `/wordcount`
Intelligently recalculate word count targets for chapters using act-aware depth architecture.

**What It Does:**
- Recalculates word targets based on actual event counts in each chapter
- Uses **act-aware depth architecture** to ensure appropriate climax intensity
- Applies mathematical formulas (no LLM calls - free and deterministic)
- Considers three-act structure and narrative pacing automatically

**Prerequisites:**
- Must have chapters.yaml with key_events (run `/generate chapters` first)
- No model selection needed (uses pure mathematics)

**How It Works - The Act-Aware Architecture:**

AgenticAuthor uses a sophisticated system that treats **complexity** (event count) and **depth** (words per event) as independent variables:

1. **Detects Story Form**: Automatically identifies form from your target word count or taxonomy
   - Flash Fiction (300-1,500) → Novelette (7,500-20,000) → Novel (50,000-110,000) → Epic (110,000-200,000)

2. **Applies Base Pacing**: Uses your pacing selection to set baseline depth
   - Fast: 800 words/event (for action-heavy stories)
   - Moderate: 950 words/event (balanced development)
   - Slow: 1,200 words/event (deep exploration)

3. **Adjusts by Act Position**: Applies act-specific multipliers for proper three-act pacing
   - **Act I** (first 25% of chapters):
     - More events (1.3×) - setup, world-building, character intro
     - Slightly efficient depth (0.95×) - many events to cover
   - **Act II** (middle 50% of chapters):
     - Standard events (1.0×) - rising action
     - Standard depth (1.0×) - baseline development
   - **Act III** (final 25% of chapters):
     - Fewer events (0.7×) - focused conflict
     - **Much deeper** (1.35×) - emotional intensity, detail, pacing

4. **Calculates Per Chapter**: For each chapter, word target = events × act_words_per_event
   - Example (80K novel, moderate pacing):
     - Chapter 1 (Act I): 5 events × 902 w/e = 4,510 words
     - Chapter 10 (Act II): 4 events × 950 w/e = 3,800 words
     - Chapter 18 (Act III): 3 events × 1,282 w/e = 3,846 words

**Why This Architecture?**

Traditional flat calculations made climaxes feel rushed:
- Act III had fewer events (focused conflict)
- But same depth per event as setup chapters
- Result: Climaxes were 40% SHORTER than Act I - underweight!

With act-aware depth:
- Act III has fewer events BUT deeper development per event
- Climaxes are slightly shorter overall (-5.5%) but much more intense
- Reader expectations met - climaxes feel substantial

**What You'll See:**
```
Calculating word counts (act-aware):
  Form: Novel
  Pacing: moderate
  Base words/event: 950 (Act II baseline)
  Act multipliers: Act I=0.95x, Act II=1.00x, Act III=1.35x

  Chapter 1 (Act I): 5 events × 902 w/e = 4,510 words (was 4,000)
  Chapter 10 (Act II): 4 events × 950 w/e = 3,800 words (was 3,500)
  Chapter 18 (Act III): 3 events × 1,282 w/e = 3,846 words (was 2,500)

Total: 84,900 words across 20 chapters
```

**Output:**
- Shows form, pacing, and multipliers used
- Lists each chapter with act position and calculation
- Displays before/after comparison with deltas
- Shows total target word count
- Updates chapters.yaml automatically
- Auto-commits changes

**Examples:**
```bash
/wordcount   # Recalculate all chapter word targets
```

**When to Use:**
- After editing chapter outlines (adding/removing events)
- When chapter word counts seem off
- After changing pacing in taxonomy
- To see act-aware calculation applied to your story

**Mathematical vs LLM:**
This command uses deterministic mathematical formulas instead of LLM analysis:
- **Benefits**: Free (no API calls), consistent (same input = same output), transparent (see the math)
- **Trade-offs**: Can't assess complexity beyond event count
- **Result**: Fast, predictable, and sufficient for 90% of cases

**Word Count Ranges by Story Form:**
- Flash Fiction: 300-1,500 words
- Short Story: 1,500-7,500 words
- Novelette: 7,500-20,000 words
- Novella: 20,000-50,000 words
- Novel: 50,000-110,000 words
- Epic: 110,000-200,000 words

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

### Book Metadata and Export

#### `/metadata [key] [value]`
View or set book metadata for export.
- **No args**: Display all metadata in a formatted table
- **key only**: Show specific metadata field
- **key and value**: Set metadata value

**Supported Fields:**
- `title` - Book title (required for export)
- `author` - Author name (required for export)
- `copyright` - Copyright year (1900-2100, defaults to current year)

**Features:**
- Auto-creates frontmatter template on first metadata set
- Validates copyright year range (1900-2100)
- Shows warnings if required fields (title, author) are missing
- Values stored in `config.yaml` under `book_metadata`
- Copyright year automatically set to current year if not specified

**Examples:**
```bash
/metadata                          # View all metadata
/metadata title "The Shadow Protocol"
/metadata author "Jane Doe"
/metadata copyright 2025
```

#### `/export <format> [filename]`
Export book to professional formats for publishing.

**Formats:**
- `rtf` - Rich Text Format for Kindle/ebook publishing
- `markdown` or `md` - Combined markdown file

**Features:**
- Checks for required metadata (title, author) before export
- Creates `exports/` directory automatically
- Default filename based on book title
- Custom filename support (absolute or relative paths)
- Shows file size and chapter count after export
- Professional formatting:
  - Title page with centered title and author
  - Copyright page with legal text
  - Frontmatter sections (dedication, acknowledgments)
  - Chapter headers with numbers and titles
  - Proper paragraph formatting (first-line indent, justification)
  - Scene breaks (centered * * *)
  - Markdown formatting converted to RTF (bold, italic)

**RTF Format Details:**
- Times New Roman font (standard for ebooks)
- 12pt font size
- First-line indent (0.25") for paragraphs (except first paragraph after headings)
- Justified text alignment
- Page breaks between chapters
- Em dash and en dash support
- Variable replacement: {{title}}, {{author}}, {{copyright_year}}

**Examples:**
```bash
/export rtf                        # Export to default path: exports/book-title.rtf
/export rtf my-book.rtf            # Custom filename
/export markdown                   # Export to markdown
/export md                         # Short form
```

**Default Export Paths:**
- RTF: `books/my-novel/exports/my-novel-title.rtf`
- Markdown: `books/my-novel/exports/my-novel-title.md`

**Frontmatter Template:**
When you first set metadata, a `frontmatter.md` template is created with:
- Title page section
- Copyright section with standard legal text
- Dedication section (placeholder)
- Acknowledgments section (placeholder)

---

#### `/copyedit [--auto]`
Professional copy editing pass for all chapter prose files.

**What It Does:**
- Edits ONLY chapter prose files (`chapters/chapter-XX.md`)
- Uses chapters.yaml as self-contained reference (metadata, characters, world, outlines)
- Passes ALL chapters for full story context (edited + remaining original)
- Processes chapters sequentially with accumulated context
- Creates timestamped backup before editing
- Shows preview with statistics before applying (unless --auto)

**What It Fixes:**
- Grammar errors (subject-verb agreement, tense consistency)
- Spelling mistakes and typos
- Punctuation errors (commas, semicolons, dialogue formatting)
- Inconsistent character details across chapters
- Pronoun consistency (especially unisex names like Alex, Jordan, Sam)
- Timeline contradictions
- Unclear or ambiguous sentences
- Dialogue formatting issues
- Factual continuity errors

**What It Does NOT Change:**
- Plot events or story structure
- Character personalities, motivations, or arcs
- Dialogue content (only fixes formatting/grammar)
- Author's narrative voice or stylistic choices
- Scene order, pacing, or dramatic beats

**Context Architecture:**
```
Chapter 1: chapters.yaml + [ch1, ch2, ..., ch20] (all original)
Chapter 2: chapters.yaml + [edited_ch1] + [ch2, ch3, ..., ch20] (original)
Chapter N: chapters.yaml + [edited_ch1...N-1] + [chN, chN+1, ...] (original)
```

Token usage stays constant (~200k) - just redistributes between edited and original.

**Examples:**
```bash
/copyedit           # Edit all chapters with preview
/copyedit --auto    # Auto-apply without preview
```

**Preview Display:**
- Statistics (word count, errors fixed, changes)
- Summary of changes made
- Continuity fixes applied
- Pronoun consistency tracking
- Quality warnings (if any)

**Configuration:**
- Temperature: 0.3 (precision over creativity)
- Backup location: `.agentic/backups/copy_edit_YYYYMMDD_HHMMSS/`
- Checkpoint saving for resume capability
- Git commit after completion

Edit `frontmatter.md` to customize sections. Use variables like {{title}}, {{author}}, etc. for automatic replacement during export.

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
| `Escape` | Clear current input line |
| `Ctrl+C` | Exit application (with confirmation) |
| `Ctrl+L` | Clear screen |
| `Up/Down` | Navigate command history |
| `Tab` | Auto-complete commands, genres, and models |
