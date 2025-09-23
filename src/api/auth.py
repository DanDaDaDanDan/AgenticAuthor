"""API authentication utilities."""
import os
from typing import Optional


def validate_api_key(api_key: Optional[str] = None) -> str:
    """
    Validate and return the OpenRouter API key.

    Args:
        api_key: Optional API key to validate. If None, reads from environment.

    Returns:
        Valid API key

    Raises:
        ValueError: If API key is invalid or missing
    """
    key = api_key or os.getenv('OPENROUTER_API_KEY', '')

    if not key:
        raise ValueError(
            "OpenRouter API key not found. "
            "Set OPENROUTER_API_KEY environment variable or pass it directly."
        )

    if not key.startswith('sk-or-'):
        raise ValueError(
            f"Invalid OpenRouter API key format. "
            f"Key must start with 'sk-or-', got: {key[:10]}..."
        )

    return key