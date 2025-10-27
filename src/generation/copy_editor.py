"""Professional copy editing for final prose."""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..api import OpenRouterClient
from ..models import Project
from ..prompts import get_prompt_loader


console = Console()


class CopyEditor:
    """Professional copy editing pass with full accumulated context.

    Edits prose files (chapters/chapter-XX.md) sequentially, passing ALL
    previously edited chapters as context for maximum consistency.

    Does NOT edit: premise_metadata.json, treatment.md, or chapters.yaml
    """

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize copy editor.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for editing
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        self.client = client
        self.project = project
        self.model = model
        self.edited_chapters = {}  # Store edited prose as we process
        self.prompt_loader = get_prompt_loader()

    async def copy_edit_all_chapters(
        self,
        show_preview: bool = True,
        auto_apply: bool = False,
        chapter_filter: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Edit all chapter prose files sequentially with full accumulated context.

        Args:
            show_preview: Show preview and get approval before applying (default True)
            auto_apply: Automatically apply all edits without preview (default False)
            chapter_filter: Optional list of chapter numbers to edit (e.g., [3, 5, 6, 7, 8])
                          If None, edits all chapters

        Returns:
            Dict with chapters_edited count and backup directory
        """
        prose_files = self.project.list_chapters()

        if not prose_files:
            raise ValueError("No prose files found. Generate prose first with /generate prose")

        # Extract chapter numbers from paths (chapter-01.md -> 1)
        all_chapter_nums = [int(p.stem.split('-')[1]) for p in prose_files]

        # Filter chapters if specified
        if chapter_filter is not None:
            # Validate that all requested chapters exist
            invalid_chapters = [ch for ch in chapter_filter if ch not in all_chapter_nums]
            if invalid_chapters:
                raise ValueError(f"Chapters not found: {', '.join(map(str, invalid_chapters))}")

            chapter_nums = [ch for ch in all_chapter_nums if ch in chapter_filter]
            # Keep original order from chapter_filter for predictable editing
            chapter_nums.sort()
        else:
            chapter_nums = all_chapter_nums

        # Create timestamped backup directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.project.path / '.agentic' / 'backups' / f'copy_edit_{timestamp}'
        backup_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[bold cyan]{'═'*70}[/bold cyan]")
        console.print(f"[bold cyan]{'  '*10}COPY EDITING PASS{'  '*10}[/bold cyan]")
        console.print(f"[bold cyan]{'═'*70}[/bold cyan]")
        console.print(f"\n  [dim]• Chapters to edit: {len(chapter_nums)}[/dim]")
        console.print(f"  [dim]• Model: {self.model}[/dim]")
        console.print(f"  [dim]• Backup: {backup_dir.relative_to(self.project.path)}[/dim]\n")

        edited_count = 0
        skipped_count = 0

        for chapter_num in chapter_nums:
            console.print(f"\n[cyan]{'═'*70}[/cyan]")
            console.print(f"[bold cyan]Copy Editing Chapter {chapter_num} of {len(chapter_nums)}[/bold cyan]")
            console.print(f"[cyan]{'═'*70}[/cyan]\n")

            # Get original prose
            original = self.project.get_chapter(chapter_num)

            # Backup original
            backup_file = backup_dir / f'chapter-{chapter_num:02d}.original.md'
            backup_file.write_text(original, encoding='utf-8')

            # Build full context with ALL previously edited chapters
            context = self._build_full_context(chapter_num)

            # Copy edit this chapter with retry logic (streams edited text in real-time)
            max_auto_retries = 2
            result = None

            for attempt in range(1, max_auto_retries + 2):  # 1 initial + 2 auto-retries + 1 user-prompted
                try:
                    if attempt > 1:
                        if attempt <= max_auto_retries + 1:
                            console.print(f"\n[yellow]⚠ Retry attempt {attempt - 1}/{max_auto_retries}...[/yellow]\n")
                        else:
                            console.print(f"\n[yellow]⚠ Retry attempt (user-requested)...[/yellow]\n")

                    result = await self._copy_edit_chapter(
                        chapter_num=chapter_num,
                        chapter_text=original,
                        context=context
                    )

                    # Success - break retry loop
                    break

                except Exception as e:
                    error_msg = str(e)

                    # Check if this is a recoverable error pattern
                    is_empty_response = "empty response" in error_msg.lower() and "0 tokens" in error_msg
                    is_json_error = "json" in error_msg.lower() or "parse" in error_msg.lower()
                    is_timeout = "timeout" in error_msg.lower() or "timed out" in error_msg.lower()
                    is_recoverable = is_empty_response or is_json_error or is_timeout

                    # Auto-retry for first 2 attempts on recoverable errors
                    if attempt <= max_auto_retries and is_recoverable:
                        console.print(f"\n[red]✗ Error:[/red] {error_msg}")
                        console.print(f"[yellow]Auto-retrying ({attempt}/{max_auto_retries})...[/yellow]")
                        continue

                    # After 2 auto-retries, prompt user
                    elif attempt == max_auto_retries + 1 and is_recoverable:
                        console.print(f"\n[red]✗ Chapter {chapter_num} failed after {max_auto_retries} auto-retries:[/red]")
                        console.print(f"   {error_msg}\n")

                        # Show model-specific guidance
                        if "gpt-5-pro" in self.model.lower():
                            console.print("[yellow]⚠ Note: gpt-5-pro has known reliability issues with cold starts[/yellow]")
                            console.print("[yellow]   Consider switching to claude-opus-4 or grok-2 for production work[/yellow]\n")

                        # Prompt for retry/abort
                        console.print("[yellow]Options:[/yellow]")
                        console.print("  [cyan]y[/cyan] - Retry this chapter again")
                        console.print("  [cyan]n[/cyan] - Abort copy editing (no changes will be committed)")

                        from ..utils.logging import get_logger
                        logger = get_logger()
                        if logger:
                            logger.warning(f"Copy edit chapter {chapter_num} failed after {max_auto_retries} retries, prompting user")

                        choice = input("\nChoice (y/n): ").strip().lower()

                        if choice == 'y':
                            continue  # Retry
                        else:
                            console.print("\n[red]Copy editing aborted by user[/red]")
                            raise Exception(f"Copy editing aborted after failure on chapter {chapter_num}")

                    # Non-recoverable error or user declined retry
                    else:
                        console.print(f"\n[red]✗ Chapter {chapter_num} failed:[/red] {error_msg}")
                        raise

            # Check if we got a result
            if result is None:
                raise Exception(f"Failed to copy edit chapter {chapter_num} after all retry attempts")

            console.print()  # Blank line after streaming

            # Verify quality
            warnings = self._verify_edit_quality(original, result)

            # Show preview and get approval
            if show_preview and not auto_apply:
                approved = self._show_edit_preview(chapter_num, original, result, warnings)
                if not approved:
                    console.print(f"[yellow]⊗ Skipped chapter {chapter_num}[/yellow]")
                    # Store original as "edited" so context continues properly
                    self.edited_chapters[chapter_num] = original
                    skipped_count += 1
                    continue

            # Save edited prose to chapters-edited/ (result is plain text now)
            self.project.save_edited_chapter(chapter_num, result)

            # Store edited version for next chapter's context
            self.edited_chapters[chapter_num] = result

            # Save checkpoint (plain text backup)
            self._save_checkpoint(chapter_num, result, backup_dir)

            # Show success
            console.print(f"\n[green]✓ Chapter {chapter_num} copy edited successfully[/green]")

            # Word count info
            orig_words = len(original.split())
            edit_words = len(result.split())
            console.print(f"  [dim]• Words: {orig_words:,} → {edit_words:,}[/dim]")

            console.print(f"  [dim]• Saved to chapters/chapter-{chapter_num:02d}.md[/dim]")

            edited_count += 1

        # Summary
        console.print(f"\n[bold green]{'═'*70}[/bold green]")
        console.print(f"[bold green]✓ Copy Editing Complete[/bold green]")
        console.print(f"[bold green]{'═'*70}[/bold green]")
        console.print(f"\n  [green]• Successfully edited: {edited_count}/{len(chapter_nums)} chapters[/green]")
        if skipped_count > 0:
            console.print(f"  [yellow]• Skipped: {skipped_count} chapters[/yellow]")
        console.print(f"  [dim]• Backup location: {backup_dir.relative_to(self.project.path)}[/dim]\n")

        return {
            'chapters_edited': edited_count,
            'chapters_skipped': skipped_count,
            'backup_dir': str(backup_dir)
        }

    def _build_full_context(self, current_chapter_num: int) -> Dict[str, Any]:
        """
        Build full READ-ONLY context for current chapter.

        Includes:
        - chapters.yaml (self-contained: metadata, characters, world, chapter outlines)
        - ALL previously edited chapter prose
        - ALL remaining original chapter prose (for forward references)

        Args:
            current_chapter_num: Chapter number being edited

        Returns:
            Context dict with all reference material
        """
        # Get chapters.yaml (self-contained structure)
        chapters_yaml = self.project.get_chapters_yaml()
        if not chapters_yaml:
            # Legacy fallback
            chapters_yaml = {'chapters': self.project.get_chapters()}

        # Get all chapter numbers (extract from paths)
        all_chapter_paths = self.project.list_chapters()
        all_chapters = [int(p.stem.split('-')[1]) for p in all_chapter_paths]
        current_index = all_chapters.index(current_chapter_num)

        # Get edited chapters (before target)
        edited_chapters = []
        for i in range(current_index):
            prev_chapter_num = all_chapters[i]
            if prev_chapter_num in self.edited_chapters:
                edited_chapters.append({
                    'number': prev_chapter_num,
                    'text': self.edited_chapters[prev_chapter_num]
                })

        # Get ALL remaining original chapters (including target and after)
        remaining_chapters = []
        for i in range(current_index, len(all_chapters)):
            chapter_num = all_chapters[i]
            # Only include if not yet edited (will be original prose)
            if chapter_num not in self.edited_chapters:
                original_prose = self.project.get_chapter(chapter_num)
                remaining_chapters.append({
                    'number': chapter_num,
                    'text': original_prose
                })

        return {
            'chapters_yaml': chapters_yaml,
            'edited_chapters': edited_chapters,
            'remaining_chapters': remaining_chapters,
            'total_chapters': len(all_chapters),
            'current_position': current_index + 1,
            'current_chapter_num': current_chapter_num
        }

    async def _copy_edit_chapter(
        self,
        chapter_num: int,
        chapter_text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Copy edit a single chapter prose with full accumulated context.

        Args:
            chapter_num: Chapter number being edited
            chapter_text: Current chapter prose text
            context: Full context from _build_full_context()

        Returns:
            Edited chapter text (plain text, no JSON formatting)
        """
        # Build comprehensive prompts using template
        # Format edited chapters (already copy edited)
        edited_chapters_text = ""
        if context['edited_chapters']:
            edited_chapters_text = "\n\n".join([
                f"### Chapter {ch['number']}\n\n{ch['text']}"
                for ch in context['edited_chapters']
            ])

        # Format remaining chapters (not yet copy edited, for forward reference)
        remaining_chapters_text = ""
        if context['remaining_chapters']:
            # Exclude current chapter from remaining (it's being edited now)
            remaining_for_context = [ch for ch in context['remaining_chapters'] if ch['number'] != chapter_num]
            if remaining_for_context:
                remaining_chapters_text = "\n\n".join([
                    f"### Chapter {ch['number']}\n\n{ch['text']}"
                    for ch in remaining_for_context
                ])

        # Get current chapter text
        current_chapter_text = chapter_text

        # Load copy-edit instructions if available
        copy_edit_instructions = self._load_copy_edit_instructions()

        # Render prompts from template
        prompts = self.prompt_loader.render(
            "editing/copy_edit",
            chapter_num=chapter_num,
            total_chapters=context['total_chapters'],
            edited_chapters_text=edited_chapters_text,
            remaining_chapters_text=remaining_chapters_text,
            current_chapter_text=current_chapter_text,
            copy_edit_instructions=copy_edit_instructions
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("editing/copy_edit", default=0.3)

        # Call LLM with streaming - returns plain text
        edited_chapter = await self.client.completion(
            model=self.model,
            prompt=prompts['user'],
            system_prompt=prompts['system'],
            temperature=temperature,
            display=True,
            reserve_tokens=5000,  # Reserve space for full chapter output
            operation=f"copy-edit-chapter-{chapter_num}"
        )

        return edited_chapter.strip()

    def _verify_edit_quality(self, original: str, edited: str) -> List[str]:
        """
        Verify edit meets quality standards and safety checks.

        Args:
            original: Original chapter prose
            edited: Edited chapter prose (plain text)

        Returns:
            List of warning strings
        """
        warnings = []

        if not edited:
            warnings.append("⚠ CRITICAL: No edited chapter returned")
            return warnings

        # Paragraph structure verification
        orig_paras = original.count('\n\n')
        edit_paras = edited.count('\n\n')
        para_change_pct = abs(edit_paras - orig_paras) / orig_paras * 100 if orig_paras > 0 else 0

        if para_change_pct > 15:
            warnings.append(f"⚠ Paragraph structure changed significantly ({para_change_pct:.1f}%)")

        # Dialogue preservation
        orig_quotes = original.count('"')
        edit_quotes = edited.count('"')

        if orig_quotes != edit_quotes:
            diff = abs(orig_quotes - edit_quotes)
            if diff > 2:  # Allow minor discrepancies
                warnings.append(f"⚠ Dialogue markers changed (quotes: {orig_quotes} → {edit_quotes})")

        # Scene break preservation
        orig_breaks = original.count('* * *')
        edit_breaks = edited.count('* * *')

        if orig_breaks != edit_breaks:
            warnings.append(f"⚠ Scene breaks changed ({orig_breaks} → {edit_breaks})")

        # Chapter heading preservation
        orig_starts_chapter = original.lstrip().startswith('# Chapter')
        edit_starts_chapter = edited.lstrip().startswith('# Chapter')

        if orig_starts_chapter and not edit_starts_chapter:
            warnings.append(f"⚠ Chapter heading was removed")

        return warnings

    def _show_edit_preview(
        self,
        chapter_num: int,
        original: str,
        edited: str,
        warnings: List[str]
    ) -> bool:
        """
        Show preview of edits and get user approval.

        Args:
            chapter_num: Chapter number
            original: Original prose
            edited: Edited prose (plain text)
            warnings: List of warnings

        Returns:
            True if user approves, False otherwise
        """
        # Calculate word count statistics
        original_words = len(original.split())
        edited_words = len(edited.split())
        word_change_pct = ((edited_words - original_words) / original_words * 100) if original_words > 0 else 0

        # Show statistics
        console.print(f"\n[bold]Chapter {chapter_num} Edit Summary[/bold]")
        console.print(f"  [dim]Word count: {original_words:,} → {edited_words:,} ({word_change_pct:+.1f}%)[/dim]")

        # Show warnings
        if warnings:
            console.print("\n[yellow]⚠ Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  {warning}")
        else:
            console.print(f"  [dim]No structural warnings detected[/dim]")

        # Get approval
        console.print()
        response = input("Apply edits? [Y/n]: ").strip().lower()
        return response != 'n'

    def _save_checkpoint(self, chapter_num: int, edited_text: str, backup_dir: Path):
        """
        Save checkpoint after each chapter for resume capability.

        Args:
            chapter_num: Chapter number just completed
            edited_text: Edited chapter prose (plain text)
            backup_dir: Backup directory
        """
        # Save checkpoint metadata
        checkpoint_file = backup_dir / 'checkpoint.json'
        checkpoint = {
            'last_chapter_edited': chapter_num,
            'chapters_completed': list(self.edited_chapters.keys()),
            'timestamp': datetime.now().isoformat()
        }

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)

        # Save edited chapter text backup
        chapter_backup_file = backup_dir / f'chapter-{chapter_num:02d}.md'
        with open(chapter_backup_file, 'w', encoding='utf-8') as f:
            f.write(edited_text)

    def _load_copy_edit_instructions(self) -> Optional[str]:
        """
        Load project-specific copy editing instructions from misc/copy-edit.md.

        If project-specific instructions don't exist, attempts to copy from
        repo root misc/copy-edit.md. Similar to style card loading pattern.

        Returns:
            Copy editing instructions text, or None if not found
        """
        copy_edit_path = self.project.path / 'misc' / 'copy-edit.md'

        # If project copy-edit doesn't exist, try to copy from repo root
        if not copy_edit_path.exists():
            from pathlib import Path
            root_copy_edit = Path('misc') / 'copy-edit.md'

            if root_copy_edit.exists():
                # Copy default copy-edit instructions to project
                copy_edit_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    import shutil
                    shutil.copy2(root_copy_edit, copy_edit_path)
                    console.print(f"[dim]Copied default copy-edit instructions from {root_copy_edit}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to copy copy-edit instructions: {e}[/yellow]")
                    return None

        # Load instructions if they exist
        if copy_edit_path.exists():
            try:
                instructions = copy_edit_path.read_text(encoding='utf-8')
                console.print(f"[dim]Using copy-edit instructions: {copy_edit_path.relative_to(self.project.path)}[/dim]")
                return instructions
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to read copy-edit instructions: {e}[/yellow]")
                return None
        else:
            console.print(f"[dim]No copy-edit instructions found - using default editing guidelines[/dim]")
            return None
