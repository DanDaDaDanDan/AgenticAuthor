"""Auto-improvement via LLM analysis and incorporation."""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel


class Improver:
    """Improve content via multi-stage LLM workflow."""

    VALID_TARGETS = ['premise', 'treatment', 'chapters']

    def __init__(self, client, project, model: str, console: Console = None):
        """
        Initialize improver.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for improvement
            console: Rich console for output (optional)
        """
        self.client = client
        self.project = project
        self.model = model
        self.console = console or Console()

    async def improve(self, target: str) -> bool:
        """
        Improve content through four stages:
        1. Analysis - LLM evaluates and suggests improvements
        2. Incorporation - LLM applies suggestions (multi-user message pattern)
        3. Validation - LLM summarizes changes and validates fidelity
        4. User approval - Human reviews and accepts/rejects

        Args:
            target: What to improve (premise, treatment, chapters)

        Returns:
            True if improvement applied, False if cancelled
        """
        if target not in self.VALID_TARGETS:
            raise ValueError(f"Invalid target: {target}. Valid: {', '.join(self.VALID_TARGETS)}")

        # Load current content
        content = self._load_content(target)
        if not content:
            raise ValueError(f"No {target} found. Generate {target} first with /generate {target}")

        # Stage 1: Analysis
        self.console.print("\n[cyan]Stage 1/4: Analyzing content for improvements...[/cyan]")
        analysis = await self._analyze(target, content)

        # Display analysis
        self._display_analysis(analysis)

        # Check if improvements suggested
        if not analysis.get('improvements'):
            self.console.print("[green]✓ Content is already high quality - no improvements needed[/green]")
            return False

        # Ask to proceed
        proceed = input("\nProceed with incorporating improvements? (y/n): ").strip().lower()
        if proceed not in ['y', 'yes']:
            self.console.print("[yellow]Improvement cancelled[/yellow]")
            return False

        # Stage 2: Incorporation (multi-user message pattern)
        self.console.print("\n[cyan]Stage 2/4: Incorporating improvements...[/cyan]")
        improved = await self._incorporate(target, content, analysis)

        # Stage 3: Validation
        self.console.print("\n[cyan]Stage 3/4: Validating changes...[/cyan]")
        validation = await self._validate(target, content, improved, analysis)

        # Display validation
        self._display_validation(validation)

        # Stage 4: User approval
        if validation['verdict'] != 'approved':
            self.console.print("\n[yellow]⚠ Validation failed - improvements not recommended[/yellow]")
            return False

        accept = input("\nAccept these changes? (y/n): ").strip().lower()
        if accept not in ['y', 'yes']:
            self.console.print("[yellow]Changes rejected[/yellow]")
            return False

        # Save improved content
        self._save_content(target, improved)

        # Git commit
        self._git_commit(target, validation['changes_summary'])

        self.console.print("\n[green]✓ Improvements applied successfully[/green]")
        return True

    async def _analyze(self, target: str, content: str) -> Dict[str, Any]:
        """Stage 1: Analyze content and suggest improvements."""
        from ..prompts import get_prompt_loader
        loader = get_prompt_loader()

        prompts = loader.render(
            "analysis/content_improvement",
            target=target,
            content=content
        )

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=0.3,
            stream=False,
            display=False,
            response_format={"type": "json_object"},
            operation=f"{target}-improvement-analysis"
        )

        return json.loads(result['content'])

    async def _incorporate(self, target: str, original: str, analysis: Dict) -> str:
        """
        Stage 2: Incorporate improvements using multi-user message pattern.

        This is the key multi-message approach:
        - Message 1: Original content
        - Message 2: Analysis with suggestions
        - Message 3: Instructions to incorporate
        """
        from ..prompts import get_prompt_loader
        loader = get_prompt_loader()

        # Render incorporation instruction (message 3)
        prompts = loader.render(
            "generation/improvement_incorporation",
            target=target
        )

        # Format analysis for context
        analysis_text = json.dumps(analysis, indent=2)

        # Multi-user message pattern - this is the natural conversation flow
        messages = [
            {"role": "system", "content": prompts['system']},
            {"role": "user", "content": f"ORIGINAL {target.upper()}:\n```\n{original}\n```"},
            {"role": "user", "content": f"IMPROVEMENT ANALYSIS:\n```json\n{analysis_text}\n```"},
            {"role": "user", "content": prompts['user']}
        ]

        result = await self.client.streaming_completion(
            model=self.model,
            messages=messages,
            temperature=0.7,
            stream=True,
            display=True,
            operation=f"{target}-improvement-incorporation"
        )

        return result['content']

    async def _validate(self, target: str, old: str, new: str, analysis: Dict) -> Dict[str, Any]:
        """Stage 3: Validate changes match analysis."""
        from ..prompts import get_prompt_loader
        loader = get_prompt_loader()

        prompts = loader.render(
            "validation/improvement_validation",
            target=target,
            old_content=old,
            new_content=new,
            analysis=json.dumps(analysis, indent=2)
        )

        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=0.1,
            stream=False,
            display=False,
            response_format={"type": "json_object"},
            operation=f"{target}-improvement-validation"
        )

        return json.loads(result['content'])

    def _display_analysis(self, analysis: Dict):
        """Display analysis results with rich formatting."""
        self.console.print("\n" + "="*80)
        self.console.print("[bold cyan]CONTENT ANALYSIS[/bold cyan]")
        self.console.print("="*80)

        self.console.print(f"\n[bold]Current Rating:[/bold] {analysis.get('overall_rating', 'N/A')}")
        self.console.print(f"[dim]{analysis.get('assessment', '')}[/dim]")

        if analysis.get('strengths'):
            self.console.print("\n[green]✓ STRENGTHS:[/green]")
            for strength in analysis['strengths']:
                self.console.print(f"  • {strength}")

        if analysis.get('improvements'):
            self.console.print("\n[yellow]⚠ SUGGESTED IMPROVEMENTS:[/yellow]\n")
            for i, imp in enumerate(analysis['improvements'], 1):
                priority = imp.get('priority', 'medium').upper()
                color = "red" if priority == "HIGH" else "yellow" if priority == "MEDIUM" else "blue"

                self.console.print(f"[{color}][{priority}][/{color}] {imp.get('area', 'General')}")
                self.console.print(f"  Issue: {imp.get('issue', 'N/A')}")
                self.console.print(f"  Fix: {imp.get('suggestion', 'N/A')}")
                self.console.print(f"  Impact: [dim]{imp.get('impact', 'N/A')}[/dim]")
                self.console.print()

        potential = analysis.get('potential_rating', 'N/A')
        self.console.print(f"[bold]Potential Rating:[/bold] {potential}")
        self.console.print("="*80 + "\n")

    def _display_validation(self, validation: Dict):
        """Display validation results with rich formatting."""
        self.console.print("\n" + "="*80)
        self.console.print("[bold cyan]VALIDATION RESULTS[/bold cyan]")
        self.console.print("="*80)

        # Changes summary
        self.console.print("\n[bold]Changes Made:[/bold]")
        for change in validation.get('changes_summary', []):
            self.console.print(f"  • {change}")

        # Fidelity check
        fidelity = validation.get('fidelity_check', {})
        matches = fidelity.get('matches_analysis', False)
        quality = fidelity.get('quality_maintained', False)
        format_ok = fidelity.get('format_preserved', True)

        self.console.print(f"\n[bold]Fidelity Check:[/bold]")
        self.console.print(f"  Matches Analysis: {'✓' if matches else '✗'}")
        self.console.print(f"  Quality Maintained: {'✓' if quality else '✗'}")
        self.console.print(f"  Format Preserved: {'✓' if format_ok else '✗'}")

        # Analysis items addressed
        if fidelity.get('analysis_items_addressed'):
            self.console.print(f"\n[bold]Analysis Items:[/bold]")
            for item in fidelity['analysis_items_addressed']:
                self.console.print(f"  • {item}")

        if fidelity.get('unintended_changes'):
            self.console.print("\n[yellow]Unintended Changes:[/yellow]")
            for change in fidelity['unintended_changes']:
                self.console.print(f"  • {change}")

        # Verdict
        verdict = validation.get('verdict', 'unknown')
        color = "green" if verdict == "approved" else "red"
        self.console.print(f"\n[bold]Verdict:[/bold] [{color}]{verdict.upper()}[/{color}]")
        self.console.print(f"[dim]{validation.get('reasoning', '')}[/dim]")

        if validation.get('concerns'):
            self.console.print("\n[yellow]Concerns:[/yellow]")
            for concern in validation['concerns']:
                self.console.print(f"  • {concern}")

        self.console.print("="*80 + "\n")

    def _load_content(self, target: str) -> Optional[str]:
        """Load current content for target."""
        if target == 'premise':
            file_path = self.project.premise_file
        elif target == 'treatment':
            file_path = self.project.treatment_file
        elif target == 'chapters':
            file_path = self.project.chapters_file
        else:
            return None

        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _save_content(self, target: str, content: str):
        """Save improved content."""
        if target == 'premise':
            file_path = self.project.premise_file
        elif target == 'treatment':
            file_path = self.project.treatment_file
        elif target == 'chapters':
            file_path = self.project.chapters_file
        else:
            raise ValueError(f"Unknown target: {target}")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _git_commit(self, target: str, changes: list):
        """Create git commit for improvements."""
        from ..utils.git import get_git_manager
        git = get_git_manager(self.project.path.parent)

        if git:
            # Format commit message
            summary = "\n".join([f"  - {c}" for c in changes[:3]])  # First 3 changes
            message = f"Improve: {target} via LLM analysis\n\n{summary}"

            if len(changes) > 3:
                message += f"\n  ... and {len(changes) - 3} more"

            message += "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>"

            git.commit(message)
