"""Markdown extraction utilities for parsing structured data from natural language generation."""

import re
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)


class MarkdownExtractor:
    """
    Extract structured data from markdown-formatted LLM responses.

    Philosophy:
    - LLMs write better content when focused on storytelling, not syntax
    - Markdown is more natural than YAML for creative writing
    - Pattern matching can extract structured data post-hoc
    - Graceful degradation: always get something useful, even if format varies
    """

    @classmethod
    def split_foundation_and_chapters(cls, markdown_text: str) -> Dict[str, Any]:
        """
        Split combined markdown into foundation and individual chapter sections.

        Args:
            markdown_text: Combined markdown with foundation + all chapters

        Returns:
            Dict with 'foundation' (str) and 'chapters' (list of str) keys
        """
        # Find first chapter header
        chapter_pattern = r'#{1,2}\s*Chapter\s*\d+'
        first_chapter_match = re.search(chapter_pattern, markdown_text, re.IGNORECASE)

        if not first_chapter_match:
            # No chapters found - entire text is foundation
            return {
                'foundation': markdown_text.strip(),
                'chapters': []
            }

        # Split foundation and chapters content
        foundation_text = markdown_text[:first_chapter_match.start()].strip()
        chapters_text = markdown_text[first_chapter_match.start():]

        # Split chapters by chapter headers
        chapter_splits = re.split(chapter_pattern, chapters_text, flags=re.IGNORECASE)

        # Process chapter sections
        chapter_sections = []
        # chapter_splits[0] is empty (before first split)
        # Odd indices (1, 3, 5...) are chapter numbers from regex groups
        # Even indices (2, 4, 6...) are chapter content

        # Actually, re.split with a pattern doesn't work like that
        # Let me use finditer to get chapter positions

        chapter_matches = list(re.finditer(chapter_pattern, chapters_text, re.IGNORECASE))

        for i, match in enumerate(chapter_matches):
            start_pos = match.start()
            # End position is start of next chapter or end of text
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(chapters_text)

            chapter_section = chapters_text[start_pos:end_pos].strip()

            # Remove trailing separator if present
            chapter_section = re.sub(r'\n---\s*$', '', chapter_section).strip()

            chapter_sections.append(chapter_section)

        return {
            'foundation': foundation_text,
            'chapters': chapter_sections
        }

    @classmethod
    def extract_foundation(cls, markdown_text: str) -> Dict[str, Any]:
        """
        Extract foundation data (metadata, characters, world) from markdown.

        Expected format:
        # Metadata
        - Genre: ...
        - Tone: ...
        - Themes: ...

        # Characters
        ## Character Name
        **Role:** ...
        **Background:** ...

        # World
        ## Setting
        ...

        Args:
            markdown_text: Markdown-formatted foundation text

        Returns:
            Dict with metadata, characters, world sections
        """
        foundation = {
            'metadata': {},
            'characters': [],
            'world': {}
        }

        # Extract metadata section
        metadata_match = re.search(
            r'#\s*Metadata\s*\n(.*?)(?=#\s*Characters|\Z)',
            markdown_text,
            re.IGNORECASE | re.DOTALL
        )
        if metadata_match:
            foundation['metadata'] = cls._extract_metadata(metadata_match.group(1))

        # Extract characters section
        characters_match = re.search(
            r'#\s*Characters\s*\n(.*?)(?=#\s*World|\Z)',
            markdown_text,
            re.IGNORECASE | re.DOTALL
        )
        if characters_match:
            foundation['characters'] = cls._extract_characters(characters_match.group(1))

        # Extract world section
        world_match = re.search(
            r'#\s*World\s*\n(.*?)(?=#\s*Chapters|\Z)',
            markdown_text,
            re.IGNORECASE | re.DOTALL
        )
        if world_match:
            foundation['world'] = cls._extract_world(world_match.group(1))

        # Validate extraction
        cls._validate_foundation(foundation, markdown_text)

        return foundation

    @classmethod
    def extract_chapters(cls, markdown_text: str) -> List[Dict[str, Any]]:
        """
        Extract chapter outlines from markdown.

        Supports THREE formats:

        BEAT SHEET FORMAT (current):
        # Chapter 1: Title
        **Act:** Act I
        **Beats:**
        - Beat 1: Action → Result
        - Beat 2: Action → Result
        **Character Development:**
        - Development 1
        **Emotional Beat:** Emotional core

        PROSE SUMMARY FORMAT (previous):
        # Chapter 1: Title
        **Act:** Act I
        [200-300 word prose summary...]

        OLD STRUCTURED FORMAT (legacy):
        # Chapter 1: Title
        **POV:** Character name
        **Act:** Act I/II/III
        **Summary:** Brief summary...
        ## Key Events
        1. Event one...

        Args:
            markdown_text: Markdown-formatted chapter text

        Returns:
            List of chapter dicts
        """
        chapters = []

        # Split by chapter headers (# Chapter N: or ## Chapter N:)
        chapter_pattern = r'#{1,2}\s*Chapter\s*(\d+)[:\s]*(.*?)\n'
        chapter_splits = re.split(chapter_pattern, markdown_text)

        # Process each chapter (skip first element if empty)
        i = 1 if chapter_splits[0].strip() == '' else 0
        while i < len(chapter_splits) - 2:
            try:
                chapter_num = int(chapter_splits[i])
            except (ValueError, TypeError):
                # If we can't parse the chapter number, the format is wrong
                # Validate will handle the error message
                break
            chapter_title = chapter_splits[i + 1].strip()
            chapter_content = chapter_splits[i + 2]

            # Try to extract fields from all formats
            pov = cls._extract_field(chapter_content, 'POV')
            act = cls._extract_field(chapter_content, 'Act')
            summary = cls._extract_field(chapter_content, 'Summary')

            # Extract beats (beat sheet format) - use list_field not list_section
            # Beats are formatted as **Beats:** followed by bullet points, not as a section header
            # IMPORTANT: Extract beats BEFORE prose summary, since prose summary extraction
            # is greedy and will consume everything after Act: including beats
            beats = cls._extract_list_field(chapter_content, 'Beats?')
            emotional_beat = cls._extract_field(chapter_content, 'Emotional Beat')

            # If no explicit Summary field and no beats, extract prose summary (prose format)
            # This is everything after Act: until next chapter or ---
            # Only do this if beats don't exist, to avoid consuming beat sheet content
            if not summary and not beats and act:
                summary = cls._extract_prose_summary(chapter_content)

            # Extract character development (both singular and plural forms)
            character_dev = cls._extract_list_section(chapter_content, 'Character Development')

            chapter_data = {
                'number': chapter_num,
                'title': chapter_title,
                'pov': pov,
                'act': act,
                'summary': summary,
                'beats': beats,  # NEW: beat sheet format
                'emotional_beat': emotional_beat,  # NEW: beat sheet format
                'key_events': cls._extract_list_section(chapter_content, 'Key Events'),
                'character_developments': character_dev,  # Works for both singular/plural
                'relationship_beats': cls._extract_list_section(chapter_content, 'Relationships?|Relationship Beats?'),
                'tension_points': cls._extract_list_section(chapter_content, 'Tension Points?'),
                'sensory_details': cls._extract_list_section(chapter_content, 'Sensory Details?'),
                'subplot_threads': cls._extract_list_section(chapter_content, 'Subplot Threads?')
            }

            chapters.append(chapter_data)
            i += 3

        # Validate extraction
        cls._validate_chapters(chapters, markdown_text)

        return chapters

    @classmethod
    def _extract_metadata(cls, text: str) -> Dict[str, Any]:
        """Extract metadata fields from text."""
        metadata = {}

        # Common fields to look for
        # Note: target_word_count and chapter_count are calculated values, not LLM-generated
        fields = [
            'genre', 'subgenre', 'tone', 'pacing', 'themes',
            'story_structure', 'narrative_style', 'target_audience',
            'setting_period', 'setting_location', 'content_warnings'
        ]

        for field in fields:
            # Try various formats: "Field: value", "- Field: value", "**Field:** value"
            field_display = field.replace('_', ' ').title()
            patterns = [
                rf'\*\*{re.escape(field_display)}:\*\*\s*([^\n]+)',  # **Field Name:** format (correct markdown)
                rf'{re.escape(field_display)}:\s*([^\n]+)',  # Field Name: format
                rf'{re.escape(field)}:\s*([^\n]+)',  # field_name: format
                rf'-\s*{re.escape(field)}:\s*([^\n]+)'  # - field_name: format
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Clean up any leading/trailing asterisks from markdown bold
                    value = value.strip('*').strip()

                    # Handle lists (themes, content_warnings)
                    if field in ['themes', 'content_warnings']:
                        # Check if it's already a list format
                        if value.startswith('['):
                            metadata[field] = cls._parse_list_value(value)
                        # Check if value is empty (just found the field with no inline value)
                        elif not value or value == '**':
                            # Extract subsequent bullet points
                            list_items = cls._extract_bullet_list_after(text, match.end())
                            if list_items:
                                metadata[field] = list_items
                            else:
                                metadata[field] = []
                        else:
                            # Value on same line, check for more bullet points
                            # Clean the value - remove bullet prefix if present
                            clean_value = re.sub(r'^\s*[-*]\s*', '', value).strip()
                            list_items = cls._extract_bullet_list_after(text, match.end())
                            if list_items:
                                metadata[field] = [clean_value] + list_items if clean_value else list_items
                            else:
                                metadata[field] = [clean_value] if clean_value else []
                    else:
                        # All other fields stored as-is
                        metadata[field] = value
                    break

        return metadata

    @classmethod
    def _extract_characters(cls, text: str) -> List[Dict[str, Any]]:
        """Extract character profiles from text."""
        characters = []

        # Split by character headers (## Name or ### Name)
        char_pattern = r'#{2,3}\s*(.*?)\n'
        char_splits = re.split(char_pattern, text)

        i = 1 if char_splits[0].strip() == '' else 0
        while i < len(char_splits) - 1:
            char_name = char_splits[i].strip()
            char_content = char_splits[i + 1]

            character = {
                'name': char_name,
                'role': cls._extract_field(char_content, 'Role'),
                'background': cls._extract_field(char_content, 'Background', multiline=True),
                'motivation': cls._extract_field(char_content, 'Motivation', multiline=True),
                'character_arc': cls._extract_field(char_content, 'Character Arc|Arc', multiline=True),
                'personality_traits': cls._extract_list_field(char_content, 'Personality Traits?|Traits'),
                'internal_conflict': cls._extract_field(char_content, 'Internal Conflict', multiline=True),
                'relationships': cls._extract_relationships(char_content)
            }

            characters.append(character)
            i += 2

        return characters

    @classmethod
    def _extract_world(cls, text: str) -> Dict[str, Any]:
        """Extract world-building information from text."""
        world = {
            'setting_overview': cls._extract_field(text, 'Setting Overview|Overview', multiline=True),
            'key_locations': cls._extract_locations(text),
            'systems_and_rules': cls._extract_systems(text),
            'social_context': cls._extract_list_section(text, 'Social Context')
        }

        return world

    @classmethod
    def _extract_prose_summary(cls, text: str) -> Optional[str]:
        """
        Extract prose summary from new format (everything after Act: until separator or end).

        Args:
            text: Chapter content text

        Returns:
            Prose summary or None
        """
        # Find the Act field
        act_match = re.search(r'\*\*Act:\*\*\s*[^\n]+\n', text, re.IGNORECASE)
        if not act_match:
            return None

        # Extract everything after Act until separator (---) or end
        start_pos = act_match.end()

        # Look for separator or end
        separator_match = re.search(r'\n---\n|^---$', text[start_pos:], re.MULTILINE)
        if separator_match:
            end_pos = start_pos + separator_match.start()
        else:
            end_pos = len(text)

        # Extract and clean
        summary = text[start_pos:end_pos].strip()

        # Remove any section headers that might have been included
        summary = re.sub(r'##\s+.*?\n', '', summary)

        return summary if summary else None

    @classmethod
    def _extract_field(cls, text: str, field_name: str, multiline: bool = False) -> Optional[str]:
        """Extract a single field value."""
        # Handle OR in field names (e.g., "Character Arc|Arc")
        field_options = field_name.split('|')

        for field_option in field_options:
            field_option = field_option.strip()
            # Try various formats - capture until newline or end
            # Note: Markdown bold is **Field:** not **Field**:
            if multiline:
                # For multiline, capture until double newline, next field, or end
                patterns = [
                    rf'^\*\*{re.escape(field_option)}:\*\*\s*(.*?)(?=\n\n|\*\*[^:]+:\*\*|##|$)',
                    rf'\*\*{re.escape(field_option)}:\*\*\s*(.*?)(?=\n\n|\*\*[^:]+:\*\*|##|$)',
                    rf'^{re.escape(field_option)}:\s*(.*?)(?=\n\n|\*\*[^:]+:\*\*|##|$)',
                ]
            else:
                # For single line, capture until newline
                patterns = [
                    rf'^\*\*{re.escape(field_option)}:\*\*\s*([^\n]+)',
                    rf'\*\*{re.escape(field_option)}:\*\*\s*([^\n]+)',
                    rf'^{re.escape(field_option)}:\s*([^\n]+)',
                ]

            flags = re.IGNORECASE | re.MULTILINE
            if multiline:
                flags |= re.DOTALL

            for pattern in patterns:
                match = re.search(pattern, text, flags)
                if match and match.group(1):
                    value = match.group(1).strip()
                    # Clean up excessive whitespace
                    if multiline:
                        value = re.sub(r'\n\s*\n', '\n', value)
                    return value

        return None

    @classmethod
    def _extract_list_field(cls, text: str, field_name: str) -> List[str]:
        """Extract a list field (like personality traits or beats)."""
        # Handle OR in field names (remove ? for optional plurals)
        field_name = field_name.replace('?', '')
        field_options = field_name.split('|')

        for field_option in field_options:
            field_option = field_option.strip()
            # Try multiple patterns to handle different markdown formats
            # **Field:** (markdown bold) or Field: (plain)
            patterns = [
                rf'\*\*{re.escape(field_option)}:\*\*\s*\n',  # **Beats:** (markdown bold)
                rf'{re.escape(field_option)}:?\s*\n',  # Beats: (plain)
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Extract bullet points after the field
                    return cls._extract_bullet_list_after(text, match.end())

        return []

    @classmethod
    def _extract_list_section(cls, text: str, section_name: str) -> List[str]:
        """Extract a list section (like Key Events)."""
        # Handle OR in section names (remove ? for optional plurals)
        section_name = section_name.replace('?', '')
        section_options = section_name.split('|')

        for section_option in section_options:
            section_option = section_option.strip()
            # Find section header - allow flexible matching
            # Build pattern without f-string conflict
            pattern = r'#{2,3}\s*' + re.escape(section_option) + r's?\s*\n'
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                # Find next section or end
                next_section = re.search(r'#{2,3}\s+', text[match.end():])
                end_pos = match.end() + next_section.start() if next_section else len(text)

                section_text = text[match.end():end_pos]

                # Extract numbered or bulleted items
                items = []

                # Try numbered list first (1. Item text)
                numbered_lines = []
                for line in section_text.split('\n'):
                    numbered_match = re.match(r'^\d+\.\s+(.+)', line)
                    if numbered_match:
                        numbered_lines.append(numbered_match.group(1).strip())

                if numbered_lines:
                    return numbered_lines

                # Try bullet points (- Item text)
                for line in section_text.split('\n'):
                    bullet_match = re.match(r'^[-*]\s+(.+)', line)
                    if bullet_match:
                        items.append(bullet_match.group(1).strip())

                return items

        return []

    @classmethod
    def _extract_bullet_list_after(cls, text: str, start_pos: int) -> List[str]:
        """Extract bullet points starting from a position."""
        items = []
        lines = text[start_pos:].split('\n')

        for line in lines:
            # Check if it's a bullet point
            bullet_match = re.match(r'^\s*[-*]\s*(.+)', line)
            if bullet_match:
                items.append(bullet_match.group(1).strip().strip('"'))
            elif items:
                # Stop at first non-bullet line after finding bullets
                break

        return items

    @classmethod
    def _extract_relationships(cls, text: str) -> List[Dict[str, str]]:
        """Extract character relationships."""
        relationships = []

        # Look for relationships section
        rel_match = re.search(r'Relationships?:?\s*\n', text, re.IGNORECASE)
        if rel_match:
            # Extract items after
            rel_text = text[rel_match.end():]

            # Look for pattern: "- Character: dynamic" or "- With Character: dynamic"
            rel_pattern = r'[-*]\s*(?:With\s+)?([^:]+):\s*(.*?)(?=\n[-*]|\n\n|$)'
            matches = re.findall(rel_pattern, rel_text, re.MULTILINE | re.DOTALL)

            for char_name, dynamic in matches:
                relationships.append({
                    'character': char_name.strip(),
                    'dynamic': dynamic.strip()
                })

        return relationships

    @classmethod
    def _extract_locations(cls, text: str) -> List[Dict[str, str]]:
        """Extract key locations."""
        locations = []

        # Look for Key Locations section - handle both **Key Locations:** and plain Key Locations:
        loc_patterns = [
            r'\*\*Key Locations?:\*\*',  # **Key Locations:**
            r'Key Locations?:',  # Key Locations:
        ]

        loc_match = None
        for pattern in loc_patterns:
            loc_match = re.search(pattern, text, re.IGNORECASE)
            if loc_match:
                break

        if loc_match:
            loc_text = text[loc_match.end():]

            # Look for pattern: "- **Location Name:** description"
            # Updated pattern to properly capture location items
            loc_pattern = r'[-*]\s*\*\*([^:]+):\*\*\s*([^\n]+)'
            matches = re.findall(loc_pattern, loc_text)

            for name, description in matches:
                locations.append({
                    'name': name.strip(),
                    'description': description.strip()
                })

        return locations

    @classmethod
    def _extract_systems(cls, text: str) -> List[Dict[str, str]]:
        """Extract systems and rules."""
        systems = []

        # Look for Systems section
        sys_match = re.search(r'Systems?(?: and Rules?)?:?\s*\n', text, re.IGNORECASE)
        if sys_match:
            sys_text = text[sys_match.end():]

            # Similar pattern to locations
            sys_pattern = r'(?:#{3}\s*|[-*]\s*\*\*)(.*?)(?:\*\*)?:\s*(.*?)(?=#{3}|[-*]\s*\*\*|\n\n|$)'
            matches = re.findall(sys_pattern, sys_text, re.MULTILINE | re.DOTALL)

            for name, description in matches:
                systems.append({
                    'system': name.strip(),
                    'description': description.strip()
                })

        return systems

    @classmethod
    def _parse_list_value(cls, value: str) -> List[str]:
        """Parse a bracketed list value like '[item1, item2, item3]'."""
        # Remove brackets
        value = value.strip('[]')
        # Split by comma and clean
        items = [item.strip().strip('"\'') for item in value.split(',')]
        return [item for item in items if item]  # Filter empty strings

    @classmethod
    def _parse_numeric_value(cls, value: str) -> int:
        """
        Parse numeric values that may include ranges or approximations.

        Handles formats like:
        - "20-25" -> 23 (midpoint, rounded up)
        - "20 to 25" -> 23 (midpoint, rounded up)
        - "80-100k" -> 90000 (handles k suffix in ranges)
        - "~20" -> 20
        - "around 20" -> 20
        - "approximately 25" -> 25
        - "20+" -> 20
        - "20,000" -> 20000
        - "20k" -> 20000

        Args:
            value: String containing a numeric value

        Returns:
            Parsed integer value
        """
        # Clean the value
        clean_value = value.strip().lower()

        # Remove commas from numbers like "20,000"
        clean_value = clean_value.replace(',', '')

        # Check for range patterns WITH k suffix (80-100k, 80k-100k)
        # First pattern: both have k (80k-100k)
        range_k_match = re.match(r'(\d+)k\s*[-–]\s*(\d+)k', clean_value)
        if range_k_match:
            start = int(range_k_match.group(1)) * 1000
            end = int(range_k_match.group(2)) * 1000
            # Return midpoint of range (rounded up for odd sums)
            return (start + end + 1) // 2

        # Second pattern: only end has k (80-100k) - interpret as thousands
        range_k_match = re.match(r'(\d+)\s*[-–]\s*(\d+)k', clean_value)
        if range_k_match:
            start = int(range_k_match.group(1)) * 1000  # assume k for consistency
            end = int(range_k_match.group(2)) * 1000
            # Return midpoint of range (rounded up for odd sums)
            return (start + end + 1) // 2

        # Handle thousands with 'k' suffix (for non-range values)
        if 'k' in clean_value:
            clean_value = clean_value.replace('k', '000')

        # Check for range patterns (20-25, 20 to 25, 20–25 with em dash)
        range_match = re.match(r'(\d+)\s*[-–]\s*(\d+)', clean_value)
        if not range_match:
            # Try "to" format
            range_match = re.match(r'(\d+)\s+to\s+(\d+)', clean_value)

        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            # Return midpoint of range (rounded up for odd sums)
            return (start + end + 1) // 2

        # Check for approximation patterns (~20, around 20, approximately 20, about 20)
        approx_match = re.match(r'(?:~|around|approximately|about|approx\.?)\s*(\d+)', clean_value)
        if approx_match:
            return int(approx_match.group(1))

        # Check for "20+" format
        plus_match = re.match(r'(\d+)\+', clean_value)
        if plus_match:
            return int(plus_match.group(1))

        # Try to extract first number found
        number_match = re.search(r'\d+', clean_value)
        if number_match:
            return int(number_match.group())

        # If all else fails, try stripping all non-digits (old behavior)
        digits_only = re.sub(r'[^\d]', '', value)
        if digits_only:
            return int(digits_only)

        # Return 0 if we can't parse anything
        raise ValueError(f"Could not parse numeric value from: {value}")

    @classmethod
    def _validate_foundation(cls, foundation: Dict[str, Any], markdown_text: str) -> None:
        """
        Validate extracted foundation data and raise warnings/errors for missing fields.

        Args:
            foundation: Extracted foundation dictionary
            markdown_text: Original markdown text (for debugging)

        Raises:
            ValueError: For critical missing fields
        """
        errors = []
        warnings = []

        # Check metadata
        metadata = foundation.get('metadata', {})
        if not metadata:
            errors.append("No metadata section found. Expected '# Metadata' section.")
        else:
            # Critical fields that should always be present
            # Note: target_word_count and chapter_count are calculated values, not stored in foundation
            critical_fields = ['genre']
            for field in critical_fields:
                if not metadata.get(field):
                    errors.append(f"Critical metadata field '{field}' is missing or null")

            # Important fields that should usually be present
            important_fields = ['themes', 'tone', 'pacing']
            for field in important_fields:
                if not metadata.get(field):
                    warnings.append(f"Important metadata field '{field}' is missing or empty")

        # Check characters
        characters = foundation.get('characters', [])
        if not characters:
            errors.append("No characters found. Expected '# Characters' section with character profiles.")
        else:
            for i, char in enumerate(characters):
                if not char.get('name'):
                    errors.append(f"Character {i+1} has no name")
                if not char.get('role'):
                    warnings.append(f"Character '{char.get('name', f'{i+1}')}' has no role")
                if not char.get('background'):
                    warnings.append(f"Character '{char.get('name', f'{i+1}')}' has no background")

        # Check world
        world = foundation.get('world', {})
        if not world or not world.get('setting_overview'):
            warnings.append("No world setting overview found. Expected '# World' section with setting details.")

        # Log warnings
        for warning in warnings:
            logger.warning(f"Markdown extraction warning: {warning}")

        # Raise error if critical issues found
        if errors:
            error_msg = "Markdown extraction failed with errors:\n" + "\n".join(f"  - {e}" for e in errors)
            if markdown_text and len(markdown_text) < 500:
                error_msg += f"\n\nReceived text:\n{markdown_text[:500]}..."
            raise ValueError(error_msg)

    @classmethod
    def _validate_chapters(cls, chapters: List[Dict[str, Any]], markdown_text: str) -> None:
        """
        Validate extracted chapter data and raise warnings/errors for missing fields.

        Args:
            chapters: List of extracted chapter dictionaries
            markdown_text: Original markdown text (for debugging)

        Raises:
            ValueError: For critical missing fields
        """
        if not chapters:
            # Check if there's any chapter-like content in the markdown
            if 'Chapter' in markdown_text or 'chapter' in markdown_text:
                raise ValueError(
                    "No chapters could be extracted but 'Chapter' text found in markdown. "
                    "Expected format: '# Chapter N: Title' or '## Chapter N: Title'"
                )
            else:
                raise ValueError(
                    "No chapters found in markdown. "
                    "Expected format: '# Chapter N: Title' or '## Chapter N: Title'"
                )

        errors = []
        warnings = []

        for chapter in chapters:
            num = chapter.get('number', '?')

            # Critical fields
            if not chapter.get('title'):
                errors.append(f"Chapter {num} has no title")

            # POV is optional (new format doesn't require it)
            if not chapter.get('pov'):
                logger.debug(f"Chapter {num} has no POV specified (optional in new format)")

            if not chapter.get('act'):
                warnings.append(f"Chapter {num} has no act specified")

            # Validate chapter content - THREE formats supported:
            # 1. BEAT SHEET (current): beats array (5-7 items) + emotional_beat
            # 2. PROSE SUMMARY (previous): summary (200-300 words)
            # 3. OLD STRUCTURED (legacy): summary + key_events

            summary = chapter.get('summary', '')
            beats = chapter.get('beats', [])
            key_events = chapter.get('key_events', [])
            summary_word_count = len(summary.split()) if summary else 0

            # At least ONE content format must be present
            if not summary and not beats and not key_events:
                errors.append(f"Chapter {num} has no content. Expected either beats, summary, or key_events.")

            # BEAT SHEET FORMAT validation
            if beats:
                logger.debug(f"Chapter {num} uses beat sheet format ({len(beats)} beats)")
                if len(beats) < 5:
                    warnings.append(f"Chapter {num} has only {len(beats)} beat(s). Expected 5-7 beats per chapter.")
                elif len(beats) > 7:
                    warnings.append(f"Chapter {num} has {len(beats)} beats. Expected 5-7 beats per chapter.")

                # Emotional beat should be present with beat sheet format
                if not chapter.get('emotional_beat'):
                    warnings.append(f"Chapter {num} uses beat sheet format but has no emotional beat")

            # PROSE SUMMARY FORMAT validation
            elif summary_word_count >= 100:
                logger.debug(f"Chapter {num} uses prose summary format ({summary_word_count} words)")
                # Prose summary is self-contained, no other validation needed

            # OLD STRUCTURED FORMAT validation
            elif summary_word_count < 100:
                # Short or no summary - old format, requires key_events
                if not key_events:
                    errors.append(f"Chapter {num} has brief/no summary and no beats. Expected '## Key Events' section with numbered or bulleted list.")
                elif len(key_events) < 2:
                    warnings.append(f"Chapter {num} has only {len(key_events)} key event(s). Consider adding more for better prose generation.")

                # Character development is important for old format
                if not chapter.get('character_developments'):
                    warnings.append(f"Chapter {num} has no character development notes")

        # Log warnings
        for warning in warnings:
            logger.warning(f"Markdown extraction warning: {warning}")

        # Raise error if critical issues found
        if errors:
            error_msg = "Chapter extraction failed with errors:\n" + "\n".join(f"  - {e}" for e in errors)
            if markdown_text and len(markdown_text) < 1000:
                error_msg += f"\n\nReceived text preview:\n{markdown_text[:1000]}..."
            raise ValueError(error_msg)


class MarkdownFormatter:
    """
    Format structured data into markdown for human readability.

    This is the inverse of MarkdownExtractor - takes structured data
    and formats it as clean, readable markdown.
    """

    @classmethod
    def format_foundation(cls, foundation: Dict[str, Any]) -> str:
        """Format foundation data as markdown."""
        sections = []

        # Metadata section
        if 'metadata' in foundation:
            sections.append(cls._format_metadata(foundation['metadata']))

        # Characters section
        if 'characters' in foundation:
            sections.append(cls._format_characters(foundation['characters']))

        # World section
        if 'world' in foundation:
            sections.append(cls._format_world(foundation['world']))

        return '\n\n'.join(sections)

    @classmethod
    def format_chapters(cls, chapters: List[Dict[str, Any]]) -> str:
        """Format chapter outlines as markdown."""
        chapter_sections = []

        for chapter in chapters:
            chapter_md = cls._format_chapter(chapter)
            chapter_sections.append(chapter_md)

        return '\n\n---\n\n'.join(chapter_sections)

    @classmethod
    def _format_metadata(cls, metadata: Dict[str, Any]) -> str:
        """Format metadata section."""
        lines = ['# Metadata\n']

        for key, value in metadata.items():
            # Format key nicely
            display_key = key.replace('_', ' ').title()

            if isinstance(value, list):
                lines.append(f'**{display_key}:**')
                for item in value:
                    lines.append(f'  - {item}')
            else:
                lines.append(f'**{display_key}:** {value}')

        return '\n'.join(lines)

    @classmethod
    def _format_characters(cls, characters: List[Dict[str, Any]]) -> str:
        """Format characters section."""
        lines = ['# Characters\n']

        for char in characters:
            lines.append(f"## {char['name']}\n")

            if char.get('role'):
                lines.append(f"**Role:** {char['role']}\n")

            if char.get('background'):
                lines.append(f"**Background:** {char['background']}\n")

            if char.get('motivation'):
                lines.append(f"**Motivation:** {char['motivation']}\n")

            if char.get('character_arc'):
                lines.append(f"**Character Arc:** {char['character_arc']}\n")

            if char.get('personality_traits'):
                lines.append('**Personality Traits:**')
                for trait in char['personality_traits']:
                    lines.append(f'  - {trait}')
                lines.append('')

            if char.get('internal_conflict'):
                lines.append(f"**Internal Conflict:** {char['internal_conflict']}\n")

            if char.get('relationships'):
                lines.append('**Relationships:**')
                for rel in char['relationships']:
                    lines.append(f"  - {rel['character']}: {rel['dynamic']}")
                lines.append('')

        return '\n'.join(lines)

    @classmethod
    def _format_world(cls, world: Dict[str, Any]) -> str:
        """Format world section."""
        lines = ['# World\n']

        if world.get('setting_overview'):
            lines.append(f"**Setting Overview:** {world['setting_overview']}\n")

        if world.get('key_locations'):
            lines.append('**Key Locations:**')
            for loc in world['key_locations']:
                lines.append(f"  - **{loc['name']}:** {loc['description']}")
            lines.append('')

        if world.get('systems_and_rules'):
            lines.append('**Systems and Rules:**')
            for sys in world['systems_and_rules']:
                lines.append(f"  - **{sys['system']}:** {sys['description']}")
            lines.append('')

        if world.get('social_context'):
            lines.append('**Social Context:**')
            for item in world['social_context']:
                lines.append(f'  - {item}')
            lines.append('')

        return '\n'.join(lines)

    @classmethod
    def _format_chapter(cls, chapter: Dict[str, Any]) -> str:
        """Format a single chapter."""
        lines = []

        # Chapter header
        lines.append(f"# Chapter {chapter['number']}: {chapter['title']}\n")

        # Basic info
        if chapter.get('pov'):
            lines.append(f"**POV:** {chapter['pov']}")
        if chapter.get('act'):
            lines.append(f"**Act:** {chapter['act']}")
        if chapter.get('summary'):
            lines.append(f"**Summary:** {chapter['summary']}\n")

        # Key events
        if chapter.get('key_events'):
            lines.append('## Key Events\n')
            for i, event in enumerate(chapter['key_events'], 1):
                lines.append(f'{i}. {event}')
            lines.append('')

        # Character developments
        if chapter.get('character_developments'):
            lines.append('## Character Development\n')
            for dev in chapter['character_developments']:
                lines.append(f'- {dev}')
            lines.append('')

        # Relationship beats
        if chapter.get('relationship_beats'):
            lines.append('## Relationship Beats\n')
            for beat in chapter['relationship_beats']:
                lines.append(f'- {beat}')
            lines.append('')

        # Tension points
        if chapter.get('tension_points'):
            lines.append('## Tension Points\n')
            for point in chapter['tension_points']:
                lines.append(f'- {point}')
            lines.append('')

        # Sensory details
        if chapter.get('sensory_details'):
            lines.append('## Sensory Details\n')
            for detail in chapter['sensory_details']:
                lines.append(f'- {detail}')
            lines.append('')

        # Subplot threads
        if chapter.get('subplot_threads'):
            lines.append('## Subplot Threads\n')
            for thread in chapter['subplot_threads']:
                lines.append(f'- {thread}')
            lines.append('')

        return '\n'.join(lines)