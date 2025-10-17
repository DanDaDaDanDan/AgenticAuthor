"""LOD context building for unified LLM prompts.

This module builds input context for LLM generation by assembling content
from multiple files into unified YAML structures.

KEY CONCEPT: context_level Parameter
======================================
The build_context() method takes a context_level parameter that indicates
"what level of content to include as INPUT", NOT what you're generating.

Examples:
    - Generating treatment? Use context_level='premise' (premise as input)
    - Generating chapters? Use context_level='treatment' (premise+treatment as input)
    - Iterating chapters? Use context_level='chapters' (include chapters too)

This is intentional: you provide existing content as context, then ask the
LLM to generate the NEXT level or iterate the CURRENT level.

Format Design
=============
The system uses efficient, purpose-specific formats:

- Treatment: Returns ONLY treatment (uses premise as input context)
- Chapters: Returns ONLY self-contained chapters.yaml (uses premise+treatment as input)
- Prose: Returns ONLY prose text (uses chapters.yaml as input)

Self-Contained Chapters Format
===============================
Chapters.yaml contains everything prose generation needs:
    - metadata: genre, pacing, tone, themes, narrative_style
    - characters: full profiles with backgrounds, motivations, arcs
    - world: setting, locations, systems, atmosphere
    - chapters: detailed outlines with events, developments, beats

This allows prose generation to work without accessing premise or treatment.
"""

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
        context_level: str,
        include_downstream: bool = False
    ) -> Dict[str, Any]:
        """
        Build unified context for LLM from separate files.

        Args:
            project: Current project
            context_level: What level of content to include as context for generation
                          ('premise' | 'treatment' | 'chapters' | 'prose')
                          This indicates "include up to this level", not what you're generating.
            include_downstream: If True, include content beyond context_level (for consistency checks)

        Returns:
            Dict that will be serialized to YAML for LLM

        Examples:
            - Generating treatment: context_level='premise', returns {premise: {...}}
            - Generating chapters: context_level='treatment', returns {premise, treatment}
            - Iterating chapters: context_level='chapters', returns {premise, treatment, chapters}
            - Full context check: context_level='prose', include_downstream=True, returns everything

        Note: context_level indicates INPUT context, not OUTPUT target.
              E.g., treatment generation uses context_level='premise' (premise as input)
        """
        context = {}

        # chapters.yaml is self-contained
        # When iterating chapters, ONLY return chapters.yaml
        # When generating chapters, return premise + treatment (as input)

        if context_level == 'chapters' and not include_downstream:
            # Chapter iteration: ONLY chapters.yaml (self-contained)
            # Return flat structure directly (not nested under 'chapters' key)
            chapters_yaml = project.get_chapters_yaml()
            if chapters_yaml:
                # Return the full chapters.yaml structure at top level
                # This has: metadata, characters, world, chapters
                return chapters_yaml
            return {}

        # For all other cases, use the old logic:

        # Include premise if needed
        if context_level in ['premise', 'treatment'] or include_downstream:
            premise = project.get_premise()
            if premise:
                metadata = self._load_premise_metadata(project)
                context['premise'] = {
                    'text': premise,
                    'metadata': metadata
                }

        # Include treatment if needed
        if context_level in ['treatment'] or include_downstream:
            treatment = project.get_treatment()
            if treatment:
                context['treatment'] = {'text': treatment}

        # Include chapters for prose generation (uses chapters.yaml)
        if context_level == 'prose' or include_downstream:
            chapters_yaml = project.get_chapters_yaml()
            if chapters_yaml:
                context['chapters'] = chapters_yaml

        # Include prose if needed
        if context_level == 'prose' or include_downstream:
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

    def build_prose_iteration_context(
        self,
        project: Project,
        target_chapter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build full context for prose iteration with ALL chapter prose.

        CRITICAL: For prose iteration, we pass full prose for ALL chapters
        to give maximum context. No truncation, context is king.

        Args:
            project: Current project
            target_chapter: Specific chapter being iterated (for identification)

        Returns:
            Dict with chapters.yaml and full prose of ALL chapters
        """
        context = {}

        # Include chapters.yaml (self-contained with metadata, characters, world, chapters)
        chapters_yaml = project.get_chapters_yaml()
        if chapters_yaml:
            context['chapters'] = chapters_yaml

        # Include FULL prose for ALL chapters (untruncated)
        prose = self._load_all_prose(project)
        if prose:
            context['prose'] = prose

        # Mark target chapter if specified
        if target_chapter is not None:
            context['target_chapter'] = target_chapter

        return context

    def build_short_story_context(
        self,
        project: Project,
        target_lod: str
    ) -> Dict[str, Any]:
        """
        Build context for short-form story iteration.

        Short stories don't use chapters.yaml, so context is simpler:
        - premise + metadata
        - treatment
        - prose (story.md content if exists)

        Args:
            project: Current project
            target_lod: Target LOD being iterated (premise/treatment/prose)

        Returns:
            Dict with premise, treatment, and optionally prose
        """
        context = {}

        # Always include premise (foundation)
        if target_lod in ['premise', 'treatment', 'prose']:
            premise = project.get_premise()
            if premise:
                metadata = self._load_premise_metadata(project)
                context['premise'] = {
                    'text': premise,
                    'metadata': metadata
                }

        # Include treatment if iterating treatment or prose
        if target_lod in ['treatment', 'prose']:
            treatment = project.get_treatment()
            if treatment:
                context['treatment'] = {'text': treatment}

        # Include story prose if iterating prose
        if target_lod == 'prose':
            story = project.get_story()
            if story:
                context['prose'] = story

        return context

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
