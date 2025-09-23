"""Unit tests for configuration system."""
import pytest
import os
from pathlib import Path
from unittest.mock import patch
import tempfile

from src.config import Settings, get_settings, constants


class TestSettings:
    """Test Settings configuration."""

    def test_api_key_validation_valid(self):
        """Test valid API key format."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-valid-key-123'}):
            settings = Settings()
            assert settings.openrouter_api_key == 'sk-or-valid-key-123'

    def test_api_key_validation_invalid(self):
        """Test invalid API key format raises error."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'invalid-key'}):
            with pytest.raises(ValueError, match="must start with 'sk-or-'"):
                Settings()

    def test_directory_creation(self, temp_dir):
        """Test that directories are created if they don't exist."""
        books_dir = temp_dir / "books"
        cache_dir = temp_dir / "cache"

        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings(
                books_dir=books_dir,
                cache_dir=cache_dir,
                taxonomies_dir=temp_dir / "tax"
            )

        assert books_dir.exists()
        assert cache_dir.exists()
        assert (temp_dir / "tax").exists()

    def test_temperature_settings(self):
        """Test temperature settings for different generation types."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings()

        assert settings.get_temperature('premise') == constants.DEFAULT_TEMPERATURES['premise']
        assert settings.get_temperature('prose') == constants.DEFAULT_TEMPERATURES['prose']
        assert settings.get_temperature('unknown') == 0.7  # default

    def test_max_tokens_settings(self):
        """Test max tokens settings for different generation types."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings()

        assert settings.get_max_tokens('premise') == constants.DEFAULT_MAX_TOKENS['premise']
        assert settings.get_max_tokens('prose') == constants.DEFAULT_MAX_TOKENS['prose']
        assert settings.get_max_tokens('unknown') == 4000  # default

    def test_active_model_property(self):
        """Test active model selection."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings()

        # Should use default when current is not set
        assert settings.active_model == settings.default_model

        # Should use current when set
        settings.set_model('openai/gpt-4')
        assert settings.active_model == 'openai/gpt-4'
        assert settings.current_model == 'openai/gpt-4'

    def test_load_config_file(self, temp_dir):
        """Test loading configuration from YAML file."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
default_model: openai/gpt-4
auto_commit: false
show_token_usage: false
temperature:
  premise: 0.5
  prose: 0.9
""")

        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings()
            settings.load_config_file(config_file)

        assert settings.default_model == 'openai/gpt-4'
        assert settings.auto_commit is False
        assert settings.show_token_usage is False
        assert settings.temperature['premise'] == 0.5
        assert settings.temperature['prose'] == 0.9

    def test_save_config_file(self, temp_dir):
        """Test saving configuration to YAML file."""
        config_file = temp_dir / "config.yaml"

        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-test'}):
            settings = Settings()
            settings.default_model = 'custom/model'
            settings.auto_commit = False
            settings.save_config_file(config_file)

        assert config_file.exists()

        # Load and verify
        import yaml
        with open(config_file) as f:
            saved = yaml.safe_load(f)

        assert saved['default_model'] == 'custom/model'
        assert saved['auto_commit'] is False


class TestConstants:
    """Test configuration constants."""

    def test_default_temperatures(self):
        """Test temperature constants are defined correctly."""
        assert 'premise' in constants.DEFAULT_TEMPERATURES
        assert 'treatment' in constants.DEFAULT_TEMPERATURES
        assert 'prose' in constants.DEFAULT_TEMPERATURES
        assert 'intent' in constants.DEFAULT_TEMPERATURES

        # Intent checking should have low temperature
        assert constants.DEFAULT_TEMPERATURES['intent'] < 0.2

    def test_intent_thresholds(self):
        """Test intent confidence thresholds."""
        assert constants.INTENT_CONFIDENCE_THRESHOLD > constants.INTENT_LOW_CONFIDENCE_THRESHOLD
        assert constants.INTENT_CONFIDENCE_THRESHOLD <= 1.0
        assert constants.INTENT_LOW_CONFIDENCE_THRESHOLD >= 0.0

    def test_analysis_types(self):
        """Test analysis types are defined."""
        expected = ['commercial', 'plot', 'characters', 'elements', 'world_building']
        assert constants.ANALYSIS_TYPES == expected

    def test_file_names(self):
        """Test file name constants."""
        assert constants.PROJECT_FILE == "project.yaml"
        assert constants.PREMISE_FILE == "premise.md"
        assert constants.TREATMENT_FILE == "treatment.md"
        assert constants.CHAPTERS_FILE == "chapters.yaml"