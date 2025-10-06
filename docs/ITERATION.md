# Iteration System Design

## Overview

The iteration system allows users to provide natural language feedback to modify any part of their book project. The system uses **unified diff format** as the primary output mechanism, enabling precise, traceable changes with full git integration.

## Core Principles

1. **Natural Language First**: Users simply describe what they want changed
2. **Unified Diff Output**: Model generates patches in standard unified diff format
3. **Smart Scale Detection**: Automatically detect if changes are small (patch) or large (regenerate)
4. **Confidence-Based Routing**: >0.8 confidence = execute, <0.8 = clarify
5. **Auto-Commit**: Every iteration creates a descriptive git commit
6. **Fail Early**: Validate content exists before attempting iteration

## Iteration Flow

```
User Input: "Add more dialogue to chapter 3"
    ↓
Intent Analysis (LLM call with structured JSON)
    ↓
    ├─ High Confidence (>0.8)
    │   ↓
    │   Determine Scale (patch vs regenerate)
    │   ↓
    │   ├─ Small Change → Generate Unified Diff
    │   │   ↓
    │   │   Apply Patch
    │   │   ↓
    │   │   Git Commit: "Iterate chapter 3: add dialogue"
    │   │
    │   └─ Large Change → Full Regeneration
    │       ↓
    │       Call appropriate generator (premise/treatment/chapters/prose)
    │       ↓
    │       Git Commit: "Regenerate chapter 3: [reason]"
    │
    └─ Low Confidence (<0.8)
        ↓
        Ask Clarification
        ↓
        Retry with clarified input
```

## Unified Diff Format

### Why Unified Diff?

1. **Standard Format**: Universally understood, works with all git tools
2. **Precise Changes**: Shows exact context and modifications
3. **LLM-Friendly**: Models trained on code can generate diffs reliably
4. **Reviewable**: Users can see exactly what will change before applying
5. **Reversible**: Can be undone with `git revert` or `patch -R`

### Example Diff Output

```diff
--- a/chapters/chapter-03.md
+++ b/chapters/chapter-03.md
@@ -45,7 +45,12 @@

 Sarah entered the library, her footsteps echoing on the marble floor.

-The old librarian looked up from his desk.
+The old librarian looked up from his desk. "Can I help you find something?"
+he asked, his voice raspy with age.
+
+"I'm looking for books on ancient magic," Sarah replied, trying to keep
+her voice steady despite her nervousness.
+
+"Ah," he said with a knowing smile. "Third floor, restricted section."

 She made her way to the stairs, wondering what secrets awaited.
```

## Scale Detection

The system automatically determines whether a change should be a patch or a full regeneration.

### Small Changes (Patch)
- Adding/removing dialogue
- Tweaking descriptions
- Minor plot adjustments
- Character detail changes
- Fixing inconsistencies
- Style refinements

**Characteristics:**
- Changes affect <30% of content
- Preserves overall structure
- Maintains existing narrative flow
- Can be expressed as precise line edits

### Large Changes (Regenerate)
- Major plot revisions
- Character arc changes
- Structural rewrites
- Genre/tone shifts
- Adding/removing scenes
- Premise modifications

**Characteristics:**
- Changes affect >30% of content
- Alters fundamental structure
- Requires full context regeneration
- Cannot be cleanly expressed as line edits

### Detection Logic

```python
def detect_scale(intent: dict, content: str) -> str:
    """
    Determine if change should be patch or regenerate.

    Args:
        intent: Parsed intent with scope, target, action
        content: Current content to be modified

    Returns:
        "patch" or "regenerate"
    """
    # Explicit keywords indicate regeneration
    regen_keywords = [
        'rewrite', 'completely change', 'start over',
        'different approach', 'major revision',
        'restructure', 'rethink', 'total rewrite'
    ]

    if any(kw in intent['user_input'].lower() for kw in regen_keywords):
        return "regenerate"

    # Check scope
    if intent['scope'] == 'entire':  # "rewrite the whole book"
        return "regenerate"

    if intent['scope'] == 'multiple':  # "change chapters 3-7"
        return "regenerate"

    # Structural changes require regeneration
    structural_actions = [
        'add_chapter', 'remove_chapter', 'merge_chapters',
        'change_structure', 'reorder', 'split'
    ]

    if intent['action'] in structural_actions:
        return "regenerate"

    # Default to patch for targeted, specific changes
    if intent['scope'] == 'specific':  # "add dialogue to chapter 3"
        return "patch"

    # When in doubt, ask the model
    return "ask_model"  # Escalate to LLM for classification
```

## Intent Analysis

### JSON Structure

```json
{
  "intent_type": "modify",
  "confidence": 0.92,
  "target_type": "chapter",
  "target_id": "3",
  "scope": "specific",
  "action": "add_dialogue",
  "description": "Add more dialogue between Sarah and the librarian",
  "scale": "patch",
  "reasoning": "User wants to add dialogue to specific scene in chapter 3, which is a localized change that doesn't affect overall structure"
}
```

### Intent Types

1. **modify**: Change existing content
2. **add**: Add new content
3. **remove**: Remove content
4. **regenerate**: Full regeneration with new direction
5. **analyze**: Request analysis (not iteration)
6. **clarify**: Need more information

### Target Types

- `premise`: Story premise
- `treatment`: Treatment document
- `chapter`: Specific chapter
- `chapters`: Multiple chapters
- `prose`: Prose content
- `taxonomy`: Genre/style metadata
- `project`: Project-wide changes

### Scope Levels

- `specific`: Single, localized change
- `section`: Part of a chapter/document
- `multiple`: Multiple chapters/sections
- `entire`: Whole document/project

## Implementation Components

### 1. Intent Analyzer (`src/generation/iteration/intent.py`)

```python
class IntentAnalyzer:
    """Analyze user feedback to determine intent."""

    async def analyze(self, feedback: str, context: dict) -> dict:
        """
        Analyze feedback and return structured intent.

        Args:
            feedback: User's natural language feedback
            context: Current project context (premise, treatment, etc.)

        Returns:
            Structured intent dict with confidence score
        """
        # Use LLM to parse intent
        # Return JSON structure
        pass
```

### 2. Diff Generator (`src/generation/iteration/diff.py`)

```python
class DiffGenerator:
    """Generate unified diffs for content changes."""

    async def generate_diff(
        self,
        original: str,
        intent: dict,
        context: dict
    ) -> str:
        """
        Generate unified diff for the requested change.

        Args:
            original: Original content
            intent: Parsed intent structure
            context: Full project context

        Returns:
            Unified diff as string
        """
        # Use LLM to generate diff
        # Validate diff format
        # Return as string
        pass

    def apply_diff(self, original: str, diff: str) -> str:
        """Apply unified diff to original content."""
        # Use Python's difflib or subprocess patch
        pass
```

### 3. Scale Detector (`src/generation/iteration/scale.py`)

```python
class ScaleDetector:
    """Detect if change should be patch or regenerate."""

    def detect_scale(self, intent: dict, content: str) -> str:
        """
        Determine if change should be patch or regenerate.

        Returns:
            "patch", "regenerate", or "ask_model"
        """
        # Implement detection logic
        pass

    async def ask_model_for_scale(
        self,
        intent: dict,
        content: str
    ) -> str:
        """Ask LLM to classify scale when unclear."""
        pass
```

### 4. Iteration Coordinator (`src/generation/iteration/coordinator.py`)

```python
class IterationCoordinator:
    """Coordinate the iteration process."""

    async def process_feedback(
        self,
        feedback: str,
        project: Project
    ) -> dict:
        """
        Process user feedback and execute iteration.

        Returns:
            Result dict with success status and commit info
        """
        # 1. Analyze intent
        intent = await self.intent_analyzer.analyze(feedback, context)

        # 2. Check confidence
        if intent['confidence'] < 0.8:
            return self._request_clarification(intent)

        # 3. Detect scale
        scale = self.scale_detector.detect_scale(intent, content)

        # 4. Execute based on scale
        if scale == "patch":
            result = await self._execute_patch(intent, project)
        else:
            result = await self._execute_regenerate(intent, project)

        # 5. Git commit
        self._commit_change(result, intent)

        return result
```

## Model Prompts

### Intent Analysis Prompt

```jinja2
You are analyzing user feedback for a book generation system.

Project Context:
- Current Content: {{ target_type }} ({{ target_id }})
- Premise: {{ premise[:200] }}...
- Treatment: {{ treatment[:200] }}...

User Feedback: "{{ feedback }}"

Analyze the intent and respond with JSON:

{
  "intent_type": "modify|add|remove|regenerate|analyze|clarify",
  "confidence": 0.0-1.0,
  "target_type": "premise|treatment|chapter|chapters|prose|taxonomy|project",
  "target_id": "specific identifier or null",
  "scope": "specific|section|multiple|entire",
  "action": "add_dialogue|fix_plot|enhance_description|etc",
  "description": "clear description of what user wants",
  "scale": "patch|regenerate|unclear",
  "reasoning": "why you classified it this way"
}

Be specific and confident. If unclear, set confidence < 0.8.
```

### Diff Generation Prompt

```jinja2
You are generating a unified diff to modify a book chapter.

Original Content:
```
{{ original_content }}
```

Intent: {{ intent.description }}
Action: {{ intent.action }}

Generate a unified diff that makes the requested change.

Requirements:
1. Use standard unified diff format
2. Include adequate context (3 lines before/after)
3. Make minimal, precise changes
4. Preserve formatting and style
5. Maintain narrative consistency

Output ONLY the diff, starting with "--- a/" and "+++ b/".

Example format:
--- a/chapters/chapter-03.md
+++ b/chapters/chapter-03.md
@@ -45,7 +45,12 @@
 [context lines]
-[old line]
+[new line]
 [context lines]
```

### Scale Detection Prompt

```jinja2
You are determining if a change should be a small patch or full regeneration.

User Request: "{{ feedback }}"

Current Content Length: {{ content_length }} words
Intent: {{ intent.description }}

Classify as:
- "patch": Small, localized change (<30% of content affected)
- "regenerate": Large structural change (>30% affected or fundamental restructuring)

Respond with JSON:
{
  "scale": "patch|regenerate",
  "estimated_change_percentage": 0-100,
  "reasoning": "why this scale is appropriate"
}
```

## Error Handling

### Patch Application Failures

```python
try:
    patched = self.diff_generator.apply_diff(original, diff)
except PatchError as e:
    # Fallback to regeneration
    self.logger.warning(f"Patch failed: {e}. Falling back to regeneration.")
    return await self._execute_regenerate(intent, project)
```

### Invalid Diffs

```python
def validate_diff(diff: str) -> bool:
    """Validate diff format before applying."""
    if not diff.startswith('---'):
        return False
    if '+++ ' not in diff:
        return False
    if '@@ ' not in diff:
        return False
    return True
```

## User Experience

### Display Diff for Review (Optional)

```python
def show_diff_preview(diff: str) -> bool:
    """Show diff and ask for confirmation."""
    console.print("\n[bold]Proposed Changes:[/bold]\n")
    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)

    confirm = Prompt.ask(
        "\nApply these changes?",
        choices=["y", "n", "e"],  # yes, no, edit
        default="y"
    )

    return confirm == "y"
```

### Progress Display

```
📝 Analyzing feedback...
   ✓ Intent: modify chapter 3 (confidence: 0.94)
   ✓ Scale: patch (localized change)

🔧 Generating changes...
   ✓ Diff created: +12 lines, -3 lines

📦 Applying changes...
   ✓ Chapter 3 updated
   ✓ Git commit: "Iterate chapter 3: add dialogue"

✅ Done! Chapter 3 has been updated with more dialogue.
```

## Git Integration

### Commit Messages

```python
def create_commit_message(intent: dict, scale: str) -> str:
    """Generate descriptive commit message."""
    action = intent['action'].replace('_', ' ')
    target = f"{intent['target_type']} {intent['target_id']}" if intent['target_id'] else intent['target_type']

    if scale == "patch":
        return f"Iterate {target}: {action}"
    else:
        return f"Regenerate {target}: {action}"
```

### Diff Viewing

```bash
# View last iteration
git show HEAD

# View diff before applying
git diff --cached

# Rollback iteration
git revert HEAD
```

## Testing Strategy

### Unit Tests

```python
def test_intent_analysis():
    """Test intent parsing."""
    feedback = "Add more dialogue to chapter 3"
    intent = await analyzer.analyze(feedback, context)

    assert intent['intent_type'] == 'modify'
    assert intent['target_type'] == 'chapter'
    assert intent['target_id'] == '3'
    assert intent['action'] == 'add_dialogue'
    assert intent['confidence'] > 0.8

def test_diff_generation():
    """Test diff creation."""
    diff = await generator.generate_diff(original, intent, context)

    assert diff.startswith('---')
    assert '+++ ' in diff
    assert '@@ ' in diff
    assert validate_diff(diff)

def test_patch_application():
    """Test applying diffs."""
    patched = generator.apply_diff(original, diff)

    assert patched != original
    assert 'new dialogue' in patched
    assert len(patched) > len(original)
```

### Integration Tests

```python
async def test_full_iteration_flow():
    """Test complete iteration process."""
    project = create_test_project()
    feedback = "Add more description to the library scene in chapter 3"

    result = await coordinator.process_feedback(feedback, project)

    assert result['success']
    assert result['scale'] == 'patch'

    # Note: Git commits are handled by the interactive session layer
    # Commits are prefixed with project name: "[project-name] Iterate chapter 3: add dialogue"
```

## Performance Considerations

### Caching

- Cache intent analysis for similar requests
- Cache model context to avoid re-reading files
- Cache taxonomy and metadata

### Token Optimization

- For patches: Only send relevant sections (not full content)
- Use smaller models for intent analysis (faster, cheaper)
- Use larger models for diff generation (better accuracy)

### Parallel Processing

- Analyze intent while loading content
- Pre-validate files while waiting for LLM response

## Future Enhancements

### Multi-Turn Iteration

```
User: "Add more dialogue"
System: [applies change]
User: "Make it more casual"
System: [iterates on previous change]
```

### Batch Iteration

```
User: "Add dialogue to chapters 3, 5, and 7"
System: [processes all three in parallel]
```

### Interactive Diff Review

```
System: "I'll add dialogue here: [shows specific location]"
User: "No, earlier in the chapter"
System: [adjusts location]
```

### Learned Preferences

Track user's iteration patterns:
- Preferred style adjustments
- Common feedback types
- Typical scope preferences

## Examples

### Example 1: Small Patch

**Input:**
```
User: "Add more dialogue between Sarah and the librarian in chapter 3"
```

**Process:**
1. Intent: modify chapter 3, add_dialogue, confidence 0.95
2. Scale: patch (specific scene, <10% of chapter)
3. Generate diff with 8 new lines of dialogue
4. Apply patch
5. Commit: "Iterate chapter 3: add dialogue"

**Output:**
```diff
--- a/chapters/chapter-03.md
+++ b/chapters/chapter-03.md
@@ -45,7 +45,15 @@

 Sarah entered the library, her footsteps echoing on the marble floor.

-The old librarian looked up from his desk.
+The old librarian looked up from his desk. "Can I help you find something?"
+he asked, peering over his spectacles.
+
+"I'm looking for information on the Crimson Archives," Sarah said,
+choosing her words carefully.
+
+The librarian's expression darkened. "That section is restricted.
+You'll need special permission."
+
+"I have permission," Sarah replied, producing the sealed letter.

 She made her way to the stairs, wondering what secrets awaited.
```

### Example 2: Full Regeneration

**Input:**
```
User: "Rewrite the premise to be darker and more horror-focused"
```

**Process:**
1. Intent: regenerate premise, change_tone, confidence 0.88
2. Scale: regenerate (fundamental change to core concept)
3. Call PremiseGenerator with new constraints
4. Replace premise.md
5. Commit: "Regenerate premise: darker horror tone"

**Output:**
```
Regenerating premise with new direction...

Previous: [high fantasy adventure]
New: [dark horror fantasy]

✓ Premise regenerated (250 words)
✓ Taxonomy updated: genre -> horror
✓ Git commit: "Regenerate premise: darker horror tone"

Note: Treatment and chapters may need regeneration to match new tone.
```

## Summary

The iteration system provides:

1. **Natural Language Interface**: Users describe changes naturally
2. **Unified Diff Output**: Standard format for precise, reviewable changes
3. **Smart Scaling**: Automatically chooses patch vs regenerate
4. **Git Integration**: Every change is tracked and reversible
5. **Fail-Safe**: Clear error handling and fallback to regeneration

This design balances flexibility, precision, and usability while maintaining the core principle of git-backed version control for all changes.
