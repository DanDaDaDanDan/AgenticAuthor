"""
Centralized calculation of story depth (words per scene) based on form and pacing.

This module provides the core architecture for determining how many scenes a story needs
and how deeply each scene should be developed based on:
- Form (novella, novel, epic) - determines COMPLEXITY (scene count)
- Pacing (fast, moderate, slow) - determines DEPTH (words per scene)

These are independent axes that combine to produce the target word count.
"""

from typing import Dict, Tuple, Optional


class DepthCalculator:
    """Calculate story structure parameters based on form and pacing."""

    # Form boundaries (word counts)
    FORM_RANGES = {
        'flash_fiction': (300, 1500),
        'short_story': (1500, 7500),
        'novelette': (7500, 20000),
        'novella': (20000, 50000),
        'novel': (50000, 110000),
        'epic': (110000, 200000),
        'series': (200000, 500000)
    }

    # Base words per scene by form and pacing
    # Format: {form: {pacing: (min_ws, max_ws, typical_ws)}}
    # Updated 2025-10: Increased ~35% to align with professional scene structure (1,200-2,000w per scene)
    WORDS_PER_SCENE = {
        'flash_fiction': {
            'fast': (270, 400, 340),          # +35% from (200, 300, 250)
            'moderate': (340, 540, 440),      # +35% from (250, 400, 325)
            'slow': (470, 675, 575)           # +35% from (350, 500, 425)
        },
        'short_story': {
            'fast': (540, 800, 675),          # +35% from (400, 600, 500)
            'moderate': (675, 1010, 845),     # +35% from (500, 750, 625)
            'slow': (875, 1215, 1045)         # +35% from (650, 900, 775)
        },
        'novelette': {
            'fast': (740, 1010, 875),         # +35% from (550, 750, 650)
            'moderate': (875, 1150, 1010),    # +35% from (650, 850, 750)
            'slow': (1080, 1350, 1215)        # +35% from (800, 1000, 900)
        },
        'novella': {
            'fast': (810, 1150, 950),         # +35% from (600, 850, 700)
            'moderate': (1010, 1285, 1150),   # +35% from (750, 950, 850)
            'slow': (1215, 1550, 1350)        # +35% from (900, 1150, 1000)
        },
        'novel': {
            'fast': (900, 1300, 1100),        # +37% from (650, 950, 800)
            'moderate': (1100, 1600, 1300),   # +37% from (800, 1100, 950)
            'slow': (1400, 2000, 1600)        # +33% from (1000, 1400, 1200)
        },
        'epic': {
            'fast': (950, 1420, 1180),        # +35% from (700, 1050, 875)
            'moderate': (1215, 1620, 1420),   # +35% from (900, 1200, 1050)
            'slow': (1485, 2160, 1825)        # +35% from (1100, 1600, 1350)
        }
    }

    # Target words per chapter by form (affects chapter count)
    CHAPTER_LENGTH_TARGETS = {
        'flash_fiction': 500,    # Very short chapters or sections
        'short_story': 1500,     # Few breaks
        'novelette': 3500,       # Moderate chapters
        'novella': 4500,         # Longer chapters
        'novel': 4000,           # Standard novel chapters
        'epic': 3500,            # More frequent breaks for epic length
        'series': 3500
    }

    # Scene variation by act (for novels/epics with three-act structure)
    # More scenes in Act I for setup, fewer in Act III for focused climax
    ACT_SCENE_MULTIPLIERS = {
        'novella': {
            'act1': 1.0,  # Uniform across acts
            'act2': 1.0,
            'act3': 1.0
        },
        'novel': {
            'act1': 1.3,  # More scenes in setup (world-building, character intro)
            'act2': 1.0,  # Standard scenes in rising action
            'act3': 0.7   # Fewer scenes in climax (focused on main conflict)
        },
        'epic': {
            'act1': 1.4,  # Many scenes (complex world, multiple threads)
            'act2': 1.0,  # Standard
            'act3': 0.6   # Very focused climax
        }
    }

    # Words-per-scene variation by act (CRITICAL for climax depth)
    # Climaxes need DEPTH even with fewer scenes - this multiplies base_ws
    ACT_WS_MULTIPLIERS = {
        'novella': {
            'act1': 1.0,  # Uniform depth
            'act2': 1.0,
            'act3': 1.0
        },
        'novel': {
            'act1': 0.95,  # Slightly more efficient (many scenes to cover)
            'act2': 1.00,  # Standard depth
            'act3': 1.35   # Much deeper (emotional intensity, detail, pacing)
        },
        'epic': {
            'act1': 0.93,  # Very efficient (massive world-building to cover)
            'act2': 1.00,  # Standard
            'act3': 1.40   # Very deep climax (multiple threads converging)
        }
    }

    # Default word count targets by form (midpoints of ranges)
    # These represent typical/recommended lengths for each form
    FORM_DEFAULTS = {
        'flash_fiction': 900,      # Midpoint of 300-1,500
        'short_story': 4500,       # Midpoint of 1,500-7,500
        'novelette': 13750,        # Midpoint of 7,500-20,000
        'novella': 35000,          # Midpoint of 20,000-50,000
        'novel': 80000,            # Midpoint of 50,000-110,000 (typical, not minimum)
        'epic': 155000,            # Midpoint of 110,000-200,000
        'series': 275000           # Midpoint of 200,000-500,000
    }

    # Genre modifiers (percentage adjustments to base word count)
    # Based on publishing industry standards and genre expectations
    GENRE_MODIFIERS = {
        'fantasy': 1.15,              # +15% for worldbuilding
        'science-fiction': 1.15,      # +15% for worldbuilding
        'mystery': 0.95,              # -5% for tight pacing
        'horror': 0.92,               # -8% for tension/pace
        'romance': 1.00,              # baseline
        'literary-fiction': 1.10,     # +10% for deeper prose
        'historical-fiction': 1.08,   # +8% for period detail
        'contemporary-fiction': 1.00, # baseline
        'young-adult': 0.85,          # -15% (YA is shorter)
        'urban-fantasy': 1.05,        # +5% (less worldbuilding than epic fantasy)
        'romantasy': 1.12,            # +12% (romance + fantasy elements)
        'thriller': 0.95,             # -5% for tight pacing
        'general': 1.00               # baseline for unspecified genre
    }

    @classmethod
    def get_default_word_count(cls, length_scope: str, genre: Optional[str] = None) -> int:
        """
        Calculate intelligent default word count based on length_scope and genre.

        Uses form midpoints adjusted by genre-specific modifiers to provide
        realistic targets aligned with publishing industry standards.

        Args:
            length_scope: Story form (novel, novella, epic, etc.)
            genre: Optional genre for modifier (e.g., 'fantasy', 'mystery')

        Returns:
            Recommended word count target

        Examples:
            >>> get_default_word_count('novel', 'fantasy')
            92000  # 80,000 × 1.15
            >>> get_default_word_count('novel', 'mystery')
            76000  # 80,000 × 0.95
            >>> get_default_word_count('novella', None)
            35000  # Baseline midpoint
        """
        # Get base word count for form
        base = cls.FORM_DEFAULTS.get(length_scope, cls.FORM_DEFAULTS['novel'])

        # Apply genre modifier if provided
        if genre:
            # Normalize genre (handle variations like 'mystery-thriller' → 'mystery')
            genre_lower = genre.lower().replace('_', '-')
            modifier = cls.GENRE_MODIFIERS.get(genre_lower, 1.0)

            # Check partial matches (e.g., 'mystery-thriller' matches 'mystery')
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

        At boundary values (e.g., 50000), prefers the larger form (novel over novella).

        Args:
            target_words: Target total word count

        Returns:
            Form name (e.g., 'novel', 'novella')
        """
        # Check ranges in reverse order to prefer larger forms at boundaries
        for form in ['series', 'epic', 'novel', 'novella', 'novelette', 'short_story', 'flash_fiction']:
            min_words, max_words = cls.FORM_RANGES[form]
            if min_words <= target_words <= max_words:
                return form

        # Fallback based on proximity
        if target_words < 20000:
            return 'novella'
        elif target_words < 110000:
            return 'novel'
        else:
            return 'epic'

    @classmethod
    def get_base_words_per_scene(cls, form: str, pacing: str) -> int:
        """
        Get typical words per scene for given form and pacing (baseline, no act adjustment).

        Args:
            form: Story form (novella, novel, epic)
            pacing: Pacing taxonomy value (fast, moderate, slow)

        Returns:
            Typical words per scene (integer)
        """
        # Normalize pacing
        pacing = pacing.lower()
        if pacing not in ['fast', 'moderate', 'slow']:
            pacing = 'moderate'  # Default

        # Get typical value from ranges
        if form in cls.WORDS_PER_SCENE and pacing in cls.WORDS_PER_SCENE[form]:
            min_ws, max_ws, typical_ws = cls.WORDS_PER_SCENE[form][pacing]
            return typical_ws

        # Fallback (updated for scene-based system)
        return 1100

    @classmethod
    def get_act_words_per_scene(cls, form: str, pacing: str, act: str) -> int:
        """
        Get words per scene for specific act (includes act-based depth multiplier).

        Args:
            form: Story form (novella, novel, epic)
            pacing: Pacing taxonomy value (fast, moderate, slow)
            act: Act identifier ('act1', 'act2', 'act3')

        Returns:
            Act-adjusted words per scene (integer)
        """
        base_ws = cls.get_base_words_per_scene(form, pacing)

        # Get act multiplier
        ws_multipliers = cls.ACT_WS_MULTIPLIERS.get(form, cls.ACT_WS_MULTIPLIERS.get('novel', {}))
        multiplier = ws_multipliers.get(act, 1.0)

        return int(base_ws * multiplier)

    @classmethod
    def get_words_per_scene_range(cls, form: str, pacing: str) -> Tuple[int, int, int]:
        """
        Get full range for words per scene (min, max, typical).

        Args:
            form: Story form
            pacing: Pacing taxonomy value

        Returns:
            Tuple of (min_ws, max_ws, typical_ws)
        """
        pacing = pacing.lower()
        if pacing not in ['fast', 'moderate', 'slow']:
            pacing = 'moderate'

        if form in cls.WORDS_PER_SCENE and pacing in cls.WORDS_PER_SCENE[form]:
            return cls.WORDS_PER_SCENE[form][pacing]

        # Fallback (updated for scene-based system)
        return (950, 1350, 1150)

    @classmethod
    def get_act_for_chapter(cls, chapter_number: int, total_chapters: int) -> str:
        """
        Determine which act a chapter belongs to based on position.

        Args:
            chapter_number: Chapter number (1-indexed)
            total_chapters: Total number of chapters

        Returns:
            Act identifier ('act1', 'act2', 'act3')
        """
        # For very small chapter counts, use simple distribution
        if total_chapters <= 3:
            if chapter_number == 1:
                return 'act1'
            elif chapter_number == total_chapters:
                return 'act3'
            else:
                return 'act2'

        # For larger counts, use percentage-based boundaries
        # Ensure at least 1 chapter in Act I and Act III
        act_1_end = max(1, int(total_chapters * 0.25))
        act_2_end = min(total_chapters - 1, int(total_chapters * 0.75))

        if chapter_number <= act_1_end:
            return 'act1'
        elif chapter_number <= act_2_end:
            return 'act2'
        else:
            return 'act3'

    @classmethod
    def calculate_structure(
        cls,
        target_words: int,
        pacing: str = 'moderate',
        form_override: Optional[str] = None,
        length_scope: Optional[str] = None
    ) -> Dict:
        """
        Calculate complete story structure parameters.

        Args:
            target_words: Target total word count
            pacing: Pacing taxonomy value (fast, moderate, slow)
            form_override: Optional explicit form (overrides detection)
            length_scope: Optional taxonomy length_scope (preferred over detection)

        Returns:
            Dict with:
                - form: Detected/specified form
                - base_ws: Typical words per scene (Act II baseline)
                - ws_range: (min, max, typical) words per scene
                - total_scenes: Calculated number of scenes needed
                - chapter_count: Recommended number of chapters
                - avg_scenes_per_chapter: Average scenes per chapter
                - chapter_length_target: Target words per chapter
                - act_event_multipliers: Event count multipliers by act
                - act_ws_multipliers: Words-per-event multipliers by act
        """
        # Determine form (priority: form_override > length_scope > detection)
        if form_override:
            form = form_override
        elif length_scope and length_scope in cls.FORM_RANGES:
            form = length_scope
        else:
            form = cls.detect_form(target_words)

        # Get words per scene
        base_ws = cls.get_base_words_per_scene(form, pacing)
        ws_range = cls.get_words_per_scene_range(form, pacing)

        # Calculate total scenes needed
        total_scenes = int(target_words / base_ws)

        # Calculate chapter count
        chapter_length_target = cls.CHAPTER_LENGTH_TARGETS.get(form, 4000)
        chapter_count = max(
            1,  # Minimum 1 chapter
            int(target_words / chapter_length_target)
        )

        # Apply minimums by form
        if form == 'novella':
            chapter_count = max(5, chapter_count)
        elif form == 'novel':
            chapter_count = max(15, chapter_count)
        elif form == 'epic':
            chapter_count = max(30, chapter_count)

        # Calculate average scenes per chapter
        avg_scenes_per_chapter = total_scenes / chapter_count if chapter_count > 0 else total_scenes

        # Get act multipliers for event distribution and depth
        act_event_multipliers = cls.ACT_SCENE_MULTIPLIERS.get(form, cls.ACT_SCENE_MULTIPLIERS['novel'])
        act_ws_multipliers = cls.ACT_WS_MULTIPLIERS.get(form, cls.ACT_WS_MULTIPLIERS['novel'])

        return {
            'form': form,
            'base_ws': base_ws,  # Act II baseline
            'ws_range': ws_range,
            'total_scenes': total_scenes,
            'chapter_count': chapter_count,
            'avg_scenes_per_chapter': round(avg_scenes_per_chapter, 1),
            'chapter_length_target': chapter_length_target,
            'act_scene_multipliers': act_event_multipliers,
            'act_ws_multipliers': act_ws_multipliers,
            'pacing': pacing  # Include for downstream use
        }

    @classmethod
    def calculate_chapter_scenes(
        cls,
        chapter_number: int,
        total_chapters: int,
        avg_scenes: float,
        form: str
    ) -> int:
        """
        Calculate scene count for a specific chapter based on act position.

        Args:
            chapter_number: Chapter number (1-indexed)
            total_chapters: Total number of chapters
            avg_scenes: Average scenes per chapter
            form: Story form

        Returns:
            Number of scenes for this chapter
        """
        # Determine act
        act = cls.get_act_for_chapter(chapter_number, total_chapters)

        # Get multiplier
        multipliers = cls.ACT_SCENE_MULTIPLIERS.get(form, cls.ACT_SCENE_MULTIPLIERS['novel'])
        multiplier = multipliers[act]

        # Calculate scenes
        scenes = int(avg_scenes * multiplier)

        # Ensure minimum (2-4 scenes per chapter)
        return max(2, min(4, scenes))

    @classmethod
    def calculate_chapter_word_target(
        cls,
        chapter_number: int,
        total_chapters: int,
        scene_count: int,
        form: str,
        pacing: str
    ) -> int:
        """
        Calculate word count target for a chapter using act-aware depth.

        Args:
            chapter_number: Chapter number (1-indexed)
            total_chapters: Total number of chapters
            scene_count: Number of scenes in this chapter
            form: Story form
            pacing: Pacing taxonomy value

        Returns:
            Word count target for this chapter
        """
        # Determine act
        act = cls.get_act_for_chapter(chapter_number, total_chapters)

        # Get act-aware words per scene
        act_ws = cls.get_act_words_per_scene(form, pacing, act)

        # Calculate target
        return scene_count * act_ws

    @classmethod
    def distribute_scenes_across_chapters(
        cls,
        total_scenes: int,
        chapter_count: int,
        form: str
    ) -> list:
        """
        Distribute scenes across all chapters based on act structure.

        Each chapter is clamped to 2-4 scenes for professional structure.
        If total_scenes cannot be distributed within this constraint,
        the last chapter may exceed the clamp.

        Args:
            total_scenes: Total scenes to distribute
            chapter_count: Number of chapters
            form: Story form

        Returns:
            List of scene counts per chapter

        Raises:
            ValueError: If total_scenes < chapter_count (impossible - need at least 1 scene per chapter)
        """
        # Validate input
        if total_scenes < chapter_count:
            raise ValueError(
                f"Cannot distribute {total_scenes} scenes across {chapter_count} chapters. "
                f"Need at least 1 scene per chapter."
            )

        # Warn if outside reasonable clamp range (2-4 scenes per chapter)
        min_clamped = chapter_count * 2
        max_clamped = chapter_count * 4
        if total_scenes < min_clamped or total_scenes > max_clamped:
            from ..utils.logging import get_logger
            logger = get_logger()
            logger.warning(
                f"Scene distribution outside clamp range: {total_scenes} scenes for {chapter_count} chapters. "
                f"Recommended range: {min_clamped}-{max_clamped} (2-4 scenes/chapter). "
                f"Some chapters may violate 2-4 scene clamp."
            )

        avg_scenes = total_scenes / chapter_count

        # Calculate initial distribution
        distribution = []
        for chapter_num in range(1, chapter_count + 1):
            scenes = cls.calculate_chapter_scenes(
                chapter_num, chapter_count, avg_scenes, form
            )
            distribution.append(scenes)

        # Normalize to match total_scenes exactly while respecting 2-4 scene clamp
        current_total = sum(distribution)
        if current_total != total_scenes:
            diff = total_scenes - current_total

            if diff > 0:
                # Need to add scenes - distribute across chapters below max (4)
                while diff > 0:
                    added = False
                    for i in range(len(distribution)):
                        if distribution[i] < 4 and diff > 0:
                            distribution[i] += 1
                            diff -= 1
                            added = True
                    # If we couldn't add any (all at max), break to avoid infinite loop
                    if not added:
                        # Fall back to adding to last chapter even if it exceeds clamp
                        # This should be rare - only when (total_scenes > chapter_count * 4)
                        distribution[-1] += diff
                        break
            else:
                # Need to remove scenes - take from chapters above min (2)
                diff = abs(diff)
                while diff > 0:
                    removed = False
                    for i in range(len(distribution) - 1, -1, -1):  # Start from end
                        if distribution[i] > 2 and diff > 0:
                            distribution[i] -= 1
                            diff -= 1
                            removed = True
                    # If we couldn't remove any (all at min), break to avoid infinite loop
                    if not removed:
                        # Fall back: set last chapter to hold remaining deficit
                        # This should be rare - only when (total_scenes < chapter_count * 2)
                        # Ensure we don't go below 1 scene
                        distribution[-1] = max(1, distribution[-1] - diff)
                        break

        return distribution

    @classmethod
    def get_scene_depth_guidance(
        cls,
        total_scenes: int,
        word_target: int,
        form: str,
        pacing: str
    ) -> Dict:
        """
        Generate guidance for scene depth variation within a chapter.

        Args:
            total_scenes: Number of scenes in this chapter
            word_target: Target word count for chapter
            form: Story form
            pacing: Pacing taxonomy

        Returns:
            Dict with:
                - avg_we: Average words per scene
                - setup_range: (min, max) for setup scenes
                - standard_range: (min, max) for standard scenes
                - climax_range: (min, max) for climactic scenes
                - distribution_example: Example distribution text
        """
        avg_we = word_target // total_scenes if total_scenes > 0 else word_target

        # Scene type ranges (as percentages of average)
        setup_range = (int(avg_we * 0.75), int(avg_we * 0.90))
        standard_range = (int(avg_we * 0.90), int(avg_we * 1.15))
        climax_range = (int(avg_we * 1.20), int(avg_we * 1.50))

        # Generate example distribution
        if total_scenes <= 4:
            # Few scenes - mostly standard/climax
            setup_count = 0
            climax_count = 1
            standard_count = total_scenes - climax_count
        elif total_scenes <= 7:
            # Moderate scenes
            setup_count = 1
            climax_count = 1
            standard_count = total_scenes - setup_count - climax_count
        else:
            # Many scenes
            setup_count = 2
            climax_count = 1
            standard_count = total_scenes - setup_count - climax_count

        # Calculate words
        setup_words = setup_count * setup_range[1]
        standard_words = standard_count * ((standard_range[0] + standard_range[1]) // 2)
        climax_words = climax_count * climax_range[1]

        example_text = f"""Example distribution for {total_scenes} scenes → {word_target:,} words:
- {setup_count} setup scene{"s" if setup_count != 1 else ""} @ ~{setup_range[1]}w = {setup_words:,}
- {standard_count} standard scene{"s" if standard_count != 1 else ""} @ ~{(standard_range[0] + standard_range[1]) // 2}w = {standard_words:,}
- {climax_count} climax scene{"s" if climax_count != 1 else ""} @ ~{climax_range[1]}w = {climax_words:,}
Total: {setup_words + standard_words + climax_words:,} words"""

        return {
            'avg_we': avg_we,
            'setup_range': setup_range,
            'standard_range': standard_range,
            'climax_range': climax_range,
            'distribution_example': example_text
        }
