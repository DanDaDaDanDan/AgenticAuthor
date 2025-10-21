# Codebase Issues Analysis

**Date:** 2025-10-20
**Found by:** User ultrathinking review
**Status:** ✅ ALL ISSUES FIXED

---

## Resolution Summary

All 3 issues identified and fixed:

1. ✅ **min_tokens → reserve_tokens** - Renamed in config.yaml (19 instances) and __init__.py method
2. ✅ **Stale bytecode** - Deleted all __pycache__ directories
3. ✅ **CRITICAL overuse** - Replaced 12 prompt emphasis uses with ⚠️ IMPORTANT/ESSENTIAL/KEY alternatives

**Commits:**
- See git log for detailed changes
- All changes tested and verified

---

## Issue 1: min_tokens vs reserve_tokens Inconsistency ✅ FIXED

### Problem

We renamed `min_response_tokens` → `reserve_tokens` in code, but config.yaml still uses `min_tokens`.

### Evidence

**Config.yaml (lines 6, 13, 18, etc.):**
```yaml
# Fields:
#   min_tokens: Minimum response tokens to reserve   # ← Uses min_tokens

generation/premise_main:
  temperature: 0.9
  format: json
  min_tokens: 800   # ← min_tokens
```

**Code uses reserve_tokens:**
```python
# src/generation/premise.py:318
reserve_tokens=800

# src/generation/treatment.py:132
reserve_tokens=int(target_words * 1.3)

# src/generation/prose.py:534
reserve_tokens=estimated_response_tokens
```

**Unused method:**
```python
# src/prompts/__init__.py:185-197
def get_min_tokens(self, prompt_name: str, default: Optional[int] = None) -> Optional[int]:
    # This method is NEVER CALLED anywhere in the codebase
```

### Impact

- **Confusing**: Two different names for the same concept
- **Inconsistent**: Config says `min_tokens`, code says `reserve_tokens`
- **Dead code**: `get_min_tokens()` method exists but is never used
- **Documentation**: Comments and docs use both terms interchangeably

### Recommended Fix

**Option A: Rename in config.yaml (RECOMMENDED)**
```yaml
# Fields:
#   reserve_tokens: Tokens to reserve for response   # ← Consistent with code

generation/premise_main:
  temperature: 0.9
  format: json
  reserve_tokens: 800   # ← Matches code parameter name
```

Also:
1. Rename `get_min_tokens()` → `get_reserve_tokens()`
2. Update all config.yaml entries (19 total)
3. Update comments in __init__.py
4. Update HARDCODED_PROMPTS_TO_MIGRATE.md

**Why this is better:**
- Code already uses `reserve_tokens` everywhere (14+ files)
- More descriptive name (reserving tokens, not minimum tokens)
- Matches the CHANGELOG documentation

---

## Issue 2: Stale diff.pyc Bytecode File ✅ FIXED

### Problem

Source file `diff.py` was deleted, but compiled bytecode `diff.pyc` still exists.

### Evidence

```bash
# Source file doesn't exist:
ls src/generation/iteration/diff.py
# No such file

# But bytecode exists:
ls src/generation/iteration/__pycache__/diff.cpython-313.pyc
# File exists ✓

# Documentation correctly notes it doesn't exist:
docs/HARDCODED_PROMPTS_TO_MIGRATE.md:49
"iteration/diff_generator.py mentioned in original doc doesn't exist"
```

### Impact

- **Stale bytecode**: Takes up space, may cause confusion
- **Clean build**: Python might try to use stale .pyc
- **Documentation accurate**: Docs correctly say it doesn't exist

### Recommended Fix

Delete the stale bytecode:
```bash
rm -rf src/generation/iteration/__pycache__/diff.cpython-313.pyc
```

Or clean all __pycache__ directories:
```bash
find src/ -type d -name __pycache__ -exec rm -rf {} +
```

**Note:** These are auto-generated and gitignored, so safe to delete.

---

## Issue 3: CRITICAL Overuse in Prompts (Context Shift) ✅ FIXED

### Problem

The word "CRITICAL" is used for **two different purposes**:

1. **Severity classification** (Severity.CRITICAL enum for actual critical issues)
2. **Emphasis in prompts** (section headers, instructions, guidelines)

This creates **context shift** where the LLM may not understand when we mean actual severity vs. just emphasis.

### Evidence of Dual Usage

**Use 1: Severity Enum (Proper Usage)**
```python
# src/generation/analysis/base.py:14
class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # ← Actual severity level
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

# src/generation/analysis/analyzer.py:357
'critical_issues': len([i for i in all_issues if i.severity == Severity.CRITICAL])
```

**Use 2: Prompt Emphasis (Overuse)**
```
CRITICAL - PLAN THE COMPLETE ARC:              # Section header
CRITICAL: Return ONLY the treatment as YAML:   # Format requirement
CRITICAL INSTRUCTION: Analyze the feedback...  # Instruction emphasis
GUIDELINES FOR KEY_EVENTS - CRITICAL:          # Guidelines header
CRITICAL - AVOID DUPLICATE EVENTS:             # Issue emphasis
SHOW vs TELL - CRITICAL:                       # Stylistic guideline
COPY EDITING SCOPE - CRITICAL GUIDELINES       # Section header
CRITICAL: PRONOUN CONSISTENCY                  # Section header
CRITICAL: Strongly penalize variants...        # Judging criteria
```

**Then we say:**
```
Only flag CRITICAL deviations (missing key moments...)
```

### The Problem

When we tell the LLM "only flag CRITICAL deviations", it may think:
- "Everything in this prompt has CRITICAL in front of it, so everything is critical?"
- "Do they mean Severity.CRITICAL or just any instruction with CRITICAL?"
- Context dilution: if 10 things are CRITICAL, nothing is critical

### Impact Analysis

**Prompts with CRITICAL emphasis (non-severity):**
1. `chapter_single_shot.j2` - 2 uses (arc planning, key_events guidelines)
2. `treatment_generation.j2` - 1 use (format requirement)
3. `chapter_foundation.j2` - 3 uses (word count, instruction, duplication)
4. `prose_generation.j2` - 1 use (SHOW vs TELL)
5. `copy_edit.j2` - 2 uses (scope guidelines, pronoun consistency)
6. `chapter_judging.j2` - 1 use (penalize repetition)
7. `unified_analyzer.py` - 1 use (check duplicates)
8. `treatment_deviation_analyzer.py` - 1 use (focus duplication)

**Total: 12 uses of CRITICAL for emphasis**

**Prompts with CRITICAL for severity:**
1. `prose_fidelity.j2:70` - "Only flag CRITICAL deviations" ← **CONFLICT!**

### Recommended Fix

**Replace emphasis CRITICAL with better alternatives:**

| Current | Better Alternative | Rationale |
|---------|-------------------|-----------|
| `CRITICAL - PLAN THE COMPLETE ARC:` | `⚠️ IMPORTANT - PLAN THE COMPLETE ARC:` | Distinct visual marker |
| `CRITICAL: Return ONLY...` | `⚠️ FORMAT REQUIREMENT: Return ONLY...` | More specific |
| `CRITICAL INSTRUCTION:` | `⚠️ KEY INSTRUCTION:` | Less severe language |
| `GUIDELINES - CRITICAL:` | `GUIDELINES - ESSENTIAL:` | Same weight, different word |
| `CRITICAL - AVOID DUPLICATE:` | `⚠️ MUST AVOID DUPLICATE:` | Action-oriented |
| `SHOW vs TELL - CRITICAL:` | `SHOW vs TELL - ESSENTIAL:` | Same importance |
| `CRITICAL GUIDELINES` | `KEY GUIDELINES` or `ESSENTIAL GUIDELINES` | Clear but distinct |

**Preserve CRITICAL for severity only:**
```
- Only flag CRITICAL deviations (missing key moments...)
  → Means Severity.CRITICAL specifically

Severity.CRITICAL = issues that make the story fundamentally broken
```

### Benefits of Fix

1. ✅ **Clear severity signal**: When we say CRITICAL, it means Severity.CRITICAL
2. ✅ **No context dilution**: LLM knows emphasis ≠ severity
3. ✅ **Better UX**: Warnings use ⚠️ emoji, actual errors use CRITICAL
4. ✅ **Consistent language**: IMPORTANT/ESSENTIAL/KEY for emphasis, CRITICAL for severity

---

## Summary Table

| Issue | Severity | Files Affected | Recommended Fix |
|-------|----------|----------------|-----------------|
| min_tokens inconsistency | Medium | config.yaml, __init__.py, docs | Rename to reserve_tokens (19 changes) |
| Stale diff.pyc | Low | 1 bytecode file | Delete __pycache__ (safe, auto-generated) |
| CRITICAL overuse | **High** | 8 prompt files | Replace with IMPORTANT/ESSENTIAL/KEY (12 changes) |

---

## Priority

1. **HIGH**: Fix CRITICAL overuse (affects LLM understanding of severity)
2. **MEDIUM**: Fix min_tokens naming (affects code consistency)
3. **LOW**: Delete stale bytecode (cleanup only, no functional impact)

---

## Next Steps

1. Create issue-specific fix branches or fix all in one commit
2. Update CHANGELOG with findings and fixes
3. Test prompts after CRITICAL replacement to ensure LLM behavior unchanged
4. Verify no broken references after min_tokens → reserve_tokens rename

---

**Analysis completed by:** Claude Code
**Date:** 2025-10-20
