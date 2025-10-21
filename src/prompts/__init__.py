"""Prompt management system for AgenticAuthor LLM calls."""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from jinja2 import Environment, FileSystemLoader, Template


class PromptLoader:
    """
    Load and render Jinja2 templates for LLM prompts.

    Supports system/user prompt separation with metadata (temperature, format, etc.).
    Templates use [SYSTEM] and [USER] sections to separate prompt types.

    Usage:
        loader = PromptLoader()
        prompts = loader.render("generation/prose_generation", chapter_number=5, ...)

        # Returns: {"system": "...", "user": "..."}
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Path to prompts directory (defaults to src/prompts/)
        """
        if prompts_dir is None:
            # Default to src/prompts/ relative to this file
            prompts_dir = Path(__file__).parent

        self.prompts_dir = Path(prompts_dir)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )

        # Load config
        self.config = self._load_config()

        # Template cache
        self._template_cache: Dict[str, Template] = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load prompts/config.yaml with metadata for all prompts."""
        config_file = self.prompts_dir / "config.yaml"

        if not config_file.exists():
            # Return empty config if not found
            return {}

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _parse_template(self, template_content: str) -> Dict[str, str]:
        """
        Parse template content into system and user sections.

        Template format:
            [SYSTEM]
            System prompt here...

            [USER]
            User prompt here...

        Args:
            template_content: Raw template text

        Returns:
            Dict with 'system' and 'user' keys
        """
        system_prompt = ""
        user_prompt = ""

        # Split on section markers
        sections = template_content.split('[SYSTEM]')

        if len(sections) > 1:
            # Found [SYSTEM] marker
            remainder = sections[1]

            if '[USER]' in remainder:
                # Both sections present
                system_part, user_part = remainder.split('[USER]', 1)
                system_prompt = system_part.strip()
                user_prompt = user_part.strip()
            else:
                # Only system section
                system_prompt = remainder.strip()
        else:
            # No [SYSTEM] marker, check for [USER] only
            sections = template_content.split('[USER]')
            if len(sections) > 1:
                user_prompt = sections[1].strip()
            else:
                # No markers - treat entire content as user prompt
                user_prompt = template_content.strip()

        return {
            "system": system_prompt,
            "user": user_prompt
        }

    def render(self, prompt_name: str, **variables) -> Dict[str, str]:
        """
        Render a prompt template with variables.

        Args:
            prompt_name: Name of prompt (e.g., "generation/prose_generation")
            **variables: Template variables to render

        Returns:
            Dict with 'system' and 'user' keys containing rendered prompts

        Raises:
            FileNotFoundError: If template not found
            jinja2.TemplateError: If template rendering fails
        """
        # Add .j2 extension if not present
        template_name = prompt_name if prompt_name.endswith('.j2') else f"{prompt_name}.j2"

        # Check cache first
        if template_name not in self._template_cache:
            # Load template
            template = self.env.get_template(template_name)
            self._template_cache[template_name] = template

        template = self._template_cache[template_name]

        # Render template
        rendered = template.render(**variables)

        # Parse into system/user sections
        return self._parse_template(rendered)

    def get_metadata(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get metadata for a prompt (temperature, format, etc.).

        Args:
            prompt_name: Name of prompt (without .j2 extension)

        Returns:
            Dict with metadata (temperature, format, reserve_tokens, etc.)
        """
        # Remove .j2 extension if present
        key = prompt_name.replace('.j2', '')

        return self.config.get(key, {})

    def get_temperature(self, prompt_name: str, default: float = 0.7) -> float:
        """
        Get temperature for a prompt.

        Args:
            prompt_name: Name of prompt
            default: Default temperature if not configured

        Returns:
            Temperature value
        """
        metadata = self.get_metadata(prompt_name)
        return metadata.get('temperature', default)

    def get_format(self, prompt_name: str, default: str = "text") -> str:
        """
        Get expected output format for a prompt.

        Args:
            prompt_name: Name of prompt
            default: Default format if not configured

        Returns:
            Format string (e.g., "text", "yaml", "json")
        """
        metadata = self.get_metadata(prompt_name)
        return metadata.get('format', default)

    def get_reserve_tokens(self, prompt_name: str, default: Optional[int] = None) -> Optional[int]:
        """
        Get reserve tokens for a prompt (used for dynamic max_tokens calculation).

        Args:
            prompt_name: Name of prompt
            default: Default reserve_tokens if not configured

        Returns:
            Reserve tokens value or None
        """
        metadata = self.get_metadata(prompt_name)
        return metadata.get('reserve_tokens', default)


# Global loader instance (singleton pattern)
_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """
    Get global PromptLoader instance (singleton).

    Returns:
        PromptLoader instance
    """
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader
