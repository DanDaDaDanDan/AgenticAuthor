"""
Word count assignment for chapters based on content and book length.

This module provides intelligent word count target assignment for chapters using LLM analysis.
"""

from typing import Dict, List, Any, Optional
import yaml
from pathlib import Path

from models import Project
from api.client import APIClient


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

    def __init__(self, client: APIClient, project: Project, model: str):
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
        Assign word count targets to all chapters.

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

        # Determine target book length
        book_length_category, target_range = self._get_target_length(metadata)

        # Use LLM to assign word counts
        new_targets = await self._analyze_and_assign(chapters, book_length_category, target_range)

        # Track changes
        changes = []
        for i, chapter in enumerate(chapters):
            ch_num = chapter.get('number', i + 1)
            old_target = chapter.get('word_count_target', 0)
            new_target = new_targets.get(ch_num, 0)

            if old_target != new_target:
                changes.append((ch_num, old_target, new_target))

            chapter['word_count_target'] = new_target

        # Update chapters in original data structure
        chapters_data['chapters'] = chapters

        # Save updated chapters.yaml
        with open(self.project.chapters_file, 'w', encoding='utf-8') as f:
            yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        total_target = sum(new_targets.values())

        return {
            'chapters': chapters,
            'total_target': total_target,
            'book_length': book_length_category,
            'target_range': target_range,
            'changes': changes
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

        # Call LLM
        response = await self.client.generate_text(
            model=self.model,
            prompt=prompt,
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=4000
        )

        # Parse response
        word_counts = self._parse_response(response, chapters)

        return word_counts

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

OUTPUT FORMAT (JSON only, no explanation):
{{
  "word_counts": {{
    1: 3000,
    2: 2500,
    3: 4000,
    ...
  }},
  "total": 45000,
  "reasoning": "Brief explanation of your distribution strategy"
}}"""

        return prompt

    def _parse_response(
        self,
        response: str,
        chapters: List[Dict[str, Any]]
    ) -> Dict[int, int]:
        """
        Parse LLM response to extract word count assignments.

        Args:
            response: LLM response text
            chapters: Original chapters list for validation

        Returns:
            Dictionary mapping chapter_number -> word_count_target
        """
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            # Fallback: assign equal word counts
            return self._fallback_equal_distribution(chapters)

        try:
            data = json.loads(json_match.group())
            word_counts_raw = data.get('word_counts', {})

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

        except json.JSONDecodeError:
            # Fallback: assign equal word counts
            return self._fallback_equal_distribution(chapters)

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
