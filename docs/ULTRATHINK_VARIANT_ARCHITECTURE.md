# Ultrathink Analysis: Multi-Variant Chapter Generation Architecture

## Summary

Implement multi-variant chapter generation where:
1. `/generate chapters` - generates foundation + 4 parallel variants
2. `/finalize chapters` - LLM judges variants and picks winner

## Reusable Components Analysis

### What Can Be Reused

**1. Foundation Generation** (`chapters.py:144-422`)
- `ChapterGenerator._generate_foundation()` - generates metadata, characters, world
- **Reuse Strategy**: Call ONCE, share across all 4 variants
- **Why**: Foundation is context, not creative output - variants should differ in chapters, not foundation
- **Location**: Save to `chapter-beats-variants/foundation.yaml` (shared)

**2. Single-Shot Generation** (`chapters.py:1093-1351`)
- `ChapterGenerator._generate_single_shot()` - generates all chapters in one LLM call
- **Reuse Strategy**: Call 4 TIMES in parallel with different temperatures
- **Why**: Core generation logic is solid, just need temperature variation
- **Modification Needed**: Accept `output_dir` parameter to save to variant directories

**3. OpenRouter Client** (`self.client.streaming_completion()`)
- Already supports `temperature` parameter
- Already supports `display` and `display_label` for streaming
- **Reuse Strategy**: Use as-is, just call 4 times with asyncio.gather()
- **Why**: No changes needed, perfect for parallel execution

**4. Project Methods** (`project.py`)
- `Project.save_foundation()` - saves foundation.yaml
- `Project.save_chapter_beat()` - saves individual chapter files
- **Reuse Strategy**: Create variant-aware versions
- **Modification Needed**: Accept `variant_dir` parameter for storage location

**5. Rich Console** (`self.console`)
- Already used throughout ChapterGenerator
- **Reuse Strategy**: Use for variant progress display
- **Why**: Consistent UX

### What Needs to Be Created

**1. VariantManager Class** (NEW)
- **Purpose**: Coordinate parallel variant generation
- **Location**: `src/generation/variants.py`
- **Methods**:
  - `generate_variants(foundation, chapter_count, total_words)` - runs 4 parallel generations
  - `_generate_single_variant(variant_num, temperature, ...)` - wraps ChapterGenerator._generate_single_shot()
  - `_get_variant_dir(variant_num)` - returns Path to variant-N/
  - `list_variants()` - returns list of available variants
- **Key Feature**: Uses asyncio.gather() for parallel execution

**2. JudgingCoordinator Class** (NEW)
- **Purpose**: LLM-based variant evaluation
- **Location**: `src/generation/judging.py`
- **Methods**:
  - `judge_variants(foundation, variants_data)` - main judging call
  - `_build_judging_prompt(foundation, variants)` - creates prompt with minimal structure
  - `_save_decision(winner_index, reasoning)` - saves to decision.json
- **Key Feature**: Minimal structure (user requested LLM freedom)

**3. Rich Live Display** (NEW)
- **Purpose**: Visual progress for 4 parallel streams
- **Implementation**: Rich.Live with 4 progress bars/status lines
- **Location**: Within VariantManager.generate_variants()
- **Key Feature**: Real-time updates as each variant progresses

**4. Command Handler** (NEW)
- **Purpose**: `/finalize chapters` command
- **Location**: `src/cli/interactive.py`
- **Integration**: Call JudgingCoordinator, copy winner to chapter-beats/

## Detailed Architecture

### File Structure

```
books/my-book/
├── chapter-beats-variants/          # NEW - temporary variant storage
│   ├── foundation.yaml              # Shared foundation
│   ├── variant-1/
│   │   ├── chapter-01.yaml
│   │   ├── chapter-02.yaml
│   │   └── ...
│   ├── variant-2/
│   │   └── ...
│   ├── variant-3/
│   │   └── ...
│   ├── variant-4/
│   │   └── ...
│   └── decision.json                # Judging results
├── chapter-beats/                   # FINALIZED chapters (winner)
│   ├── foundation.yaml
│   ├── chapter-01.yaml
│   └── ...
└── ...
```

### Temperature Strategy

**Why Vary Temperature?**
- Temperature controls creativity vs consistency
- 0.65-0.80 range balances quality with variation
- Too low (<0.5): All variants too similar
- Too high (>0.9): Risk of inconsistent/chaotic output

**Variant Configuration:**
```python
VARIANT_CONFIGS = [
    {"variant": 1, "temperature": 0.65, "label": "Conservative"},
    {"variant": 2, "temperature": 0.70, "label": "Balanced-Conservative"},
    {"variant": 3, "temperature": 0.75, "label": "Balanced-Creative"},
    {"variant": 4, "temperature": 0.80, "label": "Creative"},
]
```

### Code Reuse Pattern

**GOOD: Wrap existing logic, don't duplicate**
```python
class VariantManager:
    def __init__(self, chapter_generator: ChapterGenerator):
        self.generator = chapter_generator  # Reuse existing generator

    async def _generate_single_variant(self, variant_num, temperature, ...):
        # Call existing _generate_single_shot with modified params
        return await self.generator._generate_single_shot(
            context=context,
            foundation=foundation,
            total_words=total_words,
            chapter_count=chapter_count,
            temperature=temperature,  # ONLY difference
            output_dir=self._get_variant_dir(variant_num)  # NEW param
        )
```

**BAD: Copy-paste entire method**
```python
class VariantManager:
    async def _generate_single_variant(self, ...):
        # Copy-paste all 300 lines from _generate_single_shot
        # DUPLICATION = BAD
```

### Modification Strategy

**ChapterGenerator._generate_single_shot() changes:**
```python
async def _generate_single_shot(
    self,
    context: Dict[str, Any],
    foundation: Dict[str, Any],
    total_words: Optional[int],
    chapter_count: Optional[int],
    genre: str,
    pacing: str,
    feedback: Optional[str] = None,
    temperature: float = 0.7,  # NEW: Accept temperature (default unchanged)
    output_dir: Optional[Path] = None  # NEW: Accept custom output directory
) -> Dict[str, Any]:
    """..."""

    # ... existing code ...

    # OLD: Hardcoded temperature
    # temperature=0.7

    # NEW: Use parameter
    result = await self.client.streaming_completion(
        model=self.model,
        messages=[...],
        temperature=temperature,  # Use parameter
        ...
    )

    # OLD: Save to self.project.chapter_beats_dir
    # beats_dir = self.project.path / 'chapter-beats'

    # NEW: Use parameter or default
    if output_dir is None:
        beats_dir = self.project.chapter_beats_dir
    else:
        beats_dir = output_dir

    # ... rest unchanged ...
```

**CRITICAL: Minimal changes, maximum reuse**

### Parallel Execution Pattern

```python
async def generate_variants(self, foundation, chapter_count, total_words):
    """Generate 4 variants in parallel."""

    # Build tasks for parallel execution
    tasks = []
    for config in VARIANT_CONFIGS:
        task = self._generate_single_variant(
            variant_num=config['variant'],
            temperature=config['temperature'],
            foundation=foundation,
            chapter_count=chapter_count,
            total_words=total_words
        )
        tasks.append(task)

    # Execute in parallel with Rich Live Display
    with Live(...) as live:
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle partial failures (2+ variants = continue)
    successful = [r for r in results if not isinstance(r, Exception)]
    if len(successful) < 2:
        raise Exception("Need at least 2 variants to continue")

    return successful
```

### Judging Prompt Strategy

**User Requirement:** "allow the LLM freedom to judge how it sees fit; no need to overly provide structure"

**GOOD: Minimal structure, maximum freedom**
```python
prompt = f"""You are judging 4 different chapter outline variants for the same story.

FOUNDATION (shared by all variants):
```yaml
{foundation_yaml}
```

VARIANT 1 (Temperature: 0.65 - Conservative):
```yaml
{variant_1_yaml}
```

VARIANT 2 (Temperature: 0.70 - Balanced-Conservative):
```yaml
{variant_2_yaml}
```

VARIANT 3 (Temperature: 0.75 - Balanced-Creative):
```yaml
{variant_3_yaml}
```

VARIANT 4 (Temperature: 0.80 - Creative):
```yaml
{variant_4_yaml}
```

YOUR TASK:
Evaluate all 4 variants and select the BEST one for this story.

Consider whatever criteria you find most important for story quality:
- Narrative coherence
- Character development
- Plot structure
- Uniqueness of events
- Emotional impact
- Pacing
- Any other factors you deem relevant

RETURN FORMAT (JSON):
{{
  "winner": 1-4,
  "reasoning": "Your explanation for why this variant is best (2-4 sentences)"
}}

Return ONLY valid JSON, no markdown fences."""
```

**BAD: Over-structured, prescriptive**
```python
# DON'T DO THIS:
prompt = """
Score each variant on these 10 criteria:
1. Narrative coherence (1-10)
2. Character development (1-10)
3. Plot structure (1-10)
... (7 more)

Then weight them as follows:
- Narrative: 20%
- Character: 15%
... etc
"""
# TOO PRESCRIPTIVE - user wants LLM freedom
```

## Integration Points

### 1. /cull chapters Compatibility

**Current cull_chapters():**
```python
def cull_chapters(self) -> Dict[str, Any]:
    # Deletes chapter-beats/ directory
    beats_dir = self.project.chapter_beats_dir
    if beats_dir.exists():
        # Delete foundation.yaml + chapter-*.yaml
        ...
```

**Updated cull_chapters():**
```python
def cull_chapters(self) -> Dict[str, Any]:
    # Delete BOTH chapter-beats/ AND chapter-beats-variants/
    deleted_files = []

    # Delete finalized chapters
    beats_dir = self.project.chapter_beats_dir
    if beats_dir.exists():
        # ... existing deletion logic ...

    # NEW: Delete variants
    variants_dir = self.project.path / 'chapter-beats-variants'
    if variants_dir.exists():
        for variant_dir in variants_dir.glob('variant-*'):
            for chapter_file in variant_dir.glob('*.yaml'):
                chapter_file.unlink()
                deleted_files.append(str(chapter_file.relative_to(self.project.path)))
            variant_dir.rmdir()

        # Delete foundation and decision.json
        foundation_file = variants_dir / 'foundation.yaml'
        if foundation_file.exists():
            foundation_file.unlink()
            deleted_files.append(str(foundation_file.relative_to(self.project.path)))

        decision_file = variants_dir / 'decision.json'
        if decision_file.exists():
            decision_file.unlink()
            deleted_files.append(str(decision_file.relative_to(self.project.path)))

        # Remove directory
        variants_dir.rmdir()

    # ... rest unchanged ...
```

### 2. Prose Generation Compatibility

**NO CHANGES NEEDED**

Prose generation uses `project.get_chapters_yaml()` which reads from `chapter-beats/`, NOT `chapter-beats-variants/`.

After `/finalize chapters`, winner is copied to `chapter-beats/`, so prose generation continues to work as-is.

**Verification:**
```python
# prose.py uses this:
chapters_data = self.project.get_chapters_yaml()

# project.py:478-499
def get_chapters_yaml(self) -> Optional[Dict[str, Any]]:
    if not self.chapter_beats_dir.exists():  # chapter-beats/, not variants
        return None
    # ... loads from chapter-beats/ ...
```

**SAFE: No modifications needed to prose.py**

### 3. /generate chapters Flow

**Current Flow:**
```
User: /generate chapters
→ ChapterGenerator.generate()
→ Generate foundation
→ Generate all chapters (single-shot)
→ Save to chapter-beats/
→ Done
```

**New Flow:**
```
User: /generate chapters
→ ChapterGenerator.generate() [MODIFIED]
→ Generate foundation (once)
→ Save foundation to chapter-beats-variants/
→ VariantManager.generate_variants()
  → 4 parallel _generate_single_shot() calls
  → Save to variant-1/, variant-2/, variant-3/, variant-4/
  → Display: Rich Live with 4 progress indicators
→ Done (variants ready for judging)

User: /finalize chapters
→ JudgingCoordinator.judge_variants()
  → Load all 4 variants
  → LLM judging call
  → Save decision to decision.json
→ Copy winner to chapter-beats/
→ Done (ready for prose generation)
```

## Error Handling Strategy

### Partial Failures (Variants)

**Requirement**: Continue if 2+ variants succeed

```python
results = await asyncio.gather(*tasks, return_exceptions=True)

successful = []
failed = []

for i, result in enumerate(results, 1):
    if isinstance(result, Exception):
        console.print(f"[yellow]⚠ Variant {i} failed: {result}[/yellow]")
        failed.append((i, result))
    else:
        console.print(f"[green]✓ Variant {i} complete[/green]")
        successful.append((i, result))

if len(successful) < 2:
    raise Exception(f"Only {len(successful)} variants succeeded. Need at least 2.")

console.print(f"\n[cyan]Generated {len(successful)}/4 variants successfully[/cyan]")
# Continue with judging
```

### Judging Failures

**Requirement**: Prompt user for action

```python
try:
    result = await judge_variants(...)
except Exception as e:
    console.print(f"[yellow]Judging failed: {e}[/yellow]")
    console.print("\nOptions:")
    console.print("  1. Retry judging")
    console.print("  2. Manually select variant (1-4)")
    console.print("  3. Abort")

    choice = input("Enter choice: ").strip()

    if choice == "1":
        # Retry
        result = await judge_variants(...)
    elif choice == "2":
        # Manual selection
        variant_num = input("Enter variant number (1-4): ").strip()
        # Use selected variant
    else:
        # Abort
        raise
```

## Visual Display Strategy

### Rich Live Display for Parallel Generation

```python
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

async def generate_variants(self, ...):
    # Create progress table
    table = Table(title="Generating 4 Variants in Parallel")
    table.add_column("Variant", style="cyan")
    table.add_column("Temperature", style="dim")
    table.add_column("Status", style="white")

    # Add rows for each variant
    for config in VARIANT_CONFIGS:
        table.add_row(
            f"Variant {config['variant']}",
            str(config['temperature']),
            "[yellow]Starting...[/yellow]"
        )

    with Live(table, refresh_per_second=4) as live:
        # Start parallel generation
        # Update table rows as variants complete
        ...
```

**Alternative: Sequential Completion Display**
```
[1/4] Variant 1 (temp=0.65): ████████████████ 100% Complete
[2/4] Variant 2 (temp=0.70): ████████████████ 100% Complete
[3/4] Variant 3 (temp=0.75): ████████░░░░░░░░  60% Generating...
[4/4] Variant 4 (temp=0.80): ████░░░░░░░░░░░░  25% Generating...
```

**Recommendation**: Use simple sequential completion (easier to implement, clear UX)

## Summary of Architecture Decisions

1. **Storage**: `chapter-beats-variants/` with foundation + variant-N/ subdirs
2. **Temperature**: 0.65, 0.70, 0.75, 0.80 (balanced range)
3. **Code Reuse**: VariantManager wraps ChapterGenerator (no duplication)
4. **Judging**: Minimal structure, LLM freedom (user requirement)
5. **Parallel Execution**: asyncio.gather() with Rich display
6. **Error Handling**: 2+ variants minimum, user prompts for failures
7. **/cull chapters**: Delete both chapter-beats/ and chapter-beats-variants/
8. **Prose Generation**: No changes needed (uses chapter-beats/ after finalize)

## Files to Create/Modify

### Create:
1. `src/generation/variants.py` - VariantManager class
2. `src/generation/judging.py` - JudgingCoordinator class

### Modify:
1. `src/generation/chapters.py` - Add temperature and output_dir params to _generate_single_shot()
2. `src/cli/interactive.py` - Update /generate chapters, add /finalize chapters
3. `src/generation/cull.py` - Update cull_chapters() to delete variants
4. `src/models/project.py` - Add variant-related helper methods (optional)

## Next Steps

1. ✅ Analyzed reusable components
2. ✅ Created ultrathink analysis document
3. TODO: Design storage structure
4. TODO: Create VariantManager class
5. TODO: Implement temperature variation
6. TODO: Build visual streaming display
7. TODO: Create JudgingCoordinator class
8. TODO: Implement LLM judging
9. TODO: Add /finalize chapters command
10. TODO: Update /generate chapters
11. TODO: Update /cull chapters
12. TODO: Check compatibility
13. TODO: Test full workflow
