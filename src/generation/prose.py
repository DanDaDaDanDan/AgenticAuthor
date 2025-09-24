"""Prose generation (LOD0) for AgenticAuthor."""

import yaml
from typing import Optional, Dict, Any
from pathlib import Path

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project


DEFAULT_PROSE_TEMPLATE = """Based on this chapter outline:

Chapter {{ chapter_number }}: {{ chapter_title }}

Summary: {{ chapter_summary }}

Key Events:
{% for event in key_events %}
- {{ event }}
{% endfor %}

{% if character_developments %}
Character Developments:
{% for dev in character_developments %}
- {{ dev }}
{% endfor %}
{% endif %}

{% if previous_chapter %}
Previous chapter ended with:
{{ previous_chapter_ending }}
{% endif %}

{% if treatment %}
Overall story context:
{{ treatment[:1000] }}...
{% endif %}

Write the full prose for this chapter:
- Target length: {{ word_count_target }} words
- Write in {{ narrative_style }} style
- Use vivid, engaging prose
- Show don't tell
- Include dialogue where appropriate
- End with momentum/hook for next chapter
- Maintain consistent voice and tone

Begin the chapter now:"""


class ProseGenerator:
    """Generator for full prose (LOD0)."""

    def __init__(self, client: OpenRouterClient, project: Project):
        """
        Initialize prose generator.

        Args:
            client: OpenRouter API client
            project: Current project
        """
        self.client = client
        self.project = project

    def _get_chapter_data(self, chapter_number: int) -> Dict[str, Any]:
        """Get chapter outline data."""
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            raise Exception("No chapter outlines found. Generate chapters first with /generate chapters")

        with open(chapters_file, 'r') as f:
            chapters_data = yaml.safe_load(f)

        for chapter in chapters_data:
            if chapter['number'] == chapter_number:
                return chapter

        raise Exception(f"Chapter {chapter_number} not found")

    def _get_previous_chapter_ending(self, chapter_number: int) -> Optional[str]:
        """Get the ending of the previous chapter if it exists."""
        if chapter_number <= 1:
            return None

        prev_chapter_file = self.project.path / "chapters" / f"chapter-{chapter_number - 1:02d}.md"
        if not prev_chapter_file.exists():
            return None

        with open(prev_chapter_file, 'r') as f:
            content = f.read()

        # Get last 500 characters for context
        return content[-500:] if len(content) > 500 else content

    async def generate_chapter(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited",
        template: Optional[str] = None
    ) -> str:
        """
        Generate full prose for a chapter.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style
            template: Optional custom template

        Returns:
            Chapter prose text
        """
        # Get chapter outline
        chapter_data = self._get_chapter_data(chapter_number)

        # Get treatment for context (first 1000 chars)
        treatment = self.project.get_treatment()
        if treatment and len(treatment) > 1000:
            treatment = treatment[:1000]

        # Get previous chapter ending for continuity
        previous_ending = self._get_previous_chapter_ending(chapter_number)

        # Prepare template
        template_str = template or DEFAULT_PROSE_TEMPLATE
        jinja_template = Template(template_str)

        # Render prompt
        prompt = jinja_template.render(
            chapter_number=chapter_number,
            chapter_title=chapter_data['title'],
            chapter_summary=chapter_data['summary'],
            key_events=chapter_data.get('key_events', []),
            character_developments=chapter_data.get('character_developments', []),
            word_count_target=chapter_data.get('word_count_target', 3000),
            narrative_style=narrative_style,
            previous_chapter_ending=previous_ending,
            treatment=treatment
        )

        # Generate with API
        target_words = chapter_data.get('word_count_target', 3000)

        try:
            # Get model from project settings or default
            model = None
            if self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            # Use streaming_completion with dynamic token calculation
            result = await self.client.streaming_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,  # Higher for creative prose
                # No max_tokens - let it use full available context
                # Prose needs substantial space, estimate 1.3 tokens per word
                min_response_tokens=int(target_words * 1.3)
            )

            if result:
                # Extract content from response
                content = result.get('content', result) if isinstance(result, dict) else result

                # Save chapter
                chapter_file = self.project.path / "chapters" / f"chapter-{chapter_number:02d}.md"
                chapter_file.parent.mkdir(exist_ok=True)

                # Format with title
                formatted_content = f"# Chapter {chapter_number}: {chapter_data['title']}\n\n{content}"

                with open(chapter_file, 'w') as f:
                    f.write(formatted_content)

                # Update chapter metadata
                chapter_data['prose_generated'] = True
                chapter_data['actual_word_count'] = len(content.split())

                # Save updated chapters.yaml
                chapters_file = self.project.path / "chapters.yaml"
                with open(chapters_file, 'r') as f:
                    all_chapters = yaml.safe_load(f)

                for i, ch in enumerate(all_chapters):
                    if ch['number'] == chapter_number:
                        all_chapters[i] = chapter_data
                        break

                with open(chapters_file, 'w') as f:
                    yaml.dump(all_chapters, f, default_flow_style=False, sort_keys=False)

                # Git commit
                if self.project.git:
                    self.project.git.add()
                    self.project.git.commit(f"Generate chapter {chapter_number} prose: {chapter_data['title']}")

                return formatted_content

            raise Exception("No content generated")

        except Exception as e:
            raise Exception(f"Failed to generate prose: {e}")

    async def iterate_prose(self, chapter_number: int, feedback: str) -> str:
        """
        Iterate on existing chapter prose.

        Args:
            chapter_number: Chapter to iterate
            feedback: Natural language feedback

        Returns:
            Updated chapter prose
        """
        # Load current chapter
        chapter_file = self.project.path / "chapters" / f"chapter-{chapter_number:02d}.md"
        if not chapter_file.exists():
            raise Exception(f"Chapter {chapter_number} prose not found. Generate it first.")

        with open(chapter_file, 'r') as f:
            current_prose = f.read()

        # Create iteration prompt
        prompt = f"""Current chapter prose:
{current_prose}

User feedback: {feedback}

Please revise this chapter based on the feedback. Maintain the same overall structure and approximate length.
Return the complete revised chapter prose (including the chapter title header)."""

        # Get word count for dynamic token calculation
        current_words = len(current_prose.split())

        # Get model from project settings or default
        model = None
        if self.project.metadata and self.project.metadata.model:
            model = self.project.metadata.model
        if not model:
            from ..config import get_settings
            settings = get_settings()
            model = settings.active_model

        # Generate revision with dynamic token calculation
        result = await self.client.streaming_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,  # Lower temp for controlled iteration
            # No max_tokens - let it use full available context
            # Estimate we need roughly same token count as current chapter
            min_response_tokens=int(current_words * 1.3)
        )

        if result:
            # Extract content from response
            content = result.get('content', result) if isinstance(result, dict) else result

            # Save updated chapter
            with open(chapter_file, 'w') as f:
                f.write(content)

            # Update metadata
            chapters_file = self.project.path / "chapters.yaml"
            with open(chapters_file, 'r') as f:
                all_chapters = yaml.safe_load(f)

            for i, ch in enumerate(all_chapters):
                if ch['number'] == chapter_number:
                    all_chapters[i]['actual_word_count'] = len(content.split())
                    all_chapters[i]['last_iteration'] = feedback[:100]
                    break

            with open(chapters_file, 'w') as f:
                yaml.dump(all_chapters, f, default_flow_style=False, sort_keys=False)

            # Git commit
            if self.project.git:
                self.project.git.add()
                self.project.git.commit(f"Iterate chapter {chapter_number}: {feedback[:50]}")

            return result

        raise Exception("Failed to iterate prose")

    async def generate_all_chapters(
        self,
        narrative_style: str = "third person limited",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None
    ) -> Dict[int, str]:
        """
        Generate prose for multiple chapters.

        Args:
            narrative_style: Narrative voice/style
            start_chapter: First chapter to generate
            end_chapter: Last chapter (None for all)

        Returns:
            Dict mapping chapter numbers to prose
        """
        # Load chapters to determine range
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            raise Exception("No chapter outlines found")

        with open(chapters_file, 'r') as f:
            all_chapters = yaml.safe_load(f)

        if not end_chapter:
            end_chapter = len(all_chapters)

        results = {}

        # Generate each chapter
        for chapter_num in range(start_chapter, end_chapter + 1):
            try:
                prose = await self.generate_chapter(chapter_num, narrative_style)
                results[chapter_num] = prose
            except Exception as e:
                # Continue with other chapters
                pass

        return results