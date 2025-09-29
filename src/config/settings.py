"""Configuration management using Pydantic."""
import os
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

from .constants import (
    OPENROUTER_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_BOOKS_DIR,
    DEFAULT_TAXONOMIES_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_TEMPERATURES,
    DEFAULT_MAX_TOKENS
)


class Settings(BaseSettings):
    """Application settings loaded from environment and config files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Configuration
    openrouter_api_key: str = Field(
        default=...,
        description="OpenRouter API key (must start with 'sk-or-')",
        alias="OPENROUTER_API_KEY"
    )
    openrouter_base_url: str = Field(
        default=OPENROUTER_BASE_URL,
        description="OpenRouter API base URL"
    )

    # Storage paths
    books_dir: Path = Field(
        default=DEFAULT_BOOKS_DIR,
        description="Directory for book projects"
    )
    taxonomies_dir: Path = Field(
        default=DEFAULT_TAXONOMIES_DIR,
        description="Directory for taxonomy definitions"
    )
    cache_dir: Path = Field(
        default=DEFAULT_CACHE_DIR,
        description="Directory for cache storage"
    )

    # Model configuration
    default_model: str = Field(
        default=DEFAULT_MODEL,
        description="Default LLM model to use"
    )
    current_model: Optional[str] = Field(
        default=None,
        description="Currently selected model (runtime)"
    )

    # Generation parameters
    temperature: Dict[str, float] = Field(
        default_factory=lambda: DEFAULT_TEMPERATURES.copy(),
        description="Temperature settings for different generation types"
    )
    max_tokens: Dict[str, int] = Field(
        default_factory=lambda: DEFAULT_MAX_TOKENS.copy(),
        description="Max tokens for different generation types"
    )

    # User preferences
    auto_commit: bool = Field(
        default=True,
        description="Automatically commit changes to git"
    )
    show_token_usage: bool = Field(
        default=True,
        description="Display token usage after API calls"
    )
    streaming_output: bool = Field(
        default=True,
        description="Stream API responses to terminal"
    )
    streaming_display_mode: str = Field(
        default="status",
        description="Display mode for streaming: 'status' (fixed bar), 'live' (original), or 'simple' (plain)"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose logging"
    )

    @field_validator('openrouter_api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate that API key has correct format."""
        if not v.startswith('sk-or-'):
            raise ValueError("OpenRouter API key must start with 'sk-or-'")
        return v

    @field_validator('streaming_display_mode')
    @classmethod
    def validate_display_mode(cls, v: str) -> str:
        """Validate streaming display mode."""
        valid_modes = {'status', 'live', 'simple'}
        if v not in valid_modes:
            raise ValueError(f"Display mode must be one of: {', '.join(valid_modes)}")
        return v

    @field_validator('books_dir', 'taxonomies_dir', 'cache_dir')
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Ensure directories exist."""
        v = Path(v).resolve()
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def active_model(self) -> str:
        """Get the currently active model."""
        return self.current_model or self.default_model

    def set_model(self, model: str) -> None:
        """Set the current model."""
        self.current_model = model

    def get_temperature(self, generation_type: str) -> float:
        """Get temperature for a specific generation type."""
        return self.temperature.get(generation_type, 0.7)

    def get_max_tokens(self, generation_type: str) -> int:
        """Get max tokens for a specific generation type."""
        return self.max_tokens.get(generation_type, 4000)

    def load_config_file(self, config_path: Path) -> None:
        """Load additional settings from a YAML config file."""
        if config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f)

            # Update settings with config file data
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def save_config_file(self, config_path: Path) -> None:
        """Save current settings to a YAML config file."""
        config_data = {
            'default_model': self.default_model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'auto_commit': self.auto_commit,
            'show_token_usage': self.show_token_usage,
            'streaming_output': self.streaming_output,
            'streaming_display_mode': self.streaming_display_mode,
            'verbose': self.verbose
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()

    # Load user config if it exists
    user_config = Path.home() / '.agentic' / 'config.yaml'
    if user_config.exists():
        settings.load_config_file(user_config)

    # Load project config if it exists
    project_config = Path('config.yaml')
    if project_config.exists():
        settings.load_config_file(project_config)

    return settings