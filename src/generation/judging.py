"""LLM-based judging for multi-variant chapter generation."""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import yaml
import shutil

from rich.console import Console

from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader


class JudgingCoordinator:
    """
    Coordinate LLM-based evaluation and selection of chapter outline variants.

    Uses minimal structure to give LLM freedom in judging criteria and reasoning.
    Saves judging decisions for transparency and reproducibility.
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize judging coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for judging
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        self.client = client
        self.project = project
        self.model = model
        self.console = Console()
        self.prompt_loader = get_prompt_loader()
        self.variants_dir = project.path / 'chapter-beats-variants'
        self.decisions_file = self.variants_dir / 'decision.json'

    def _build_judging_prompt(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> Dict[str, str]:
        """
        Build judging prompt with minimal structure using PromptLoader.

        User requirement: "allow the LLM freedom to judge how it sees fit; no need to overly provide structure"

        This prompt provides context and asks for evaluation, but doesn't prescribe
        specific criteria, scoring systems, or weights. LLM decides what matters.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Dict with 'system' and 'user' prompts
        """
        from .variants import VARIANT_CONFIGS

        # Serialize foundation
        foundation_yaml = yaml.dump(foundation, sort_keys=False, allow_unicode=True)

        # Build variants sections
        variants_sections = ""
        for variant_num in sorted(variants_data.keys()):
            chapters = variants_data[variant_num]

            # Find config for this variant
            config = next((c for c in VARIANT_CONFIGS if c['variant'] == variant_num), None)
            temp_label = ""
            if config:
                temp_label = f" - Temperature: {config['temperature']} ({config['label']})"

            variant_yaml = yaml.dump(
                {'chapters': chapters},
                sort_keys=False,
                allow_unicode=True
            )

            variants_sections += f"""VARIANT {variant_num}{temp_label}:
```yaml
{variant_yaml}
```

"""

        # Build list of actual variant numbers (e.g., "1, 3, 4" if variant 2 failed)
        variant_numbers = ', '.join(map(str, sorted(variants_data.keys())))

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "analysis/chapter_judging",
            variants_count=len(variants_data),
            foundation_yaml=foundation_yaml,
            variants_sections=variants_sections,
            variant_numbers=variant_numbers
        )

        return prompts

    async def judge_variants(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> Tuple[int, str]:
        """
        Call LLM to judge variants and select winner.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Tuple of (winner_variant_num, reasoning)

        Raises:
            Exception: If judging fails or returns invalid response
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== VARIANT JUDGING START ===")
            logger.info(f"Judging {len(variants_data)} variants")
            logger.info(f"Using model: {self.model}")

        # Build prompt
        prompts = self._build_judging_prompt(foundation, variants_data)

        if logger:
            logger.debug(f"Judging prompt length: {len(prompts['user'])} characters")

        # Make judging call with LOW temperature for consistency
        self.console.print(f"\n[cyan]Judging {len(variants_data)} variants...[/cyan]")
        self.console.print(f"[dim]Using model: {self.model}[/dim]\n")

        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompts['user']}
                ],
                temperature=0.1,  # Low temperature for consistent, reliable judgment
                stream=False,  # No streaming for judging (want complete response)
                display=False,  # Don't display during judging
                min_response_tokens=100,
                response_format={"type": "json_object"}  # Use structured JSON output
            )

            if not result:
                raise Exception("No response from LLM judge")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            if logger:
                logger.debug(f"Judging response: {response_text[:500]}...")

            # Parse JSON response
            try:
                # Strip markdown fences if present
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    # Remove fences
                    lines = response_text.split('\n')
                    # Skip first and last lines (fences)
                    response_text = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)
                    response_text = response_text.strip()

                # Remove 'json' language identifier if present
                if response_text.startswith('json'):
                    response_text = response_text[4:].strip()

                judging_result = json.loads(response_text)

            except json.JSONDecodeError as e:
                if logger:
                    logger.error(f"Failed to parse judging JSON: {e}")
                    logger.error(f"Response text: {response_text}")

                raise Exception(f"Failed to parse judging response as JSON: {e}")

            # Extract winner and reasoning
            winner = judging_result.get('winner')
            reasoning = judging_result.get('reasoning', 'No reasoning provided')

            if not winner:
                raise Exception("Judging response missing 'winner' field")

            # Convert winner to int (LLM might return string "1" instead of int 1)
            try:
                winner = int(winner)
            except (TypeError, ValueError) as e:
                raise Exception(
                    f"Invalid winner type: {type(winner).__name__} (value: {winner}). "
                    f"Expected integer variant number."
                )

            # Validate winner is in valid range
            if winner not in variants_data:
                raise Exception(
                    f"Invalid winner variant number: {winner}. "
                    f"Must be one of: {list(variants_data.keys())}"
                )

            if logger:
                logger.info(f"Judging complete: Winner is Variant {winner}")
                logger.debug(f"Reasoning: {reasoning}")

            # Display results
            self.console.print(f"[green]✓ Judging complete[/green]\n")
            self.console.print(f"[bold cyan]Winner: Variant {winner}[/bold cyan]")
            self.console.print(f"\n[white]Reasoning:[/white]")
            self.console.print(f"[dim]{reasoning}[/dim]\n")

            return (winner, reasoning)

        except Exception as e:
            if logger:
                logger.error(f"Judging failed: {e}")
            raise

    def _save_decision(
        self,
        winner: int,
        reasoning: str,
        variants_evaluated: List[int],
        timestamp: Optional[str] = None
    ):
        """
        Save judging decision to decision.json for transparency.

        Args:
            winner: Winning variant number
            reasoning: LLM's reasoning for selection
            variants_evaluated: List of variant numbers that were evaluated
            timestamp: Optional timestamp (defaults to now)
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if timestamp is None:
            timestamp = datetime.now().isoformat()

        decision_data = {
            'timestamp': timestamp,
            'model': self.model,
            'winner': winner,
            'reasoning': reasoning,
            'variants_evaluated': variants_evaluated,
            'decision_method': 'llm_judging'
        }

        # Ensure variants directory exists
        self.variants_dir.mkdir(exist_ok=True)

        # Save decision
        with open(self.decisions_file, 'w', encoding='utf-8') as f:
            json.dump(decision_data, f, indent=2)

        if logger:
            logger.info(f"Saved judging decision to: {self.decisions_file}")

    def finalize_winner(
        self,
        winner_variant_num: int,
        reasoning: str,
        variants_evaluated: List[int]
    ):
        """
        Copy winning variant to chapter-beats/ directory and save decision.

        Args:
            winner_variant_num: Winning variant number
            reasoning: LLM's reasoning for selection
            variants_evaluated: List of variant numbers that were evaluated
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info(f"=== FINALIZING WINNER: Variant {winner_variant_num} ===")

        # Source: chapter-beats-variants/variant-N/
        variant_dir = self.variants_dir / f'variant-{winner_variant_num}'

        # Destination: chapter-beats/
        beats_dir = self.project.chapter_beats_dir

        if not variant_dir.exists():
            raise Exception(f"Winner variant directory not found: {variant_dir}")

        # Ensure chapter-beats/ directory exists
        beats_dir.mkdir(exist_ok=True)

        # Copy foundation (shared by all variants)
        foundation_src = self.variants_dir / 'foundation.yaml'
        foundation_dst = beats_dir / 'foundation.yaml'

        if foundation_src.exists():
            shutil.copy2(foundation_src, foundation_dst)

            if logger:
                logger.debug(f"Copied foundation: {foundation_src} -> {foundation_dst}")
        else:
            if logger:
                logger.warning(f"Foundation not found at {foundation_src}")

        # Copy all chapter files from winner variant
        chapter_files = sorted(variant_dir.glob('chapter-*.yaml'))

        if logger:
            logger.debug(f"Copying {len(chapter_files)} chapter files from variant {winner_variant_num}")

        for chapter_file in chapter_files:
            dst_file = beats_dir / chapter_file.name
            shutil.copy2(chapter_file, dst_file)

            if logger:
                logger.debug(f"Copied: {chapter_file.name}")

        # Save decision record
        self._save_decision(
            winner=winner_variant_num,
            reasoning=reasoning,
            variants_evaluated=variants_evaluated
        )

        self.console.print(f"[green]✓ Finalized Variant {winner_variant_num} to chapter-beats/[/green]")
        self.console.print(f"[dim]Copied {len(chapter_files)} chapter files + foundation[/dim]\n")

        if logger:
            logger.info(f"=== FINALIZATION COMPLETE ===")

    async def judge_and_finalize(
        self,
        foundation: Dict[str, Any],
        variants_data: Dict[int, List[Dict[str, Any]]]
    ) -> int:
        """
        Complete workflow: judge variants and finalize winner.

        Args:
            foundation: Foundation dict with metadata, characters, world
            variants_data: Dict mapping variant_num -> list of chapter dicts

        Returns:
            Winner variant number

        Raises:
            Exception: If judging or finalization fails
        """
        # Judge variants
        winner, reasoning = await self.judge_variants(foundation, variants_data)

        # Finalize winner
        self.finalize_winner(
            winner_variant_num=winner,
            reasoning=reasoning,
            variants_evaluated=list(variants_data.keys())
        )

        return winner

    def get_decision(self) -> Optional[Dict[str, Any]]:
        """
        Load saved judging decision.

        Returns:
            Decision dict with winner, reasoning, timestamp, etc., or None if not found
        """
        if self.decisions_file.exists():
            with open(self.decisions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
