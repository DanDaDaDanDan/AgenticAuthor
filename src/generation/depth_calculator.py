"""
Centralized calculation of story depth (words per event) based on form and pacing.

This module provides the core architecture for determining how many events a story needs
and how deeply each event should be developed based on:
- Form (novella, novel, epic) - determines COMPLEXITY (event count)
- Pacing (fast, moderate, slow) - determines DEPTH (words per event)

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

    # Base words per event by form and pacing
    # Format: {form: {pacing: (min_we, max_we, typical_we)}}
    WORDS_PER_EVENT = {
        'flash_fiction': {
            'fast': (200, 300, 250),
            'moderate': (250, 400, 325),
            'slow': (350, 500, 425)
        },
        'short_story': {
            'fast': (400, 600, 500),
            'moderate': (500, 750, 625),
            'slow': (650, 900, 775)
        },
        'novelette': {
            'fast': (550, 750, 650),
            'moderate': (650, 850, 750),
            'slow': (800, 1000, 900)
        },
        'novella': {
            'fast': (600, 850, 700),
            'moderate': (750, 950, 850),
            'slow': (900, 1150, 1000)
        },
        'novel': {
            'fast': (650, 950, 800),
            'moderate': (800, 1100, 950),
            'slow': (1000, 1400, 1200)
        },
        'epic': {
            'fast': (700, 1050, 875),
            'moderate': (900, 1200, 1050),
            'slow': (1100, 1600, 1350)
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

    # Event variation by act (for novels/epics with three-act structure)
    ACT_EVENT_MULTIPLIERS = {
        'novella': {
            'act1': 1.0,  # Uniform across acts
            'act2': 1.0,
            'act3': 1.0
        },
        'novel': {
            'act1': 1.3,  # More events in setup (8 vs 6 baseline)
            'act2': 1.0,  # Standard events in rising action (6)
            'act3': 0.7   # Fewer, deeper events in climax (4)
        },
        'epic': {
            'act1': 1.4,
            'act2': 1.0,
            'act3': 0.6
        }
    }

    @classmethod
    def detect_form(cls, target_words: int) -> str:
        """
        Determine story form based on target word count.

        Args:
            target_words: Target total word count

        Returns:
            Form name (e.g., 'novel', 'novella')
        """
        for form, (min_words, max_words) in cls.FORM_RANGES.items():
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
    def get_base_words_per_event(cls, form: str, pacing: str) -> int:
        """
        Get typical words per event for given form and pacing.

        Args:
            form: Story form (novella, novel, epic)
            pacing: Pacing taxonomy value (fast, moderate, slow)

        Returns:
            Typical words per event (integer)
        """
        # Normalize pacing
        pacing = pacing.lower()
        if pacing not in ['fast', 'moderate', 'slow']:
            pacing = 'moderate'  # Default

        # Get typical value from ranges
        if form in cls.WORDS_PER_EVENT and pacing in cls.WORDS_PER_EVENT[form]:
            min_we, max_we, typical_we = cls.WORDS_PER_EVENT[form][pacing]
            return typical_we

        # Fallback
        return 800

    @classmethod
    def get_words_per_event_range(cls, form: str, pacing: str) -> Tuple[int, int, int]:
        """
        Get full range for words per event (min, max, typical).

        Args:
            form: Story form
            pacing: Pacing taxonomy value

        Returns:
            Tuple of (min_we, max_we, typical_we)
        """
        pacing = pacing.lower()
        if pacing not in ['fast', 'moderate', 'slow']:
            pacing = 'moderate'

        if form in cls.WORDS_PER_EVENT and pacing in cls.WORDS_PER_EVENT[form]:
            return cls.WORDS_PER_EVENT[form][pacing]

        # Fallback
        return (700, 1000, 850)

    @classmethod
    def calculate_structure(
        cls,
        target_words: int,
        pacing: str = 'moderate',
        form_override: Optional[str] = None
    ) -> Dict:
        """
        Calculate complete story structure parameters.

        Args:
            target_words: Target total word count
            pacing: Pacing taxonomy value (fast, moderate, slow)
            form_override: Optional explicit form (overrides detection)

        Returns:
            Dict with:
                - form: Detected/specified form
                - base_we: Typical words per event
                - we_range: (min, max, typical) words per event
                - total_events: Calculated number of events needed
                - chapter_count: Recommended number of chapters
                - avg_events_per_chapter: Average events per chapter
                - chapter_length_target: Target words per chapter
                - act_multipliers: Event count multipliers by act
        """
        # Determine form
        form = form_override if form_override else cls.detect_form(target_words)

        # Get words per event
        base_we = cls.get_base_words_per_event(form, pacing)
        we_range = cls.get_words_per_event_range(form, pacing)

        # Calculate total events needed
        total_events = int(target_words / base_we)

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

        # Calculate average events per chapter
        avg_events_per_chapter = total_events / chapter_count if chapter_count > 0 else total_events

        # Get act multipliers for event distribution
        act_multipliers = cls.ACT_EVENT_MULTIPLIERS.get(form, cls.ACT_EVENT_MULTIPLIERS['novel'])

        return {
            'form': form,
            'base_we': base_we,
            'we_range': we_range,
            'total_events': total_events,
            'chapter_count': chapter_count,
            'avg_events_per_chapter': round(avg_events_per_chapter, 1),
            'chapter_length_target': chapter_length_target,
            'act_multipliers': act_multipliers
        }

    @classmethod
    def calculate_chapter_events(
        cls,
        chapter_number: int,
        total_chapters: int,
        avg_events: float,
        form: str
    ) -> int:
        """
        Calculate event count for a specific chapter based on act position.

        Args:
            chapter_number: Chapter number (1-indexed)
            total_chapters: Total number of chapters
            avg_events: Average events per chapter
            form: Story form

        Returns:
            Number of events for this chapter
        """
        # Determine act
        act_1_end = int(total_chapters * 0.25)
        act_2_end = int(total_chapters * 0.75)

        if chapter_number <= act_1_end:
            act = 'act1'
        elif chapter_number <= act_2_end:
            act = 'act2'
        else:
            act = 'act3'

        # Get multiplier
        multipliers = cls.ACT_EVENT_MULTIPLIERS.get(form, cls.ACT_EVENT_MULTIPLIERS['novel'])
        multiplier = multipliers[act]

        # Calculate events
        events = int(avg_events * multiplier)

        # Ensure minimum
        return max(3, events)

    @classmethod
    def distribute_events_across_chapters(
        cls,
        total_events: int,
        chapter_count: int,
        form: str
    ) -> list:
        """
        Distribute events across all chapters based on act structure.

        Args:
            total_events: Total events to distribute
            chapter_count: Number of chapters
            form: Story form

        Returns:
            List of event counts per chapter
        """
        avg_events = total_events / chapter_count

        # Calculate initial distribution
        distribution = []
        for chapter_num in range(1, chapter_count + 1):
            events = cls.calculate_chapter_events(
                chapter_num, chapter_count, avg_events, form
            )
            distribution.append(events)

        # Normalize to match total_events exactly
        current_total = sum(distribution)
        if current_total != total_events:
            scale = total_events / current_total
            distribution = [max(3, int(e * scale)) for e in distribution]

            # Adjust last chapter to hit exact total
            diff = total_events - sum(distribution)
            distribution[-1] += diff

        return distribution

    @classmethod
    def get_scene_depth_guidance(
        cls,
        total_events: int,
        word_target: int,
        form: str,
        pacing: str
    ) -> Dict:
        """
        Generate guidance for scene depth variation within a chapter.

        Args:
            total_events: Number of events in this chapter
            word_target: Target word count for chapter
            form: Story form
            pacing: Pacing taxonomy

        Returns:
            Dict with:
                - avg_we: Average words per event
                - setup_range: (min, max) for setup scenes
                - standard_range: (min, max) for standard scenes
                - climax_range: (min, max) for climactic scenes
                - distribution_example: Example distribution text
        """
        avg_we = word_target // total_events if total_events > 0 else word_target

        # Scene type ranges (as percentages of average)
        setup_range = (int(avg_we * 0.75), int(avg_we * 0.90))
        standard_range = (int(avg_we * 0.90), int(avg_we * 1.15))
        climax_range = (int(avg_we * 1.20), int(avg_we * 1.50))

        # Generate example distribution
        if total_events <= 4:
            # Few events - mostly standard/climax
            setup_count = 0
            climax_count = 1
            standard_count = total_events - climax_count
        elif total_events <= 7:
            # Moderate events
            setup_count = 1
            climax_count = 1
            standard_count = total_events - setup_count - climax_count
        else:
            # Many events
            setup_count = 2
            climax_count = 1
            standard_count = total_events - setup_count - climax_count

        # Calculate words
        setup_words = setup_count * setup_range[1]
        standard_words = standard_count * ((standard_range[0] + standard_range[1]) // 2)
        climax_words = climax_count * climax_range[1]

        example_text = f"""Example distribution for {total_events} events → {word_target:,} words:
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
