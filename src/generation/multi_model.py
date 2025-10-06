"""Multi-model competition mode for AgenticAuthor."""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..api import OpenRouterClient
from ..models import Project
from ..config import get_settings


JUDGING_PROMPT_TEMPLATE = """You are an expert judge evaluating multiple {content_type} outputs for a creative writing project.

{context}

Your task is to evaluate {num_candidates} candidate outputs and select the best one.

Evaluation Criteria:
{criteria}

Rate each candidate on a scale of 1-10 for each criterion, then provide:
1. Individual scores for each criterion
2. Total score (sum of all criteria)
3. Brief reasoning for your decision
4. The winner (candidate number)

Return your evaluation as a JSON object with this structure:
{{
  "evaluations": [
    {{
      "candidate": 1,
      "model": "model-name",
      "scores": {{
        "criterion1": 8,
        "criterion2": 9,
        ...
      }},
      "total": 85,
      "strengths": ["strength 1", "strength 2"],
      "weaknesses": ["weakness 1", "weakness 2"]
    }},
    ...
  ],
  "winner": 2,
  "reasoning": "Detailed explanation of why this candidate won",
  "recommendation": "Any suggestions for improvement"
}}

Here are the candidates to evaluate:

{candidates}

Provide your evaluation now:"""


CRITERIA_BY_TYPE = {
    "premise": {
        "hook": "How compelling is the hook? Does it grab attention?",
        "originality": "How original and fresh is the concept?",
        "clarity": "How clear and understandable is the premise?",
        "potential": "Does it have potential for a full story?",
        "genre_fit": "How well does it fit the intended genre?",
        "emotional_resonance": "Does it create emotional engagement?",
        "stakes": "Are the stakes clear and compelling?",
        "character_potential": "Do the characters seem interesting?"
    },
    "treatment": {
        "structure": "How well-structured is the three-act structure?",
        "pacing": "Is the pacing appropriate and engaging?",
        "character_development": "How well-developed are the character arcs?",
        "plot_coherence": "How coherent and logical is the plot?",
        "world_building": "How rich and consistent is the world-building?",
        "theme_integration": "How well-integrated are the thematic elements?",
        "conflict": "How compelling and escalating is the conflict?",
        "resolution": "How satisfying is the resolution?",
        "prose_quality": "How good is the writing quality?"
    },
    "chapters": {
        "outline_detail": "How detailed and comprehensive are the outlines?",
        "chapter_pacing": "How well-paced are individual chapters?",
        "overall_arc": "How well do chapters build the overall arc?",
        "beat_quality": "How specific and compelling are the beats?",
        "character_moments": "How well are character moments captured?",
        "tension_building": "How effectively is tension built?",
        "chapter_hooks": "How strong are the chapter endings?",
        "coherence": "How coherent is the overall structure?"
    },
    "prose": {
        "writing_quality": "How good is the prose quality?",
        "voice": "How strong and consistent is the narrative voice?",
        "pacing": "How well-paced is the prose?",
        "dialogue": "How natural and engaging is the dialogue?",
        "description": "How vivid and engaging are descriptions?",
        "emotion": "How well does it convey emotion?",
        "readability": "How readable and engaging is the text?",
        "style_consistency": "How consistent is the style?",
        "character_voice": "How distinct are character voices?",
        "scene_craft": "How well-crafted are individual scenes?"
    }
}


class MultiModelGenerator:
    """Generator that runs multiple models in competition and judges the output."""

    def __init__(self, client: OpenRouterClient, project: Project, console: Optional[Console] = None):
        """
        Initialize multi-model generator.

        Args:
            client: OpenRouter API client
            project: Current project
            console: Optional Rich console for output
        """
        self.client = client
        self.project = project
        self.console = console or Console()
        self.settings = get_settings()

        # Ensure multimodel directory exists
        self.multimodel_dir = self.project.path / "multimodel"
        self.multimodel_dir.mkdir(exist_ok=True)

    def _get_slug(self, model: str) -> str:
        """Convert model name to filename-safe slug."""
        return model.replace('/', '_').replace(':', '_').replace('.', '_')

    def _get_criteria(self, content_type: str) -> Dict[str, str]:
        """Get evaluation criteria for content type."""
        return CRITERIA_BY_TYPE.get(content_type, CRITERIA_BY_TYPE["prose"])

    def _format_context(self, content_type: str, **kwargs) -> str:
        """Format context for judging prompt."""
        context_parts = []

        if 'premise' in kwargs and kwargs['premise']:
            context_parts.append(f"Story Premise:\n{kwargs['premise'][:500]}...")

        if 'treatment' in kwargs and kwargs['treatment']:
            context_parts.append(f"Treatment Summary:\n{kwargs['treatment'][:500]}...")

        if 'genre' in kwargs and kwargs['genre']:
            context_parts.append(f"Genre: {kwargs['genre']}")

        if 'chapter_number' in kwargs:
            context_parts.append(f"Chapter Number: {kwargs['chapter_number']}")

        return "\n\n".join(context_parts) if context_parts else "No additional context provided."

    async def generate_parallel(
        self,
        generator_func: Callable,
        content_type: str,
        file_prefix: str,
        context: Optional[Dict[str, Any]] = None,
        **generator_kwargs
    ) -> Dict[str, Any]:
        """
        Run generation in parallel across multiple models and judge the results.

        Args:
            generator_func: Async function that generates content (takes model param)
            content_type: Type of content (premise/treatment/chapters/prose)
            file_prefix: Prefix for saved candidate files
            context: Additional context for judging
            **generator_kwargs: Additional kwargs to pass to generator_func

        Returns:
            Dict with winner, all candidates, and judging results
        """
        context = context or {}

        # Get competition models
        models = self.settings.competition_models
        judge_model = self.settings.judge_model

        # Show what we're doing
        self.console.print("\n" + "="*60)
        self.console.print(f"[bold cyan]🏆 MULTI-MODEL COMPETITION MODE[/bold cyan]")
        self.console.print("="*60)
        self.console.print(f"Content Type: {content_type}")
        self.console.print(f"Competitors: {len(models)} models")
        self.console.print(f"Judge: {judge_model}")
        self.console.print()

        # Show competitors
        competitors_table = Table(title="Competitors", show_header=True)
        competitors_table.add_column("#", style="cyan", width=4)
        competitors_table.add_column("Model", style="yellow")

        for i, model in enumerate(models, 1):
            competitors_table.add_row(str(i), model)

        self.console.print(competitors_table)
        self.console.print("\n[cyan]Starting parallel generation...[/cyan]\n")

        # Run generation in parallel
        tasks = []
        for model in models:
            self.console.print(f"[dim]Launching: {model}...[/dim]")
            task = generator_func(model=model, **generator_kwargs)
            tasks.append((model, task))

        # Wait for all to complete
        candidates = []
        for model, task in tasks:
            try:
                self.console.print(f"\n[cyan]Waiting for {model}...[/cyan]")
                result = await task
                candidates.append({
                    'model': model,
                    'content': result,
                    'word_count': len(result.split()) if isinstance(result, str) else 0,
                    'success': True
                })
                self.console.print(f"[green]✓ {model} completed ({len(result.split()) if isinstance(result, str) else 0} words)[/green]")
            except Exception as e:
                self.console.print(f"[red]✗ {model} failed: {e}[/red]")
                candidates.append({
                    'model': model,
                    'content': None,
                    'error': str(e),
                    'success': False
                })

        # Filter successful candidates
        successful = [c for c in candidates if c['success']]

        if len(successful) < 2:
            self.console.print(f"[red]Not enough successful candidates ({len(successful)}/3). Falling back to single-model.[/red]")
            # Return the first successful candidate or None
            if successful:
                return {
                    'winner': successful[0],
                    'candidates': candidates,
                    'judging': None,
                    'fallback': True
                }
            return None

        # Save all candidates
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        for i, candidate in enumerate(successful, 1):
            slug = self._get_slug(candidate['model'])
            candidate_file = self.multimodel_dir / f"{file_prefix}_{timestamp}_{slug}.md"
            with open(candidate_file, 'w', encoding='utf-8') as f:
                f.write(f"# Candidate {i}: {candidate['model']}\n\n")
                f.write(candidate['content'])
            candidate['saved_file'] = str(candidate_file.relative_to(self.project.path))

        # Show candidates comparison
        self.console.print("\n" + "="*60)
        self.console.print("[bold cyan]CANDIDATE OUTPUTS[/bold cyan]")
        self.console.print("="*60 + "\n")

        comparison_table = Table(show_header=True, title="Candidate Comparison")
        comparison_table.add_column("#", style="cyan", width=4)
        comparison_table.add_column("Model", style="yellow")
        comparison_table.add_column("Words", style="green", justify="right")
        comparison_table.add_column("Preview", style="white", max_width=60)

        for i, candidate in enumerate(successful, 1):
            content = candidate['content']
            preview = content[:150].replace('\n', ' ') + "..." if len(content) > 150 else content
            comparison_table.add_row(
                str(i),
                candidate['model'],
                str(candidate['word_count']),
                preview
            )

        self.console.print(comparison_table)
        self.console.print()

        # Judge the outputs
        self.console.print(f"[cyan]🧑‍⚖️  Sending to judge: {judge_model}...[/cyan]\n")

        judging_result = await self._judge_candidates(
            successful,
            content_type,
            judge_model,
            context
        )

        # Show judging results
        self._display_judging_results(judging_result, successful)

        # Save decision
        decision_file = self.multimodel_dir / "decisions.json"
        decisions = []
        if decision_file.exists():
            with open(decision_file, 'r', encoding='utf-8') as f:
                decisions = json.load(f)

        decisions.append({
            'timestamp': timestamp,
            'content_type': content_type,
            'file_prefix': file_prefix,
            'winner': judging_result['winner'],
            'winner_model': successful[judging_result['winner'] - 1]['model'],
            'evaluations': judging_result['evaluations'],
            'reasoning': judging_result['reasoning'],
            'recommendation': judging_result.get('recommendation')
        })

        with open(decision_file, 'w', encoding='utf-8') as f:
            json.dump(decisions, f, indent=2)

        # Return winner
        winner_index = judging_result['winner'] - 1
        winner = successful[winner_index]

        return {
            'winner': winner,
            'candidates': candidates,
            'judging': judging_result,
            'fallback': False
        }

    async def _judge_candidates(
        self,
        candidates: List[Dict[str, Any]],
        content_type: str,
        judge_model: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use judge model to evaluate candidates.

        Args:
            candidates: List of successful candidates
            content_type: Type of content being judged
            judge_model: Model to use for judging
            context: Additional context for judging

        Returns:
            Judging results as dict
        """
        # Get criteria
        criteria = self._get_criteria(content_type)

        # Format criteria
        criteria_text = "\n".join([
            f"- {name}: {description}"
            for name, description in criteria.items()
        ])

        # Format candidates
        candidates_text = ""
        for i, candidate in enumerate(candidates, 1):
            candidates_text += f"\n\n{'='*60}\n"
            candidates_text += f"CANDIDATE {i}: {candidate['model']}\n"
            candidates_text += f"{'='*60}\n\n"
            candidates_text += candidate['content']

        # Format context
        context_text = self._format_context(content_type, **context)

        # Build prompt
        prompt = JUDGING_PROMPT_TEMPLATE.format(
            content_type=content_type,
            context=context_text,
            num_candidates=len(candidates),
            criteria=criteria_text,
            candidates=candidates_text
        )

        # Call judge model
        try:
            result = await self.client.json_completion(
                model=judge_model,
                prompt=prompt,
                temperature=0.3,  # Lower for more consistent judging
                display_label="Judge evaluation",
                display_mode="silent"
            )

            return result

        except Exception as e:
            self.console.print(f"[red]Judge evaluation failed: {e}[/red]")
            # Fallback: return first candidate as winner
            return {
                'evaluations': [
                    {
                        'candidate': i,
                        'model': c['model'],
                        'scores': {},
                        'total': 0,
                        'strengths': [],
                        'weaknesses': []
                    }
                    for i, c in enumerate(candidates, 1)
                ],
                'winner': 1,
                'reasoning': f"Judge failed: {e}. Defaulting to first candidate.",
                'recommendation': "Manual review recommended."
            }

    def _display_judging_results(self, judging: Dict[str, Any], candidates: List[Dict[str, Any]]):
        """Display judging results in a nice format."""
        self.console.print("\n" + "="*60)
        self.console.print("[bold cyan]🧑‍⚖️  JUDGING RESULTS[/bold cyan]")
        self.console.print("="*60 + "\n")

        # Scores table
        scores_table = Table(show_header=True, title="Evaluation Scores")
        scores_table.add_column("#", style="cyan", width=4)
        scores_table.add_column("Model", style="yellow", width=30)
        scores_table.add_column("Total", style="magenta bold", justify="right", width=8)
        scores_table.add_column("Result", style="white", width=10)

        winner_index = judging['winner']

        for eval_data in judging['evaluations']:
            candidate_num = eval_data['candidate']
            is_winner = candidate_num == winner_index

            result = "🏆 WINNER" if is_winner else ""
            style = "green bold" if is_winner else "white"

            scores_table.add_row(
                str(candidate_num),
                eval_data['model'],
                str(eval_data['total']),
                result,
                style=style
            )

        self.console.print(scores_table)

        # Winner details
        winner_eval = next(e for e in judging['evaluations'] if e['candidate'] == winner_index)
        winner_model = winner_eval['model']

        self.console.print(f"\n[bold green]🏆 Winner: {winner_model}[/bold green]")
        self.console.print(f"[bold]Reasoning:[/bold] {judging['reasoning']}\n")

        # Show strengths and weaknesses
        if winner_eval.get('strengths'):
            self.console.print("[bold green]Strengths:[/bold green]")
            for strength in winner_eval['strengths']:
                self.console.print(f"  • {strength}")
            self.console.print()

        if winner_eval.get('weaknesses'):
            self.console.print("[bold yellow]Weaknesses:[/bold yellow]")
            for weakness in winner_eval['weaknesses']:
                self.console.print(f"  • {weakness}")
            self.console.print()

        if judging.get('recommendation'):
            self.console.print(f"[bold cyan]Recommendation:[/bold cyan] {judging['recommendation']}\n")

        self.console.print("="*60 + "\n")
