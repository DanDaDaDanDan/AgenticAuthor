"""LOD response parsing to split unified YAML back to individual files."""

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
                chapters = data['chapters']
                if isinstance(chapters, dict):
                    # New self-contained format (metadata, characters, world, chapters)
                    project.save_chapters_yaml(chapters)
                    updated_files.append('chapters.yaml')
                elif isinstance(chapters, list):
                    # Legacy format - save as list to chapters.yaml
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
            if 'premise' not in data:
                raise ValueError("Response missing 'premise' section (should be preserved)")
            if 'treatment' not in data:
                raise ValueError("Response missing 'treatment' section")
            if not isinstance(data['treatment'], dict) or 'text' not in data['treatment']:
                raise ValueError("Treatment section must have 'text' field")

        elif target_lod == 'chapters':
            if 'premise' not in data:
                raise ValueError("Response missing 'premise' section (should be preserved)")
            if 'treatment' not in data:
                raise ValueError("Response missing 'treatment' section (should be preserved)")
            if 'chapters' not in data:
                raise ValueError("Response missing 'chapters' section")
            if not isinstance(data['chapters'], list):
                raise ValueError("Chapters section must be a list")

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
