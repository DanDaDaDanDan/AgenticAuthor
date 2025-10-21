# Hardcoded Prompts to Migrate to .j2 Templates

This document lists all hardcoded LLM prompts found in the codebase that should be migrated to Jinja2 templates in `src/prompts/`.

## Migration Status (2025-10-20)

### ✅ Completed Migrations

1. **copy_editor.py** - Professional copy editing prompt
   - Template: `src/prompts/editing/copy_edit.j2`
   - Config: Added to `config.yaml`
   - Status: COMPLETE

2. **premise.py** - All 6 prompts migrated ✅
   - ✅ Genre detection → `src/prompts/analysis/genre_detection.j2`
   - ✅ Taxonomy iteration → `src/prompts/iteration/taxonomy_update.j2`
   - ✅ Regenerate with taxonomy → `src/prompts/generation/premise_with_taxonomy.j2`
   - ✅ Main premise generation → `src/prompts/generation/premise_main.j2`
   - ✅ Taxonomy-only analysis → `src/prompts/analysis/taxonomy_extraction.j2`
   - ✅ Premise iteration → `src/prompts/iteration/premise_revision.j2`

3. **kdp_metadata.py** - 3 prompts migrated ✅
   - ✅ Description generation → `src/prompts/kdp/description.j2`
   - ✅ Keywords generation → `src/prompts/kdp/keywords.j2`
   - ✅ Author bio generation → `src/prompts/kdp/author_bio.j2`

### ❌ Remaining to Migrate

4. **iteration/intent.py** - ✅ ALREADY MIGRATED
   - Uses `src/prompts/analysis/intent_check.j2`
   - No further migration needed

5. **analysis/unified_analyzer.py** - Low priority
   - Uses inline Jinja2 template strings (already templated)
   - Could be externalized but works as-is

## Summary

Found **3 major files** with prompts successfully migrated:

1. **copy_editor.py** - Full copy editing prompt (512 lines) ✅ COMPLETE
2. **kdp_metadata.py** - Multiple KDP-related prompts (3 prompts) ✅ COMPLETE
3. **premise.py** - Multiple premise generation prompts (6 prompts) ✅ COMPLETE

**Progress: 10 of 10 core prompts migrated (100%)**

**Notes:**
- `iteration/intent_analyzer.py` mentioned in original doc is actually `intent.py` and already uses templates
- `iteration/diff_generator.py` mentioned in original doc doesn't exist
- Some analyzers use inline Jinja2 templates which is acceptable

## Detailed Listings

### 1. copy_editor.py (HIGH PRIORITY - 512 lines)

**Location**: `src/generation/copy_editor.py`
**Method**: `_build_copy_edit_prompt()` (lines 247-511)

**Prompt Content**: Professional copy editing prompt with extensive guidelines
- Copy editing scope and guidelines
- Pronoun consistency checks
- Character tracking
- Continuity verification
- Example edits (good and bad)
- Required output format

**Suggested Template**: `src/prompts/editing/copy_edit.j2`

---

### 2. kdp_metadata.py (MEDIUM PRIORITY)

**Location**: `src/generation/kdp_metadata.py`

#### Prompt 1: Description Generation (lines 56-83)
**Method**: `generate_description()`
**Suggested Template**: `src/prompts/kdp/description.j2`

#### Prompt 2: Title & Subtitle Generation (lines 183-222)
**Method**: `generate_title_subtitle()`
**Suggested Template**: `src/prompts/kdp/title_subtitle.j2`

#### Prompt 3: Keywords Generation (lines 290-317)
**Method**: `generate_keywords()`
**Suggested Template**: `src/prompts/kdp/keywords.j2`

---

### 3. premise.py (MEDIUM PRIORITY)

**Location**: `src/generation/premise.py`

#### Prompt 1: Taxonomy Iteration (lines 85-112)
**Method**: `iterate_taxonomy()`
**Suggested Template**: `src/prompts/iteration/taxonomy_update.j2`

#### Prompt 2: Regenerate with Taxonomy (lines 158-180)
**Method**: `regenerate_with_taxonomy()`
**Suggested Template**: `src/prompts/generation/premise_with_taxonomy.j2`

#### Prompt 3: Genre Detection (lines 215-229)
**Method**: `detect_genre()`
**Suggested Template**: `src/prompts/analysis/genre_detection.j2`

#### Prompt 4: Main Premise Generation (lines 315-342)
**Method**: `generate()`
**Suggested Template**: `src/prompts/generation/premise_main.j2`

#### Prompt 5: Taxonomy-Only Analysis (lines 416-435)
**Method**: `generate_taxonomy_only()`
**Suggested Template**: `src/prompts/analysis/taxonomy_extraction.j2`

#### Prompt 6: Premise Iteration (lines 521-543)
**Method**: `iterate()`
**Suggested Template**: `src/prompts/iteration/premise_revision.j2`

---

### 4. iteration/intent_analyzer.py (LOW PRIORITY)

**Location**: `src/generation/iteration/intent_analyzer.py`

#### Prompt 1: General Intent Analysis (lines 51-121)
**Method**: `analyze_intent()`
**Suggested Template**: `src/prompts/iteration/intent_general.j2`

#### Prompt 2: Prose Intent Analysis (lines 167-217)
**Method**: `_prose_intent_prompt()`
**Suggested Template**: `src/prompts/iteration/intent_prose.j2`

---

### 5. iteration/diff_generator.py (LOW PRIORITY)

**Location**: `src/generation/iteration/diff_generator.py`

#### Prompt 1: Diff Generation (lines 41-125)
**Method**: `generate()`
**Suggested Template**: `src/prompts/iteration/diff_generation.j2`

---

## Migration Benefits

1. **Visibility**: All prompts viewable in one place
2. **Maintainability**: Easy to update prompts without touching code
3. **Configuration**: Centralized temperature/token settings
4. **Testing**: Can test prompt changes independently
5. **Consistency**: Enforces standard prompt structure

## Migration Priority

1. **HIGH**: copy_editor.py (largest, most complex prompt)
2. **MEDIUM**: kdp_metadata.py, premise.py (multiple related prompts)
3. **LOW**: iteration/*.py (simpler prompts, less frequently modified)

## Implementation Pattern

When migrating, follow this pattern:

1. Create template file in appropriate directory:
   ```
   src/prompts/
   ├── generation/     # For content generation
   ├── editing/        # For copy editing
   ├── kdp/           # For KDP metadata
   ├── iteration/     # For iteration/feedback
   └── analysis/      # For analysis/detection
   ```

2. Split template into [SYSTEM] and [USER] sections:
   ```jinja2
   {# Template documentation #}

   [SYSTEM]
   System prompt content...

   [USER]
   User prompt with {{ variables }}
   ```

3. Add metadata to `src/prompts/config.yaml`:
   ```yaml
   editing/copy_edit:
     temperature: 0.3
     format: json
     min_tokens: 8000
     top_p: 0.9
   ```

4. Update code to use PromptLoader:
   ```python
   prompts = self.prompt_loader.render(
       "editing/copy_edit",
       chapter_text=chapter_text,
       context=context
   )
   ```

## Note on reserve_tokens

The `min_response_tokens` parameter has been renamed to `reserve_tokens` throughout the codebase for clarity. This is an internal parameter used to calculate appropriate `max_tokens` for API calls based on model capabilities.

---

Generated: 2025-10-20