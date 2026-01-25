"""LOD context building for unified LLM prompts.

This module builds input context for LLM generation by assembling content
from multiple files.

MARKDOWN-FIRST ARCHITECTURE
============================
All LLM prompts use native markdown format (NOT YAML):
- build_markdown_context() - PRIMARY method for LLM prompts
- build_context() - Returns dicts for extracting metadata (NOT for LLM prompts)

KEY CONCEPT: context_level Parameter
======================================
The build_markdown_context() method takes a context_level parameter that indicates
"what level of content to include as INPUT", NOT what you're generating.

Examples:
    - Generating treatment? Use context_level='premise' (premise as input)
    - Generating plan? Use context_level='treatment' (premise+treatment as input)

This is intentional: you provide existing content as context, then ask the
LLM to generate the NEXT level.

Format Design
=============
The system uses efficient, purpose-specific formats:

- Treatment: Returns ONLY treatment text (uses premise as markdown input context)
- Plan: Returns structure-plan.md (uses premise+treatment as input)
- Prose: Returns prose text (uses structure-plan.md as input)
"""

import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..models import Project


class LODContextBuilder:
    """Build unified context from multi-file storage for LLM consumption.

    PRIMARY USE: build_markdown_context() for LLM prompts (returns markdown strings)
    SECONDARY USE: build_context() for metadata extraction (returns dicts)
    """

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
                          ('premise' | 'treatment' | 'plan' | 'prose')
                          This indicates "include up to this level", not what you're generating.
            include_downstream: If True, include content beyond context_level (for consistency checks)

        Returns:
            Dict that will be serialized to YAML for LLM

        Examples:
            - Generating treatment: context_level='premise', returns {premise: {...}}
            - Generating plan: context_level='treatment', returns {premise, treatment}
            - Generating prose: context_level='plan', returns {premise, treatment, plan}
            - Full context check: context_level='prose', include_downstream=True, returns everything

        Note: context_level indicates INPUT context, not OUTPUT target.
              E.g., treatment generation uses context_level='premise' (premise as input)
        """
        context = {}

        # Include premise if needed
        if context_level in ['premise', 'treatment', 'plan'] or include_downstream:
            premise = project.get_premise()
            if premise:
                metadata = self._load_premise_metadata(project)
                context['premise'] = {
                    'text': premise,
                    'metadata': metadata
                }

        # Include treatment if needed
        if context_level in ['treatment', 'plan'] or include_downstream:
            treatment = project.get_treatment()
            if treatment:
                context['treatment'] = {'text': treatment}

        # Include structure plan for prose generation
        if context_level in ['plan', 'prose'] or include_downstream:
            plan = project.get_structure_plan()
            if plan:
                context['plan'] = {'text': plan}

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

    def build_markdown_context(
        self,
        project: Project,
        context_level: str
    ) -> str:
        """
        Build markdown context for LLM prompts by loading content as markdown.

        This is the NEW preferred method for passing context to LLMs.
        Returns raw markdown with clear section fences instead of YAML.

        Args:
            project: Current project
            context_level: What level to include ('premise' | 'treatment')

        Returns:
            Markdown string with fenced sections

        Examples:
            - Generating chapters: context_level='treatment'
              Returns: premise + treatment with section headers
        """
        sections = []

        # Include premise if needed
        # NOTE: Premise is stored in premise_metadata.json, not premise.md
        if context_level in ['premise', 'treatment']:
            premise_text = project.get_premise()
            if premise_text:
                sections.append("## PREMISE\n\n" + premise_text)

        # Include treatment if needed
        # NOTE: Treatment is stored in treatment/treatment.md
        if context_level == 'treatment':
            treatment_text = project.get_treatment()
            if treatment_text:
                sections.append("## TREATMENT\n\n" + treatment_text)

        return "\n\n---\n\n".join(sections)
