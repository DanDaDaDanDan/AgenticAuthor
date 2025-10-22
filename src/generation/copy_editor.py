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

    async def copy_edit_all_chapters(self, show_preview: bool = True, auto_apply: bool = False) -> Dict[str, Any]:
        """
        Edit all chapter prose files sequentially with full accumulated context.

        Args:
            show_preview: Show preview and get approval before applying (default True)
            auto_apply: Automatically apply all edits without preview (default False)

        Returns:
            Dict with chapters_edited count and backup directory
        """
        prose_files = self.project.list_chapters()

        if not prose_files:
            raise ValueError("No prose files found. Generate prose first with /generate prose")

        # Extract chapter numbers from paths (chapter-01.md -> 1)
        chapter_nums = [int(p.stem.split('-')[1]) for p in prose_files]

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

            # Copy edit this chapter (streams edited text in real-time)
            result = await self._copy_edit_chapter(
                chapter_num=chapter_num,
                chapter_text=original,
                context=context
            )

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

            # Save edited prose
            edited_text = result['edited_chapter']
            self.project.save_chapter(chapter_num, edited_text)

            # Store edited version for next chapter's context
            self.edited_chapters[chapter_num] = edited_text

            # Save checkpoint
            self._save_checkpoint(chapter_num, result, backup_dir)

            # Show success with statistics
            stats = result.get('statistics', {})
            console.print(f"\n[green]✓ Chapter {chapter_num} copy edited successfully[/green]")

            total_fixes = stats.get('total_errors_fixed', 0)
            word_change = stats.get('word_count_change_percent', 0)

            if total_fixes > 0:
                console.print(f"  [dim]• {total_fixes} total edits made[/dim]")
            if abs(word_change) > 0.1:
                console.print(f"  [dim]• Word count: {word_change:+.1f}%[/dim]")

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
    ) -> Dict[str, Any]:
        """
        Copy edit a single chapter prose with full accumulated context.

        Args:
            chapter_num: Chapter number being edited
            chapter_text: Current chapter prose text
            context: Full context from _build_full_context()

        Returns:
            Result dict with edited_chapter, changes_made, statistics, etc.
        """
        # Build comprehensive prompts using template
        # Format edited chapters (already perfect)
        edited_chapters_text = ""
        if context['edited_chapters']:
            edited_chapters_text = "\n\n".join([
                f"### Chapter {ch['number']} (ALREADY COPY EDITED)\n\n{ch['text']}"
                for ch in context['edited_chapters']
            ])

        # Format remaining original chapters (for forward references)
        remaining_chapters_text = ""
        if context['remaining_chapters']:
            # Don't include the current chapter in remaining (it's what we're editing)
            remaining_for_context = [ch for ch in context['remaining_chapters'] if ch['number'] != chapter_num]
            if remaining_for_context:
                remaining_chapters_text = "\n\n".join([
                    f"### Chapter {ch['number']} (ORIGINAL - NOT YET EDITED)\n\n{ch['text']}"
                    for ch in remaining_for_context
                ])

        # Get current chapter text from remaining
        current_chapter_text = chapter_text
        for ch in context['remaining_chapters']:
            if ch['number'] == chapter_num:
                current_chapter_text = ch['text']
                break

        # Serialize chapters.yaml to markdown for context
        from ..utils.markdown_extractors import MarkdownFormatter
        chapters_markdown = MarkdownFormatter.format_chapters_yaml(context['chapters_yaml'])

        # Render prompts from template
        prompts = self.prompt_loader.render(
            "editing/copy_edit",
            chapter_num=chapter_num,
            total_chapters=context['total_chapters'],
            chapters_markdown=chapters_markdown,
            edited_chapters_text=edited_chapters_text,
            remaining_chapters_text=remaining_chapters_text,
            current_chapter_text=current_chapter_text,
            original_word_count=len(chapter_text.split())
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("editing/copy_edit", default=0.3)

        # Call LLM with streaming enabled to show edited text as it's generated
        result = await self.client.json_completion(
            model=self.model,
            prompt=prompts['user'],
            system_prompt=prompts['system'],
            temperature=temperature,
            display_field="edited_chapter",  # Stream the edited chapter text
            display_label=f"Copy editing chapter {chapter_num}",
            display_mode="field",  # Extract and display just the edited_chapter field
            reserve_tokens=8000  # Full chapter + detailed changes
        )

        return result

    def _verify_edit_quality(self, original: str, result: Dict[str, Any]) -> List[str]:
        """
        Verify edit meets quality standards and safety checks.

        Args:
            original: Original chapter prose
            result: Edit result from LLM

        Returns:
            List of warning strings
        """
        warnings = []
        edited = result.get('edited_chapter', '')

        if not edited:
            warnings.append("⚠ CRITICAL: No edited chapter returned")
            return warnings

        # Word count verification (info only, not a warning)
        # Copy editing focuses on correctness, not hitting exact word counts
        orig_words = len(original.split())
        edit_words = len(edited.split())
        # change_pct calculated but not used for warnings

        # Paragraph structure verification
        orig_paras = original.count('\n\n')
        edit_paras = edited.count('\n\n')
        para_change_pct = abs(edit_paras - orig_paras) / orig_paras * 100 if orig_paras > 0 else 0

        if para_change_pct > 10:
            warnings.append(f"⚠ Paragraph structure changed by {para_change_pct:.1f}%")

        # Dialogue preservation
        orig_quotes = original.count('"')
        edit_quotes = edited.count('"')

        if orig_quotes != edit_quotes:
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

        # Pronoun consistency check from result
        if result.get('pronoun_consistency', {}).get('potential_concerns'):
            for concern in result['pronoun_consistency']['potential_concerns']:
                warnings.append(f"⚠ Pronoun concern: {concern}")

        # Review flags from LLM
        if result.get('review_flags'):
            for flag in result['review_flags']:
                warnings.append(f"⚠ LLM flagged: {flag}")

        return warnings

    def _show_edit_preview(
        self,
        chapter_num: int,
        original: str,
        result: Dict[str, Any],
        warnings: List[str]
    ) -> bool:
        """
        Show preview of edits and get user approval.

        Args:
            chapter_num: Chapter number
            original: Original prose
            result: Edit result
            warnings: List of warnings

        Returns:
            True if user approves, False otherwise
        """
        stats = result.get('statistics', {})
        changes = result.get('changes_made', [])
        continuity = result.get('continuity_fixes', [])

        # Create statistics table
        table = Table(title=f"Chapter {chapter_num} Edit Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Original words", str(stats.get('original_word_count', 0)))
        table.add_row("Edited words", str(stats.get('edited_word_count', 0)))
        table.add_row("Change %", f"{stats.get('word_count_change_percent', 0):.1f}%")
        table.add_row("Total fixes", str(stats.get('total_errors_fixed', 0)))
        table.add_row("Mechanical errors", str(stats.get('mechanical_errors', 0)))
        table.add_row("Continuity errors", str(stats.get('continuity_errors', 0)))
        table.add_row("Clarity improvements", str(stats.get('clarity_improvements', 0)))

        console.print(table)

        # Show changes
        if changes:
            console.print("\n[cyan]Changes Made:[/cyan]")
            for change in changes[:10]:  # Show first 10
                console.print(f"  • {change}")
            if len(changes) > 10:
                console.print(f"  ... and {len(changes) - 10} more")

        # Show continuity fixes
        if continuity:
            console.print("\n[yellow]Continuity Fixes:[/yellow]")
            for fix in continuity:
                console.print(f"  • {fix}")

        # Show warnings
        if warnings:
            console.print("\n[red]⚠ Warnings:[/red]")
            for warning in warnings:
                console.print(f"  {warning}")

        # Get approval
        console.print()
        response = input("Apply these edits? [Y/n]: ").strip().lower()
        return response != 'n'

    def _save_checkpoint(self, chapter_num: int, result: Dict[str, Any], backup_dir: Path):
        """
        Save checkpoint after each chapter for resume capability.

        Args:
            chapter_num: Chapter number just completed
            result: Edit result
            backup_dir: Backup directory
        """
        checkpoint_file = backup_dir / 'checkpoint.json'
        checkpoint = {
            'last_chapter_edited': chapter_num,
            'chapters_completed': list(self.edited_chapters.keys()),
            'timestamp': datetime.now().isoformat()
        }

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)
