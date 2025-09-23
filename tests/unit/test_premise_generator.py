"""Tests for enhanced premise generator."""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.generation.premise import PremiseGenerator
from src.models import Project
from src.api import OpenRouterClient


class TestPremiseGenerator:
    """Test enhanced PremiseGenerator functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenRouter client."""
        client = Mock(spec=OpenRouterClient)
        client.json_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_project(self, temp_dir):
        """Create a mock project."""
        project_dir = temp_dir / "test_project"
        project_dir.mkdir()
        project = Project.create(project_dir, name="Test Project", genre="fantasy")
        return project

    @pytest.mark.asyncio
    async def test_generate_with_genre_only(self, mock_client, mock_project):
        """Test generating premise with only genre specified."""
        # Setup mock response
        mock_response = {
            "premise": "A young mage discovers ancient powers",
            "protagonist": "Young mage",
            "antagonist": "Dark sorcerer",
            "stakes": "The fate of the realm",
            "hook": "Ancient magic awakens",
            "themes": ["power", "responsibility", "growth"],
            "selections": {
                "tone": ["dark", "mysterious"],
                "pacing": ["moderate"]
            }
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project, model="test-model")
        result = await generator.generate(genre="fantasy")

        # Verify result
        assert result == mock_response
        assert "premise" in result
        assert "selections" in result

        # Verify API was called with correct parameters
        mock_client.json_completion.assert_called_once()
        call_args = mock_client.json_completion.call_args
        assert call_args[1]["model"] == "test-model"
        assert "fantasy" in call_args[1]["prompt"]

    @pytest.mark.asyncio
    async def test_generate_with_user_input(self, mock_client, mock_project):
        """Test generating premise with user concept."""
        mock_response = {
            "premise": "In a world where emotions power magic",
            "protagonist": "Emotionally suppressed teen",
            "antagonist": "Emotion harvester",
            "stakes": "Humanity's ability to feel",
            "hook": "Emotions as magical fuel",
            "themes": ["emotions", "humanity", "power"],
            "selections": {}
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project, model="test-model")
        result = await generator.generate(
            user_input="a world where emotions power magic",
            genre="fantasy"
        )

        # Verify user input was included in prompt
        call_args = mock_client.json_completion.call_args
        prompt = call_args[1]["prompt"]
        assert "emotions power magic" in prompt
        assert "USER GUIDANCE" in prompt

    @pytest.mark.asyncio
    async def test_generate_with_history(self, mock_client, mock_project):
        """Test generating premise with history to avoid repetition."""
        from src.generation.taxonomies import PremiseHistory

        # Create history with previous generations
        history = Mock(spec=PremiseHistory)
        history.format_for_prompt.return_value = "PREVIOUS GENERATIONS: Previous premise about wizards"

        mock_response = {
            "premise": "A knight seeks redemption",
            "themes": ["redemption", "honor"],
            "selections": {}
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.generate(
            genre="fantasy",
            premise_history=history
        )

        # Verify history was included in prompt
        call_args = mock_client.json_completion.call_args
        prompt = call_args[1]["prompt"]
        assert "PREVIOUS GENERATIONS" in prompt
        assert "Previous premise about wizards" in prompt

    @pytest.mark.asyncio
    async def test_generate_taxonomy_only(self, mock_client, mock_project):
        """Test generating only taxonomy selections for existing treatment."""
        treatment = "A long treatment about a hero's journey " * 50  # Make it long

        mock_response = {
            "selections": {
                "tone": ["epic", "heroic"],
                "pacing": ["moderate", "building"],
                "themes": ["heroism", "sacrifice"]
            }
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.generate_taxonomy_only(treatment, "fantasy")

        # Verify result
        assert "selections" in result
        assert result["selections"]["tone"] == ["epic", "heroic"]

        # Verify treatment was included in prompt
        call_args = mock_client.json_completion.call_args
        prompt = call_args[1]["prompt"]
        assert "hero's journey" in prompt
        assert "TREATMENT:" in prompt

    @pytest.mark.asyncio
    async def test_iterate_premise(self, mock_client, mock_project):
        """Test iterating on existing premise with feedback."""
        # Setup existing premise
        mock_project.save_premise("Original premise about a wizard")

        # Save metadata
        metadata = {
            "premise": "Original premise about a wizard",
            "protagonist": "Young wizard",
            "themes": ["magic", "growth"]
        }
        metadata_path = mock_project.path / "premise_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        mock_response = {
            "premise": "Updated premise with more action",
            "protagonist": "Battle-hardened wizard",
            "themes": ["magic", "war", "sacrifice"]
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.iterate("Add more action and conflict")

        # Verify feedback was used
        call_args = mock_client.json_completion.call_args
        prompt = call_args[1]["prompt"]
        assert "Add more action and conflict" in prompt
        assert "Original premise about a wizard" in prompt

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_client, mock_project):
        """Test error handling in generation."""
        mock_client.json_completion.side_effect = Exception("API Error")

        generator = PremiseGenerator(mock_client, mock_project)

        with pytest.raises(Exception) as exc_info:
            await generator.generate(genre="fantasy")

        assert "Failed to generate premise" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_saves_premise_to_project(self, mock_client, mock_project):
        """Test that generated premise is saved to project."""
        mock_response = {
            "premise": "A saved premise",
            "themes": ["test"],
            "selections": {}
        }
        mock_client.json_completion.return_value = mock_response

        generator = PremiseGenerator(mock_client, mock_project)
        await generator.generate(genre="fantasy")

        # Verify premise was saved
        saved_premise = mock_project.get_premise()
        assert saved_premise == "A saved premise"

        # Verify metadata was saved
        metadata_path = mock_project.path / "premise_metadata.json"
        assert metadata_path.exists()
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        assert metadata["premise"] == "A saved premise"

    @pytest.mark.asyncio
    async def test_model_fallback(self, mock_client, mock_project):
        """Test model fallback when not specified."""
        mock_response = {"premise": "Test", "themes": []}
        mock_client.json_completion.return_value = mock_response

        # Test with no model specified
        generator = PremiseGenerator(mock_client, mock_project, model=None)

        with patch('src.config.get_settings') as mock_settings:
            settings = MagicMock()
            settings.active_model = "fallback-model"
            mock_settings.return_value = settings

            await generator.generate(genre="fantasy")

            # Should use settings model
            call_args = mock_client.json_completion.call_args
            assert call_args[1]["model"] == "fallback-model"