# Inlined Prompts Found

## Files with inline prompts that should eventually be migrated:

1. **src/export/dedication_generator.py**
   - Line 50: System prompt for dedication generation
   - Lines 136-177: User prompt with genre-specific guidance

2. **src/generation/kdp_metadata.py**
   - Lines 127-153: generate_categories() prompt
   - Lines 215-245: suggest_comp_titles() prompt
   - Lines 335-366: _build_comprehensive_prompt() for all metadata

3. **src/generation/premise.py**
   - Line 610+: Batch premise generation prompt

## Note:
These are lower priority than the iteration removal. Can be migrated later.

