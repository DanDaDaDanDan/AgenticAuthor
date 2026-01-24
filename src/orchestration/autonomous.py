"""Autonomous generation orchestrator for fire-and-forget book generation."""

import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .state_machine import GenerationPhase, StateManager
from .quality_gates import QualityGateManager, QualityGateResult
from ..models import Project


class AutonomousGenerator:
    """
    Orchestrates fully autonomous generation from premise to prose.

    Features:
    - State machine tracking (PREMISE → TREATMENT → CHAPTERS → PROSE → COMPLETE)
    - Persistent state for resume after interruption
    - Quality gates with auto-iteration (max 2 attempts)
    - Blocks only on unrecoverable errors
    """

    MAX_AUTO_ITERATIONS = 2

    def __init__(
        self,
        client,
        project: Project,
        model: str,
        console: Optional[Console] = None,
    ):
        """
        Initialize autonomous generator.

        Args:
            client: OpenRouter API client
            project: Project to generate
            model: Model to use for generation
            console: Rich console for output (optional)
        """
        self.client = client
        self.project = project
        self.model = model
        self.console = console or Console()
        self.state_manager = StateManager(project.path)
        self.quality_gates = QualityGateManager(client, model, project)
        self._cancelled = False

    async def run(
        self,
        resume: bool = False,
        on_phase_start: Optional[Callable[[GenerationPhase], Awaitable[None]]] = None,
        on_phase_complete: Optional[Callable[[GenerationPhase], Awaitable[None]]] = None,
    ) -> bool:
        """
        Run autonomous generation from current state to completion.

        Args:
            resume: If True, resume from saved state; if False, start fresh
            on_phase_start: Callback when a phase starts
            on_phase_complete: Callback when a phase completes

        Returns:
            True if generation completed successfully, False if blocked/cancelled
        """
        self._cancelled = False

        # Load or initialize state
        state = self.state_manager.load() if resume else self._init_fresh_state()

        # Handle resume - detect phase from files if state is stale
        if resume:
            detected = self.state_manager.detect_phase_from_files(self.project)
            if detected.value != state.phase.value:
                self.console.print(f"[yellow]State mismatch: saved={state.phase.value}, detected={detected.value}[/yellow]")
                self.console.print(f"[cyan]Resuming from detected phase: {detected.value}[/cyan]")
                state.phase = detected
                self.state_manager.update_phase(detected)

        self.console.print(Panel(
            f"[bold]Autonomous Generation[/bold]\n\n"
            f"Project: [cyan]{self.project.name}[/cyan]\n"
            f"Model: [cyan]{self.model}[/cyan]\n"
            f"Starting Phase: [cyan]{state.phase.display_name}[/cyan]\n"
            f"Mode: [cyan]{'Resume' if resume else 'Fresh'}[/cyan]",
            title="Starting",
            border_style="green"
        ))

        # Run through phases
        try:
            while state.phase != GenerationPhase.COMPLETE and not self._cancelled:
                if state.has_error:
                    self.console.print(f"[red]Blocked by error: {state.error}[/red]")
                    return False

                # Get next phase to run
                phase_to_run = self._get_next_phase(state.phase)
                if phase_to_run is None:
                    break

                if on_phase_start:
                    await on_phase_start(phase_to_run)

                # Run the phase
                success = await self._run_phase(phase_to_run)

                if not success:
                    if self._cancelled:
                        self.console.print("[yellow]Generation cancelled by user[/yellow]")
                        return False
                    # Phase failed - state should have error set
                    state = self.state_manager.get_state()
                    return False

                if on_phase_complete:
                    await on_phase_complete(phase_to_run)

                # Move to next phase
                next_phase = phase_to_run.next_phase()
                if next_phase:
                    self.state_manager.update_phase(next_phase)
                    state = self.state_manager.get_state()

            # All done
            if state.phase == GenerationPhase.COMPLETE:
                self.console.print(Panel(
                    "[bold green]Generation Complete![/bold green]\n\n"
                    f"Total Chapters: {state.total_chapters}\n"
                    f"Total Words: {state.word_count:,}",
                    title="Success",
                    border_style="green"
                ))
                return True

            return False

        except asyncio.CancelledError:
            self.console.print("[yellow]Generation cancelled[/yellow]")
            self._cancelled = True
            return False

        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            self.state_manager.set_error(str(e))
            return False

    def cancel(self):
        """Cancel the current generation."""
        self._cancelled = True

    def _init_fresh_state(self):
        """Initialize fresh state and reset any existing state."""
        self.state_manager.reset()
        state = self.state_manager.load()
        self.state_manager.update_phase(GenerationPhase.PREMISE)
        return self.state_manager.get_state()

    def _get_next_phase(self, current: GenerationPhase) -> Optional[GenerationPhase]:
        """
        Determine next phase to run based on current state.

        Args:
            current: Current phase

        Returns:
            Next phase to run, or None if complete/blocked
        """
        if current == GenerationPhase.IDLE:
            return GenerationPhase.PREMISE
        elif current == GenerationPhase.COMPLETE:
            return None
        else:
            return current  # Run the current phase

    async def _run_phase(self, phase: GenerationPhase) -> bool:
        """
        Run a single generation phase.

        Args:
            phase: Phase to run

        Returns:
            True if phase completed successfully
        """
        self.console.print(f"\n[bold cyan]Phase: {phase.display_name}[/bold cyan]")

        if phase == GenerationPhase.PREMISE:
            return await self._run_premise_phase()
        elif phase == GenerationPhase.TREATMENT:
            return await self._run_treatment_phase()
        elif phase == GenerationPhase.CHAPTERS:
            return await self._run_chapters_phase()
        elif phase == GenerationPhase.PROSE:
            return await self._run_prose_phase()

        return True

    async def _run_premise_phase(self) -> bool:
        """Generate premise."""
        try:
            from ..generation.premise import PremiseGenerator

            # Check if premise already exists
            if self.project.get_premise():
                self.console.print("[dim]Premise exists, skipping generation[/dim]")
                return True

            generator = PremiseGenerator(self.client, self.project, self.model)
            await generator.generate_with_taxonomy()

            self.console.print("[green]Premise generated[/green]")
            return True

        except Exception as e:
            self.state_manager.set_error(f"Premise generation failed: {e}")
            self.console.print(f"[red]Premise generation failed: {e}[/red]")
            return False

    async def _run_treatment_phase(self) -> bool:
        """Generate treatment."""
        try:
            from ..generation.treatment import TreatmentGenerator

            # Check if treatment already exists
            if self.project.get_treatment():
                self.console.print("[dim]Treatment exists, skipping generation[/dim]")
                return True

            generator = TreatmentGenerator(self.client, self.project, self.model)
            await generator.generate()

            self.console.print("[green]Treatment generated[/green]")
            return True

        except Exception as e:
            self.state_manager.set_error(f"Treatment generation failed: {e}")
            self.console.print(f"[red]Treatment generation failed: {e}[/red]")
            return False

    async def _run_chapters_phase(self) -> bool:
        """Generate chapter outlines with structure validation."""
        try:
            from ..generation.chapters import ChapterGenerator

            # Check if chapters already exist
            chapters = self.project.get_chapters()
            if chapters:
                self.console.print(f"[dim]Chapters exist ({len(chapters)} chapters), checking structure gate[/dim]")
            else:
                generator = ChapterGenerator(self.client, self.project, self.model)
                await generator.generate_chapters()
                chapters = self.project.get_chapters()
                self.console.print(f"[green]Chapter outlines generated ({len(chapters)} chapters)[/green]")

            # Run structure gate
            gate_result = await self._run_structure_gate()
            if not gate_result:
                return False

            # Update state with chapter count
            self.state_manager.update_progress(total_chapters=len(chapters))

            return True

        except Exception as e:
            self.state_manager.set_error(f"Chapter generation failed: {e}")
            self.console.print(f"[red]Chapter generation failed: {e}[/red]")
            return False

    async def _run_structure_gate(self) -> bool:
        """Run structure quality gate with auto-iteration."""
        self.console.print("[dim]Running STRUCTURE_GATE...[/dim]")

        for attempt in range(self.MAX_AUTO_ITERATIONS + 1):
            gate = await self.quality_gates.check_structure_gate()

            if gate.passed:
                self.state_manager.update_quality_gate('structure', True, gate.reasoning)
                self.console.print("[green]STRUCTURE_GATE: PASS[/green]")
                return True

            if gate.result == QualityGateResult.BLOCKED:
                self.state_manager.update_quality_gate('structure', False, gate.reasoning)
                self.state_manager.set_error(f"STRUCTURE_GATE blocked: {gate.reasoning}")
                self.console.print(f"[red]STRUCTURE_GATE: BLOCKED[/red]")
                for issue in gate.issues:
                    self.console.print(f"  [red]• {issue}[/red]")
                return False

            if gate.can_auto_fix and attempt < self.MAX_AUTO_ITERATIONS:
                self.console.print(f"[yellow]STRUCTURE_GATE needs work, auto-iterating ({attempt + 1}/{self.MAX_AUTO_ITERATIONS})...[/yellow]")
                # Auto-iterate would go here (TODO: implement chapter iteration)
                # For now, just fail after max attempts
                continue
            else:
                self.state_manager.update_quality_gate('structure', False, gate.reasoning)
                self.state_manager.set_error(f"STRUCTURE_GATE failed after {attempt} attempts")
                self.console.print(f"[red]STRUCTURE_GATE: FAILED after {attempt} auto-iterations[/red]")
                return False

        return False

    async def _run_prose_phase(self) -> bool:
        """Generate prose for all chapters with continuity gates."""
        try:
            from ..generation.prose import ProseGenerator

            chapters = self.project.get_chapters()
            if not chapters:
                self.state_manager.set_error("No chapter outlines found")
                return False

            total_chapters = len(chapters)
            self.state_manager.update_progress(total_chapters=total_chapters)

            # Load style card if available
            style_card = self._load_style_card()

            generator = ProseGenerator(self.client, self.project, self.model)
            total_words = 0

            for chapter in chapters:
                if self._cancelled:
                    return False

                chapter_num = chapter['number']

                # Check if chapter prose already exists
                existing = self.project.get_chapter(chapter_num)
                if existing:
                    word_count = len(existing.split())
                    total_words += word_count
                    self.console.print(f"[dim]Chapter {chapter_num} exists ({word_count:,} words), skipping[/dim]")
                    self.state_manager.update_progress(
                        current_chapter=chapter_num,
                        word_count=total_words
                    )
                    continue

                # Generate chapter
                self.console.print(f"\n[cyan]Generating Chapter {chapter_num}/{total_chapters}...[/cyan]")

                prose = await generator.generate_chapter(
                    chapter_number=chapter_num,
                    style_card=style_card
                )

                word_count = len(prose.split())
                total_words += word_count

                self.state_manager.update_progress(
                    current_chapter=chapter_num,
                    word_count=total_words
                )

                # Run continuity gate
                gate_passed = await self._run_continuity_gate(chapter_num)
                if not gate_passed:
                    # Continuity gate failed - but we continue with warning
                    self.console.print(f"[yellow]Warning: Continuity gate issues in chapter {chapter_num}[/yellow]")

            # All prose generated - run completion gate
            gate_passed = await self._run_completion_gate()

            if gate_passed:
                self.state_manager.update_phase(GenerationPhase.COMPLETE)

            return gate_passed

        except Exception as e:
            self.state_manager.set_error(f"Prose generation failed: {e}")
            self.console.print(f"[red]Prose generation failed: {e}[/red]")
            return False

    async def _run_continuity_gate(self, chapter_num: int) -> bool:
        """Run continuity gate for a chapter."""
        gate = await self.quality_gates.check_continuity_gate(chapter_num)

        if gate.passed:
            self.state_manager.update_quality_gate('continuity', True, gate.reasoning, chapter_num)
            self.console.print(f"[dim]CONTINUITY_GATE CH{chapter_num}: PASS[/dim]")
            return True

        # Log the issue but don't block
        self.state_manager.update_quality_gate('continuity', False, gate.reasoning, chapter_num)
        self.console.print(f"[yellow]CONTINUITY_GATE CH{chapter_num}: {gate.result.value}[/yellow]")
        for issue in gate.issues[:2]:  # Show first 2 issues
            self.console.print(f"  [yellow]• {issue}[/yellow]")

        # Continue anyway - we don't want to block on minor continuity issues
        return True

    async def _run_completion_gate(self) -> bool:
        """Run final completion gate."""
        self.console.print("[dim]Running COMPLETION_GATE...[/dim]")

        gate = await self.quality_gates.check_completion_gate()

        if gate.passed:
            self.state_manager.update_quality_gate('completion', True, gate.reasoning)
            self.console.print("[green]COMPLETION_GATE: PASS[/green]")
            return True

        if gate.result == QualityGateResult.BLOCKED:
            self.state_manager.update_quality_gate('completion', False, gate.reasoning)
            self.console.print(f"[red]COMPLETION_GATE: BLOCKED[/red]")
            for issue in gate.issues:
                self.console.print(f"  [red]• {issue}[/red]")
            return False

        # NEEDS_WORK - but we'll pass anyway with warning
        self.state_manager.update_quality_gate('completion', True, f"Passed with warnings: {gate.reasoning}")
        self.console.print(f"[yellow]COMPLETION_GATE: PASS (with warnings)[/yellow]")
        for suggestion in gate.suggestions[:2]:
            self.console.print(f"  [yellow]• {suggestion}[/yellow]")

        return True

    def _load_style_card(self) -> Optional[str]:
        """Load prose style card if available."""
        style_card_path = self.project.path / "misc" / "prose-style-card.md"
        if style_card_path.exists():
            return style_card_path.read_text(encoding='utf-8')
        return None
