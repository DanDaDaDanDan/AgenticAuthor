"""LOD response parsing to split unified YAML back to individual files.

This module handles parsing LLM responses and saving them to the appropriate files.
It supports multiple response formats for backward compatibility.

Format Detection and Handling
==============================
The parser automatically detects which format the LLM used:

1. NEW Self-Contained Chapters Format:
   {
     metadata: {genre, pacing, tone, ...},
     characters: [{name, role, background, ...}],
     world: {setting_overview, locations, ...},
     chapters: [{number, title, key_events, ...}]
   }

   Used by: Normal chapters generation, competition mode
   Validation: Strict structural checks for all required fields
   Saves to: chapters.yaml (entire structure)

2. OLD Efficient Format (treatment/prose):
   {
     treatment: {text: "..."}
   }
   OR
   {
     prose: [{chapter: 1, text: "..."}]
   }

   Used by: Treatment generation (ONLY returns treatment, not premise)
   Validation: Basic presence checks
   Saves to: Respective files only

3. LEGACY Format (backward compatibility):
   {
     premise: {...},
     treatment: {...},
     chapters: [...]
   }

   Used by: Older iteration code paths
   Validation: Permissive, accepts what's present
   Saves to: All present sections

Validation Strategy
===================
- NEW format: Strict validation with detailed error messages
- EFFICIENT format: Basic validation (must have target section)
- LEGACY format: Permissive (saves whatever is present)

This ensures new code has high quality while maintaining backward compatibility.

Culling Strategy
================
Files are automatically deleted based on what was modified:

- Modify premise → Delete treatment, chapters, prose
- Modify treatment → Delete chapters, prose (keep premise)
- Modify chapters → Delete affected chapter prose files
- Modify prose → No culling (just update that chapter)

This maintains consistency: if you change a high level, downstream content
becomes invalid and must be regenerated.
"""

import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..models import Project


class LODResponseParser:
    """Parse LLM's unified YAML response back to individual files."""

    def parse_and_save(
        self,
        response: str,
        project: Project,
        target_lod: str,
        original_context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Parse YAML response and optionally save to appropriate files.

        Args:
            response: Raw LLM response (may include markdown fences)
            project: Current project
            target_lod: What we were iterating/generating
            original_context: Original context before iteration (to detect changes)
            dry_run: If True, parse and validate but don't save files (for multi-model competition)

        Returns:
            Dict with:
                - 'parsed_data': Parsed YAML dict (always included)
                - 'updated_files': List of files that would be/were updated
                - 'deleted_files': List of files that would be/were deleted (culled)
                - 'changes': Dict of what changed per LOD
        """
        # Strip markdown fences if present
        response = self._strip_markdown_fences(response)

        # Parse YAML
        try:
            data = yaml.safe_load(response)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse LLM response as YAML: {e}")

        if not isinstance(data, dict):
            raise ValueError(f"Expected YAML dict, got {type(data)}")

        # Validate that target LOD is present in response
        self._validate_response(data, target_lod)

        updated_files = []
        changes = {}

        # Track what changed (compare to original_context)
        if original_context:
            changes = self._detect_changes(original_context, data)

        # If dry_run, only track what WOULD be updated, don't actually save
        if not dry_run:
            # Save premise if present
            if 'premise' in data:
                premise_data = data['premise']
                if isinstance(premise_data, dict) and 'text' in premise_data:
                    project.save_premise(premise_data['text'])
                    updated_files.append('premise.md')

                    # Save metadata if present
                    if 'metadata' in premise_data:
                        self._save_premise_metadata(project, premise_data['metadata'])
                        updated_files.append('premise_metadata.json')

            # Save treatment if present
            if 'treatment' in data:
                treatment_data = data['treatment']
                if isinstance(treatment_data, dict) and 'text' in treatment_data:
                    project.save_treatment(treatment_data['text'])
                    updated_files.append('treatment.md')

            # Save chapters if present
            if 'chapters' in data:
                # Detect format: NEW self-contained has metadata/characters/world at top level
                if 'metadata' in data and 'characters' in data and 'world' in data:
                    # NEW self-contained format - save entire structure
                    project.save_chapters_yaml(data)
                    updated_files.append('chapters.yaml')
                else:
                    # OLD/LEGACY format - only chapters section
                    chapters = data['chapters']
                    if isinstance(chapters, dict):
                        # Dict format (could be partial new format)
                        project.save_chapters_yaml(chapters)
                        updated_files.append('chapters.yaml')
                    elif isinstance(chapters, list):
                        # Legacy list format - save as list to chapters.yaml
                        with open(project.chapters_file, 'w', encoding='utf-8') as f:
                            yaml.dump(chapters, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                        updated_files.append('chapters.yaml')

            # Save prose if present
            if 'prose' in data:
                for prose_entry in data['prose']:
                    if isinstance(prose_entry, dict) and 'chapter' in prose_entry and 'text' in prose_entry:
                        chapter_num = prose_entry['chapter']
                        prose_text = prose_entry['text']
                        project.save_chapter(chapter_num, prose_text)
                        updated_files.append(f'chapters/chapter-{chapter_num:02d}.md')

            # Apply culling based on target_lod (NOT what LLM changed)
            deleted_files = self._apply_culling(project, target_lod, data)
        else:
            # Dry run: just track what would be updated
            if 'premise' in data:
                updated_files.append('premise.md')
                if data['premise'].get('metadata'):
                    updated_files.append('premise_metadata.json')

            if 'treatment' in data:
                updated_files.append('treatment.md')

            if 'chapters' in data:
                updated_files.append('chapters.yaml')

            if 'prose' in data:
                for prose_entry in data['prose']:
                    if isinstance(prose_entry, dict) and 'chapter' in prose_entry:
                        chapter_num = prose_entry['chapter']
                        updated_files.append(f'chapters/chapter-{chapter_num:02d}.md')

            # Dry run culling simulation
            deleted_files = self._simulate_culling(project, target_lod, data)

        return {
            'parsed_data': data,
            'updated_files': updated_files,
            'deleted_files': deleted_files,
            'changes': changes
        }

    def _detect_changes(self, original: Dict[str, Any], updated: Dict[str, Any]) -> Dict[str, bool]:
        """
        Detect what LODs actually changed.

        Returns:
            Dict like {'premise': True, 'treatment': False, 'chapters': True}
        """
        changes = {}

        # Check premise
        if 'premise' in original and 'premise' in updated:
            orig_text = original['premise'].get('text', '')
            new_text = updated['premise'].get('text', '')
            changes['premise'] = orig_text != new_text
        elif 'premise' in updated:
            changes['premise'] = True

        # Check treatment
        if 'treatment' in original and 'treatment' in updated:
            orig_text = original['treatment'].get('text', '')
            new_text = updated['treatment'].get('text', '')
            changes['treatment'] = orig_text != new_text
        elif 'treatment' in updated:
            changes['treatment'] = True

        # Check chapters (simple check - any change to the list)
        if 'chapters' in original and 'chapters' in updated:
            changes['chapters'] = original['chapters'] != updated['chapters']
        elif 'chapters' in updated:
            changes['chapters'] = True

        # Check prose
        if 'prose' in original and 'prose' in updated:
            changes['prose'] = original['prose'] != updated['prose']
        elif 'prose' in updated:
            changes['prose'] = True

        return changes

    def _simulate_culling(
        self,
        project: Project,
        target_lod: str,
        llm_data: Dict[str, Any]
    ) -> List[str]:
        """
        Simulate culling for dry_run mode (don't actually delete files).

        Args:
            project: Current project
            target_lod: What we directly iterated/generated
            llm_data: Parsed LLM response

        Returns:
            List of file paths that WOULD be deleted
        """
        deleted = []

        if target_lod == 'premise':
            # Would delete treatment, chapters, prose
            if project.treatment_file.exists():
                deleted.append('treatment.md')

            if project.chapters_file.exists():
                deleted.append('chapters.yaml')

            for chapter_file in project.list_chapters():
                deleted.append(str(chapter_file.relative_to(project.path)))

        elif target_lod == 'treatment':
            # Would delete chapters, prose (keep premise)
            if project.chapters_file.exists():
                deleted.append('chapters.yaml')

            for chapter_file in project.list_chapters():
                deleted.append(str(chapter_file.relative_to(project.path)))

        elif target_lod == 'chapters':
            # Would delete prose for chapters that changed
            old_chapters = project.get_chapters() or []
            new_chapters = llm_data.get('chapters', [])

            for new_ch in new_chapters:
                ch_num = new_ch['number']
                old_ch = next((c for c in old_chapters if c['number'] == ch_num), None)

                if old_ch is None or self._chapter_differs(old_ch, new_ch):
                    prose_file = project.chapters_dir / f'chapter-{ch_num:02d}.md'
                    if prose_file.exists():
                        deleted.append(f'chapters/chapter-{ch_num:02d}.md')

        return deleted

    def _apply_culling(
        self,
        project: Project,
        target_lod: str,
        llm_data: Dict[str, Any]
    ) -> List[str]:
        """
        Delete downstream files based on what LOD was directly modified.

        CRITICAL: Only cull based on target_lod, NOT what the LLM changed.
        If iterating chapters and LLM updates premise (upward sync), we DON'T cull downstream.

        Args:
            project: Current project
            target_lod: What we directly iterated/generated
            llm_data: Parsed LLM response

        Returns:
            List of deleted file paths (relative to project)
        """
        deleted = []

        if target_lod == 'premise':
            # Delete treatment, chapters, prose
            if project.treatment_file.exists():
                project.treatment_file.unlink()
                deleted.append('treatment.md')

            if project.chapters_file.exists():
                project.chapters_file.unlink()
                deleted.append('chapters.yaml')

            for chapter_file in project.list_chapters():
                chapter_file.unlink()
                deleted.append(str(chapter_file.relative_to(project.path)))

        elif target_lod == 'treatment':
            # Delete chapters, prose (keep premise)
            if project.chapters_file.exists():
                project.chapters_file.unlink()
                deleted.append('chapters.yaml')

            for chapter_file in project.list_chapters():
                chapter_file.unlink()
                deleted.append(str(chapter_file.relative_to(project.path)))

        elif target_lod == 'chapters':
            # Delete prose for chapters that changed
            # Compare LLM's chapters vs existing chapters.yaml
            deleted.extend(self._cull_affected_prose(project, llm_data))

        # target_lod == 'prose': No culling, just update specific chapter

        return deleted

    def _cull_affected_prose(self, project: Project, llm_data: Dict[str, Any]) -> List[str]:
        """
        Delete prose for chapters whose outlines were modified.

        Args:
            project: Current project
            llm_data: Parsed LLM response with updated chapters

        Returns:
            List of deleted prose file paths
        """
        # Load old chapters
        old_chapters = project.get_chapters() or []
        new_chapters = llm_data.get('chapters', [])

        deleted = []
        for new_ch in new_chapters:
            ch_num = new_ch['number']
            # Check if chapter changed
            old_ch = next((c for c in old_chapters if c['number'] == ch_num), None)

            if old_ch is None or self._chapter_differs(old_ch, new_ch):
                # Chapter changed, delete prose
                prose_file = project.chapters_dir / f'chapter-{ch_num:02d}.md'
                if prose_file.exists():
                    prose_file.unlink()
                    deleted.append(f'chapters/chapter-{ch_num:02d}.md')

        return deleted

    def _chapter_differs(self, old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """
        Check if chapter outline meaningfully changed.

        Compares key fields that would affect prose generation.
        """
        # Compare key fields
        key_fields = [
            'title', 'summary', 'key_events', 'character_developments',
            'relationship_beats', 'tension_points'
        ]

        for field in key_fields:
            if old.get(field) != new.get(field):
                return True

        return False

    def _save_premise_metadata(self, project: Project, metadata: Dict[str, Any]):
        """Save premise metadata to premise_metadata.json."""
        metadata_path = project.premise_metadata_file
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _validate_response(self, data: Dict[str, Any], target_lod: str):
        """
        Validate that the response has the expected structure.

        Args:
            data: Parsed YAML data
            target_lod: What LOD we were generating/iterating

        Raises:
            ValueError: If response is missing expected sections
        """
        # Check that target LOD is present
        if target_lod == 'premise':
            if 'premise' not in data:
                raise ValueError("Response missing 'premise' section")
            if not isinstance(data['premise'], dict) or 'text' not in data['premise']:
                raise ValueError("Premise section must have 'text' field")

        elif target_lod == 'treatment':
            # Treatment generation now returns ONLY treatment (not premise)
            if 'treatment' not in data:
                raise ValueError("Response missing 'treatment' section")
            if not isinstance(data['treatment'], dict) or 'text' not in data['treatment']:
                raise ValueError("Treatment section must have 'text' field")

        elif target_lod == 'chapters':
            # Chapters can be in two formats:
            # 1. NEW self-contained: {metadata: {}, characters: [], world: {}, chapters: []}
            # 2. OLD with context: {premise: {}, treatment: {}, chapters: []}

            # Both formats MUST have 'chapters' section
            if 'chapters' not in data:
                raise ValueError("Response missing 'chapters' section")

            # Detect format based on presence of metadata
            if 'metadata' in data:
                # NEW self-contained format - validate required sections
                required_sections = ['metadata', 'characters', 'world', 'chapters']
                missing = [s for s in required_sections if s not in data]
                if missing:
                    raise ValueError(f"New chapters format missing required sections: {', '.join(missing)}")

                # In new format, chapters is a list at top level
                if not isinstance(data['chapters'], list):
                    raise ValueError("In new format, chapters must be a list")

                # Deep structural validation for new format
                self._validate_new_chapters_structure(data)

            # OLD format is no longer validated strictly (backward compatibility only)
            # Just ensure chapters is list or dict
            elif not isinstance(data['chapters'], (list, dict)):
                raise ValueError("Chapters section must be a list or dict")

        elif target_lod == 'prose':
            if 'premise' not in data:
                raise ValueError("Response missing 'premise' section (should be preserved)")
            if 'treatment' not in data:
                raise ValueError("Response missing 'treatment' section (should be preserved)")
            if 'chapters' not in data:
                raise ValueError("Response missing 'chapters' section (should be preserved)")
            if 'prose' not in data:
                raise ValueError("Response missing 'prose' section")
            if not isinstance(data['prose'], list):
                raise ValueError("Prose section must be a list")

    def _validate_new_chapters_structure(self, data: Dict[str, Any]):
        """
        Deep structural validation for new self-contained chapters format.

        Validates that the structure has all required fields and proper types
        to ensure prose generation has complete information.

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

                required_chapter_fields = ['number', 'title', 'summary', 'key_events', 'word_count_target']
                for field in required_chapter_fields:
                    if field not in chapter:
                        errors.append(f"chapters[{i}] missing: {field}")

                # Validate key_events is a list
                if 'key_events' in chapter and not isinstance(chapter['key_events'], list):
                    errors.append(f"chapters[{i}].key_events must be a list")
                elif 'key_events' in chapter and len(chapter['key_events']) == 0:
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
