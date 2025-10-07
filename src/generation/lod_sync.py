"""LOD (Level of Detail) synchronization and consistency checking."""

from typing import Dict, List, Optional, Any
from pathlib import Path
from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project


CONSISTENCY_CHECK_TEMPLATE = """You are analyzing consistency between different levels of detail in a book project.

LOD Hierarchy:
- Premise (LOD3): High-level concept, themes, characters
- Treatment (LOD2): Story beats, act structure, key scenes
- Chapters (LOD2): Detailed chapter outlines with specific events
- Prose (LOD0): Full written text

Current Context:
{{ context }}

Task: Compare the modified {{ modified_lod }} with related LODs and identify inconsistencies.

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

Guidelines:
- "minor": Small details that would improve consistency but don't break the story
- "moderate": Notable inconsistencies that readers might notice
- "major": Critical contradictions that break narrative logic

Examples of inconsistencies:
- Character name changed in chapters but not in treatment
- Plot point removed from chapters but still in treatment
- Prose diverges significantly from chapter outline
- Chapter outline mentions character arc not present in treatment
- Theme emphasized in premise not reflected in chapters
"""


SYNC_UPDATE_TEMPLATE = """You are updating a {{ target_lod }} to maintain consistency with changes made to {{ source_lod }}.

Original {{ target_lod }}:
```
{{ original_content }}
```

Modified {{ source_lod }}:
```
{{ modified_source }}
```

Changes Made:
{{ changes_description }}

Inconsistencies to Fix:
{{ inconsistencies }}

Task: Generate an updated version of the {{ target_lod }} that:
1. Incorporates the changes from {{ source_lod }}
2. Fixes all identified inconsistencies
3. Maintains the appropriate level of detail for {{ target_lod }}
4. Preserves content not affected by the changes

Return ONLY the updated {{ target_lod }} content, no explanations.
"""


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

    async def check_consistency(
        self,
        modified_lod: str,
        changes_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check consistency between LODs after a modification.

        Args:
            modified_lod: Which LOD was modified (premise, treatment, chapters, prose)
            changes_description: Description of what changed

        Returns:
            Consistency report with inconsistencies and recommendations
        """
        # Gather context from all LODs
        context = self._build_context(modified_lod)

        # Render prompt
        template = Template(CONSISTENCY_CHECK_TEMPLATE)
        prompt = template.render(
            context=context,
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
    ) -> str:
        """
        Sync target LOD with changes from source LOD.

        Args:
            source_lod: LOD that was modified
            target_lod: LOD to update
            inconsistencies: List of inconsistencies to fix
            changes_description: Description of changes made

        Returns:
            Updated content for target LOD
        """
        # Load content
        original_content = self._get_lod_content(target_lod)
        modified_source = self._get_lod_content(source_lod)

        if not original_content:
            raise ValueError(f"No content found for {target_lod}")

        # Render prompt
        template = Template(SYNC_UPDATE_TEMPLATE)
        prompt = template.render(
            target_lod=target_lod,
            source_lod=source_lod,
            original_content=original_content,
            modified_source=modified_source,
            changes_description=changes_description,
            inconsistencies=self._format_inconsistencies(inconsistencies, target_lod)
        )

        # Generate updated content
        response = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at maintaining narrative consistency across different levels of detail."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            stream=True,
            display=True,
            display_label=f"Syncing {target_lod}"
        )

        return response.get('content', '').strip()

    def _build_context(self, modified_lod: str) -> str:
        """
        Build context showing all LOD content.

        NO TRUNCATION - Modern LLMs have massive context windows and consistency
        checking requires seeing ALL content to find inconsistencies.
        """
        parts = []

        # Extract base LOD and specific target (e.g., "chapters:5" -> "chapters", "5")
        base_lod = modified_lod.split(':')[0] if ':' in modified_lod else modified_lod
        specific_target = modified_lod.split(':')[1] if ':' in modified_lod else None

        # Premise - FULL content, no truncation
        premise = self.project.get_premise()
        if premise:
            marker = " (MODIFIED)" if base_lod == "premise" else ""
            parts.append(f"Premise{marker}:\n{premise}")

        # Treatment - FULL content, no truncation
        treatment = self.project.get_treatment()
        if treatment:
            marker = " (MODIFIED)" if base_lod == "treatment" else ""
            parts.append(f"Treatment{marker}:\n{treatment}")

        # Chapters - FULL chapters.yaml, no truncation
        chapters_file = self.project.path / "chapters.yaml"
        if chapters_file.exists():
            chapters_content = chapters_file.read_text(encoding='utf-8')
            marker = ""
            if base_lod == "chapters":
                marker = f" (MODIFIED: Chapter {specific_target})" if specific_target else " (MODIFIED)"
            parts.append(f"Chapters{marker}:\n{chapters_content}")

        # Prose - FULL content, no truncation
        # Even though prose can be large, we need it all for accurate consistency checking
        prose_chapters = self.project.list_chapters()
        if prose_chapters:
            marker = ""
            if base_lod == "prose":
                marker = f" (MODIFIED: Chapter {specific_target})" if specific_target else " (MODIFIED)"

            prose_parts = []
            for chapter_num in sorted(prose_chapters):
                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_file.exists():
                    content = chapter_file.read_text(encoding='utf-8')
                    chapter_marker = f" (MODIFIED)" if specific_target and int(specific_target) == chapter_num else ""
                    prose_parts.append(f"=== Chapter {chapter_num}{chapter_marker} ===\n{content}")

            if prose_parts:
                parts.append(f"Prose{marker}:\n" + "\n\n".join(prose_parts))

        return "\n\n".join(parts)

    def _get_lod_content(self, lod: str) -> Optional[str]:
        """Get content for a specific LOD."""
        if lod == "premise":
            return self.project.get_premise()

        elif lod == "treatment":
            return self.project.get_treatment()

        elif lod == "chapters":
            chapters_file = self.project.path / "chapters.yaml"
            if chapters_file.exists():
                return chapters_file.read_text(encoding='utf-8')

        elif lod.startswith("prose"):
            # For prose, return full content - no truncation
            prose_chapters = self.project.list_chapters()
            if not prose_chapters:
                return None

            # Check if specific chapter requested
            if ":" in lod:
                chapter_num = int(lod.split(":")[1])
                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_file.exists():
                    return chapter_file.read_text(encoding='utf-8')
                return None

            # Return ALL prose - full content of all chapters
            prose_parts = []
            for chapter_num in sorted(prose_chapters):
                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_file.exists():
                    content = chapter_file.read_text(encoding='utf-8')
                    prose_parts.append(f"=== Chapter {chapter_num} ===\n{content}")

            return "\n\n".join(prose_parts) if prose_parts else None

        return None

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
