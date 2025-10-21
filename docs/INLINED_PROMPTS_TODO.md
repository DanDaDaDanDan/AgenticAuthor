# Inlined Prompts Found

## Migrated:

1. **✅ src/export/dedication_generator.py** - Migrated to src/prompts/generation/dedication_generation.j2

## Files with inline prompts that should eventually be migrated:

1. **src/generation/kdp_metadata.py**
   - Lines 127-153: generate_categories() prompt
   - Lines 215-245: suggest_comp_titles() prompt
   - Lines 335-366: _build_comprehensive_prompt() for all metadata

2. **src/generation/premise.py**
   - Line 610+: Batch premise generation prompt

## Note:
These are lower priority than the iteration removal. Can be migrated later.

