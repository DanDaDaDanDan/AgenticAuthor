# Iteration System - Critical Bugs Found

**Date**: 2025-10-23
**Status**: Needs immediate fixes before testing

## Critical Issues

### 1. Chapter Format Mismatch (CRITICAL - System Broken)

**Problem**: Iteration code assumes markdown (`.md`) but actual chapter files are YAML (`.yaml`)

**Affected Code**:
- `iterator.py:133` - `_target_exists()` looks for `chapter-*.md`
- `iterator.py:269-276` - `_get_current_content()` reads `foundation.md`
- `iterator.py:683-689` - `_save_content()` saves as `foundation.md` and `chapter-*.md`

**Impact**: Chapter iteration completely broken - can't find files, can't save results

**Solution Options**:

**Option A**: Convert to markdown for iteration (simpler for LLM)
- Read YAML files, convert to markdown for prompts
- LLM generates markdown
- Convert markdown back to YAML for saving
- **Pros**: LLM better at markdown, matches prompt template
- **Cons**: Need YAML ↔ markdown conversion logic

**Option B**: Keep YAML throughout
- Read YAML files as-is
- LLM generates YAML
- Save YAML directly
- Update chapter_iteration.j2 template to request YAML output
- **Pros**: No conversion, matches actual file format
- **Cons**: LLMs less reliable with YAML formatting

**Recommendation**: Option B - Keep YAML throughout
- Simpler implementation (no conversion)
- Matches actual file system
- Just need to update prompt template

### 2. Prose Iteration Template Mismatch (CRITICAL - Will Fail)

**Problem**: Existing `prose_iteration.j2` is for single-chapter surgical fixes, expects:
- `chapter_number`
- `chapter_yaml`
- `prose_text`
- `issues_formatted`

But iterator passes:
- `iteration_context`
- `old_content`
- `attempt`

**Impact**: Prose iteration will fail with template variable errors

**Solution**: Create new template `prose_full_iteration.j2` for full prose regeneration

### 3. Missing Import (HIGH - Will Crash)

**Problem**: `subprocess` used at line 624 but not imported

```python
# Line 624
commit_sha = subprocess.check_output(...)  # subprocess not imported
```

**Impact**: Runtime error when finalizing iteration

**Solution**: Add `import subprocess` at top of file

### 4. Git Commit Prefix Missing (HIGH - Breaks Convention)

**Problem**: Commits don't include project name prefix:
```python
commit_message = f"[{target}] {feedback[:80]}"  # Missing [project-name] prefix
```

Should be:
```
[project-name] [target] feedback
```

**Impact**: Breaks shared git repository convention, inconsistent with other commits

**Solution**: Add project name to commit message:
```python
commit_message = f"[{self.project.name}] [{target}] {feedback[:80]}"
```

### 5. No Safety Warning (MEDIUM - UX Issue)

**Problem**: No warning that iteration is destructive operation

**Impact**: Users might iterate on production books instead of clones

**Solution**: Add first-time warning to `iterate()` method:
```python
if not iteration_history.count():
    self.console.print("\n[bold yellow]⚠️  WARNING: Iteration replaces content permanently![/yellow]")
    self.console.print("[dim]Always test on cloned projects first.[/dim]")
    choice = input("Continue? (yes/no): ").strip().lower()
    if choice not in ['yes', 'y']:
        return False
```

### 6. JSON Parsing Error Handling (MEDIUM - Robustness)

**Problem**: No try/except around `json.loads()` in `_save_content()` for premise

```python
premise_data = json.loads(new_content)  # Could fail
```

**Impact**: Unclear error if LLM returns invalid JSON

**Solution**: Add error handling:
```python
try:
    premise_data = json.loads(new_content)
except json.JSONDecodeError as e:
    raise Exception(f"Failed to parse premise JSON: {e}\n\nLLM Response:\n{new_content[:500]}")
```

## Non-Critical Issues

### 7. Hardcoded Metadata (LOW - Future Enhancement)

**Problem**: `files_changed` and `lines_changed` hardcoded:
```python
files_changed = 1  # TODO: count actual files
lines_changed = 0  # TODO: count actual lines
```

**Impact**: Inaccurate iteration history metadata

**Solution**: Calculate actual values using git diff:
```python
# Count files changed
result = subprocess.run(
    ['git', 'diff', '--name-only', 'HEAD~1'],
    cwd=settings.books_dir,
    capture_output=True,
    text=True
)
files_changed = len([line for line in result.stdout.split('\n') if line.strip()])

# Count lines changed
result = subprocess.run(
    ['git', 'diff', '--shortstat', 'HEAD~1'],
    cwd=settings.books_dir,
    capture_output=True,
    text=True
)
# Parse output like "1 file changed, 10 insertions(+), 5 deletions(-)"
# Extract lines_changed = insertions + deletions
```

## Recommended Fix Priority

1. **MUST FIX BEFORE ANY TESTING**:
   - Issue #1: Chapter format mismatch
   - Issue #2: Prose template mismatch
   - Issue #3: Missing subprocess import
   - Issue #4: Git commit prefix

2. **SHOULD FIX BEFORE RELEASE**:
   - Issue #5: Safety warning
   - Issue #6: JSON error handling

3. **NICE TO HAVE**:
   - Issue #7: Accurate metadata calculation

## Testing Plan (After Fixes)

1. Clone a test book project
2. Test premise iteration with simple feedback
3. Test treatment iteration
4. Test chapter iteration (verify YAML handling)
5. Test prose iteration
6. Verify git commits have correct format
7. Verify iteration history tracking
8. Test downstream cascade (cull-all vs keep-all)
9. Test judge validation loop
10. Test semantic diff generation

**CRITICAL**: Only test on cloned projects, never production books!
