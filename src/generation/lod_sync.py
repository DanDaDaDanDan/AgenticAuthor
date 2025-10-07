"""LOD (Level of Detail) synchronization and consistency checking."""

import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from .lod_context import LODContextBuilder
from .lod_parser import LODResponseParser


CONSISTENCY_CHECK_TEMPLATE = """You are analyzing consistency between different levels of detail in a book project.

LOD Hierarchy:
- Premise (LOD3): High-level concept, themes, characters
- Treatment (LOD2): Story beats, act structure, key scenes
- Chapters (LOD2): Detailed chapter outlines with specific events
- Prose (LOD0): Full written text

Current Context:
{{ context }}

Task: Compare the modified {{ modified_lod }} with related LODs and identify ACTUAL INCONSISTENCIES (contradictions), not expected elaborations.

STEP 1: CHARACTER NAME VERIFICATION
Before analyzing anything else, systematically check ALL character names:
- Compare every named character in treatment vs chapters vs prose
- Flag ANY name changes, even if subtle (e.g., "Sofia Reyes" → "Sofia Romano")
- ESPECIALLY check victim names, supporting characters, antagonists
- Even if same role/description, different name = MAJOR inconsistency

CRITICAL: Understand LOD Direction
- **Lower LODs (chapters/prose) SHOULD elaborate on higher LODs (treatment/premise)**
  - Adding supporting/minor characters is EXPECTED (not an inconsistency)
  - Adding locations, sensory details, pacing adjustments is EXPECTED
  - Only flag if lower LOD CONTRADICTS or REMOVES higher LOD content

- **Higher LODs (treatment) being checked against lower LODs (chapters)**
  - Only flag if treatment is MISSING major plot elements that exist in chapters
  - Don't flag minor characters, locations, or details added in chapters

Acceptable Elaborations (DO NOT FLAG):
✓ Chapters add supporting/minor characters not in treatment (e.g., tech experts, informants)
✓ Chapters introduce new locations when needed for scenes
✓ Timing/pacing adjustments that don't break plot logic (e.g., character development timing)
✓ Sensory details, character mannerisms, background elements
✓ Dialogue and scene choreography details

True Inconsistencies to Flag (FLAG THESE):
✗ Direct contradictions (e.g., "hospitalized" vs "active in field" for same character/time)
✗ Timeline breaks (events out of order, character in two places)
✗ Character name/role changes between LODs
✗ Major plot elements in chapters missing from treatment (significant subplots)
✗ Plot points removed from chapters that were in treatment
✗ Severity of injuries/events contradicted (e.g., "carved up" vs "minor wound")

Respond with JSON:
{
  "is_consistent": true/false,
  "inconsistencies": [
    {
      "lod": "treatment|chapters|prose",
      "issue": "Description of what doesn't match",
      "severity": "minor|moderate|major",
      "location": "Specific location (chapter number, section, etc.)",
      "suggestion": "Specific fix to apply"
    }
  ],
  "needs_cascade": ["treatment", "chapters", "prose"],
  "reasoning": "Why these LODs need updating"
}

Severity Guidelines:
- "major": Plot contradictions, timeline breaks, character role changes, injury severity mismatches
- "moderate": Major subplots in chapters but missing from treatment, significant contradictions
- "minor": Only for true inconsistencies, not elaborations (use sparingly)

Examples of TRUE inconsistencies:
- Character name changed (John → Jake, Sofia Reyes → Sofia Romano)
- Injury severity contradiction (hospitalized vs walking around)
- Timeline break (Chapter 6 hospitalized, Chapter 7 investigating)
- Major subplot in chapters completely missing from treatment (e.g., captain's son subplot)
- Character arc contradicted (treatment says X learns Y, chapters show X already knows Y)
- Victim identity mismatch (same role/description but different name)

Examples of ACCEPTABLE elaborations (NOT inconsistencies):
- Supporting character appears in chapters but not treatment (expected detail)
- Location introduced in chapters for a scene (expected detail)
- Character development timing adjusted for pacing (creative freedom)
- Sensory details added in prose (expected elaboration)
"""


SYNC_UPDATE_TEMPLATE = """You are synchronizing LODs to maintain consistency.

CRITICAL PRINCIPLE: The most detailed LOD is AUTHORITATIVE
- LOD Hierarchy (most → least detailed): Prose (LOD0) → Chapters (LOD2) → Treatment (LOD2) → Premise (LOD3)
- When syncing UP (less detailed): Match the detailed version (e.g., update treatment to match chapters)
- When syncing DOWN (more detailed): Only update if less detailed version changed significantly

{{ direction_guidance }}

Current book content in YAML format:

```yaml
{{ context_yaml }}
```

Changes Made:
{{ changes_description }}

Inconsistencies to Fix:
{{ inconsistencies }}

Task: Generate an updated version of ALL sections that:
1. **Defers to {{ source_lod }} as the authoritative source** (more detailed = more accurate)
2. Fixes all identified inconsistencies by matching {{ source_lod }}
3. Maintains appropriate level of detail for each section
4. Preserves content not affected by the changes

CRITICAL: Return your response as YAML with ALL sections:
```yaml
premise:
  text: |
    ... (update if needed to match {{ source_lod }})
  metadata: ...

treatment:
  text: |
    ... (update if needed to match {{ source_lod }})

chapters:
  - number: 1
    title: "..."
    # ... (update if needed to match {{ source_lod }})

prose:
  - chapter: 1
    text: |
      ... (update if needed to match {{ source_lod }})
```

Do NOT wrap your response in additional markdown code fences (```).
Return ONLY the YAML content with all sections."""


class LODSyncManager:
    """Manage synchronization between different levels of detail."""

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize LOD sync manager.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for sync operations
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.project = project
        self.model = model
        self.context_builder = LODContextBuilder()
        self.parser = LODResponseParser()

    async def check_consistency(
        self,
        modified_lod: str,
        changes_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check consistency between LODs after a modification using unified context.

        Args:
            modified_lod: Which LOD was modified (premise, treatment, chapters, prose)
            changes_description: Description of what changed

        Returns:
            Consistency report with inconsistencies and recommendations
        """
        # Build unified context (include everything for consistency checking)
        context = self.context_builder.build_context(
            project=self.project,
            target_lod='prose',  # Include all LODs
            include_downstream=True
        )

        # Serialize to YAML for LLM
        context_yaml = self.context_builder.to_yaml_string(context)

        # Render prompt
        template = Template(CONSISTENCY_CHECK_TEMPLATE)
        prompt = template.render(
            context=context_yaml,  # Now using YAML context
            modified_lod=modified_lod
        )

        # Get consistency analysis
        result = await self.client.json_completion(
            model=self.model,
            prompt=prompt,
            temperature=0.3,
            display_label=f"Checking LOD consistency"
        )

        return result

    async def sync_lod(
        self,
        source_lod: str,
        target_lod: str,
        inconsistencies: List[Dict[str, Any]],
        changes_description: str
    ) -> Dict[str, Any]:
        """
        Sync LODs using unified context approach.

        CRITICAL: Most detailed LOD is AUTHORITATIVE
        - If syncing chapters → treatment, chapters is the source (more detailed)
        - If syncing treatment → chapters, we swap so chapters becomes source

        Args:
            source_lod: LOD that was modified (may be swapped to ensure detailed → less detailed)
            target_lod: LOD to update (may be swapped to ensure detailed → less detailed)
            inconsistencies: List of inconsistencies to fix
            changes_description: Description of changes made

        Returns:
            Dict with parse result (updated_files, deleted_files, etc.)
        """
        # LOD detail levels (higher = more detailed)
        lod_detail_level = {
            'prose': 4,
            'chapters': 3,
            'treatment': 2,
            'premise': 1
        }

        # Ensure source is always MORE detailed than target
        source_detail = lod_detail_level.get(source_lod.split(':')[0], 0)
        target_detail = lod_detail_level.get(target_lod.split(':')[0], 0)

        # Swap if target is more detailed (enforce detailed → less detailed direction)
        if target_detail > source_detail:
            source_lod, target_lod = target_lod, source_lod
            direction_guidance = f"Syncing UP: {target_lod} is less detailed, so defer to {source_lod}"
        else:
            direction_guidance = f"Syncing DOWN: {source_lod} is more detailed, so use it as authority"

        # Build unified context (include everything for sync)
        context = self.context_builder.build_context(
            project=self.project,
            target_lod='prose',  # Include all LODs for sync
            include_downstream=True
        )

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Render prompt
        template = Template(SYNC_UPDATE_TEMPLATE)
        prompt = template.render(
            source_lod=source_lod,
            target_lod=target_lod,
            context_yaml=context_yaml,
            changes_description=changes_description,
            inconsistencies=self._format_inconsistencies(inconsistencies, target_lod),
            direction_guidance=direction_guidance
        )

        # Generate updated content
        response = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at maintaining narrative consistency across different levels of detail. You always return valid YAML without additional formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            stream=True,
            display=True,
            display_label=f"Syncing {target_lod} with {source_lod}"
        )

        if not response:
            raise Exception("No response from API")

        # Extract response text
        response_text = response.get('content', response) if isinstance(response, dict) else response

        # Parse and save to files
        parse_result = self.parser.parse_and_save(
            response=response_text,
            project=self.project,
            target_lod=target_lod,  # Use target_lod for culling rules
            original_context=context
        )

        return parse_result

    def _format_inconsistencies(
        self,
        inconsistencies: List[Dict[str, Any]],
        target_lod: str
    ) -> str:
        """Format inconsistencies for prompt."""
        relevant = [i for i in inconsistencies if i.get('lod') == target_lod]

        if not relevant:
            return "No specific inconsistencies identified."

        parts = []
        for i, issue in enumerate(relevant, 1):
            parts.append(
                f"{i}. [{issue.get('severity', 'moderate').upper()}] "
                f"{issue.get('issue')} "
                f"(Location: {issue.get('location', 'N/A')})\n"
                f"   Suggestion: {issue.get('suggestion')}"
            )

        return "\n".join(parts)

    def _strip_markdown_fences(self, content: str) -> str:
        """
        Strip markdown code fences if LLM wrapped output in ```yaml or ``` blocks.

        Args:
            content: Raw content from LLM

        Returns:
            Content with code fences removed
        """
        # Remove opening fence (```yaml, ```markdown, ```md, or just ```)
        if content.startswith('```'):
            lines = content.split('\n')
            # Remove first line if it's a fence
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            # Remove last line if it's a fence
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines)

        return content.strip()

    def get_affected_lods(self, modified_lod: str) -> List[str]:
        """
        Get list of LODs that should be checked after modifying a given LOD.

        Args:
            modified_lod: The LOD that was modified

        Returns:
            List of LOD names to check for consistency
        """
        # Cascading rules
        cascade_map = {
            "premise": ["treatment", "chapters", "prose"],
            "treatment": ["chapters", "prose"],
            "chapters": ["treatment", "prose"],  # Chapters can affect treatment (upward)
            "prose": ["chapters"]  # Prose changes should update chapter outlines
        }

        return cascade_map.get(modified_lod, [])
