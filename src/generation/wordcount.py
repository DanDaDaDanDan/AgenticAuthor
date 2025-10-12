"""
Word count assignment for chapters based on content and book length.

This module provides intelligent word count target assignment for chapters using LLM analysis.
"""

from typing import Dict, List, Any, Optional
import yaml
from pathlib import Path

from ..models import Project
from ..api import OpenRouterClient
from .depth_calculator import DepthCalculator


class WordCountAssigner:
    """Assigns word count targets to chapters based on content and desired book length."""

    # Word count ranges by length_scope taxonomy
    LENGTH_RANGES = {
        'flash_fiction': (300, 1500),
        'short_story': (1500, 7500),
        'novelette': (7500, 20000),
        'novella': (20000, 50000),
        'novel': (50000, 110000),
        'epic': (110000, 200000),
        'series': (200000, 500000)
    }

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize word count assigner.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for analysis
        """
        self.client = client
        self.project = project
        self.model = model

    async def assign_word_counts(self) -> Dict[str, Any]:
        """
        Assign word count targets to all chapters based on event counts.

        Uses the depth architecture: word_count_target = event_count × base_we
        where base_we is calculated from form + pacing.

        Returns:
            Dictionary with:
                - 'chapters': List of chapters with updated word_count_target
                - 'total_target': Total target word count
                - 'book_length': Detected book length category
                - 'changes': List of (chapter_num, old_target, new_target) tuples

        Raises:
            Exception: If chapters.yaml doesn't exist or has wrong format
        """
        # Load chapters.yaml
        if not self.project.chapters_file.exists():
            raise Exception("No chapters.yaml found. Generate chapters first with /generate chapters")

        with open(self.project.chapters_file, 'r', encoding='utf-8') as f:
            chapters_data = yaml.safe_load(f)

        if not isinstance(chapters_data, dict):
            raise Exception("chapters.yaml is in legacy format. This command requires the self-contained format (metadata, characters, world, chapters).")

        if 'chapters' not in chapters_data:
            raise Exception("No chapters found in chapters.yaml")

        metadata = chapters_data.get('metadata', {})
        chapters = chapters_data.get('chapters', [])

        if not chapters:
            raise Exception("No chapters found in chapters.yaml")

        # Get target word count and pacing from metadata
        target_word_count = metadata.get('target_word_count', 50000)
        pacing = metadata.get('pacing', 'moderate')

        # Calculate base words per event
        form = DepthCalculator.detect_form(target_word_count)
        base_we = DepthCalculator.get_base_words_per_event(form, pacing)

        print(f"\nCalculating word counts:")
        print(f"  Form: {form.replace('_', ' ').title()}")
        print(f"  Pacing: {pacing}")
        print(f"  Base words/event: {base_we}")
        print()

        # Calculate word counts based on actual event counts
        new_targets = {}
        changes = []

        for chapter in chapters:
            ch_num = chapter.get('number')
            if ch_num is None:
                continue

            # Count events in this chapter
            key_events = chapter.get('key_events', [])
            event_count = len(key_events)

            # Calculate word target: events × base_we
            new_target = event_count * base_we

            # Track changes
            old_target = chapter.get('word_count_target', 0)
            if old_target != new_target:
                changes.append((ch_num, old_target, new_target))
                print(f"  Chapter {ch_num}: {event_count} events × {base_we} w/e = {new_target:,} words (was {old_target:,})")

            # Update chapter
            chapter['word_count_target'] = new_target
            new_targets[ch_num] = new_target

        # Update chapters in original data structure
        chapters_data['chapters'] = chapters

        # Save updated chapters.yaml
        with open(self.project.chapters_file, 'w', encoding='utf-8') as f:
            yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        total_target = sum(new_targets.values())

        # Determine book length category for display
        book_length_category, target_range = self._get_target_length(metadata)

        print(f"\nTotal: {total_target:,} words across {len(chapters)} chapters")

        return {
            'chapters': chapters,
            'total_target': total_target,
            'book_length': book_length_category,
            'target_range': target_range,
            'changes': changes,
            'base_we': base_we,
            'form': form
        }

    def _get_target_length(self, metadata: Dict[str, Any]) -> tuple[str, tuple[int, int]]:
        """
        Determine target book length from metadata.

        Args:
            metadata: Metadata section from chapters.yaml

        Returns:
            Tuple of (category_name, (min_words, max_words))
        """
        # Check taxonomy for length_scope
        taxonomy = metadata.get('taxonomy', {})
        length_scope = taxonomy.get('length_scope', 'novel')  # Default to novel

        if length_scope in self.LENGTH_RANGES:
            return length_scope, self.LENGTH_RANGES[length_scope]

        # Fallback to novel
        return 'novel', self.LENGTH_RANGES['novel']

    async def _analyze_and_assign(
        self,
        chapters: List[Dict[str, Any]],
        book_length_category: str,
        target_range: tuple[int, int]
    ) -> Dict[int, int]:
        """
        Use LLM to analyze chapters and assign word counts.

        Args:
            chapters: List of chapter dictionaries
            book_length_category: Category like 'novel', 'novella', etc.
            target_range: (min, max) word count for this category

        Returns:
            Dictionary mapping chapter_number -> word_count_target
        """
        # Build prompt for LLM
        prompt = self._build_prompt(chapters, book_length_category, target_range)

        # Call LLM with json_completion (returns parsed dict)
        try:
            response_data = await self.client.json_completion(
                model=self.model,
                prompt=prompt,
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=4000
            )

            # Parse response data
            word_counts = self._parse_response(response_data, chapters)

            return word_counts

        except Exception as e:
            # If LLM fails, use fallback
            print(f"Warning: LLM word count assignment failed ({e}), using equal distribution")
            return self._fallback_equal_distribution(chapters)

    def _build_prompt(
        self,
        chapters: List[Dict[str, Any]],
        book_length_category: str,
        target_range: tuple[int, int]
    ) -> str:
        """Build LLM prompt for word count assignment."""
        min_words, max_words = target_range
        target_midpoint = (min_words + max_words) // 2

        # Build chapter summaries
        chapter_info = []
        for ch in chapters:
            ch_num = ch.get('number', '?')
            title = ch.get('title', 'Untitled')
            summary = ch.get('summary', '')
            key_events = ch.get('key_events', [])

            info = f"Chapter {ch_num}: {title}\n"
            info += f"  Summary: {summary}\n"
            if key_events:
                info += f"  Key Events: {', '.join(key_events)}\n"
            chapter_info.append(info)

        chapters_text = "\n".join(chapter_info)

        prompt = f"""You are a professional editor assigning word count targets to chapters in a {book_length_category}.

TARGET BOOK LENGTH: {min_words:,} - {max_words:,} words (aim for ~{target_midpoint:,} words total)

CHAPTERS:
{chapters_text}

TASK: Assign a word_count_target to each chapter based on:
1. Chapter complexity (more events/complexity = more words)
2. Narrative pacing (climax chapters may be longer, setup chapters shorter)
3. Story structure (opening and closing chapters have different needs)
4. Total must be within the target range above

RULES:
- Assign reasonable word counts (typical chapters: 2,000-5,000 words)
- More complex chapters with multiple key events deserve more words
- Setup chapters can be shorter (1,500-3,000)
- Climax chapters can be longer (4,000-7,000)
- The TOTAL across all chapters should be close to {target_midpoint:,} words
- Be specific and intentional with your assignments

OUTPUT FORMAT (valid JSON only, no explanation):
{{
  "word_counts": {{
    "1": 3000,
    "2": 2500,
    "3": 4000
  }},
  "total": 45000,
  "reasoning": "Brief explanation of your distribution strategy"
}}

IMPORTANT: Keys must be quoted strings. Do not include ellipsis (...) in the actual output."""

        return prompt

    def _parse_response(
        self,
        response: Dict[str, Any],
        chapters: List[Dict[str, Any]]
    ) -> Dict[int, int]:
        """
        Parse LLM response to extract word count assignments.

        Args:
            response: LLM response dict (already parsed JSON)
            chapters: Original chapters list for validation

        Returns:
            Dictionary mapping chapter_number -> word_count_target
        """
        # Response is already parsed JSON dict from json_completion
        if not isinstance(response, dict):
            return self._fallback_equal_distribution(chapters)

        word_counts_raw = response.get('word_counts', {})

        if not word_counts_raw:
            return self._fallback_equal_distribution(chapters)

        # Convert string keys to int if needed
        word_counts = {}
        for k, v in word_counts_raw.items():
            try:
                ch_num = int(k)
                word_count = int(v)
                word_counts[ch_num] = word_count
            except (ValueError, TypeError):
                continue

        # Validate we have all chapters
        chapter_numbers = [ch.get('number') for ch in chapters if 'number' in ch]
        for ch_num in chapter_numbers:
            if ch_num not in word_counts:
                # Missing assignment, use fallback
                return self._fallback_equal_distribution(chapters)

        return word_counts

    def _fallback_equal_distribution(self, chapters: List[Dict[str, Any]]) -> Dict[int, int]:
        """
        Fallback: distribute word count equally across all chapters.

        Args:
            chapters: List of chapter dictionaries

        Returns:
            Dictionary mapping chapter_number -> word_count_target
        """
        num_chapters = len(chapters)
        if num_chapters == 0:
            return {}

        # Use default novel midpoint
        total_target = 80000  # Middle of novel range
        per_chapter = total_target // num_chapters

        word_counts = {}
        for ch in chapters:
            ch_num = ch.get('number')
            if ch_num is not None:
                word_counts[ch_num] = per_chapter

        return word_counts
