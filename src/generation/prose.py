"""Prose generation (LOD0) for AgenticAuthor."""

import json
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from ..utils.tokens import estimate_tokens


SEQUENTIAL_PROSE_TEMPLATE = """## Story Foundation:

### Premise:
{{ premise }}

{% if taxonomy_selections %}
### Genre & Style Elements:
{{ taxonomy_selections }}
{% endif %}

### Full Treatment:
{{ treatment }}

## Book Progress:

{% for chapter in all_chapters %}
{% if chapter.prose_generated %}
### Chapter {{ chapter.number }}: {{ chapter.title }} [WRITTEN]
{{ chapter.full_prose }}

{% else %}
### Chapter {{ chapter.number }}: {{ chapter.title }} [OUTLINE]
Summary: {{ chapter.summary }}
{% if chapter.pov %}POV: {{ chapter.pov }}{% endif %}
{% if chapter.act %}Act: {{ chapter.act }}{% endif %}

Key Events:
{% for event in chapter.key_events %}
- {{ event }}
{% endfor %}

{% if chapter.character_developments %}
Character Developments:
{% for dev in chapter.character_developments %}
- {{ dev }}
{% endfor %}
{% endif %}

{% if chapter.relationship_beats %}
Relationship Beats:
{% for beat in chapter.relationship_beats %}
- {{ beat }}
{% endfor %}
{% endif %}

{% if chapter.tension_points %}
Tension Points:
{% for point in chapter.tension_points %}
- {{ point }}
{% endfor %}
{% endif %}

{% if chapter.sensory_details %}
Sensory Details:
{% for detail in chapter.sensory_details %}
- {{ detail }}
{% endfor %}
{% endif %}

{% if chapter.subplot_threads %}
Subplot Threads:
{% for thread in chapter.subplot_threads %}
- {{ thread }}
{% endfor %}
{% endif %}

Word Count Target: {{ chapter.word_count_target }}
{% endif %}
{% endfor %}

## CURRENT TASK: Write Chapter {{ current_chapter_number }}

You have the complete story context above. The chapters marked [WRITTEN] show the actual prose already generated. The chapters marked [OUTLINE] show what's coming.

Write Chapter {{ current_chapter_number }} now, ensuring:
1. Perfect continuity from the previous chapter's ending
2. Consistent character voices and development shown in earlier prose
3. Proper pacing relative to the whole story arc
4. Natural progression toward upcoming chapter outlines
5. Approximately {{ word_count_target }} words
6. Build on established world-building details, character traits, and plot threads
7. Pay off any setups from earlier chapters when appropriate
8. Maintain the tone and style established in previous chapters

Begin Chapter {{ current_chapter_number }}: {{ current_chapter_title }}:"""


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


    def load_all_chapters_with_prose(self) -> List[Dict[str, Any]]:
        """Load all chapter outlines and merge with any existing prose."""

        # Load chapter outlines
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            raise Exception("No chapter outlines found. Generate chapters first with /generate chapters")

        with open(chapters_file, 'r') as f:
            chapters = yaml.safe_load(f) or []

        # For each chapter, check if prose exists and load it
        for chapter in chapters:
            chapter_file = self.project.path / "chapters" / f"chapter-{chapter['number']:02d}.md"
            if chapter_file.exists():
                with open(chapter_file, 'r') as f:
                    chapter['full_prose'] = f.read()
                    chapter['prose_generated'] = True
            else:
                chapter['prose_generated'] = False

        return chapters

    def get_taxonomy_selections(self) -> Optional[str]:
        """Load and format taxonomy selections from premise metadata."""
        metadata_file = self.project.path / "premise_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                data = json.load(f)
                if 'selections' in data:
                    # Format selections nicely
                    selections = data['selections']
                    formatted = []
                    for category, values in selections.items():
                        if values:
                            formatted.append(f"{category}: {', '.join(values)}")
                    return '\n'.join(formatted)

        # Fallback to just genre
        if self.project.metadata and self.project.metadata.genre:
            return f"Genre: {self.project.metadata.genre}"
        return None

    async def calculate_prose_context_tokens(self, chapter_number: int) -> Dict[str, Any]:
        """Calculate tokens needed for sequential generation with full context."""

        # Get all content - fail early if required content missing
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first with /generate premise")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first with /generate treatment")

        taxonomy = self.get_taxonomy_selections() or ""  # Optional

        # Calculate base tokens
        premise_tokens = estimate_tokens(premise)
        treatment_tokens = estimate_tokens(treatment)
        taxonomy_tokens = estimate_tokens(taxonomy)

        # Calculate chapter tokens (outlines + existing prose)
        chapters_tokens = 0
        chapters = self.load_all_chapters_with_prose()

        for ch in chapters:
            if ch.get('prose_generated'):
                chapters_tokens += estimate_tokens(ch.get('full_prose', ''))
            else:
                # Estimate outline tokens
                outline_text = f"Chapter {ch.get('number', 0)}: {ch.get('title', '')}\n"
                outline_text += f"Summary: {ch.get('summary', '')}\n"
                outline_text += f"Key Events: {ch.get('key_events', [])}\n"
                outline_text += f"Character Developments: {ch.get('character_developments', [])}\n"
                chapters_tokens += estimate_tokens(outline_text)

        # Total context
        total_context = premise_tokens + treatment_tokens + taxonomy_tokens + chapters_tokens

        # Get target words for current chapter
        target_words = 3000  # default
        for ch in chapters:
            if ch.get('number') == chapter_number:
                target_words = ch.get('word_count_target', 3000)
                break

        # Response space needed (1.3x target words)
        response_needed = int(target_words * 1.3)

        # Total needed with buffer
        total_needed = total_context + response_needed + 1000

        # Check if configured model is sufficient
        configured_model = self.project.metadata.model if self.project.metadata else None
        if not configured_model:
            from ..config import Settings
            settings = Settings()
            configured_model = settings.active_model

        recommended_model = None
        is_sufficient = False

        if configured_model:
            # Check if configured model has sufficient capacity
            from ..api.models import ModelList
            models = await self.client.discover_models()
            models_list = ModelList(models=models)
            configured_model_obj = models_list.find_by_id(configured_model)

            if configured_model_obj:
                is_sufficient = (
                    configured_model_obj.context_length >= total_needed and
                    configured_model_obj.get_max_output_tokens() >= response_needed
                )

        # Only recommend if configured model is insufficient or missing
        if not is_sufficient:
            from ..api.models import ModelList
            models = await self.client.discover_models()
            models_list = ModelList(models=models)
            recommended = models_list.select_by_requirements(
                min_context=total_needed,
                min_output_tokens=response_needed
            )

            if not recommended:
                raise Exception(
                    f"No model found with sufficient capacity. "
                    f"Required: {total_needed:,} context tokens and {response_needed:,} output tokens"
                )

            recommended_model = recommended.id

        return {
            "premise_tokens": premise_tokens,
            "treatment_tokens": treatment_tokens,
            "taxonomy_tokens": taxonomy_tokens,
            "chapters_tokens": chapters_tokens,
            "total_context_tokens": total_context,
            "response_tokens": response_needed,
            "total_needed": total_needed,
            "recommended_model": recommended_model,
            "target_words": target_words
        }

    async def generate_chapter_sequential(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited"
    ) -> str:
        """
        Generate full prose for a chapter with complete story context.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style

        Returns:
            Chapter prose text
        """
        # Check token requirements first
        token_calc = await self.calculate_prose_context_tokens(chapter_number)

        print(f"\n📊 Token Analysis for Chapter {chapter_number}:")
        print(f"  Premise: {token_calc['premise_tokens']:,} tokens")
        print(f"  Treatment: {token_calc['treatment_tokens']:,} tokens")
        print(f"  Taxonomy: {token_calc['taxonomy_tokens']:,} tokens")
        print(f"  Chapters: {token_calc['chapters_tokens']:,} tokens")
        print(f"  Total Context: {token_calc['total_context_tokens']:,} tokens")
        print(f"  Response Needed: {token_calc['response_tokens']:,} tokens")
        print(f"  Total Required: {token_calc['total_needed']:,} tokens")
        if token_calc['recommended_model']:
            print(f"  ⚠️  Recommended Model: {token_calc['recommended_model']}")
        print()

        # Get all content - fail early if required content missing
        premise = self.project.get_premise()
        if not premise:
            raise Exception("No premise found. Generate premise first with /generate premise")

        treatment = self.project.get_treatment()
        if not treatment:
            raise Exception("No treatment found. Generate treatment first with /generate treatment")

        taxonomy_selections = self.get_taxonomy_selections()  # Optional
        all_chapters = self.load_all_chapters_with_prose()  # Will fail if no chapters exist

        # Find current chapter data
        current_chapter = None
        for ch in all_chapters:
            if ch['number'] == chapter_number:
                current_chapter = ch
                break

        if not current_chapter:
            raise Exception(f"Chapter {chapter_number} not found")

        # Prepare template
        jinja_template = Template(SEQUENTIAL_PROSE_TEMPLATE)

        # Render prompt with full context
        prompt = jinja_template.render(
            premise=premise,
            taxonomy_selections=taxonomy_selections,
            treatment=treatment,
            all_chapters=all_chapters,
            current_chapter_number=chapter_number,
            current_chapter_title=current_chapter['title'],
            word_count_target=current_chapter.get('word_count_target', 3000)
        )

        # Generate with API
        try:
            # Get model from project settings or use recommended
            model = None
            if self.project.metadata and self.project.metadata.model:
                model = self.project.metadata.model
            if not model:
                from ..config import get_settings
                settings = get_settings()
                model = settings.active_model

            # Check if model has sufficient context
            model_obj = await self.client.get_model(model)
            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {model}")

            if not model_obj.has_sufficient_context(token_calc['total_needed']):
                print(f"⚠️  Warning: {model} has insufficient context window")
                print(f"   Model context: {model_obj.context_length:,} tokens")
                print(f"   Required: {token_calc['total_needed']:,} tokens")
                if token_calc['recommended_model']:
                    print(f"   Consider using: {token_calc['recommended_model']}")

            # Also check output capacity
            max_output = model_obj.get_max_output_tokens()
            if max_output and max_output < token_calc['response_tokens']:
                print(f"⚠️  Warning: {model} may have insufficient output capacity")
                print(f"   Model max output: {max_output:,} tokens")
                print(f"   Required: {token_calc['response_tokens']:,} tokens")

            # Use streaming_completion with calculated tokens
            result = await self.client.streaming_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,  # Higher for creative prose
                display=True,  # Show streaming progress
                min_response_tokens=token_calc['response_tokens']
            )

            if result:
                # Extract content from response
                content = result.get('content', result) if isinstance(result, dict) else result

                # Save chapter
                chapter_file = self.project.path / "chapters" / f"chapter-{chapter_number:02d}.md"
                chapter_file.parent.mkdir(exist_ok=True)

                # Format with title
                formatted_content = f"# Chapter {chapter_number}: {current_chapter['title']}\n\n{content}"

                with open(chapter_file, 'w') as f:
                    f.write(formatted_content)

                # Update chapter metadata
                current_chapter['prose_generated'] = True
                current_chapter['actual_word_count'] = len(content.split())
                current_chapter['generation_mode'] = 'sequential'

                # Save updated chapters.yaml
                chapters_file = self.project.path / "chapters.yaml"
                with open(chapters_file, 'w') as f:
                    yaml.dump(all_chapters, f, default_flow_style=False, sort_keys=False)

                print(f"\n✅ Chapter {chapter_number} generated successfully")
                print(f"   Word count: {len(content.split()):,}")

                return formatted_content

            raise Exception("No content generated")

        except Exception as e:
            raise Exception(f"Failed to generate prose: {e}")

    async def generate_chapter(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited"
    ) -> str:
        """
        Generate full prose for a chapter with complete story context.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style

        Returns:
            Chapter prose text
        """
        return await self.generate_chapter_sequential(
            chapter_number=chapter_number,
            narrative_style=narrative_style
        )

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

            # Git commit handled by caller if needed

            return result

        raise Exception("Failed to iterate prose")

    async def generate_all_chapters(
        self,
        narrative_style: str = "third person limited",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None
    ) -> Dict[int, str]:
        """
        Generate prose for all chapters sequentially with full context.

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

        print(f"\n{'='*60}")
        print(f"📚 Generating Chapters {start_chapter} to {end_chapter}")
        print(f"   Mode: Sequential (Full Context)")
        print(f"   Narrative Style: {narrative_style}")
        print(f"{'='*60}\n")

        # IMPORTANT: Generate chapters in order for sequential mode
        # Each chapter builds on the previous ones
        for chapter_num in range(start_chapter, end_chapter + 1):
            try:
                print(f"\n📖 Generating Chapter {chapter_num}/{end_chapter}...")

                prose = await self.generate_chapter(
                    chapter_number=chapter_num,
                    narrative_style=narrative_style
                )
                results[chapter_num] = prose

                # Show progress
                print(f"✓ Chapter {chapter_num} complete")

                # Each chapter adds to context for next
                if chapter_num < end_chapter:
                    print(f"   Context updated for Chapter {chapter_num + 1}")

            except Exception as e:
                print(f"❌ Failed to generate Chapter {chapter_num}: {e}")
                # We should stop if a chapter fails
                # as later chapters depend on earlier ones
                print("   Stopping sequential generation due to error")
                break

        print(f"\n{'='*60}")
        print(f"📊 Generation Summary:")
        print(f"   Completed: {len(results)}/{end_chapter - start_chapter + 1} chapters")
        print(f"   Total Words: {sum(len(p.split()) for p in results.values()):,}")
        print(f"{'='*60}\n")

        return results