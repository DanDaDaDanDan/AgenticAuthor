# project.yaml Usage Analysis

## Where project.yaml is READ

**File:** `src/models/project.py`
**Method:** `_load_metadata()` (lines 149-154)

```python
def _load_metadata(self):
    """Load project metadata from project.yaml."""
    if self.project_file.exists():
        with open(self.project_file) as f:
            data = yaml.safe_load(f)
            self.metadata = ProjectMetadata(**data)
```

This method is called during `Project.__init__()` (line 46), so every time a Project is instantiated, project.yaml is loaded.

---

## ProjectMetadata Fields (lines 10-26)

All fields stored in project.yaml:

```python
class ProjectMetadata(BaseModel):
    name: str
    created_at: datetime
    updated_at: datetime
    author: Optional[str]
    genre: Optional[str]
    taxonomy: Optional[str]
    model: Optional[str]
    word_count: int
    chapter_count: int
    story_type: Optional[str]  # 'short_form' or 'long_form'
    status: str
    tags: List[str]
    iteration_target: Optional[str]  # Current iteration target (premise/treatment/chapters/prose)
    custom_data: Dict[str, Any]
```

---

## What Reads What Fields

### Field: `genre`

**File:** `src/cli/interactive.py`
- Line 578: Get genre for iteration coordinator
- Line 708: Get genre for iteration diff generation
- Lines 888-889: Display genre in project list
- Line 996: Display genre in /status command
- Line 1539: Fallback genre for premise generation
- Line 1546: Fallback genre for batch premise generation
- Line 1572: Fallback genre for iteration
- Line 1961: Fallback genre for treatment generation

**File:** `src/generation/premise.py`
- Line 81: Get genre for taxonomy iteration
- Lines 134-135: Fallback genre for regenerate_with_taxonomy
- Lines 241-242: Fallback genre for detect_genre
- Lines 361-362: Fallback genre for generate
- Lines 580-581: Fallback genre for iterate

**File:** `src/generation/chapters.py`
- Lines 551-552: Fallback genre for chapter generation

**File:** `src/generation/prose.py`
- Lines 82-83: Get genre for prose generation context

**File:** `src/generation/analysis/analyzer.py`
- Lines 109-110: Get genre for analysis context

**File:** `src/generation/iteration/intent.py`
- Line 246: Get genre for intent analysis

---

### Field: `model`

**File:** `src/cli/interactive.py`
- Line 1014: Display model in /status command
- Line 1204: Set model when user selects a model

**File:** `src/generation/premise.py`
- Lines 302-303: Fallback model for regenerate_with_taxonomy
- Lines 384-385: Fallback model for generate
- Lines 479-480: Fallback model for iterate

**File:** `src/generation/prose.py`
- Line 331: Get configured model for prose generation

---

### Field: `word_count`

**File:** `src/cli/main.py`
- Line 162: Display word count in project list

**File:** `src/cli/interactive.py`
- Lines 890-891: Display word count in /open project selector
- Line 1016: Display word count in /status command

**File:** `src/models/project.py`
- Line 590: Set word_count in _update_word_count()
- Line 441: Set word_count in save_story() for short stories

---

### Field: `chapter_count`

**File:** `src/cli/interactive.py`
- Line 1018: Display chapter count in /status command

**File:** `src/models/project.py`
- Line 333: Set chapter_count when saving chapter outlines

---

### Field: `status`

**File:** `src/cli/main.py`
- Line 161: Display status in project list

**File:** `src/cli/interactive.py`
- Line 1019: Display status in /status command

**File:** `src/generation/iteration/intent.py`
- Line 247: Get status for intent analysis

---

### Field: `created_at`

**File:** `src/cli/interactive.py`
- Line 994: Display created date in /status command

**File:** `src/models/project.py`
- Line 663: Set created_at when cloning project

---

### Field: `updated_at`

**File:** `src/cli/main.py`
- Line 163: Display updated date in project list

**File:** `src/cli/interactive.py`
- Lines 892-893: Display days ago in /open project selector
- Line 995: Display updated date in /status command

**File:** `src/models/project.py`
- Multiple locations: Updated via update_timestamp() method when saving any content

---

### Field: `iteration_target`

**File:** `src/cli/interactive.py`
- Lines 238-239: Restore iteration_target when opening project
- Lines 2372-2373: Clear iteration_target when iteration completes
- Lines 2437-2438: Set iteration_target when starting iteration

---

### Field: `story_type`

**File:** `src/generation/short_story.py`
- Lines 170-171: Set story_type to 'short_form' for short stories

**File:** `src/models/project.py`
- Lines 522-523: Check story_type in is_short_form()
- Lines 543-545: Set story_type based on word count detection

---

### Field: `name`

**File:** `src/models/project.py`
- Line 662: Update name when cloning project

---

### Fields NOT directly accessed in code

- `author` - Only used for exporter metadata (not project metadata)
- `taxonomy` - Never read (only written)
- `tags` - Never used
- `custom_data` - Never used

---

## Summary

**ACTIVELY USED FIELDS:**
1. `genre` - Heavily used throughout generation and iteration
2. `model` - Used for model selection and defaults
3. `word_count` - Used for display and tracking
4. `chapter_count` - Used for display
5. `status` - Used for display
6. `created_at` - Used for display
7. `updated_at` - Used for display and tracking
8. `iteration_target` - Used for iteration state management
9. `story_type` - Used for short-form detection
10. `name` - Used for project identification

**UNUSED FIELDS:**
- `author` - Defined but never read (only book_metadata.author is used)
- `taxonomy` - Written but never read
- `tags` - Never used
- `custom_data` - Never used

---

**Conclusion:** project.yaml IS actively used throughout the codebase. Most fields are read and used for display, defaults, or state management.
