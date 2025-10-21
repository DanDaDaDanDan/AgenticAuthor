# Inline Jinja2 Templates Explained

## What Are Inline Jinja2 Templates?

An **inline Jinja2 template** is a template string that:
1. Is defined directly in a Python file (usually as a constant)
2. Uses Jinja2 syntax for variable interpolation ({{ }}, {% %})
3. Is rendered at runtime using `Template(template_str).render(**variables)`

This is different from **externalized templates** which are stored in separate `.j2` files and loaded via the PromptLoader system.

---

## Example: Inline Template (Current)

**File:** `src/generation/analysis/unified_analyzer.py` (lines 7-60)

```python
# Template defined as Python string constant
UNIFIED_ANALYSIS_PROMPT = """You are an expert story editor. Read this {{ content_type }} and provide honest feedback.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

{% if genre %}
Genre: {{ genre }}
{% endif %}

Rate the quality and provide constructive criticism...
"""

# Later in code (line 104-110):
prompt = self._create_analysis_prompt(
    UNIFIED_ANALYSIS_PROMPT,  # Pass template string directly
    content,
    content_type,
    ctx,
    max_content_words=8000
)

# Base class method (base.py:271-272):
template = Template(template_str)  # Create Jinja2 Template object
return template.render(**ctx)      # Render with variables
```

**Characteristics:**
- ✅ Template is defined in the same file as the code
- ✅ Uses Jinja2 syntax ({{ }} for variables, {% %} for control flow)
- ✅ Rendered at runtime with `Template(template_str)`
- ❌ Template is hardcoded in Python file (harder to edit, no syntax highlighting)
- ❌ No centralized configuration (temperature, tokens, etc.)
- ❌ Not loaded via PromptLoader

---

## What "Externalized" Means

**Externalized templates** are moved to separate `.j2` files in the `src/prompts/` directory and loaded via PromptLoader.

### Example: Externalized Template (Proposed)

**File:** `src/prompts/analysis/unified_analysis.j2` (new file)

```jinja2
{# Unified story analysis prompt #}
{# Variables: content, content_type, premise, genre, treatment, chapter_outline #}

[SYSTEM]
You are an expert story editor providing honest, constructive feedback.

[USER]
Read this {{ content_type }} and provide honest feedback.

Content to Analyze:
```
{{ content }}
```

{% if premise %}
Premise Context:
{{ premise }}
{% endif %}

{% if genre %}
Genre: {{ genre }}
{% endif %}

Rate the quality and provide constructive criticism...

Respond with ONLY valid JSON:
{
  "grade": "A+ | A | B+ | ...",
  "grade_justification": "...",
  "overall_assessment": "...",
  "feedback": [...],
  "strengths": [...],
  "next_steps": "..."
}
```

**File:** `src/prompts/config.yaml` (updated)

```yaml
analysis/unified_analysis:
  temperature: 0.3
  format: json
  min_tokens: 4000
```

**File:** `src/generation/analysis/unified_analyzer.py` (updated)

```python
from ...prompts import get_prompt_loader

class UnifiedAnalyzer(BaseAnalyzer):
    def __init__(self, client, model):
        super().__init__(client, model)
        self.prompt_loader = get_prompt_loader()  # Get singleton instance

    async def analyze(self, content, content_type, context=None):
        # Build context
        ctx = context or {}
        ctx.update({
            'content': self._truncate_content(content, 8000),
            'content_type': content_type,
        })

        # Load and render template from file
        prompts = self.prompt_loader.render(
            "analysis/unified_analysis",
            **ctx
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature(
            "analysis/unified_analysis",
            default=0.3
        )

        # Call LLM
        response = await self._call_llm(
            prompts['user'],
            system_prompt=prompts['system'],
            temperature=temperature,
            reserve_tokens=4000
        )

        # ... parse response
```

**Benefits of Externalization:**
- ✅ Template is separate from code (easier to edit)
- ✅ Syntax highlighting for Jinja2 templates in editors
- ✅ Centralized configuration (temperature, tokens in config.yaml)
- ✅ Consistent with rest of codebase (all other prompts externalized)
- ✅ Can test/modify prompts without touching code
- ✅ Clear separation of system vs user prompts

---

## Why Some Templates Are Still Inline

**Current state:**
- **Most prompts:** Externalized to `src/prompts/*.j2` files ✅ (100% of core prompts)
- **Analysis prompts:** Still inline in analyzer classes (unified_analyzer.py, treatment_deviation_analyzer.py)

**Why these are still inline:**
- These use the `_create_analysis_prompt()` helper which expects a template string
- Works perfectly fine as-is
- Lower priority since they're less frequently modified
- Would require refactoring the BaseAnalyzer API

**Could they be externalized?**
Yes, absolutely! It would require:
1. Creating .j2 files in `src/prompts/analysis/`
2. Adding config entries in `config.yaml`
3. Updating analyzers to use PromptLoader instead of inline strings
4. Potentially refactoring BaseAnalyzer._create_analysis_prompt() to use PromptLoader

**Is it worth doing?**
- **Low priority** - these prompts work fine and are rarely modified
- **Benefits are modest** - mostly consistency and easier editing
- **Could be done** if we want 100% externalization for consistency

---

## Summary

**Inline Jinja2 Template:**
- Template string defined in Python file as constant
- Uses Jinja2 syntax ({{ }}, {% %})
- Rendered with `Template(template_str).render()`
- Example: `UNIFIED_ANALYSIS_PROMPT` in unified_analyzer.py

**Externalized Template:**
- Template stored in separate .j2 file
- Loaded and rendered via PromptLoader
- Configuration in config.yaml
- Example: All core prompts in `src/prompts/`

**What "could be externalized" means:**
- Move template from Python file to .j2 file
- Add config entry in config.yaml
- Update code to use PromptLoader.render()
- Benefits: consistency, easier editing, centralized config
