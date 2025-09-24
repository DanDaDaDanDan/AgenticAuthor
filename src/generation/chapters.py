"""Chapter outline generation (LOD2) for AgenticAuthor."""

import json
import yaml
from typing import Optional, List, Dict, Any

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project, ChapterOutline


DEFAULT_CHAPTERS_TEMPLATE = """Based on this treatment:
{{ treatment }}

Generate detailed chapter outlines that break down the story into {{ chapter_count }} chapters.

For each chapter, provide:
1. Chapter number
2. Title (evocative, not generic)
3. POV character (if applicable)
4. Summary (2-3 sentences)
5. Key events (3-5 bullet points)
6. Character developments
7. Word count target (distribute {{ total_words }} words across chapters)

Return as JSON array with this structure:
[
  {
    "number": 1,
    "title": "Chapter Title",
    "pov": "Character Name",
    "summary": "What happens in this chapter",
    "key_events": ["Event 1", "Event 2", "Event 3"],
    "character_developments": ["Development 1", "Development 2"],
    "word_count_target": 3000,
    "act": "Act I"
  },
  ...
]

Ensure good pacing:
- Act I: ~25% of chapters (setup)
- Act II: ~50% of chapters (development)
- Act III: ~25% of chapters (resolution)
- Each chapter should end with momentum
- Vary chapter lengths for rhythm"""


class ChapterGenerator:
    """Generator for chapter outlines (LOD2)."""

    def __init__(self, client: OpenRouterClient, project: Project):
        """
        Initialize chapter generator.

        Args:
            client: OpenRouter API client
            project: Current project
        """
        self.client = client
        self.project = project

    def _calculate_chapter_count(self, total_words: int) -> int:
        """Calculate recommended chapter count based on word count."""
        avg_chapter_length = 3000  # Typical chapter length
        return max(8, min(30, total_words // avg_chapter_length))

    async def generate(
        self,
        chapter_count: Optional[int] = None,
        total_words: int = 50000,
        template: Optional[str] = None
    ) -> List[ChapterOutline]:
        """
        Generate chapter outlines from treatment.

        Args:
            chapter_count: Number of chapters (auto-calculated if not provided)
            total_words: Target total word count
            template: Optional custom template

        Returns:
            List of ChapterOutline objects
        """
        # Load treatment
        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first with /generate treatment")

        # Calculate chapter count if not provided
        if not chapter_count:
            chapter_count = self._calculate_chapter_count(total_words)

        # Prepare template
        template_str = template or DEFAULT_CHAPTERS_TEMPLATE
        jinja_template = Template(template_str)

        # Render prompt
        prompt = jinja_template.render(
            treatment=treatment,
            chapter_count=chapter_count,
            total_words=total_words
        )

        # Generate with API
        try:
            # Get model from project settings or default
            model = None
            if self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            result = await self.client.json_completion(
                model=model,
                prompt=prompt,
                temperature=0.6,  # Balanced for structure
                display_field="0",  # Display first chapter as it generates
                display_label="Generating chapter outlines",
                # No max_tokens - let it use full available context
                min_response_tokens=3000  # Chapter outlines need lots of space
            )

            if result and isinstance(result, list):
                # Convert to ChapterOutline objects
                chapters = []
                for chapter_data in result:
                    chapter = ChapterOutline(
                        number=chapter_data['number'],
                        title=chapter_data['title'],
                        summary=chapter_data['summary'],
                        key_events=chapter_data.get('key_events', []),
                        word_count_target=chapter_data.get('word_count_target', 3000)
                    )
                    # Store additional data
                    chapter.pov = chapter_data.get('pov')
                    chapter.act = chapter_data.get('act')
                    chapter.character_developments = chapter_data.get('character_developments', [])
                    chapters.append(chapter)

                # Save to project
                chapters_file = self.project.path / "chapters.yaml"
                chapters_data = []
                for chapter in chapters:
                    chapter_dict = {
                        'number': chapter.number,
                        'title': chapter.title,
                        'summary': chapter.summary,
                        'key_events': chapter.key_events,
                        'word_count_target': chapter.word_count_target
                    }
                    if hasattr(chapter, 'pov') and chapter.pov:
                        chapter_dict['pov'] = chapter.pov
                    if hasattr(chapter, 'act') and chapter.act:
                        chapter_dict['act'] = chapter.act
                    if hasattr(chapter, 'character_developments'):
                        chapter_dict['character_developments'] = chapter.character_developments
                    chapters_data.append(chapter_dict)

                with open(chapters_file, 'w') as f:
                    yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False)

                # Git commit handled by caller if needed

                return chapters

            raise Exception("Invalid response format from API")

        except Exception as e:
            raise Exception(f"Failed to generate chapters: {e}")

    async def iterate_chapter(self, chapter_number: int, feedback: str) -> ChapterOutline:
        """
        Iterate on a specific chapter outline.

        Args:
            chapter_number: Chapter to iterate on
            feedback: Natural language feedback

        Returns:
            Updated ChapterOutline
        """
        # Load current chapters
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            raise Exception("No chapter outlines found. Generate chapters first with /generate chapters")

        with open(chapters_file, 'r') as f:
            chapters_data = yaml.safe_load(f)

        # Find the chapter
        chapter_data = None
        chapter_index = None
        for i, ch in enumerate(chapters_data):
            if ch['number'] == chapter_number:
                chapter_data = ch
                chapter_index = i
                break

        if not chapter_data:
            raise Exception(f"Chapter {chapter_number} not found")

        # Create iteration prompt
        prompt = f"""Current chapter outline:
{json.dumps(chapter_data, indent=2)}

User feedback: {feedback}

Please revise this chapter outline based on the feedback. Return the updated chapter in the same JSON format."""

        # Generate revision
        # Get model from project settings or default
        model = None
        if self.project.metadata and self.project.metadata.model:
            model = self.project.metadata.model
        if not model:
            from ..config import get_settings
            settings = get_settings()
            model = settings.active_model

        result = await self.client.json_completion(
            model=model,
            prompt=prompt,
            temperature=0.5,
            display_field="summary",  # Display the updated summary
            display_label=f"Revising chapter {chapter_number}",
            # No max_tokens - let it use full available context
            min_response_tokens=800  # Single chapter outline needs moderate space
        )

        if result:
            # Update the chapter
            chapters_data[chapter_index] = result

            # Save updated chapters
            with open(chapters_file, 'w') as f:
                yaml.dump(chapters_data, f, default_flow_style=False, sort_keys=False)

            # Git commit
            if self.project.git:
                self.project.git.add()
                self.project.git.commit(f"Iterate chapter {chapter_number}: {feedback[:50]}")

            # Return as ChapterOutline
            return ChapterOutline(
                number=result['number'],
                title=result['title'],
                summary=result['summary'],
                key_events=result.get('key_events', []),
                word_count_target=result.get('word_count_target', 3000)
            )

        raise Exception("Failed to iterate chapter")