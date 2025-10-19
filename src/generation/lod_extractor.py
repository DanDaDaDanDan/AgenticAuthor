"""LOD response extraction - pure YAML parsing without I/O.

This module provides pure extraction of structured data from LLM responses.
NO file saving, NO culling, NO side effects.

Generators are responsible for:
- Saving extracted data to files
- Culling downstream content (using CullManager)
- Managing project state

The extractor is a pure function: String in → Dict out.
"""

import yaml
from typing import Dict, Any


class LODResponseExtractor:
    """Extract structured data from LLM YAML responses (pure function, no I/O)."""

    def extract(self, response: str, target: str) -> Dict[str, Any]:
        """
        Extract structured data from LLM YAML response.

        Pure function: String in → Dict out (no side effects).
        No saving, no culling, no file I/O.

        Args:
            response: Raw LLM response (may include markdown fences)
            target: What we were generating (premise/treatment/chapters/prose)

        Returns:
            Parsed YAML dict

        Raises:
            ValueError: If response is invalid or missing expected sections
        """
        # Strip markdown fences
        response = self._strip_markdown_fences(response)

        # Parse YAML
        try:
            data = yaml.safe_load(response)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse LLM response as YAML: {e}")

        if not isinstance(data, dict):
            raise ValueError(f"Expected YAML dict, got {type(data)}")

        # Validate structure
        self._validate_response(data, target)

        return data

    def _validate_response(self, data: Dict[str, Any], target: str):
        """
        Validate that the response has the expected structure.

        Args:
            data: Parsed YAML data
            target: What LOD we were generating/iterating

        Raises:
            ValueError: If response is missing expected sections
        """
        # Check that target LOD is present
        if target == 'premise':
            if 'premise' not in data:
                raise ValueError("Response missing 'premise' section")
            if not isinstance(data['premise'], dict) or 'text' not in data['premise']:
                raise ValueError("Premise section must have 'text' field")

        elif target == 'treatment':
            # Treatment generation returns ONLY treatment (not premise)
            if 'treatment' not in data:
                raise ValueError("Response missing 'treatment' section")
            if not isinstance(data['treatment'], dict) or 'text' not in data['treatment']:
                raise ValueError("Treatment section must have 'text' field")

        elif target == 'chapters':
            # Chapters can be in multiple formats - just ensure chapters section exists
            if 'chapters' not in data:
                raise ValueError("Response missing 'chapters' section")

            # Detect format based on presence of metadata
            if 'metadata' in data:
                # NEW self-contained format - validate required sections
                required_sections = ['metadata', 'characters', 'world', 'chapters']
                missing = [s for s in required_sections if s not in data]
                if missing:
                    raise ValueError(f"New chapters format missing required sections: {', '.join(missing)}")

                if not isinstance(data['chapters'], list):
                    raise ValueError("In new format, chapters must be a list")

                # Deep structural validation for new format
                self._validate_new_chapters_structure(data)

            # OLD format - basic check
            elif not isinstance(data['chapters'], (list, dict)):
                raise ValueError("Chapters section must be a list or dict")

        elif target == 'prose':
            if 'prose' not in data:
                raise ValueError("Response missing 'prose' section")
            if not isinstance(data['prose'], list):
                raise ValueError("Prose section must be a list")

    def _validate_new_chapters_structure(self, data: Dict[str, Any]):
        """
        Deep structural validation for new self-contained chapters format.

        Args:
            data: Parsed chapters YAML data in new format

        Raises:
            ValueError: If structure is invalid or missing required fields
        """
        errors = []

        # Validate metadata section
        metadata = data.get('metadata', {})
        if not isinstance(metadata, dict):
            errors.append("metadata must be a dict")
        else:
            required_meta_fields = ['genre', 'tone', 'pacing', 'themes', 'narrative_style', 'target_word_count']
            for field in required_meta_fields:
                if field not in metadata:
                    errors.append(f"metadata missing required field: {field}")

        # Validate characters section
        characters = data.get('characters', [])
        if not isinstance(characters, list):
            errors.append("characters must be a list")
        elif len(characters) == 0:
            errors.append("characters list is empty - need at least protagonist")
        else:
            for i, char in enumerate(characters):
                if not isinstance(char, dict):
                    errors.append(f"characters[{i}] must be a dict")
                    continue

                required_char_fields = ['name', 'role', 'background', 'motivation']
                for field in required_char_fields:
                    if field not in char:
                        errors.append(f"characters[{i}] ({char.get('name', 'unknown')}) missing: {field}")

        # Validate world section
        world = data.get('world', {})
        if not isinstance(world, dict):
            errors.append("world must be a dict")
        else:
            required_world_fields = ['setting_overview', 'key_locations']
            for field in required_world_fields:
                if field not in world:
                    errors.append(f"world missing required field: {field}")

        # Validate chapters section
        chapters = data.get('chapters', [])
        if not isinstance(chapters, list):
            errors.append("chapters must be a list")
        elif len(chapters) == 0:
            errors.append("chapters list is empty")
        else:
            for i, chapter in enumerate(chapters):
                if not isinstance(chapter, dict):
                    errors.append(f"chapters[{i}] must be a dict")
                    continue

                # Base required fields (support both scenes and key_events formats)
                required_base_fields = ['number', 'title', 'summary', 'word_count_target']
                for field in required_base_fields:
                    if field not in chapter:
                        errors.append(f"chapters[{i}] missing: {field}")

                # Check for content field (scenes OR key_events)
                has_scenes = 'scenes' in chapter
                has_key_events = 'key_events' in chapter

                if not has_scenes and not has_key_events:
                    errors.append(f"chapters[{i}] missing both 'scenes' and 'key_events' (one required)")

                # Validate scenes format if present
                if has_scenes:
                    if not isinstance(chapter['scenes'], list):
                        errors.append(f"chapters[{i}].scenes must be a list")
                    elif len(chapter['scenes']) == 0:
                        errors.append(f"chapters[{i}].scenes is empty")

                # Validate key_events format if present (legacy support)
                if has_key_events:
                    if not isinstance(chapter['key_events'], list):
                        errors.append(f"chapters[{i}].key_events must be a list")
                    elif len(chapter['key_events']) == 0:
                        errors.append(f"chapters[{i}].key_events is empty")

        # Raise aggregated errors
        if errors:
            error_msg = "New chapters format validation failed:\n  - " + "\n  - ".join(errors)
            raise ValueError(error_msg)

    def _strip_markdown_fences(self, content: str) -> str:
        """
        Strip markdown code fences if LLM wrapped output in ```yaml or ``` blocks.

        Args:
            content: Raw content from LLM

        Returns:
            Content with code fences removed
        """
        content = content.strip()

        # Remove opening fence (```yaml, ```markdown, ```md, or just ```)
        if content.startswith('```'):
            lines = content.split('\n')
            # Remove first line if it's a fence
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            # Remove last line if it's a fence
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines)

        return content.strip()
