"""LOD context building for unified LLM prompts."""

import json
import re
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..models import Project


class LODContextBuilder:
    """Build unified YAML context from multi-file storage for LLM consumption."""

    def build_context(
        self,
        project: Project,
        target_lod: str,
        include_downstream: bool = False
    ) -> Dict[str, Any]:
        """
        Build unified context for LLM from separate files.

        Args:
            project: Current project
            target_lod: What we're generating/iterating ('premise' | 'treatment' | 'chapters' | 'prose')
            include_downstream: If True, include content beyond target_lod (for consistency checks)

        Returns:
            Dict that will be serialized to YAML for LLM

        Examples:
            - Generating treatment: target_lod='premise', returns {premise: {...}}
            - Generating chapters: target_lod='treatment', returns {premise, treatment}
            - Iterating chapters: target_lod='chapters', returns {premise, treatment, chapters}
            - Full context check: target_lod='prose', include_downstream=True, returns everything
        """
        context = {}

        # NEW LOGIC: chapters.yaml is self-contained
        # When iterating chapters, ONLY return chapters.yaml
        # When generating chapters, return premise + treatment (as input)

        if target_lod == 'chapters' and not include_downstream:
            # Chapter iteration: ONLY chapters.yaml (self-contained)
            chapters_yaml = project.get_chapters_yaml()
            if chapters_yaml:
                context['chapters'] = chapters_yaml
            else:
                # Legacy format fallback
                chapters = project.get_chapters()
                if chapters:
                    context['chapters'] = chapters
            return context

        # For all other cases, use the old logic:

        # Include premise if needed
        if target_lod in ['premise', 'treatment'] or include_downstream:
            premise = project.get_premise()
            if premise:
                metadata = self._load_premise_metadata(project)
                context['premise'] = {
                    'text': premise,
                    'metadata': metadata
                }

        # Include treatment if needed
        if target_lod in ['treatment'] or include_downstream:
            treatment = project.get_treatment()
            if treatment:
                context['treatment'] = {'text': treatment}

        # Include chapters for prose generation (uses chapters.yaml)
        if target_lod == 'prose' or include_downstream:
            chapters_yaml = project.get_chapters_yaml()
            if chapters_yaml:
                context['chapters'] = chapters_yaml
            else:
                # Legacy format fallback
                chapters = project.get_chapters()
                if chapters:
                    context['chapters'] = chapters

        # Include prose if needed
        if target_lod == 'prose' or include_downstream:
            prose = self._load_all_prose(project)
            if prose:
                context['prose'] = prose

        return context

    def _load_premise_metadata(self, project: Project) -> Dict[str, Any]:
        """Load premise_metadata.json if it exists."""
        metadata_path = project.premise_metadata_file
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _load_all_prose(self, project: Project) -> List[Dict[str, Any]]:
        """Load all chapter prose files with encoding auto-fix."""
        prose = []
        for chapter_file in project.list_chapters():
            num = self._extract_chapter_number(chapter_file)
            try:
                text = chapter_file.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Try alternate encodings and auto-fix to UTF-8
                try:
                    text = chapter_file.read_text(encoding='cp1252')
                except UnicodeDecodeError:
                    text = chapter_file.read_text(encoding='latin-1')

                # Fix file permanently by re-writing as UTF-8
                chapter_file.write_text(text, encoding='utf-8')

            prose.append({
                'chapter': num,
                'text': text,
                'word_count': len(text.split())
            })
        return prose

    def _extract_chapter_number(self, chapter_file: Path) -> int:
        """Extract chapter number from filename like 'chapter-01.md'."""
        match = re.search(r'chapter-(\d+)', chapter_file.name)
        if match:
            return int(match.group(1))
        return 0

    def to_yaml_string(self, context: Dict[str, Any]) -> str:
        """Serialize context to YAML string for LLM."""
        return yaml.dump(context, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def get_lod_stage(self, project: Project) -> str:
        """
        Determine the current LOD stage of the project.

        Returns:
            'none' | 'premise' | 'treatment' | 'chapters' | 'prose'
        """
        if project.list_chapters():
            return 'prose'
        elif project.chapters_file.exists():
            return 'chapters'
        elif project.treatment_file.exists():
            return 'treatment'
        elif project.premise_file.exists():
            return 'premise'
        else:
            return 'none'
