"""Flexible prose generation supporting both direct and plan-based approaches."""

import re
from typing import Optional, List
from pathlib import Path

from rich.console import Console

from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader


class FlexibleProseGenerator:
    """
    Generates prose with maximum creative flexibility.

    Supports two modes:
    1. Direct: Treatment → Prose (for short stories)
    2. From Plan: Structure Plan → Sequential Units (for novels)

    The model decides structure; we just execute it.
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize flexible prose generator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation
        """
        if not model:
            raise ValueError("No model selected. Use /model to select first.")
        self.client = client
        self.project = project
        self.model = model
        self.console = Console()
        self.prompt_loader = get_prompt_loader()

    def get_structure_plan(self) -> Optional[str]:
        """Load structure plan if it exists."""
        plan_file = self.project.path / "structure-plan.md"
        if plan_file.exists():
            return plan_file.read_text(encoding='utf-8')
        return None

    def parse_plan_units(self, plan: str) -> List[str]:
        """
        Parse structure plan to extract individual units (chapters/sections).

        Looks for common patterns:
        - "Chapter N:" or "## Chapter N"
        - "Section N:" or "## Section N"
        - "Part N:" or "## Part N"
        - Numbered items like "1." or "### 1."

        Args:
            plan: Structure plan text

        Returns:
            List of unit descriptions
        """
        units = []

        # Try to find the OUTLINE section
        outline_match = re.search(r'#{1,3}\s*(?:2\.\s*)?OUTLINE\s*\n(.*?)(?=\n#{1,3}\s*(?:3\.|PACING|TECHNICAL)|$)', plan, re.IGNORECASE | re.DOTALL)

        if outline_match:
            outline_section = outline_match.group(1)
        else:
            # Fall back to the full plan
            outline_section = plan

        # Pattern 1: "### Chapter N" or "## Chapter N" style
        chapter_pattern = r'#{2,4}\s*(?:Chapter|Section|Part|Unit)\s*(\d+)[:\s]*([^\n]*)\n(.*?)(?=\n#{2,4}\s*(?:Chapter|Section|Part|Unit)|$)'
        matches = re.findall(chapter_pattern, outline_section, re.IGNORECASE | re.DOTALL)

        if matches:
            for num, title, content in matches:
                unit_desc = f"{title.strip()}\n{content.strip()}" if title.strip() else content.strip()
                units.append(unit_desc)
            return units

        # Pattern 2: "**Chapter N:**" or "**N.**" style (bold markers)
        bold_pattern = r'\*\*(?:Chapter\s*)?(\d+)[\.:]\*\*\s*([^\n]*)\n(.*?)(?=\n\*\*(?:Chapter\s*)?\d+[\.:]\*\*|$)'
        matches = re.findall(bold_pattern, outline_section, re.IGNORECASE | re.DOTALL)

        if matches:
            for num, title, content in matches:
                unit_desc = f"{title.strip()}\n{content.strip()}" if title.strip() else content.strip()
                units.append(unit_desc)
            return units

        # Pattern 3: Numbered list "1." or "1)" style
        numbered_pattern = r'^(\d+)[.\)]\s+(.+?)(?=\n\d+[.\)]|\n#{2,}|$)'
        matches = re.findall(numbered_pattern, outline_section, re.MULTILINE | re.DOTALL)

        if matches:
            for num, content in matches:
                units.append(content.strip())
            return units

        # Pattern 4: Lines starting with "- Chapter" or "- **Chapter"
        bullet_pattern = r'^[-*]\s+\*?\*?(?:Chapter|Section|Part|Unit)\s*(\d+)[:\s]*\*?\*?\s*(.+?)(?=\n[-*]\s+\*?\*?(?:Chapter|Section|Part|Unit)|$)'
        matches = re.findall(bullet_pattern, outline_section, re.MULTILINE | re.IGNORECASE | re.DOTALL)

        if matches:
            for num, content in matches:
                units.append(content.strip())
            return units

        # If nothing matched, return empty list (will fall back to direct generation)
        return []

    def _get_prior_prose(self) -> str:
        """Get all previously generated prose."""
        prose_parts = []

        # Check for story.md (short stories)
        if self.project.story_file.exists():
            content = self.project.get_story()
            if content:
                prose_parts.append(content)

        # Check for chapter files
        chapters_dir = self.project.chapters_dir
        if chapters_dir.exists():
            chapter_files = sorted(chapters_dir.glob("chapter-*.md"))
            for ch_file in chapter_files:
                try:
                    content = ch_file.read_text(encoding='utf-8')
                    prose_parts.append(content)
                except Exception:
                    pass

        return "\n\n---\n\n".join(prose_parts)

    async def generate_direct(self, style_card: Optional[str] = None) -> str:
        """
        Generate prose directly from treatment (no structure plan).

        Used for short stories where intermediate planning isn't needed.

        Args:
            style_card: Optional prose style guidance

        Returns:
            Generated prose
        """
        # Load required context
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first.")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first.")

        # Get taxonomy for guidance
        taxonomy = self.project.get_taxonomy() or {}
        target_words = self.project.get_target_words()

        import yaml
        taxonomy_text = yaml.dump(taxonomy, default_flow_style=False, allow_unicode=True) if taxonomy else ""

        # Render prompt
        prompts = self.prompt_loader.render(
            "generation/prose_direct",
            premise=premise,
            treatment=treatment,
            taxonomy=taxonomy_text,
            target_words=target_words,
            style_card=style_card,
        )

        temperature = self.prompt_loader.get_temperature("generation/prose_direct", default=0.8)

        self.console.print("[cyan]Generating prose directly from treatment...[/cyan]")

        # Generate
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            display=True,
            display_label="Story",
        )

        if not result:
            raise Exception("No response from API")

        prose = result.get('content', result) if isinstance(result, dict) else result

        # Save to story.md
        self.project.story_file.parent.mkdir(parents=True, exist_ok=True)
        self.project.story_file.write_text(prose, encoding='utf-8')

        self.console.print(f"\n[green]Story saved to {self.project.story_file}[/green]")

        return prose

    async def generate_unit(
        self,
        unit_number: int,
        unit_description: str,
        total_units: int,
        style_card: Optional[str] = None,
    ) -> str:
        """
        Generate prose for a single unit following the structure plan.

        Args:
            unit_number: Which unit to generate (1-based)
            unit_description: Description of this unit from the plan
            total_units: Total number of units
            style_card: Optional prose style guidance

        Returns:
            Generated prose
        """
        # Load required context
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first.")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first.")

        structure_plan = self.get_structure_plan()
        if not structure_plan:
            raise Exception("No structure plan found. Generate plan first.")

        # Get prior prose for context
        prior_prose = self._get_prior_prose()

        # Render prompt
        prompts = self.prompt_loader.render(
            "generation/prose_from_plan",
            premise=premise,
            treatment=treatment,
            structure_plan=structure_plan,
            unit_number=unit_number,
            unit_description=unit_description,
            prior_prose=prior_prose,
            total_units=total_units,
            style_card=style_card,
        )

        temperature = self.prompt_loader.get_temperature("generation/prose_from_plan", default=0.8)

        # Generate
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            display=True,
            display_label=f"Unit {unit_number}",
        )

        if not result:
            raise Exception("No response from API")

        prose = result.get('content', result) if isinstance(result, dict) else result

        # Save to chapters/chapter-NN.md
        self.project.chapters_dir.mkdir(parents=True, exist_ok=True)
        unit_file = self.project.chapters_dir / f"chapter-{unit_number:02d}.md"
        unit_file.write_text(prose, encoding='utf-8')

        self.console.print(f"\n[green]Unit {unit_number} saved to {unit_file}[/green]")

        return prose
