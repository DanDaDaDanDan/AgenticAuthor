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


console = Console()


class CopyEditor:
    """Professional copy editing pass with full accumulated context.

    Edits prose files (chapters/chapter-XX.md) sequentially, passing ALL
    previously edited chapters as context for maximum consistency.

    Does NOT edit: premise.md, treatment.md, or chapters.yaml
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

        # Create timestamped backup directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.project.path / '.agentic' / 'backups' / f'copy_edit_{timestamp}'
        backup_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[cyan]═══ Copy Editing Pass ═══[/cyan]")
        console.print(f"Chapters: {len(chapters)}")
        console.print(f"Model: {self.model}")
        console.print(f"Backup: {backup_dir.relative_to(self.project.path)}\n")

        edited_count = 0
        skipped_count = 0

        for i, chapter_num in enumerate(chapters, 1):
            console.print(f"\n[cyan]═══ Chapter {chapter_num}/{len(chapters)} ═══[/cyan]")

            # Get original prose
            original = self.project.get_chapter(chapter_num)

            # Backup original
            backup_file = backup_dir / f'chapter-{chapter_num:02d}.original.md'
            backup_file.write_text(original, encoding='utf-8')

            # Build full context with ALL previously edited chapters
            context = self._build_full_context(chapter_num)

            # Copy edit this chapter
            result = await self._copy_edit_chapter(
                chapter_num=chapter_num,
                chapter_text=original,
                context=context
            )

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

            # Show success
            stats = result['statistics']
            console.print(f"[green]✓ Chapter {chapter_num} edited[/green]")
            console.print(f"  {stats['total_errors_fixed']} total fixes")
            console.print(f"  {stats['word_count_change_percent']:.1f}% word count change")

            edited_count += 1

        # Summary
        console.print(f"\n[green]═══ Copy Editing Complete ═══[/green]")
        console.print(f"Edited: {edited_count}/{len(chapters)} chapters")
        if skipped_count > 0:
            console.print(f"Skipped: {skipped_count} chapters")
        console.print(f"Backup: {backup_dir.relative_to(self.project.path)}")

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

        # Get all chapter numbers
        all_chapters = self.project.list_chapters()
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
        # Build comprehensive prompt
        prompt = self._build_copy_edit_prompt(chapter_num, chapter_text, context)

        # Call LLM with low temperature for precision
        result = await self.client.json_completion(
            model=self.model,
            prompt=prompt,
            temperature=0.3,  # Low temp for precision and consistency
            display_label=f"Copy editing chapter {chapter_num}",
            min_response_tokens=8000  # Full chapter + detailed changes
        )

        return result

    def _build_copy_edit_prompt(
        self,
        chapter_num: int,
        chapter_text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Build comprehensive copy editing prompt with full context.

        Args:
            chapter_num: Chapter number being edited
            chapter_text: Current chapter prose
            context: Full context dict

        Returns:
            Complete prompt string
        """
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

        # Extract character info from chapters.yaml for easy reference
        characters_info = ""
        chapters_yaml = context['chapters_yaml']
        if chapters_yaml and 'characters' in chapters_yaml:
            chars = chapters_yaml['characters']
            char_list = []
            for char in chars:
                name = char.get('name', 'Unknown')
                role = char.get('role', '')
                char_list.append(f"- {name} ({role})")
            characters_info = "\n".join(char_list)

        # Serialize chapters.yaml for context
        import yaml
        chapters_yaml_str = yaml.dump(chapters_yaml, sort_keys=False, allow_unicode=True)

        return f"""You are a professional copy editor performing a final editing pass on a novel.

This is CHAPTER {chapter_num} of {context['total_chapters']}.

═══════════════════════════════════════════════════════════════
COPY EDITING SCOPE - CRITICAL GUIDELINES
═══════════════════════════════════════════════════════════════

✓ YOU MUST FIX:
  • Grammar errors (subject-verb agreement, tense consistency, etc.)
  • Spelling mistakes and typos
  • Punctuation errors (commas, semicolons, dialogue formatting)
  • Inconsistent character details across chapters
    - Names, physical descriptions, ages
    - Pronoun consistency (especially with unisex names!)
    - Character voice and speech patterns
  • Timeline contradictions with other chapters
  • Unclear or ambiguous sentences that confuse readers
  • Inconsistent terminology or proper nouns
  • Dialogue formatting issues
  • Awkward or confusing sentence structures
  • Factual continuity errors with other chapters

✗ YOU MUST NOT CHANGE:
  • Plot events or story structure
  • Character personalities, motivations, or arcs
  • Dialogue CONTENT (only fix formatting/grammar)
  • Author's narrative voice or stylistic choices
  • Scene order, pacing, or dramatic beats
  • Creative choices that aren't actual errors

═══════════════════════════════════════════════════════════════
CRITICAL: PRONOUN CONSISTENCY
═══════════════════════════════════════════════════════════════

Pay special attention to character pronouns:
- If a character has a unisex name (Alex, Jordan, Sam, etc.), verify pronouns match other chapters
- Check for accidental pronoun switches within a chapter
- Ensure "they" is used consistently if character is non-binary
- Flag any ambiguous pronoun usage that could confuse readers

Example issues to catch:
❌ "Alex walked in. She looked around. He sat down." (inconsistent)
✓ "Alex walked in. He looked around. He sat down." (consistent)

❌ "Sam and Jordan talked. She agreed with him." (ambiguous - who is she/him?)
✓ "Sam and Jordan talked. Sam agreed with Jordan." (clear)

═══════════════════════════════════════════════════════════════
STORY STRUCTURE (chapters.yaml - self-contained reference)
═══════════════════════════════════════════════════════════════

```yaml
{chapters_yaml_str}
```

This contains:
- metadata: genre, tone, themes, pacing, narrative style
- characters: full profiles, backgrounds, motivations, arcs, relationships
- world: setting, locations, systems, atmosphere
- chapters: detailed outlines for all chapters

Use this for:
- Character consistency (names, descriptions, pronouns, relationships)
- World-building details
- Timeline and plot progression
- Thematic consistency

═══════════════════════════════════════════════════════════════
EDITED CHAPTERS (perfect versions for consistency reference)
═══════════════════════════════════════════════════════════════

{edited_chapters_text if edited_chapters_text else "No chapters edited yet - this is the first chapter."}

═══════════════════════════════════════════════════════════════
REMAINING CHAPTERS (original versions for forward reference)
═══════════════════════════════════════════════════════════════

{remaining_chapters_text if remaining_chapters_text else "No remaining chapters - this is the last chapter."}

═══════════════════════════════════════════════════════════════
CURRENT CHAPTER PROSE TO EDIT (Chapter {chapter_num})
═══════════════════════════════════════════════════════════════

{current_chapter_text}

═══════════════════════════════════════════════════════════════
EDITING PROCESS
═══════════════════════════════════════════════════════════════

1. Read current chapter carefully
2. Cross-reference with previous edited chapters for:
   - Character consistency (names, descriptions, pronouns)
   - Timeline continuity
   - Terminology consistency
   - Character voice patterns
3. Fix all mechanical errors (grammar, spelling, punctuation)
4. Clarify confusing or ambiguous sentences
5. Ensure dialogue formatting is correct and consistent
6. Verify pronoun usage is consistent and unambiguous
7. Maintain the author's voice throughout

EDITING EXAMPLES:

GOOD EDITS (these are appropriate):
Before: "Sarah walked in the room, her eyes scanning the crowed."
After: "Sarah walked into the room, her eyes scanning the crowd."
Why: Fixed preposition and spelling error

Before: He said "I don't know."
After: He said, "I don't know."
Why: Added comma before dialogue (standard formatting)

Before: "Alex grabbed his coat. She ran out the door."
After: "Alex grabbed his coat. He ran out the door."
Why: Fixed pronoun inconsistency (Alex is male based on previous chapters)

Before: "The detective examined the clues. They were confusing."
After: "The detective examined the clues. The evidence was confusing."
Why: Clarified ambiguous "they" - could mean detective or clues

BAD EDITS (don't do these):
Before: "Sarah walked into the room."
After: "Sarah strode confidently into the spacious room."
Why WRONG: Added details and changed author's voice

Before: "He was angry."
After: "He was furious."
Why WRONG: Changed emotional intensity without author's intent

Before: "It was raining."
After: "It was a dark and stormy night."
Why WRONG: Embellished beyond fixing an error

═══════════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

Return JSON with this exact structure:

{{
  "edited_chapter": "Complete edited chapter text with all fixes applied. Include the full chapter prose.",

  "changes_made": [
    "List every category of change made, with counts",
    "Example: Fixed 7 spelling errors",
    "Example: Corrected 12 dialogue punctuation errors",
    "Example: Fixed pronoun inconsistency in paragraph 5 (changed 'she' to 'he' to match chapter 2)",
    "Example: Clarified ambiguous 'they' in paragraph 8",
    "Example: Changed 'grey' to 'gray' (3 instances) for consistency with previous chapters"
  ],

  "continuity_fixes": [
    "List any continuity errors found and fixed",
    "Example: Chapter 2 established Alex uses he/him pronouns - fixed 2 instances of 'she' in this chapter",
    "Example: Previous chapter showed character with injured left leg - fixed reference to 'right leg' in paragraph 10",
    "Example: Character's eye color was blue in chapter 3 - fixed 'green eyes' reference in paragraph 15"
  ],

  "pronoun_consistency": {{
    "issues_found": 0,
    "issues_fixed": [
      "Specific pronoun fixes made",
      "Example: Alex - fixed she→he in paragraph 5",
      "Example: Sam - clarified ambiguous 'they' in paragraph 12"
    ],
    "potential_concerns": [
      "Any remaining pronoun usage that might be ambiguous",
      "Example: 'Jordan and Sam talked. They agreed.' - 'they' could mean both or just one"
    ]
  }},

  "statistics": {{
    "original_word_count": {len(chapter_text.split())},
    "edited_word_count": 0,
    "word_count_change_percent": 0.0,
    "total_errors_fixed": 0,
    "mechanical_errors": 0,
    "continuity_errors": 0,
    "clarity_improvements": 0
  }},

  "character_tracking": {{
    "characters_in_this_chapter": ["list all characters who appear"],
    "new_character_details": [
      "Any new details about characters revealed this chapter",
      "Example: Alex's last name revealed as Chen",
      "Example: Sarah's age mentioned as 28"
    ]
  }},

  "review_flags": [
    "Flag anything that needs human review",
    "Example: Possible plot inconsistency with chapter 2 - please verify timeline",
    "Example: Character pronoun unclear - is Morgan male or female?",
    "Example: Large clarification in paragraph 12 - please verify maintains author's intent"
  ]
}}

REMEMBER:
- This is copy editing the PROSE ONLY, NOT creative rewriting
- You are NOT editing premise.md, treatment.md, or chapters.yaml - those are read-only reference
- Preserve the author's voice and creative choices
- Fix errors and ensure consistency
- When in doubt about a creative choice vs an error, flag it for review
- Pay special attention to pronoun consistency across all chapters"""

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
