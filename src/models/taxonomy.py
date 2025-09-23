"""Taxonomy models for genre definitions."""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field


class GenreElement(BaseModel):
    """A single genre element or trope."""

    name: str = Field(description="Element name")
    description: str = Field(description="Element description")
    category: Optional[str] = Field(None, description="Element category")
    examples: List[str] = Field(default_factory=list, description="Examples")
    weight: float = Field(1.0, description="Importance weight")


class Taxonomy(BaseModel):
    """Genre taxonomy definition."""

    name: str = Field(description="Taxonomy name")
    description: str = Field(description="Taxonomy description")
    genre: str = Field(description="Primary genre")
    subgenres: List[str] = Field(default_factory=list, description="Subgenres")

    # Story elements
    themes: List[GenreElement] = Field(default_factory=list, description="Common themes")
    tropes: List[GenreElement] = Field(default_factory=list, description="Genre tropes")
    character_types: List[GenreElement] = Field(
        default_factory=list,
        description="Character archetypes"
    )
    plot_structures: List[GenreElement] = Field(
        default_factory=list,
        description="Plot structures"
    )
    settings: List[GenreElement] = Field(
        default_factory=list,
        description="Common settings"
    )
    conflicts: List[GenreElement] = Field(
        default_factory=list,
        description="Conflict types"
    )

    # Style guidance
    tone_options: List[str] = Field(default_factory=list, description="Tone options")
    pov_options: List[str] = Field(default_factory=list, description="POV options")
    pacing_guidance: Optional[str] = Field(None, description="Pacing advice")

    # Audience
    target_audience: Optional[str] = Field(None, description="Target audience")
    content_warnings: List[str] = Field(default_factory=list, description="Content warnings")

    @classmethod
    def load_from_file(cls, file_path: Path) -> "Taxonomy":
        """
        Load taxonomy from JSON file.

        Args:
            file_path: Path to taxonomy JSON file

        Returns:
            Taxonomy instance
        """
        with open(file_path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Taxonomy":
        """
        Create taxonomy from dictionary.

        Args:
            data: Dictionary with taxonomy data

        Returns:
            Taxonomy instance
        """
        # Convert element lists
        for key in ['themes', 'tropes', 'character_types', 'plot_structures', 'settings', 'conflicts']:
            if key in data and isinstance(data[key], list):
                elements = []
                for item in data[key]:
                    if isinstance(item, dict):
                        elements.append(GenreElement(**item))
                    else:
                        # Simple string format
                        elements.append(GenreElement(name=item, description=item))
                data[key] = elements

        return cls(**data)

    def save_to_file(self, file_path: Path):
        """
        Save taxonomy to JSON file.

        Args:
            file_path: Path where to save the taxonomy
        """
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = self.model_dump(exclude_none=True)

        # Convert GenreElement objects to dicts
        for key in ['themes', 'tropes', 'character_types', 'plot_structures', 'settings', 'conflicts']:
            if key in data and isinstance(data[key], list):
                # Check if items are GenreElement objects or already dicts
                converted = []
                for item in data[key]:
                    if hasattr(item, 'model_dump'):
                        converted.append(item.model_dump())
                    else:
                        # Already a dict
                        converted.append(item)
                data[key] = converted

        return data

    def get_random_elements(self, category: str, count: int = 3) -> List[GenreElement]:
        """
        Get random elements from a category.

        Args:
            category: Element category (themes, tropes, etc.)
            count: Number of elements to return

        Returns:
            List of random elements
        """
        import random

        elements = getattr(self, category, [])
        if not elements:
            return []

        # Weight-based selection
        selected = []
        available = elements.copy()

        for _ in range(min(count, len(available))):
            weights = [e.weight for e in available]
            chosen = random.choices(available, weights=weights, k=1)[0]
            selected.append(chosen)
            available.remove(chosen)

        return selected

    def to_prompt_context(self) -> str:
        """
        Generate prompt context from taxonomy.

        Returns:
            Formatted string for use in prompts
        """
        lines = [
            f"Genre: {self.genre}",
            f"Description: {self.description}"
        ]

        if self.subgenres:
            lines.append(f"Subgenres: {', '.join(self.subgenres)}")

        if self.themes:
            theme_names = [t.name for t in self.themes[:5]]
            lines.append(f"Key Themes: {', '.join(theme_names)}")

        if self.tropes:
            trope_names = [t.name for t in self.tropes[:5]]
            lines.append(f"Common Tropes: {', '.join(trope_names)}")

        if self.tone_options:
            lines.append(f"Tone Options: {', '.join(self.tone_options[:3])}")

        if self.target_audience:
            lines.append(f"Target Audience: {self.target_audience}")

        return "\n".join(lines)


class TaxonomyManager:
    """Manage available taxonomies."""

    def __init__(self, taxonomies_dir: Path):
        """
        Initialize taxonomy manager.

        Args:
            taxonomies_dir: Directory containing taxonomy JSON files
        """
        self.taxonomies_dir = Path(taxonomies_dir)
        self._cache: Dict[str, Taxonomy] = {}

    def list_available(self) -> List[str]:
        """List available taxonomy names."""
        if not self.taxonomies_dir.exists():
            return []

        taxonomies = []
        for file in self.taxonomies_dir.glob("*-taxonomy.json"):
            name = file.stem.replace('-taxonomy', '')
            taxonomies.append(name)

        return sorted(taxonomies)

    def load(self, name: str) -> Optional[Taxonomy]:
        """
        Load a taxonomy by name.

        Args:
            name: Taxonomy name (without -taxonomy.json suffix)

        Returns:
            Taxonomy instance or None if not found
        """
        if name in self._cache:
            return self._cache[name]

        file_path = self.taxonomies_dir / f"{name}-taxonomy.json"
        if not file_path.exists():
            # Try with full filename
            alt_path = self.taxonomies_dir / name
            if alt_path.exists():
                file_path = alt_path
            else:
                return None

        try:
            taxonomy = Taxonomy.load_from_file(file_path)
            self._cache[name] = taxonomy
            return taxonomy
        except Exception:
            return None

    def get_or_default(self, name: Optional[str]) -> Taxonomy:
        """
        Get taxonomy by name or return default.

        Args:
            name: Taxonomy name or None for default

        Returns:
            Taxonomy instance
        """
        if name:
            taxonomy = self.load(name)
            if taxonomy:
                return taxonomy

        # Return a basic default taxonomy
        return Taxonomy(
            name="default",
            description="Default story taxonomy",
            genre="fiction",
            themes=[
                GenreElement(name="Growth", description="Character development"),
                GenreElement(name="Conflict", description="Central conflict"),
                GenreElement(name="Resolution", description="Story resolution")
            ]
        )