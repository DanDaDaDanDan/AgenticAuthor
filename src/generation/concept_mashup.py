"""Concept mashup generator - combines movies with story modifiers."""

import random
from typing import List, Dict
from pathlib import Path


class ConceptMashupGenerator:
    """Generator for movie + modifier mashup concepts."""

    def __init__(self, base_dir: Path = None):
        """
        Initialize mashup generator.

        Args:
            base_dir: Base directory of project (defaults to repo root)
        """
        if base_dir is None:
            # Default to repo root
            base_dir = Path(__file__).parent.parent.parent

        self.movies_file = base_dir / "misc" / "movies.txt"
        self.modifiers_file = base_dir / "misc" / "story-modifiers.txt"

    def load_movies(self) -> List[str]:
        """
        Load movie list from movies.txt.

        Returns:
            List of movie titles
        """
        if not self.movies_file.exists():
            raise FileNotFoundError(f"Movies file not found: {self.movies_file}")

        with open(self.movies_file, 'r', encoding='utf-8') as f:
            # Read lines, strip whitespace, filter empty lines
            movies = [line.strip() for line in f if line.strip()]

        if not movies:
            raise ValueError("Movies file is empty")

        return movies

    def load_modifiers(self) -> List[str]:
        """
        Load modifier list from story-modifiers.txt.

        Returns:
            List of story modifiers
        """
        if not self.modifiers_file.exists():
            raise FileNotFoundError(f"Modifiers file not found: {self.modifiers_file}")

        with open(self.modifiers_file, 'r', encoding='utf-8') as f:
            # Read lines, strip whitespace, filter empty lines
            modifiers = [line.strip() for line in f if line.strip()]

        if not modifiers:
            raise ValueError("Modifiers file is empty")

        return modifiers

    def generate_combinations(self, count: int = 50) -> List[Dict[str, any]]:
        """
        Generate random movie + modifier combinations.

        Args:
            count: Number of combinations to generate (default 50)

        Returns:
            List of dicts with:
                - number: int (1-indexed)
                - movie: str
                - modifier: str
                - concept: str (formatted combination)

        Raises:
            ValueError: If count is invalid or files can't be loaded
        """
        if count < 1:
            raise ValueError("Count must be at least 1")

        # Load data
        movies = self.load_movies()
        modifiers = self.load_modifiers()

        # Calculate maximum possible unique combinations
        max_combinations = len(movies) * len(modifiers)

        if count > max_combinations:
            print(f"[warning] Requested {count} combinations but only {max_combinations} unique pairings possible.")
            print(f"[warning] Generating all {max_combinations} combinations...")
            count = max_combinations

        # Generate unique random combinations
        used = set()
        concepts = []

        # Safety: prevent infinite loop if we somehow can't generate enough
        max_attempts = count * 10

        attempts = 0
        while len(concepts) < count and attempts < max_attempts:
            attempts += 1

            movie = random.choice(movies)
            modifier = random.choice(modifiers)
            key = (movie, modifier)

            if key not in used:
                used.add(key)
                concepts.append({
                    'number': len(concepts) + 1,
                    'movie': movie,
                    'modifier': modifier,
                    'concept': f"{movie} {modifier}"
                })

        if len(concepts) < count:
            print(f"[warning] Could only generate {len(concepts)} unique combinations (requested {count})")

        return concepts

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about available data.

        Returns:
            Dict with movie_count, modifier_count, max_combinations
        """
        try:
            movies = self.load_movies()
            modifiers = self.load_modifiers()

            return {
                'movie_count': len(movies),
                'modifier_count': len(modifiers),
                'max_combinations': len(movies) * len(modifiers)
            }
        except Exception as e:
            return {
                'movie_count': 0,
                'modifier_count': 0,
                'max_combinations': 0,
                'error': str(e)
            }
