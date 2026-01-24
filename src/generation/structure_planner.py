"""Structure planning for flexible story organization."""

from typing import Optional, Dict, Any
from pathlib import Path

from rich.console import Console

from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader


class StructurePlanner:
    """
    Generates a model-driven structure plan for prose generation.

    Instead of forcing rigid chapter beats, this lets the model decide
    how to best structure the story based on genre, length, and content.

    The model might propose:
    - Traditional chapters with specific word targets
    - Scene-based structure with breaks
    - Alternating POV chapters
    - Epistolary format (letters, diary entries)
    - Act-based structure
    - Any other format that serves the story
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize structure planner.

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

    @property
    def plan_file(self) -> Path:
        """Path to structure plan file."""
        return self.project.path / "structure-plan.md"

    def get_plan(self) -> Optional[str]:
        """Load existing structure plan."""
        if self.plan_file.exists():
            return self.plan_file.read_text(encoding='utf-8')
        return None

    def save_plan(self, content: str) -> None:
        """Save structure plan."""
        self.plan_file.write_text(content, encoding='utf-8')

    async def generate_plan(self) -> str:
        """
        Generate a structure plan for the story.

        Uses premise, treatment, and taxonomy to let the model
        propose the best structure for this specific story.

        Returns:
            Structure plan as markdown text
        """
        # Load required context
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first.")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first.")

        # Get taxonomy for length/genre guidance
        taxonomy = self.project.get_taxonomy() or {}
        target_words = self.project.get_target_words()

        # Determine story scale
        is_short = self.project.is_short_form()

        # Build context
        import yaml
        taxonomy_text = ""
        if taxonomy:
            taxonomy_text = yaml.dump(taxonomy, default_flow_style=False, allow_unicode=True)

        # Render prompt
        prompts = self.prompt_loader.render(
            "generation/structure_plan",
            premise=premise,
            treatment=treatment,
            taxonomy=taxonomy_text,
            target_words=target_words,
            is_short_form=is_short,
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("generation/structure_plan", default=0.7)

        self.console.print("[cyan]Generating structure plan...[/cyan]")
        self.console.print("[dim]The model will propose how to best structure this story.[/dim]\n")

        # Generate
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            display=True,
            display_label="Structure Plan",
        )

        if not result:
            raise Exception("No response from API")

        plan = result.get('content', result) if isinstance(result, dict) else result

        # Save the plan
        self.save_plan(plan)

        self.console.print(f"\n[green]Structure plan saved to {self.plan_file}[/green]")

        return plan

    def has_plan(self) -> bool:
        """Check if a structure plan exists."""
        return self.plan_file.exists()
