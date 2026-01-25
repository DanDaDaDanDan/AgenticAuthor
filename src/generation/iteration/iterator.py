"""Main iteration coordinator."""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from rich.console import Console

from .history import IterationHistory
from .judge import IterationJudge
from .semantic_diff import SemanticDiffGenerator


class Iterator:
    """Coordinates iteration workflow across all LOD levels."""

    VALID_TARGETS = ['premise', 'treatment', 'chapters', 'prose']

    def __init__(self, client, project, model: str, console: Console = None):
        """
        Initialize iterator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for iteration
            console: Rich console for output (optional)
        """
        self.client = client
        self.project = project
        self.model = model
        self.console = console or Console()
        self.judge = IterationJudge(client, model)
        self.diff_generator = SemanticDiffGenerator(client, model)

    async def iterate(
        self,
        target: str,
        feedback: str
    ) -> bool:
        """
        Execute complete iteration workflow.

        Args:
            target: Iteration target (premise, treatment, chapters, prose)
            feedback: User feedback text

        Returns:
            True if iteration succeeded and was accepted, False otherwise
        """
        from ...utils.logging import get_logger
        logger = get_logger()

        # Validate target
        if target not in self.VALID_TARGETS:
            raise ValueError(f"Invalid target: {target}. Valid: {', '.join(self.VALID_TARGETS)}")

        # Check if target content exists
        if not self._target_exists(target):
            raise ValueError(f"No {target} found. Generate {target} first with /generate {target}")

        if logger:
            logger.info(f"Starting iteration on {target}: {feedback[:100]}...")

        # 1. Load context and history
        self.console.print(f"\n[cyan]Loading context for {target} iteration...[/cyan]")
        context, iteration_history = await self._load_context(target)

        # Show context summary
        self._show_context_summary(target, context, iteration_history)

        # Safety warning on first iteration
        if iteration_history.count() == 0:
            self.console.print("\n[bold yellow]⚠️  WARNING: Iteration replaces content permanently![/bold yellow]")
            self.console.print("[dim]Always test on cloned projects first (use /clone).[/dim]")
            self.console.print("[dim]Git commits are created automatically for easy rollback.[/dim]")
            choice = input("\nContinue with iteration? (y/n): ").strip().lower()
            if choice not in ['y', 'yes']:
                self.console.print("[yellow]Iteration cancelled[/yellow]")
                return False

        # 2. Check downstream and get user decision
        cull_downstream = await self._check_downstream(target)
        if cull_downstream is None:  # User cancelled
            self.console.print("[yellow]Iteration cancelled[/yellow]")
            return False

        # 3. Save old content for comparison
        old_content = self._get_current_content(target)

        # 4. Generation loop with judge validation
        new_content, judge_attempts, judge_verdict = await self._generation_loop(
            target, feedback, context, iteration_history, old_content
        )

        if new_content is None:  # User rejected during loop
            return False

        # 5. Generate semantic diff
        self.console.print("\n[cyan]Generating semantic diff...[/cyan]")
        semantic_diff = await self.diff_generator.generate_diff(
            feedback=feedback,
            iteration_history=iteration_history.get_context_for_llm(),
            old_content=old_content,
            new_content=new_content,
            judge_reasoning=judge_verdict.get('reasoning', ''),
            target=target
        )

        # 6. Show diff and get user approval
        accepted = await self._get_user_approval(semantic_diff, target, old_content, new_content)

        if not accepted:
            self.console.print("\n[yellow]Changes rejected. Content not modified.[/yellow]")
            return False

        # 7. Finalize: save content, cull downstream, update history, commit
        await self._finalize_iteration(
            target=target,
            new_content=new_content,
            feedback=feedback,
            judge_attempts=judge_attempts,
            judge_verdict=judge_verdict,
            semantic_diff=semantic_diff,
            cull_downstream=cull_downstream,
            iteration_history=iteration_history
        )

        self.console.print(f"\n[green]✓[/green] Iteration complete ({judge_attempts} judge attempts)")
        self.console.print(f"\nTo review: [cyan]git diff HEAD~1[/cyan]")
        self.console.print(f"To undo: [cyan]git reset --hard HEAD~1[/cyan]")

        return True

    def _target_exists(self, target: str) -> bool:
        """Check if target content exists."""
        if target == 'premise':
            return self.project.premise_metadata_file.exists()
        elif target == 'treatment':
            return self.project.treatment_file.exists()
        elif target == 'plan':
            return self.project.structure_plan_file.exists()
        elif target == 'prose':
            # Use project method for prose chapters
            return self.project.chapters_dir.exists() and \
                   bool(self.project.list_chapters())
        return False

    async def _load_context(self, target: str) -> Tuple[Dict[str, Any], IterationHistory]:
        """
        Load context and iteration history for target.

        Returns:
            (context dict, IterationHistory object)
        """
        from ..lod_context import LODContextBuilder

        # Get context level for target
        context_level_map = {
            'premise': 'premise',
            'treatment': 'treatment',
            'plan': 'plan',
            'prose': 'prose'
        }
        context_level = context_level_map[target]

        # Build context
        context_builder = LODContextBuilder()
        context = context_builder.build_context(
            project=self.project,
            context_level=context_level,
            include_downstream=False  # Don't include downstream in iteration context
        )

        # Load iteration history
        history_file = self._get_history_file(target)
        iteration_history = IterationHistory(history_file)

        return context, iteration_history

    def _get_history_file(self, target: str) -> Path:
        """Get iteration history file path for target."""
        if target == 'premise':
            return self.project.premise_dir / 'iteration_history.json'
        elif target == 'treatment':
            return self.project.treatment_dir / 'iteration_history.json'
        elif target == 'plan':
            return self.project.path / 'plan_iteration_history.json'
        elif target == 'prose':
            return self.project.chapters_dir / 'iteration_history.json'
        raise ValueError(f"Unknown target: {target}")

    def _show_context_summary(self, target: str, context: Dict, iteration_history: IterationHistory):
        """Show summary of loaded context."""
        self.console.print("  Context loaded:")

        if 'premise' in context:
            self.console.print("    ✓ Premise")
        if 'treatment' in context:
            self.console.print("    ✓ Treatment")
        if 'taxonomy' in context:
            self.console.print("    ✓ Taxonomy")
        if 'chapters' in context:
            if isinstance(context['chapters'], dict):
                # Has metadata/characters/world/chapters structure
                self.console.print(f"    ✓ Chapters (foundation + {len(context['chapters'].get('chapters', []))} chapters)")
            elif isinstance(context['chapters'], list):
                self.console.print(f"    ✓ Chapters ({len(context['chapters'])} chapters)")
        if 'prose' in context:
            self.console.print(f"    ✓ Prose ({len(context['prose'])} chapters)")

        count = iteration_history.count()
        if count > 0:
            self.console.print(f"    ✓ Iteration history ({count} previous iterations)")
            self.console.print(f"\n[dim]Previous iterations:[/dim]")
            for line in iteration_history.get_summary().split('\n'):
                self.console.print(f"  [dim]{line}[/dim]")

    async def _check_downstream(self, target: str) -> Optional[bool]:
        """
        Check for downstream content and get user decision.

        Returns:
            True if should cull, False if keep, None if cancelled
        """
        downstream_items = []

        if target == 'premise':
            if self.project.treatment_file.exists():
                downstream_items.append('Treatment')
            if self.project.structure_plan_file.exists():
                downstream_items.append('Structure Plan')
            if self.project.chapters_dir.exists():
                downstream_items.append('Prose')
        elif target == 'treatment':
            if self.project.structure_plan_file.exists():
                downstream_items.append('Structure Plan')
            if self.project.chapters_dir.exists():
                downstream_items.append('Prose')
        elif target == 'plan':
            if self.project.chapters_dir.exists():
                chapter_count = len(list(self.project.chapters_dir.glob('chapter-*.md')))
                downstream_items.append(f'Prose ({chapter_count} chapters)')

        if not downstream_items:
            return False  # No downstream content

        # Show warning
        self.console.print(f"\n[yellow]⚠️  Downstream content will be affected:[/yellow]")
        for item in downstream_items:
            self.console.print(f"  • {item}")

        # Get user decision
        while True:
            choice = input("\nAction (c=cull / k=keep / a=abort): ").strip().lower()

            if choice in ['cull', 'c']:
                return True
            elif choice in ['keep', 'k']:
                return False
            elif choice in ['abort', 'a', 'cancel']:
                return None
            else:
                self.console.print("[red]Invalid choice. Use: c (cull), k (keep), or a (abort)[/red]")

    def _get_current_content(self, target: str) -> str:
        """Get current content for target as string."""
        if target == 'premise':
            premise_meta = self.project.get_premise_metadata()
            return json.dumps(premise_meta, indent=2) if premise_meta else ""

        elif target == 'treatment':
            return self.project.get_treatment() or ""

        elif target == 'plan':
            return self.project.get_structure_plan() or ""

        elif target == 'prose':
            # Combine all prose chapters
            parts = []
            for chapter_file in sorted(self.project.list_chapters()):
                parts.append(chapter_file.read_text(encoding='utf-8'))
            return '\n\n---\n\n'.join(parts)

        return ""

    async def _generation_loop(
        self,
        target: str,
        feedback: str,
        context: Dict[str, Any],
        iteration_history: IterationHistory,
        old_content: str
    ) -> Tuple[Optional[str], int, Dict[str, Any]]:
        """
        Run generation loop with judge validation.

        Returns:
            (new_content, judge_attempts, final_judge_verdict)
            or (None, 0, {}) if user rejected
        """
        from ...utils.logging import get_logger
        logger = get_logger()

        from ...config import get_settings
        settings = get_settings()

        attempt = 0
        accumulated_judge_feedback = []
        final_verdict = {}

        while True:
            attempt += 1
            # Clarify what's being generated for chapters target
            if target == 'chapters':
                self.console.print(f"\n[cyan]Generating foundation + chapters... Attempt {attempt}[/cyan]")
            else:
                self.console.print(f"\n[cyan]Generating {target}... Attempt {attempt}[/cyan]")

            # Build prompt context
            prompt_context = self._build_prompt_context(
                target=target,
                context=context,
                feedback=feedback,
                iteration_history=iteration_history,
                accumulated_judge_feedback=accumulated_judge_feedback
            )

            # Generate content
            new_content = await self._generate_content(target, prompt_context, attempt)

            # Save to debug
            debug_dir = self._save_to_debug(target, attempt, new_content)

            self.console.print(f"[green]✓[/green] Generated (saved to debug)")

            # Run judge validation
            self.console.print("\n[cyan]Running validation judge...[/cyan]")

            # Build context string for judge
            context_str = self._build_context_string(context)

            verdict = await self.judge.validate(
                feedback=feedback,
                iteration_history=iteration_history.get_context_for_llm(),
                old_content=old_content,
                new_content=new_content,
                context=context_str,
                target=target
            )

            # Save judge verdict to debug
            verdict_file = debug_dir / f"attempt_{attempt}_judge_verdict.json"
            verdict_file.write_text(json.dumps(verdict, indent=2), encoding='utf-8')

            final_verdict = verdict

            if verdict.get('verdict') == 'approved':
                self.console.print("[green]Judge verdict: ✓ APPROVED[/green]\n")
                self.console.print("[dim]Judge reasoning:[/dim]")
                self.console.print(f"[dim]{verdict.get('reasoning', 'No reasoning provided')}[/dim]")
                return new_content, attempt, verdict

            else:
                # Needs revision
                self.console.print("[yellow]Judge verdict: ✗ NEEDS REVISION[/yellow]\n")
                self.console.print("[dim]Judge feedback:[/dim]")
                self.console.print(f"[dim]{verdict.get('reasoning', 'No reasoning provided')}[/dim]")

                if verdict.get('specific_issues'):
                    self.console.print("\n[dim]Specific issues:[/dim]")
                    for issue in verdict['specific_issues']:
                        self.console.print(f"  [dim]• {issue}[/dim]")

                # Get user decision
                while True:
                    choice = input("\nContinue with judge feedback? (y/n/view): ").strip().lower()

                    if choice in ['y', 'yes']:
                        # Add judge feedback to accumulator
                        judge_feedback_text = verdict.get('reasoning', '')
                        if verdict.get('suggestions'):
                            judge_feedback_text += "\n\nSuggestions:\n"
                            judge_feedback_text += "\n".join(f"- {s}" for s in verdict['suggestions'])

                        accumulated_judge_feedback.append(judge_feedback_text)
                        break

                    elif choice in ['n', 'no']:
                        # Stop loop, accept current result
                        self.console.print("\n[yellow]Accepting partial result without judge approval[/yellow]")
                        return new_content, attempt, verdict

                    elif choice in ['view', 'v']:
                        # Show semantic diff of current attempt
                        self.console.print("\n[cyan]Generating semantic diff for current attempt...[/cyan]")
                        partial_diff = await self.diff_generator.generate_diff(
                            feedback=feedback,
                            iteration_history=iteration_history.get_context_for_llm(),
                            old_content=old_content,
                            new_content=new_content,
                            judge_reasoning=verdict.get('reasoning', ''),
                            target=target
                        )

                        self.console.print("\n" + "━" * 70)
                        self.console.print(partial_diff)
                        self.console.print("━" * 70 + "\n")

                        # Ask again
                        continue

                    else:
                        self.console.print("[red]Invalid choice. Use: y, n, or view[/red]")

    def _build_prompt_context(
        self,
        target: str,
        context: Dict[str, Any],
        feedback: str,
        iteration_history: IterationHistory,
        accumulated_judge_feedback: list
    ) -> str:
        """Build context string for generation prompt."""
        # This would be customized per target
        # For now, just combine everything
        parts = []

        parts.append(f"USER FEEDBACK:\n{feedback}\n")

        if accumulated_judge_feedback:
            parts.append("JUDGE FEEDBACK FROM PREVIOUS ATTEMPTS:")
            for i, jf in enumerate(accumulated_judge_feedback, 1):
                parts.append(f"\nAttempt {i} Judge Feedback:\n{jf}")
            parts.append("")

        if iteration_history.count() > 0:
            parts.append("ITERATION HISTORY:")
            for it in iteration_history.get_context_for_llm():
                parts.append(f"\nPrevious: {it['feedback']}")
                parts.append(f"Result: {it['semantic_summary']}")
            parts.append("")

        # Add context elements
        if 'premise' in context:
            parts.append(f"PREMISE:\n{context['premise'].get('text', '')}\n")

        if 'treatment' in context:
            parts.append(f"TREATMENT:\n{context['treatment']}\n")

        if 'taxonomy' in context:
            parts.append(f"TAXONOMY:\n{json.dumps(context['taxonomy'], indent=2)}\n")

        # For prose iteration, include chapter structure
        if target == 'prose' and 'chapters' in context:
            import yaml
            if isinstance(context['chapters'], dict):
                # Has metadata/characters/world/chapters structure
                chapters_yaml = yaml.dump(context['chapters'], default_flow_style=False, allow_unicode=True)
                parts.append(f"CHAPTERS STRUCTURE:\n```yaml\n{chapters_yaml}```\n")
            elif isinstance(context['chapters'], list):
                chapters_yaml = yaml.dump({'chapters': context['chapters']}, default_flow_style=False, allow_unicode=True)
                parts.append(f"CHAPTERS STRUCTURE:\n```yaml\n{chapters_yaml}```\n")

        return '\n'.join(parts)

    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Build context string for judge."""
        parts = []

        if 'premise' in context:
            parts.append(f"PREMISE:\n{context['premise'].get('text', '')}")

        if 'treatment' in context:
            parts.append(f"TREATMENT:\n{context['treatment']}")

        if 'taxonomy' in context:
            parts.append(f"TAXONOMY:\n{json.dumps(context['taxonomy'], indent=2)}")

        if 'chapters' in context:
            if isinstance(context['chapters'], dict):
                chapters_count = len(context['chapters'].get('chapters', []))
                parts.append(f"CHAPTERS: {chapters_count} chapters with foundation")
            elif isinstance(context['chapters'], list):
                parts.append(f"CHAPTERS: {len(context['chapters'])} chapters")

        return '\n\n'.join(parts)

    async def _generate_content(self, target: str, prompt_context: str, attempt: int) -> str:
        """
        Generate new content for target based on iteration feedback.

        Args:
            target: Iteration target (premise, treatment, chapters, prose)
            prompt_context: Full context string with feedback and history
            attempt: Current attempt number

        Returns:
            Generated content as string
        """
        from ...prompts import get_prompt_loader
        prompt_loader = get_prompt_loader()

        # Map target to prompt template
        prompt_map = {
            'premise': 'generation/premise_iteration',
            'treatment': 'generation/treatment_iteration',
            'chapters': 'generation/chapter_iteration',
            'prose': 'generation/prose_full_iteration'  # Full prose iteration (not surgical fixes)
        }

        prompt_name = prompt_map.get(target)
        if not prompt_name:
            raise ValueError(f"Unknown target: {target}")

        # Get current content for reference
        old_content = self._get_current_content(target)

        # Render prompt
        prompts = prompt_loader.render(
            prompt_name,
            iteration_context=prompt_context,
            old_content=old_content,
            attempt=attempt
        )

        # Get temperature from config
        temperature = prompt_loader.get_temperature(prompt_name, default=0.7)

        # Generate with streaming
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=True,
            display=True
        )

        if not result:
            raise Exception(f"No response from {target} iteration generator")

        content = result.get('content', result) if isinstance(result, dict) else result

        return content.strip()

    def _save_to_debug(self, target: str, attempt: int, content: str) -> Path:
        """Save generation attempt to debug directory."""
        from ...config import get_settings
        settings = get_settings()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = settings.get_debug_dir(self.project.name) / f"iteration_{target}_{timestamp}"
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Save content
        content_file = debug_dir / f"attempt_{attempt}_raw.md"
        content_file.write_text(content, encoding='utf-8')

        return debug_dir

    async def _get_user_approval(
        self,
        semantic_diff: str,
        target: str,
        old_content: str,
        new_content: str
    ) -> bool:
        """
        Show semantic diff and get user approval.

        Returns:
            True if accepted, False if rejected
        """
        # Show semantic diff
        self.console.print("\n" + "━" * 70)
        self.console.print("ITERATION SUMMARY")
        self.console.print("━" * 70)
        self.console.print(semantic_diff)
        self.console.print("━" * 70 + "\n")

        # Get approval
        while True:
            choice = input("Accept these changes? (y/n/diff): ").strip().lower()

            if choice in ['y', 'yes']:
                return True

            elif choice in ['n', 'no']:
                return False

            elif choice in ['diff', 'd']:
                # Show detailed diff (TODO: implement drill-down)
                self.console.print("\n[yellow]Detailed text diff not yet implemented[/yellow]")
                self.console.print("[dim]Use: git diff after accepting to see detailed changes[/dim]\n")
                continue

            else:
                self.console.print("[red]Invalid choice. Use: y, n, or diff[/red]")

    async def _finalize_iteration(
        self,
        target: str,
        new_content: str,
        feedback: str,
        judge_attempts: int,
        judge_verdict: Dict[str, Any],
        semantic_diff: str,
        cull_downstream: bool,
        iteration_history: IterationHistory
    ):
        """Finalize iteration: save content, cull downstream, update history, commit."""
        from ...storage.git_manager import GitManager
        from ...config import get_settings

        self.console.print("\n[cyan]Finalizing iteration...[/cyan]")

        # 1. Save new content
        self._save_content(target, new_content)
        self.console.print("  ✓ Content saved")

        # 1b. Update combined.md if chapters target
        if target == 'chapters':
            try:
                combined_path = self.project.write_combined_markdown(target='chapters', include_prose=False)
                self.console.print(f"  ✓ Updated combined.md")
            except Exception as e:
                self.console.print(f"  [yellow]⚠[/yellow] Failed to update combined.md: {e}")

        # 2. Cull downstream if requested
        if cull_downstream:
            self._cull_downstream(target)
            self.console.print("  ✓ Downstream culled")

        # 3. Update iteration history
        settings = get_settings()

        # Commit first to get SHA (include project name prefix for shared git)
        git = GitManager(settings.books_dir)
        git.add()
        commit_message = f"[{self.project.name}] Iterate {target}: {feedback[:60]}"
        git.commit(commit_message)

        # Get commit SHA
        commit_sha = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=settings.books_dir,
            text=True
        ).strip()

        # Count changed files/lines (approximate)
        files_changed = 1  # TODO: count actual files
        lines_changed = 0  # TODO: count actual lines

        iteration_history.add_iteration(
            feedback=feedback,
            judge_attempts=judge_attempts,
            judge_verdict=judge_verdict.get('verdict', 'unknown'),
            judge_reasoning=judge_verdict.get('reasoning', ''),
            semantic_summary=semantic_diff[:500],  # Save truncated version
            commit_sha=commit_sha,
            files_changed=files_changed,
            lines_changed=lines_changed
        )
        self.console.print("  ✓ Iteration history updated")
        self.console.print(f"  ✓ Git commit: {commit_sha[:7]}")

    def _save_content(self, target: str, new_content: str):
        """
        Save new content for target.

        Args:
            target: Iteration target (premise, treatment, chapters, prose)
            new_content: Generated content to save
        """
        if target == 'premise':
            # Parse and save premise metadata
            # Content should be JSON with text and taxonomy
            try:
                premise_data = json.loads(new_content)
            except json.JSONDecodeError as e:
                raise Exception(
                    f"Failed to parse premise JSON: {e}\n\n"
                    f"LLM Response (first 500 chars):\n{new_content[:500]}"
                )

            # Save to premise_metadata.json
            self.project.premise_metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.project.premise_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(premise_data, f, indent=2)

        elif target == 'treatment':
            # Save treatment as markdown
            self.project.treatment_dir.mkdir(parents=True, exist_ok=True)
            self.project.treatment_file.write_text(new_content, encoding='utf-8')

        elif target == 'plan':
            # Save structure plan as markdown
            self.project.save_structure_plan(new_content)

        elif target == 'prose':
            # Parse prose chapters from content
            # Content should be chapter-NN.md sections separated by markers
            self.project.chapters_dir.mkdir(parents=True, exist_ok=True)

            # Split content by chapter markers
            sections = new_content.split('\n\n---\n\n')

            # Validate split result
            prose_sections = [s.strip() for s in sections if s.strip()]
            if not prose_sections:
                raise Exception(
                    "No prose sections found after split. "
                    "LLM may not have returned valid content."
                )

            # Count existing chapters to validate we got the right number
            existing_chapters = len(list(self.project.list_chapters()))
            if existing_chapters > 0 and len(prose_sections) != existing_chapters:
                self.console.print(
                    f"[yellow]Warning: Got {len(prose_sections)} chapters but "
                    f"expected {existing_chapters}. Proceeding anyway.[/yellow]"
                )

            # Save each chapter
            for i, section in enumerate(prose_sections, 1):
                chapter_file = self.project.chapters_dir / f"chapter-{i:02d}.md"
                chapter_file.write_text(section, encoding='utf-8')

        else:
            raise ValueError(f"Unknown target: {target}")

    def _cull_downstream(self, target: str):
        """Cull downstream content."""
        import shutil

        if target == 'premise':
            # Cull treatment, plan, prose
            if self.project.treatment_file.exists():
                self.project.treatment_file.unlink()
            if self.project.structure_plan_file.exists():
                self.project.structure_plan_file.unlink()
            if self.project.chapters_dir.exists():
                shutil.rmtree(self.project.chapters_dir)

        elif target == 'treatment':
            # Cull plan, prose
            if self.project.structure_plan_file.exists():
                self.project.structure_plan_file.unlink()
            if self.project.chapters_dir.exists():
                shutil.rmtree(self.project.chapters_dir)

        elif target == 'plan':
            # Cull prose
            if self.project.chapters_dir.exists():
                shutil.rmtree(self.project.chapters_dir)
