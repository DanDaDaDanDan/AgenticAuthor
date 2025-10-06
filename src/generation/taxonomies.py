"""Taxonomy loading and management for genre-specific generation."""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path


class TaxonomyLoader:
    """Handles loading and merging of genre-specific taxonomies."""

    # Available genres with their taxonomy files
    GENRES = {
        'fantasy': 'fantasy-taxonomy.json',
        'romance': 'romance-taxonomy.json',
        'mystery': 'mystery-thriller-taxonomy.json',
        'thriller': 'mystery-thriller-taxonomy.json',
        'science-fiction': 'science-fiction-taxonomy.json',
        'sci-fi': 'science-fiction-taxonomy.json',
        'horror': 'horror-taxonomy.json',
        'contemporary': 'contemporary-fiction-taxonomy.json',
        'historical': 'historical-fiction-taxonomy.json',
        'literary': 'literary-fiction-taxonomy.json',
        'young-adult': 'young-adult-taxonomy.json',
        'ya': 'young-adult-taxonomy.json',
        'urban-fantasy': 'urban-fantasy-taxonomy.json',
        'romantasy': 'romantasy-taxonomy.json',
        'custom': 'generic-taxonomy.json',
        'general': 'generic-taxonomy.json'
    }

    def __init__(self, taxonomy_dir: Optional[Path] = None):
        """
        Initialize taxonomy loader.

        Args:
            taxonomy_dir: Directory containing taxonomy files
        """
        if taxonomy_dir:
            self.taxonomy_dir = Path(taxonomy_dir)
        else:
            # Default to root taxonomies directory
            self.taxonomy_dir = Path(__file__).parent.parent.parent / "taxonomies"

    def get_available_genres(self) -> List[str]:
        """Get list of available genres."""
        # Return unique genre names (not aliases)
        unique_genres = []
        seen_files = set()

        for genre, filename in self.GENRES.items():
            if filename not in seen_files and genre not in ['custom', 'general']:
                unique_genres.append(genre)
                seen_files.add(filename)

        return sorted(unique_genres)

    def normalize_genre(self, genre: str) -> str:
        """
        Normalize genre name to match taxonomy file.

        Args:
            genre: Genre name or alias

        Returns:
            Normalized genre name
        """
        genre_lower = genre.lower().strip()

        # Check if it's a known genre/alias
        if genre_lower in self.GENRES:
            return genre_lower

        # Try to match partial names
        for known_genre in self.GENRES:
            if genre_lower in known_genre or known_genre in genre_lower:
                return known_genre

        # Default to general/custom
        return 'general'

    def load_base_taxonomy(self) -> Dict[str, Any]:
        """Load the base taxonomy that all genres share."""
        base_file = self.taxonomy_dir / "base-taxonomy.json"

        if base_file.exists():
            with open(base_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        return {"categories": {}}

    def load_genre_taxonomy(self, genre: str) -> Dict[str, Any]:
        """
        Load taxonomy for a specific genre.

        Args:
            genre: Genre name

        Returns:
            Taxonomy dictionary
        """
        normalized_genre = self.normalize_genre(genre)
        filename = self.GENRES.get(normalized_genre, 'generic-taxonomy.json')

        taxonomy_file = self.taxonomy_dir / filename

        if taxonomy_file.exists():
            with open(taxonomy_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fallback to generic
        generic_file = self.taxonomy_dir / "generic-taxonomy.json"
        if generic_file.exists():
            with open(generic_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        return {"categories": {}}

    def load_merged_taxonomy(self, genre: str) -> Dict[str, Any]:
        """
        Load and merge base + genre-specific taxonomy.

        Args:
            genre: Genre name

        Returns:
            Merged taxonomy dictionary
        """
        base = self.load_base_taxonomy()
        genre_specific = self.load_genre_taxonomy(genre)

        # Merge categories (genre-specific overrides base)
        merged = {
            **genre_specific,
            "categories": {
                **base.get("categories", {}),
                **genre_specific.get("categories", {})
            }
        }

        return merged

    def get_category_options(self, taxonomy: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Extract category options from taxonomy for AI prompt.

        Args:
            taxonomy: Loaded taxonomy dictionary

        Returns:
            Dict mapping category names to list of options
        """
        category_options = {}

        categories = taxonomy.get("categories", {})
        for category_key, category_data in categories.items():
            options = []

            # Extract option names
            if "options" in category_data:
                for option_data in category_data["options"].values():
                    if isinstance(option_data, dict) and "name" in option_data:
                        options.append(option_data["name"])

            if options:
                category_options[category_key] = options

        return category_options

    def get_category_display_names(self, taxonomy: Dict[str, Any]) -> Dict[str, str]:
        """
        Get human-readable display names for categories.

        Args:
            taxonomy: Loaded taxonomy dictionary

        Returns:
            Dict mapping category keys to display names
        """
        display_names = {}

        categories = taxonomy.get("categories", {})
        for category_key, category_data in categories.items():
            if "category_name" in category_data:
                display_names[category_key] = category_data["category_name"]
            else:
                # Convert snake_case to Title Case
                display_names[category_key] = category_key.replace('_', ' ').title()

        return display_names


class PremiseAnalyzer:
    """Analyzes user input to determine premise type and treatment."""

    @staticmethod
    def analyze(text: str) -> Dict[str, Any]:
        """
        Analyze input text to determine its type.

        Args:
            text: Input text to analyze

        Returns:
            Analysis results including word count, type, etc.
        """
        if not text:
            return {
                'type': 'empty',
                'word_count': 0,
                'paragraph_count': 0,
                'is_treatment': False,
                'has_structure': False
            }

        # Clean and count
        cleaned = text.strip()
        words = cleaned.split()
        word_count = len(words)

        # Count paragraphs
        paragraphs = [p for p in cleaned.split('\n\n') if p.strip()]
        paragraph_count = len(paragraphs)

        # Check for structure indicators
        has_structure = (
            paragraph_count > 2 or
            '•' in cleaned or
            '- ' in cleaned or
            '1.' in cleaned or
            'Act ' in cleaned or
            'Chapter' in cleaned.lower()
        )

        # Determine if it's a treatment
        is_treatment = word_count > 200 and (paragraph_count > 1 or has_structure)

        # Determine type
        if word_count == 0:
            premise_type = 'empty'
        elif word_count < 20:
            premise_type = 'brief'
        elif word_count < 100:
            premise_type = 'standard'
        elif word_count < 200:
            premise_type = 'detailed'
        else:
            premise_type = 'treatment'

        return {
            'type': premise_type,
            'word_count': word_count,
            'paragraph_count': paragraph_count,
            'is_treatment': is_treatment,
            'has_structure': has_structure,
            'text': cleaned
        }


class PremiseHistory:
    """Manages premise generation history to avoid repetition."""

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize premise history.

        Args:
            history_file: Path to history JSON file
        """
        if history_file:
            self.history_file = Path(history_file)
        else:
            # Default to project-local .agentic/premise_history.json
            self.history_file = Path(".agentic") / "premise_history.json"

        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_history(self):
        """Save history to file."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2)

    def add(self, premise: str, genre: str, selections: Dict[str, Any]):
        """
        Add a premise to history.

        Args:
            premise: The generated premise text
            genre: Genre used
            selections: Taxonomy selections made
        """
        from datetime import datetime

        entry = {
            'premise': premise[:200],  # Store first 200 chars
            'genre': genre,
            'selections': selections,
            'timestamp': datetime.now().isoformat(),
            'full_premise': premise
        }

        self.history.append(entry)

        # Keep only last 10
        if len(self.history) > 10:
            self.history = self.history[-10:]

        self._save_history()

    def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent premise history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent premise entries
        """
        return self.history[-limit:] if self.history else []

    def clear(self):
        """Clear all history."""
        self.history = []
        self._save_history()

    def format_for_prompt(self) -> str:
        """
        Format history for inclusion in AI prompt.

        Returns:
            Formatted history string
        """
        if not self.history:
            return ""

        lines = ["PREVIOUS GENERATIONS (avoid repeating these concepts):"]

        for i, entry in enumerate(self.history[-5:], 1):
            premise_preview = entry['premise'][:60] + "..."
            genre = entry.get('genre', 'unknown')

            # Extract key selections
            selections = entry.get('selections', {})
            key_elements = []

            for category, values in selections.items():
                if values:
                    if isinstance(values, list):
                        key_elements.append(f"{category}: {', '.join(values[:2])}")
                    else:
                        key_elements.append(f"{category}: {values}")

            line = f"{i}. [{genre}] \"{premise_preview}\" - {', '.join(key_elements[:3])}"
            lines.append(line)

        lines.append("\nIMPORTANT: Generate something DIFFERENT from the above.")

        return '\n'.join(lines)