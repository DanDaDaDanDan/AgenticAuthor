"""
Story structure calculator: Chapter count and act distribution.

This module calculates chapter count from total word count and distributes
chapters across three-act structure with peak moment identification.

Simplified philosophy: Let LLMs determine prose quality and length naturally.
We only provide structural guidance (acts, peak moments), not word count targets.
"""

from typing import Dict, Optional


class DepthCalculator:
    """Calculate story structure with act distribution and peak roles."""

    # Form boundaries (word counts) - used for genre defaults
    FORM_RANGES = {
        'flash_fiction': (300, 1500),
        'short_story': (1500, 7500),
        'novelette': (7500, 20000),
        'novella': (20000, 50000),
        'novel': (50000, 110000),
        'epic': (110000, 200000),
        'series': (200000, 500000)
    }

    # Default word count targets by form (midpoints of ranges)
    FORM_DEFAULTS = {
        'flash_fiction': 900,
        'short_story': 4500,
        'novelette': 13750,
        'novella': 35000,
        'novel': 80000,
        'epic': 155000,
        'series': 275000
    }

    # Genre modifiers for word count
    GENRE_MODIFIERS = {
        'fantasy': 1.15,
        'science-fiction': 1.15,
        'mystery': 0.95,
        'horror': 0.92,
        'romance': 1.00,
        'literary-fiction': 1.10,
        'historical-fiction': 1.08,
        'contemporary-fiction': 1.00,
        'young-adult': 0.85,
        'urban-fantasy': 1.05,
        'romantasy': 1.12,
        'thriller': 0.95,
        'general': 1.00
    }

    # Average words per chapter (for chapter count calculation ONLY)
    # Not used as targets - just for initial chapter count estimation
    CHAPTER_LENGTH_ESTIMATES = {
        'flash_fiction': 500,
        'short_story': 1500,
        'novelette': 3500,
        'novella': 4500,
        'novel': 3500,      # ~23 chapters for 80k novel
        'epic': 3500,
        'series': 3500
    }

    @classmethod
    def get_default_word_count(cls, length_scope: str, genre: Optional[str] = None) -> int:
        """
        Calculate intelligent default word count based on length_scope and genre.

        Args:
            length_scope: Story form (novel, novella, epic, etc.)
            genre: Optional genre for modifier

        Returns:
            Recommended word count target
        """
        base = cls.FORM_DEFAULTS.get(length_scope, cls.FORM_DEFAULTS['novel'])

        if genre:
            genre_lower = genre.lower().replace('_', '-')
            modifier = cls.GENRE_MODIFIERS.get(genre_lower, 1.0)

            if modifier == 1.0 and '-' in genre_lower:
                base_genre = genre_lower.split('-')[0]
                modifier = cls.GENRE_MODIFIERS.get(base_genre, 1.0)
        else:
            modifier = 1.0

        return int(base * modifier)

    @classmethod
    def detect_form(cls, target_words: int) -> str:
        """
        Determine story form based on target word count.

        Args:
            target_words: Target total word count

        Returns:
            Form name (e.g., 'novel', 'novella')
        """
        for form in ['series', 'epic', 'novel', 'novella', 'novelette', 'short_story', 'flash_fiction']:
            min_words, max_words = cls.FORM_RANGES[form]
            if min_words <= target_words <= max_words:
                return form

        # Fallback
        if target_words < 20000:
            return 'novella'
        elif target_words < 110000:
            return 'novel'
        else:
            return 'epic'

    @classmethod
    def calculate_chapter_structure(
        cls,
        total_words: int,
        length_scope: Optional[str] = None
    ) -> Dict:
        """
        Calculate chapter count and act distribution.

        This is the main method for story structure planning.
        Returns chapter count and structural guidance (acts, peak roles).
        Does NOT assign word count targets to individual chapters.

        Args:
            total_words: Target total word count for book
            length_scope: Optional story form (auto-detected if not provided)

        Returns:
            Dict with:
                - form: Detected form (novel, novella, etc.)
                - total_words: Target total
                - chapter_count: Number of chapters
                - chapters_per_act: [act1_count, act2_count, act3_count]
                - chapter_roles: Dict mapping chapter_number -> role
                    Roles: 'inciting_setup', 'midpoint', 'crisis', 'climax',
                           'denouement', 'escalation'
        """
        # Detect or use provided form
        if length_scope:
            normalized_scope = length_scope.lower().replace(' ', '_')
            form = normalized_scope if normalized_scope in cls.FORM_RANGES else cls.detect_form(total_words)
        else:
            form = cls.detect_form(total_words)

        # Calculate chapter count (simple: total_words / average_chapter_length)
        chapter_length_estimate = cls.CHAPTER_LENGTH_ESTIMATES.get(form, 3500)
        chapter_count = max(1, round(total_words / chapter_length_estimate))

        # Distribute chapters across acts (25% / 50% / 25%)
        if chapter_count == 1:
            # Single chapter - all acts combined
            act1_chapters = 0
            act2_chapters = 1
            act3_chapters = 0
        elif chapter_count == 2:
            # Two chapters - beginning and end
            act1_chapters = 1
            act2_chapters = 0
            act3_chapters = 1
        elif chapter_count == 3:
            # Three chapters - one per act
            act1_chapters = 1
            act2_chapters = 1
            act3_chapters = 1
        else:
            # Standard distribution for 4+ chapters
            act1_chapters = max(1, int(chapter_count * 0.25))
            act3_chapters = max(1, int(chapter_count * 0.25))
            act2_chapters = chapter_count - act1_chapters - act3_chapters

        # Assign peak roles to specific chapters
        peak_roles = {}

        # Calculate peak chapter positions
        if chapter_count == 1:
            # Single chapter gets climax role (most important)
            midpoint_chapter = -1
            crisis_chapter = -1
        elif chapter_count == 2:
            # Two chapters - no midpoint or crisis
            midpoint_chapter = -1
            crisis_chapter = -1
        elif chapter_count == 3:
            # Three chapters - midpoint only (ch 2)
            midpoint_chapter = 2
            crisis_chapter = -1  # Skip crisis to avoid collision
        else:
            # Standard calculation for 4+ chapters
            midpoint_chapter = act1_chapters + (act2_chapters // 2) if act2_chapters > 0 else -1
            crisis_chapter = act1_chapters + act2_chapters - 1 if act2_chapters > 0 else -1

        # Assign roles with priority (later assignments can overwrite)
        for ch in range(1, chapter_count + 1):
            # Default to escalation
            peak_roles[ch] = 'escalation'

        # Apply specific roles (order matters - later assignments override)
        if chapter_count >= 2:
            peak_roles[chapter_count - 1] = 'denouement'  # Penultimate chapter

        peak_roles[1] = 'inciting_setup'  # First chapter

        if midpoint_chapter > 0 and midpoint_chapter <= chapter_count:
            peak_roles[midpoint_chapter] = 'midpoint'

        if crisis_chapter > 0 and crisis_chapter <= chapter_count:
            peak_roles[crisis_chapter] = 'crisis'

        peak_roles[chapter_count] = 'climax'  # Last chapter (highest priority)

        return {
            'form': form,
            'total_words': total_words,
            'chapter_count': chapter_count,
            'chapters_per_act': [act1_chapters, act2_chapters, act3_chapters],
            'chapter_roles': peak_roles
        }

    # ===== BACKWARD COMPATIBILITY METHODS =====
    # These are kept for existing code that may use the old API

    @classmethod
    def calculate_structure(
        cls,
        total_words: int,
        pacing: str,
        length_scope: Optional[str] = None
    ) -> Dict:
        """
        Calculate story structure (backward compatibility).

        Args:
            total_words: Target total word count
            pacing: Story pacing (fast, moderate, slow) - IGNORED in new system
            length_scope: Optional length scope

        Returns:
            Dict with form, chapter_count (for backward compatibility)
        """
        result = cls.calculate_chapter_structure(total_words, length_scope)

        # Return simplified format for compatibility
        return {
            'form': result['form'],
            'chapter_count': result['chapter_count']
        }

    @classmethod
    def get_act_for_chapter(cls, chapter_number: int, total_chapters: int) -> str:
        """
        Determine which act a chapter belongs to (backward compatibility).

        Args:
            chapter_number: Chapter number (1-indexed)
            total_chapters: Total number of chapters

        Returns:
            Act name: 'act1', 'act2', or 'act3'
        """
        if total_chapters <= 3:
            if chapter_number == 1:
                return 'act1'
            elif chapter_number == total_chapters:
                return 'act3'
            else:
                return 'act2'

        act_1_end = max(1, int(total_chapters * 0.25))
        act_2_end = min(total_chapters - 1, int(total_chapters * 0.75))

        if chapter_number <= act_1_end:
            return 'act1'
        elif chapter_number <= act_2_end:
            return 'act2'
        else:
            return 'act3'
