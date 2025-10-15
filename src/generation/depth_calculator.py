"""
Top-down beat-driven word budgeting: Book → Acts → Chapters → Scenes → Beats.

This module implements the "Design in beats, publish in scenes" philosophy.

Word budgeting flows from top to bottom:
1. Acts get percentage splits (25% / 50% / 25%)
2. Chapters get weighted shares of act budgets (with peak multipliers)
3. Scenes get portions of chapter budgets (minus glue fraction)
4. Beats get weighted shares of scene budgets

Key concepts:
- Glue fraction: 20-30% of chapter words for transitions/exposition outside scenes
- Peak multipliers: High-leverage chapters (inciting, midpoint, crisis, climax) get more words
- Scene impacts: Set-piece (3), important (2), connective (1) affect word allocation
- Beat weights: Turn/reversal beats get 25-30% of scene words (biggest moment)
"""

from typing import Dict, Tuple, Optional, List


class DepthCalculator:
    """Calculate story structure with top-down word budgeting."""

    # Form boundaries (word counts) - kept for genre defaults
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

    # Target words per chapter by form (for calculating chapter count)
    CHAPTER_LENGTH_TARGETS = {
        'flash_fiction': 500,
        'short_story': 1500,
        'novelette': 3500,
        'novella': 4500,
        'novel': 4000,
        'epic': 3500,
        'series': 3500
    }

    # ===== TOP-DOWN BUDGETING CONSTANTS =====

    # Act percentage splits (three-act structure)
    DEFAULT_ACT_WEIGHTS = [0.25, 0.50, 0.25]  # Act I, Act II, Act III

    # Glue fraction: transitions/exposition not inside scenes
    DEFAULT_GLUE_FRACTION = 0.25  # 20-30% typical

    # Peak chapter multipliers for high-leverage moments
    PEAK_MULTIPLIERS = {
        'inciting_setup': 1.25,    # Inciting incident chapter
        'midpoint': 1.50,          # Midpoint chapter (BIGGEST multiplier)
        'crisis': 1.30,            # All-is-lost / Crisis chapter
        'climax': 1.50,            # Climax chapter
        'escalation': 1.0,         # Standard chapters
        'denouement': 0.9          # Denouement (shorter)
    }

    # Scene impact multipliers for word allocation
    SCENE_IMPACT_MULTIPLIERS = {
        1: 0.75,   # Connective scene (-25%)
        2: 1.0,    # Important scene (baseline)
        3: 1.25    # Set-piece scene (+25%)
    }

    # Beat weight patterns by beat count (percentages sum to 100)
    BEAT_WEIGHT_PATTERNS = {
        5: [15, 20, 30, 20, 15],           # 5-beat: turn gets 30%
        6: [10, 15, 20, 25, 20, 10],       # 6-beat: turn gets 25%
        7: [10, 12, 18, 25, 18, 12, 5]     # 7-beat: turn gets 25%
    }

    # Beat type labels by position
    BEAT_TYPE_TEMPLATES = {
        5: ['setup', 'obstacle', 'reversal', 'consequence', 'exit'],
        6: ['setup', 'obstacle', 'complication', 'reversal', 'consequence', 'exit'],
        7: ['setup', 'obstacle', 'complication', 'reveal', 'reversal', 'consequence', 'exit']
    }

    # Pacing anchors (percentage of total words where plot points should fall)
    PACING_ANCHORS = {
        'inciting_incident': (0.0, 0.10),    # By 10%
        'act_ii_break': (0.20, 0.28),        # 20-28%
        'midpoint': (0.48, 0.55),            # 48-55%
        'crisis': (0.72, 0.78),              # 72-78%
        'climax': (0.85, 0.95)               # 85-95%
    }

    # Typical scene counts by form (for initial estimates)
    TYPICAL_SCENES_PER_CHAPTER = {
        'flash_fiction': 1,
        'short_story': 2,
        'novelette': 3,
        'novella': 3,
        'novel': 4,
        'epic': 4,
        'series': 4
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
    def calculate_top_down_budget(
        cls,
        total_words: int,
        chapter_count: int,
        form: Optional[str] = None,
        act_weights: Optional[List[float]] = None,
        glue_fraction: float = None
    ) -> Dict:
        """
        Top-down word budgeting: Book → Acts → Chapters.

        This is the main entry point for the beat-driven architecture.

        Args:
            total_words: Target total word count for book
            chapter_count: Number of chapters
            form: Story form (novel, novella, epic) - auto-detected if not provided
            act_weights: Act percentage splits (default [0.25, 0.50, 0.25])
            glue_fraction: Fraction of chapter words for transitions (default 0.25)

        Returns:
            Dict with complete budget breakdown:
                - total_words: Total target
                - form: Detected form
                - act_weights: Act percentages used
                - act_budgets: [act1_words, act2_words, act3_words]
                - glue_fraction: Glue fraction used
                - chapter_count: Total chapters
                - chapters_per_act: [act1_count, act2_count, act3_count]
                - chapter_budgets: List of dicts per chapter with:
                    * number: Chapter number (1-indexed)
                    * role: Peak role (inciting_setup, midpoint, crisis, climax, escalation)
                    * act: Act name (Act I, Act II, Act III)
                    * words_total: Total chapter words (including glue)
                    * words_scenes: Words for scenes only (excluding glue)
                    * typical_scenes: Typical scene count for this chapter
        """
        # Defaults
        if form is None:
            form = cls.detect_form(total_words)
        if act_weights is None:
            act_weights = cls.DEFAULT_ACT_WEIGHTS
        if glue_fraction is None:
            glue_fraction = cls.DEFAULT_GLUE_FRACTION

        # Step 1: Budget acts (25% / 50% / 25%)
        act_budgets = [int(total_words * w) for w in act_weights]

        # Step 2: Determine chapters per act (roughly 25%/50%/25% split)
        act1_chapters = max(1, int(chapter_count * 0.25))
        act3_chapters = max(1, int(chapter_count * 0.25))
        act2_chapters = chapter_count - act1_chapters - act3_chapters

        # Step 3: Assign peak roles and multipliers
        peak_roles = {}
        midpoint_chapter = act1_chapters + (act2_chapters // 2)
        crisis_chapter = act1_chapters + act2_chapters - 1

        for ch in range(1, chapter_count + 1):
            if ch == 1:
                peak_roles[ch] = 'inciting_setup'
            elif ch == midpoint_chapter:
                peak_roles[ch] = 'midpoint'
            elif ch == crisis_chapter:
                peak_roles[ch] = 'crisis'
            elif ch == chapter_count:
                peak_roles[ch] = 'climax'
            elif ch == chapter_count - 1:  # Penultimate chapter
                peak_roles[ch] = 'denouement'
            else:
                peak_roles[ch] = 'escalation'

        # Step 4: Budget chapters within each act
        chapter_budgets = []

        for act_idx, (act_w, act_ch_count) in enumerate([
            (act_budgets[0], act1_chapters),
            (act_budgets[1], act2_chapters),
            (act_budgets[2], act3_chapters)
        ]):
            # Get chapters in this act
            if act_idx == 0:
                ch_range = range(1, act1_chapters + 1)
                act_name = "Act I"
            elif act_idx == 1:
                ch_range = range(act1_chapters + 1, act1_chapters + act2_chapters + 1)
                act_name = "Act II"
            else:
                ch_range = range(act1_chapters + act2_chapters + 1, chapter_count + 1)
                act_name = "Act III"

            # Calculate raw weights with peak multipliers
            raw_weights = {}
            for ch in ch_range:
                role = peak_roles[ch]
                multiplier = cls.PEAK_MULTIPLIERS.get(role, 1.0)
                raw_weights[ch] = multiplier

            total_weight = sum(raw_weights.values())

            # Normalize to act budget and split into scenes vs glue
            for ch in ch_range:
                ch_words_total = int(act_w * (raw_weights[ch] / total_weight))
                ch_words_scenes = int(ch_words_total * (1 - glue_fraction))

                # Estimate typical scene count for this chapter
                typical_scenes = cls.TYPICAL_SCENES_PER_CHAPTER.get(form, 4)

                chapter_budgets.append({
                    'number': ch,
                    'role': peak_roles[ch],
                    'act': act_name,
                    'words_total': ch_words_total,
                    'words_scenes': ch_words_scenes,
                    'typical_scenes': typical_scenes
                })

        return {
            'total_words': total_words,
            'form': form,
            'act_weights': act_weights,
            'act_budgets': act_budgets,
            'glue_fraction': glue_fraction,
            'chapter_count': chapter_count,
            'chapters_per_act': [act1_chapters, act2_chapters, act3_chapters],
            'chapter_budgets': chapter_budgets
        }

    @classmethod
    def calculate_scene_budget(
        cls,
        chapter_words: int,
        scene_count: int,
        scene_impacts: Optional[List[int]] = None
    ) -> List[int]:
        """
        Distribute chapter's scene budget across scenes using impact ratings.

        Args:
            chapter_words: Words available for scenes (after glue removed)
            scene_count: Number of scenes
            scene_impacts: Impact rating per scene (1=connective, 2=important, 3=set-piece)
                           If not provided, assumes all scenes have impact=2

        Returns:
            List of word targets per scene
        """
        if scene_impacts is None:
            # Default: all important (impact=2)
            scene_impacts = [2] * scene_count

        # Get multipliers
        raw_weights = [cls.SCENE_IMPACT_MULTIPLIERS.get(imp, 1.0) for imp in scene_impacts]
        total_weight = sum(raw_weights)

        # Distribute words
        scene_budgets = []
        for weight in raw_weights:
            scene_words = int(chapter_words * (weight / total_weight))
            scene_budgets.append(scene_words)

        return scene_budgets

    @classmethod
    def calculate_beat_budget(cls, scene_words: int, beat_count: int = 6) -> List[Dict]:
        """
        Distribute scene words across beats using weight pattern.

        Args:
            scene_words: Total words for this scene
            beat_count: Number of beats (5, 6, or 7)

        Returns:
            List of beat dicts with type, target_words
        """
        # Default to 6 if invalid
        if beat_count not in cls.BEAT_WEIGHT_PATTERNS:
            beat_count = 6

        weights = cls.BEAT_WEIGHT_PATTERNS[beat_count]
        types = cls.BEAT_TYPE_TEMPLATES[beat_count]

        beats = []
        for i, (weight, beat_type) in enumerate(zip(weights, types)):
            beat_words = int(scene_words * (weight / 100))
            beats.append({
                'type': beat_type,
                'target_words': beat_words,
                'note': ''  # To be filled by LLM
            })

        return beats

    @classmethod
    def assign_scene_impacts(cls, scene_count: int, chapter_role: str) -> List[int]:
        """
        Auto-assign scene impact ratings based on position and chapter role.

        Args:
            scene_count: Number of scenes in chapter
            chapter_role: Chapter role (inciting_setup, midpoint, crisis, climax, escalation)

        Returns:
            List of impact ratings (1=connective, 2=important, 3=set-piece)
        """
        impacts = []

        for i in range(scene_count):
            is_first = (i == 0)
            is_last = (i == scene_count - 1)

            # First/last scenes are usually connective
            if is_first or is_last:
                impacts.append(1)
            # Middle scenes in peak chapters get set-piece rating
            elif chapter_role in ['midpoint', 'crisis', 'climax']:
                impacts.append(3)
            # Other middle scenes are important
            else:
                impacts.append(2)

        return impacts

    @classmethod
    def validate_pacing_anchors(cls, chapter_budgets: List[Dict], total_words: int) -> Dict:
        """
        Check if peak chapters fall within expected pacing anchor percentages.

        Args:
            chapter_budgets: List of chapter budget dicts from calculate_top_down_budget()
            total_words: Total word count

        Returns:
            Dict with validation results:
                - valid: bool (all anchors within range)
                - anchors: Dict of anchor_name → (actual_pct, expected_range, in_range)
        """
        # Find peak chapters and their cumulative word positions
        cumulative = 0
        peak_positions = {}

        for ch in chapter_budgets:
            cumulative += ch['words_total']
            role = ch['role']

            if role == 'inciting_setup':
                peak_positions['inciting_incident'] = (cumulative / total_words, ch['number'])
            elif role == 'midpoint':
                peak_positions['midpoint'] = (cumulative / total_words, ch['number'])
            elif role == 'crisis':
                peak_positions['crisis'] = (cumulative / total_words, ch['number'])
            elif role == 'climax':
                peak_positions['climax'] = (cumulative / total_words, ch['number'])

        # Validate against expected ranges
        results = {}
        all_valid = True

        for anchor_name, (actual_pct, ch_num) in peak_positions.items():
            if anchor_name in cls.PACING_ANCHORS:
                min_pct, max_pct = cls.PACING_ANCHORS[anchor_name]
                in_range = min_pct <= actual_pct <= max_pct

                results[anchor_name] = {
                    'actual_pct': round(actual_pct * 100, 1),
                    'expected_range': (min_pct * 100, max_pct * 100),
                    'in_range': in_range,
                    'chapter': ch_num
                }

                if not in_range:
                    all_valid = False

        return {
            'valid': all_valid,
            'anchors': results
        }

    # ===== BACKWARD COMPATIBILITY METHODS =====
    # These are kept for existing code that uses the old API

    @classmethod
    def calculate_structure(
        cls,
        total_words: int,
        pacing: str,
        length_scope: Optional[str] = None
    ) -> Dict:
        """
        Calculate complete story structure (backward compatibility method).

        Args:
            total_words: Target total word count
            pacing: Story pacing (fast, moderate, slow)
            length_scope: Optional length scope (overrides auto-detection)

        Returns:
            Dict with form, chapter_count, base_ws, total_scenes, scenes_per_chapter, etc.
        """
        # Detect or use provided form
        if length_scope:
            normalized_scope = length_scope.lower().replace(' ', '_')
            form = normalized_scope if normalized_scope in cls.FORM_RANGES else cls.detect_form(total_words)
        else:
            form = cls.detect_form(total_words)

        # Calculate chapter count based on form
        chapter_length_target = cls.CHAPTER_LENGTH_TARGETS.get(form, 4000)
        chapter_count = max(1, round(total_words / chapter_length_target))

        # Get typical scenes per chapter for this form
        typical_scenes = cls.TYPICAL_SCENES_PER_CHAPTER.get(form, 4)

        # Estimate total scenes
        total_scenes = chapter_count * typical_scenes

        # Calculate base words per scene (Act II baseline)
        if total_scenes > 0:
            base_ws = total_words // total_scenes
        else:
            base_ws = 1500  # Fallback

        # Distribute scenes across chapters (simple version for compatibility)
        scenes_per_chapter = [typical_scenes] * chapter_count

        return {
            'form': form,
            'chapter_count': chapter_count,
            'base_ws': base_ws,
            'total_scenes': total_scenes,
            'scenes_per_chapter': scenes_per_chapter,
            'typical_scenes_per_chapter': typical_scenes
        }

    @classmethod
    def get_act_for_chapter(cls, chapter_number: int, total_chapters: int) -> str:
        """Determine which act a chapter belongs to (for backward compatibility)."""
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

    @classmethod
    def get_act_words_per_scene(cls, form: str, pacing: str, act: str) -> int:
        """Get words per scene for a specific act (backward compatibility)."""
        # Use typical scenes per chapter to estimate base
        typical_scenes = cls.TYPICAL_SCENES_PER_CHAPTER.get(form, 4)
        base_chapter_length = cls.CHAPTER_LENGTH_TARGETS.get(form, 4000)
        base_ws = base_chapter_length // typical_scenes if typical_scenes > 0 else 1000

        # Apply simple act multipliers (Act II is baseline)
        act_multipliers = {
            'act1': 0.95,  # Slightly shorter scenes in Act I
            'act2': 1.0,   # Baseline
            'act3': 1.05   # Slightly longer scenes in Act III
        }

        multiplier = act_multipliers.get(act, 1.0)
        return int(base_ws * multiplier)
