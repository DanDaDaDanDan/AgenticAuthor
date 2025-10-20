"""
Robust YAML parsing utilities for handling LLM-generated content.

This module provides fault-tolerant YAML parsing that can handle common
LLM formatting issues while extracting content reliably.
"""

import yaml
import re
from typing import Dict, Any, Optional, List
from pathlib import Path


class RobustYAMLParser:
    """
    Parse YAML with multiple fallback strategies for LLM-generated content.

    Strategy:
    1. Try strict YAML parsing (fast path)
    2. Sanitize and retry (remove fences, fix indentation)
    3. Pattern-based extraction (regex fallback)
    4. Fail only if content is truly missing
    """

    @staticmethod
    def sanitize_yaml_text(text: str) -> str:
        """
        Clean common LLM formatting issues from YAML text.

        Args:
            text: Raw text that should be YAML

        Returns:
            Cleaned text ready for YAML parsing
        """
        if not text:
            return text

        # Remove markdown code fences (even though prompt says not to add them)
        text = re.sub(r'^```ya?ml\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)

        # Remove any leading/trailing backticks
        text = text.strip('`')

        # Fix Windows line endings
        text = text.replace('\r\n', '\n')

        # Fix tabs (convert to spaces for consistency)
        text = text.replace('\t', '  ')

        # Fix smart quotes that sometimes appear
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Remove any BOM characters
        text = text.replace('\ufeff', '')

        # Ensure proper spacing after colons in simple key-value pairs
        # But don't touch colons in quoted strings or multi-line values
        lines = text.split('\n')
        fixed_lines = []
        in_multiline = False

        for line in lines:
            # Check if we're in a multi-line string
            if '|' in line or '>' in line:
                in_multiline = True
            elif line and not line[0].isspace() and ':' in line:
                in_multiline = False

            # Fix spacing after colons in key-value pairs
            if not in_multiline and ':' in line and not line.strip().startswith('#'):
                # Only fix if it looks like a key-value pair
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*:', line.strip()):
                    line = re.sub(r':(?! )', ': ', line)

            fixed_lines.append(line)

        text = '\n'.join(fixed_lines)

        return text.strip()

    @staticmethod
    def extract_metadata_section(text: str) -> Dict[str, Any]:
        """
        Extract metadata section using flexible patterns.

        Args:
            text: Text containing metadata section

        Returns:
            Dict with metadata fields
        """
        metadata = {}

        # Extract common fields with patterns
        patterns = {
            'genre': r'genre:\s*["\']?([^"\'\n]+)["\']?',
            'subgenre': r'subgenre:\s*["\']?([^"\'\n]+)["\']?',
            'target_word_count': r'target_word_count:\s*(\d+)',
            'chapter_count': r'chapter_count:\s*(\d+)',
            'pacing': r'pacing:\s*["\']?([^"\'\n]+)["\']?',
            'tone': r'tone:\s*["\']?([^"\'\n]+)["\']?',
            'narrative_style': r'narrative_style:\s*["\']?([^"\'\n]+)["\']?',
            'setting_period': r'setting_period:\s*["\']?([^"\'\n]+)["\']?',
            'setting_location': r'setting_location:\s*["\']?([^"\'\n]+)["\']?',
            'target_audience': r'target_audience:\s*["\']?([^"\'\n]+)["\']?',
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Convert numbers
                if field in ['target_word_count', 'chapter_count']:
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                metadata[field] = value

        # Extract themes (list)
        themes_match = re.search(r'themes:\s*\n((?:\s*-\s*[^\n]+\n?)+)', text, re.MULTILINE)
        if themes_match:
            themes_text = themes_match.group(1)
            themes = []
            for line in themes_text.split('\n'):
                if line.strip().startswith('-'):
                    theme = line.strip().lstrip('-').strip().strip('"\'')
                    if theme:
                        themes.append(theme)
            if themes:
                metadata['themes'] = themes

        # Extract act_weights if present
        weights_match = re.search(r'act_weights:\s*\n\s*-\s*([\d.]+)\s*\n\s*-\s*([\d.]+)\s*\n\s*-\s*([\d.]+)', text)
        if weights_match:
            try:
                metadata['act_weights'] = [
                    float(weights_match.group(1)),
                    float(weights_match.group(2)),
                    float(weights_match.group(3))
                ]
            except ValueError:
                pass

        return metadata

    @staticmethod
    def extract_characters_section(text: str) -> List[Dict[str, Any]]:
        """
        Extract characters section using flexible patterns.

        Args:
            text: Text containing characters section

        Returns:
            List of character dicts
        """
        characters = []

        # Find each character block (starts with "- name:")
        character_pattern = r'-\s+name:\s*["\']?([^"\'\n]+)["\']?(.*?)(?=(?:-\s+name:|world:|$))'
        matches = re.finditer(character_pattern, text, re.DOTALL)

        for match in matches:
            char_name = match.group(1).strip()
            char_text = match.group(2)

            character = {'name': char_name}

            # Extract character fields
            fields = {
                'role': r'role:\s*["\']?([^"\'\n]+)["\']?',
                'background': r'background:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*\w+:|$)',
                'motivation': r'motivation:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*\w+:|$)',
                'character_arc': r'character_arc:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*\w+:|$)',
                'internal_conflict': r'internal_conflict:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*\w+:|$)',
            }

            for field, pattern in fields.items():
                field_match = re.search(pattern, char_text, re.DOTALL | re.IGNORECASE)
                if field_match:
                    value = field_match.group(1).strip()
                    # Clean up multi-line values
                    if field != 'role':
                        value = re.sub(r'\n\s+', ' ', value).strip()
                    character[field] = value

            # Extract personality traits
            traits_match = re.search(r'personality_traits:\s*\n((?:\s*-\s*[^\n]+\n?)+)', char_text, re.MULTILINE)
            if traits_match:
                traits_text = traits_match.group(1)
                traits = []
                for line in traits_text.split('\n'):
                    if line.strip().startswith('-'):
                        trait = line.strip().lstrip('-').strip().strip('"\'')
                        if trait:
                            traits.append(trait)
                if traits:
                    character['personality_traits'] = traits

            # Extract relationships
            rel_pattern = r'relationships:\s*\n((?:\s*-\s*character:.*?\n\s*dynamic:.*?\n?)+)'
            rel_match = re.search(rel_pattern, char_text, re.MULTILINE)
            if rel_match:
                rel_text = rel_match.group(1)
                relationships = []

                # Parse each relationship
                rel_items = re.finditer(r'-\s*character:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*dynamic:\s*["\']?([^"\'\n]+)["\']?', rel_text)
                for rel_item in rel_items:
                    relationships.append({
                        'character': rel_item.group(1).strip(),
                        'dynamic': rel_item.group(2).strip()
                    })

                if relationships:
                    character['relationships'] = relationships

            if character.get('name'):  # Only add if we at least have a name
                characters.append(character)

        return characters

    @staticmethod
    def extract_world_section(text: str) -> Dict[str, Any]:
        """
        Extract world section using flexible patterns.

        Args:
            text: Text containing world section

        Returns:
            Dict with world information
        """
        world = {}

        # Extract setting overview
        overview_match = re.search(r'setting_overview:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*\w+:|$)', text, re.DOTALL)
        if overview_match:
            world['setting_overview'] = re.sub(r'\n\s+', ' ', overview_match.group(1)).strip()

        # Extract key locations
        locations = []
        loc_pattern = r'-\s+name:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*description:\s*["\']?(.+?)["\']?(?=\n\s*-|\n\s*\w+:|$)'
        loc_matches = re.finditer(loc_pattern, text, re.DOTALL)

        for match in loc_matches:
            locations.append({
                'name': match.group(1).strip(),
                'description': re.sub(r'\n\s+', ' ', match.group(2)).strip()
            })

        if locations:
            world['key_locations'] = locations

        # Extract systems and rules
        systems = []
        sys_pattern = r'-\s+system:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*description:\s*[|>]?\s*\n?\s*(.+?)(?=\n\s*-|\n\s*\w+:|$)'
        sys_matches = re.finditer(sys_pattern, text, re.DOTALL)

        for match in sys_matches:
            systems.append({
                'system': match.group(1).strip(),
                'description': re.sub(r'\n\s+', ' ', match.group(2)).strip()
            })

        if systems:
            world['systems_and_rules'] = systems

        # Extract social context (list)
        social_match = re.search(r'social_context:\s*\n((?:\s*-\s*[^\n]+\n?)+)', text, re.MULTILINE)
        if social_match:
            social_text = social_match.group(1)
            social_context = []
            for line in social_text.split('\n'):
                if line.strip().startswith('-'):
                    context = line.strip().lstrip('-').strip().strip('"\'')
                    if context:
                        social_context.append(context)
            if social_context:
                world['social_context'] = social_context

        return world

    @classmethod
    def parse_foundation(cls, text: str, debug_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Parse foundation YAML with multiple fallback strategies.

        Args:
            text: Raw text that should contain foundation YAML
            debug_path: Optional path to save debug files on failure

        Returns:
            Dict with metadata, characters, and world sections

        Raises:
            Exception: Only if content is truly missing or unparseable
        """
        from ..utils.logging import get_logger
        logger = get_logger()

        # Save raw input for debugging if path provided
        if debug_path:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            raw_file = debug_path.parent / f"{debug_path.stem}_raw.txt"
            raw_file.write_text(text, encoding='utf-8')

        # STRATEGY 1: Try strict YAML parsing (fast path)
        try:
            result = yaml.safe_load(text)
            if isinstance(result, dict) and all(k in result for k in ['metadata', 'characters', 'world']):
                if logger:
                    logger.debug("Foundation parsed successfully via strict YAML")
                return result
        except yaml.YAMLError as e:
            if logger:
                logger.debug(f"Strict YAML parsing failed: {e}")

        # STRATEGY 2: Sanitize and retry
        sanitized = cls.sanitize_yaml_text(text)
        if sanitized != text:
            try:
                result = yaml.safe_load(sanitized)
                if isinstance(result, dict) and all(k in result for k in ['metadata', 'characters', 'world']):
                    if logger:
                        logger.debug("Foundation parsed successfully after sanitization")
                    if debug_path:
                        sanitized_file = debug_path.parent / f"{debug_path.stem}_sanitized.yaml"
                        sanitized_file.write_text(sanitized, encoding='utf-8')
                    return result
            except yaml.YAMLError as e:
                if logger:
                    logger.debug(f"Sanitized YAML parsing failed: {e}")

        # STRATEGY 3: Pattern-based extraction
        if logger:
            logger.info("Falling back to pattern-based foundation extraction")

        foundation = {}

        # Find the three main sections
        metadata_match = re.search(r'metadata:(.*?)(?=characters:|world:|$)', text, re.DOTALL)
        characters_match = re.search(r'characters:(.*?)(?=world:|$)', text, re.DOTALL)
        world_match = re.search(r'world:(.*?)(?=$)', text, re.DOTALL)

        # Extract metadata
        if metadata_match:
            foundation['metadata'] = cls.extract_metadata_section(metadata_match.group(1))
        else:
            raise Exception("Failed to extract metadata section from foundation")

        # Extract characters
        if characters_match:
            foundation['characters'] = cls.extract_characters_section(characters_match.group(1))
        else:
            raise Exception("Failed to extract characters section from foundation")

        # Extract world
        if world_match:
            foundation['world'] = cls.extract_world_section(world_match.group(1))
        else:
            raise Exception("Failed to extract world section from foundation")

        # Validate we got meaningful content
        if not foundation.get('metadata'):
            raise Exception("Metadata section is empty")
        if not foundation.get('characters'):
            raise Exception("Characters section is empty")
        if not foundation.get('world'):
            raise Exception("World section is empty")

        if logger:
            logger.info(f"Successfully extracted foundation via patterns: "
                       f"{len(foundation.get('metadata', {}))} metadata fields, "
                       f"{len(foundation.get('characters', []))} characters, "
                       f"{len(foundation.get('world', {}))} world fields")

        # Save the reconstructed foundation if debug path provided
        if debug_path:
            reconstructed_file = debug_path.parent / f"{debug_path.stem}_reconstructed.yaml"
            reconstructed_file.write_text(
                yaml.dump(foundation, default_flow_style=False, allow_unicode=True),
                encoding='utf-8'
            )

        return foundation


def parse_foundation_robust(text: str, project_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Convenience function to parse foundation with robust fallbacks.

    Args:
        text: Raw foundation text
        project_path: Optional project path for debug files

    Returns:
        Parsed foundation dict
    """
    debug_path = None
    if project_path:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = project_path / '.agentic' / 'debug' / f'foundation_{timestamp}.yaml'

    return RobustYAMLParser.parse_foundation(text, debug_path)