"""Tests for taxonomy loading and premise analysis."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory


class TestTaxonomyLoader:
    """Test TaxonomyLoader functionality."""

    def test_get_available_genres(self):
        """Test getting list of available genres."""
        loader = TaxonomyLoader()
        genres = loader.get_available_genres()

        assert isinstance(genres, list)
        assert len(genres) > 0
        assert 'fantasy' in genres
        assert 'romance' in genres
        assert 'mystery' in genres
        # Should not include aliases or generic
        assert 'sci-fi' not in genres
        assert 'ya' not in genres
        assert 'general' not in genres

    def test_normalize_genre(self):
        """Test genre normalization."""
        loader = TaxonomyLoader()

        # Direct matches
        assert loader.normalize_genre('fantasy') == 'fantasy'
        assert loader.normalize_genre('Fantasy') == 'fantasy'
        assert loader.normalize_genre('FANTASY') == 'fantasy'

        # Aliases
        assert loader.normalize_genre('sci-fi') == 'sci-fi'
        assert loader.normalize_genre('ya') == 'ya'

        # Partial matches
        # 'scifi' doesn't contain 'science-fiction' so defaults to general
        assert loader.normalize_genre('scifi') == 'general'
        # 'rom' is contained in 'romance'
        assert loader.normalize_genre('rom') == 'romance'

        # Unknown genres default to general
        assert loader.normalize_genre('unknown-genre') == 'general'

    def test_load_genre_taxonomy(self, temp_dir):
        """Test loading genre-specific taxonomy."""
        # Create a test taxonomy directory
        taxonomy_dir = temp_dir / "taxonomies"
        taxonomy_dir.mkdir()

        # Create a test fantasy taxonomy
        fantasy_tax = {
            "categories": {
                "magic_system": {
                    "category_name": "Magic System",
                    "options": {
                        "hard": {"name": "Hard Magic"},
                        "soft": {"name": "Soft Magic"}
                    }
                }
            }
        }

        with open(taxonomy_dir / "fantasy-taxonomy.json", "w") as f:
            json.dump(fantasy_tax, f)

        loader = TaxonomyLoader(taxonomy_dir)
        taxonomy = loader.load_genre_taxonomy("fantasy")

        assert "categories" in taxonomy
        assert "magic_system" in taxonomy["categories"]

    def test_load_merged_taxonomy(self, temp_dir):
        """Test merging base and genre taxonomies."""
        taxonomy_dir = temp_dir / "taxonomies"
        taxonomy_dir.mkdir()

        # Create base taxonomy
        base_tax = {
            "categories": {
                "pacing": {
                    "category_name": "Pacing",
                    "options": {
                        "fast": {"name": "Fast-paced"},
                        "slow": {"name": "Slow-burn"}
                    }
                }
            }
        }

        # Create genre taxonomy
        genre_tax = {
            "categories": {
                "magic_system": {
                    "category_name": "Magic System",
                    "options": {
                        "hard": {"name": "Hard Magic"}
                    }
                },
                "pacing": {
                    "category_name": "Pacing Override",
                    "options": {
                        "variable": {"name": "Variable pacing"}
                    }
                }
            }
        }

        with open(taxonomy_dir / "base-taxonomy.json", "w") as f:
            json.dump(base_tax, f)
        with open(taxonomy_dir / "fantasy-taxonomy.json", "w") as f:
            json.dump(genre_tax, f)

        loader = TaxonomyLoader(taxonomy_dir)
        merged = loader.load_merged_taxonomy("fantasy")

        # Genre-specific should override base
        assert merged["categories"]["pacing"]["category_name"] == "Pacing Override"
        # Genre-specific categories should be included
        assert "magic_system" in merged["categories"]

    def test_get_category_options(self):
        """Test extracting category options."""
        taxonomy = {
            "categories": {
                "tone": {
                    "options": {
                        "dark": {"name": "Dark"},
                        "light": {"name": "Light-hearted"},
                        "serious": {"name": "Serious"}
                    }
                },
                "empty_category": {
                    "options": {}
                }
            }
        }

        loader = TaxonomyLoader()
        options = loader.get_category_options(taxonomy)

        assert "tone" in options
        assert options["tone"] == ["Dark", "Light-hearted", "Serious"]
        # Empty categories should not be included
        assert "empty_category" not in options


class TestPremiseAnalyzer:
    """Test PremiseAnalyzer functionality."""

    def test_analyze_empty_text(self):
        """Test analyzing empty text."""
        result = PremiseAnalyzer.analyze("")

        assert result["type"] == "empty"
        assert result["word_count"] == 0
        assert result["paragraph_count"] == 0
        assert result["is_treatment"] == False
        assert result["has_structure"] == False

    def test_analyze_brief_premise(self):
        """Test analyzing brief premise."""
        text = "A young wizard discovers a hidden world"
        result = PremiseAnalyzer.analyze(text)

        assert result["type"] == "brief"
        assert result["word_count"] == 7
        assert result["is_treatment"] == False

    def test_analyze_standard_premise(self):
        """Test analyzing standard premise."""
        text = " ".join(["word"] * 50)  # 50 words
        result = PremiseAnalyzer.analyze(text)

        assert result["type"] == "standard"
        assert result["word_count"] == 50
        assert result["is_treatment"] == False

    def test_analyze_detailed_premise(self):
        """Test analyzing detailed premise."""
        text = " ".join(["word"] * 150)  # 150 words
        result = PremiseAnalyzer.analyze(text)

        assert result["type"] == "detailed"
        assert result["word_count"] == 150
        assert result["is_treatment"] == False

    def test_analyze_treatment(self):
        """Test analyzing full treatment."""
        # Create 250+ word treatment with structure
        paragraphs = [
            " ".join(["word"] * 60),
            " ".join(["word"] * 60),
            " ".join(["word"] * 60),
            " ".join(["word"] * 80)
        ]
        text = "\n\n".join(paragraphs)
        result = PremiseAnalyzer.analyze(text)

        assert result["type"] == "treatment"
        assert result["word_count"] == 260
        assert result["paragraph_count"] == 4
        assert result["is_treatment"] == True
        assert result["has_structure"] == True

    def test_detect_structure_indicators(self):
        """Test detection of structure indicators."""
        texts_with_structure = [
            "Act 1: The beginning\n\nAct 2: The middle",
            "Chapter 1 - Introduction\n\nSomething happens",
            "• First point\n• Second point",
            "1. First item\n2. Second item",
            "- Bullet point one\n- Bullet point two"
        ]

        for text in texts_with_structure:
            result = PremiseAnalyzer.analyze(text)
            assert result["has_structure"] == True


class TestPremiseHistory:
    """Test PremiseHistory functionality."""

    def test_initialize_history(self, temp_dir):
        """Test initializing premise history."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        assert history.history == []
        assert history.history_file == history_file

    def test_add_premise(self, temp_dir):
        """Test adding premise to history."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        history.add(
            premise="A test premise",
            genre="fantasy",
            selections={"tone": ["dark"]}
        )

        assert len(history.history) == 1
        assert history.history[0]["premise"] == "A test premise"
        assert history.history[0]["genre"] == "fantasy"
        assert "timestamp" in history.history[0]

    def test_history_limit(self, temp_dir):
        """Test history is limited to 10 entries."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        # Add 15 premises
        for i in range(15):
            history.add(
                premise=f"Premise {i}",
                genre="fantasy",
                selections={}
            )

        # Should only keep last 10
        assert len(history.history) == 10
        assert history.history[0]["premise"] == "Premise 5"
        assert history.history[-1]["premise"] == "Premise 14"

    def test_get_recent(self, temp_dir):
        """Test getting recent history."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        for i in range(7):
            history.add(f"Premise {i}", "fantasy", {})

        recent = history.get_recent(5)
        assert len(recent) == 5
        assert recent[0]["premise"] == "Premise 2"

    def test_format_for_prompt(self, temp_dir):
        """Test formatting history for AI prompt."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        history.add(
            "A wizard discovers magic",
            "fantasy",
            {"tone": ["dark", "mysterious"], "pacing": "fast"}
        )

        formatted = history.format_for_prompt()

        assert "PREVIOUS GENERATIONS" in formatted
        assert "avoid repeating" in formatted.lower()
        assert "fantasy" in formatted
        assert "wizard discovers magic" in formatted.lower()

    def test_clear_history(self, temp_dir):
        """Test clearing history."""
        history_file = temp_dir / "history.json"
        history = PremiseHistory(history_file)

        history.add("Test premise", "fantasy", {})
        assert len(history.history) == 1

        history.clear()
        assert len(history.history) == 0

        # Check file is also cleared
        with open(history_file, 'r') as f:
            data = json.load(f)
        assert data == []

    def test_persistence(self, temp_dir):
        """Test history persistence across instances."""
        history_file = temp_dir / "history.json"

        # First instance
        history1 = PremiseHistory(history_file)
        history1.add("First premise", "fantasy", {})

        # Second instance should load existing history
        history2 = PremiseHistory(history_file)
        assert len(history2.history) == 1
        assert history2.history[0]["premise"] == "First premise"