"""Prose generation (LOD0) for AgenticAuthor."""

import json
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path

from jinja2 import Template

from ..api import OpenRouterClient
from ..models import Project
from ..utils.tokens import estimate_tokens
from ..config import get_settings
from .lod_context import LODContextBuilder
from .lod_parser import LODResponseParser
from .depth_calculator import DepthCalculator


class ProseGenerator:
    """Generator for full prose (LOD0)."""

    def __init__(self, client: OpenRouterClient, project: Project, model: str):
        """
        Initialize prose generator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation (required)
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.project = project
        self.model = model
        self.context_builder = LODContextBuilder()
        self.parser = LODResponseParser()


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
                # Estimate outline tokens (support both scenes and key_events)
                outline_text = f"Chapter {ch.get('number', 0)}: {ch.get('title', '')}\n"
                outline_text += f"Summary: {ch.get('summary', '')}\n"
                scenes_or_events = ch.get('scenes', ch.get('key_events', []))
                outline_text += f"Scenes: {scenes_or_events}\n"
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
            configured_model = self.model

        recommended_model = None
        is_sufficient = False

        if configured_model:
            # Check if configured model has sufficient capacity
            from ..api.models import ModelList
            models = await self.client.discover_models()
            models_list = ModelList(models=models)
            configured_model_obj = models_list.get_by_id(configured_model)

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
        Generate full prose for a chapter using ONLY chapters.yaml (self-contained).

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style

        Returns:
            Chapter prose text
        """
        # Load chapters.yaml (self-contained - no premise/treatment needed)
        chapters_data = self.project.get_chapters_yaml()

        if not chapters_data:
            raise Exception(
                "chapters.yaml not found or in legacy format. "
                "Please regenerate chapters with /generate chapters to create the new self-contained format."
            )

        # Extract sections
        metadata = chapters_data.get('metadata', {})
        characters = chapters_data.get('characters', [])
        world = chapters_data.get('world', {})
        chapters = chapters_data.get('chapters', [])

        # Find current chapter
        current_chapter = None
        for ch in chapters:
            if ch['number'] == chapter_number:
                current_chapter = ch
                break

        if not current_chapter:
            raise Exception(f"Chapter {chapter_number} not found in chapters.yaml")

        # Get previous chapters for context
        prev_chapters = [ch for ch in chapters if ch['number'] < chapter_number]

        # Build previous chapters summary
        prev_summary = ""
        if prev_chapters:
            prev_summary = "\nPREVIOUS CHAPTERS SUMMARY:\n"
            for ch in prev_chapters:
                prev_summary += f"\nChapter {ch['number']}: {ch['title']}\n"
                prev_summary += f"Summary: {ch.get('summary', 'N/A')}\n"
                # Check if prose exists for this chapter
                prose_file = self.project.chapters_dir / f"chapter-{ch['number']:02d}.md"
                if prose_file.exists():
                    prose_text = prose_file.read_text(encoding='utf-8')
                    # Include last paragraph for continuity
                    paragraphs = [p.strip() for p in prose_text.split('\n\n') if p.strip()]
                    if paragraphs:
                        prev_summary += f"Ending: ...{paragraphs[-1]}\n"

        # Serialize to YAML for prompt
        chapters_yaml = yaml.dump(chapters_data, sort_keys=False)

        # Build prose generation prompt
        word_count_target = current_chapter.get('word_count_target', 3000)

        # Support both new (scenes) and old (key_events) formats
        scenes = current_chapter.get('scenes', current_chapter.get('key_events', []))
        num_scenes = len(scenes)
        uses_structured_scenes = 'scenes' in current_chapter and isinstance(scenes, list) and len(scenes) > 0 and isinstance(scenes[0], dict)

        # Calculate scene depth guidance from actual scene targets
        if uses_structured_scenes and scenes:
            # Get scene targets from structured scenes
            scene_targets = [scene.get('target_words', 0) for scene in scenes]
            avg_ws = sum(scene_targets) // len(scene_targets) if scene_targets else word_count_target // num_scenes
        else:
            # Fallback: distribute evenly
            avg_ws = word_count_target // num_scenes if num_scenes > 0 else 1500

        # Simple guidance ranges based on average
        setup_range = (int(avg_ws * 0.7), int(avg_ws * 0.9))      # 70-90% for setup/transition
        standard_range = (int(avg_ws * 0.9), int(avg_ws * 1.1))   # 90-110% for standard
        climax_range = (int(avg_ws * 1.2), int(avg_ws * 1.5))     # 120-150% for climax

        # Build scene-by-scene breakdown if using structured format
        scene_breakdown = ""
        if uses_structured_scenes:
            scene_breakdown = "\n\nSCENE-BY-SCENE BREAKDOWN WITH BEAT STRUCTURE:\n"
            for i, scene in enumerate(scenes, 1):
                target_scene_words = scene.get('target_words', avg_ws)
                scene_breakdown += f"\nScene {i}: \"{scene.get('scene', 'Untitled')}\"\n"
                scene_breakdown += f"  Location: {scene.get('location', 'N/A')}\n"

                # Extended scene fields (beat architecture)
                objective = scene.get('objective', scene.get('pov_goal', 'N/A'))
                opposition = scene.get('opposition', scene.get('conflict', 'N/A'))
                value_shift = scene.get('value_shift', 'N/A')
                exit_hook = scene.get('exit_hook', 'N/A')

                scene_breakdown += f"  Objective: {objective}\n"
                scene_breakdown += f"  Opposition: {opposition}\n"
                scene_breakdown += f"  Value Shift: {value_shift}\n"
                scene_breakdown += f"  Stakes: {scene.get('stakes', 'N/A')}\n"
                scene_breakdown += f"  Outcome: {scene.get('outcome', 'N/A')}\n"
                scene_breakdown += f"  Exit Hook: {exit_hook}\n"
                scene_breakdown += f"  Emotional Beat: {scene.get('emotional_beat', 'N/A')}\n"
                if scene.get('sensory_focus'):
                    scene_breakdown += f"  Sensory Focus: {', '.join(scene.get('sensory_focus', []))}\n"
                scene_breakdown += f"  TARGET: {target_scene_words:,} words MINIMUM\n"

                # Add beats array if present
                beats = scene.get('beats', [])
                if beats:
                    scene_breakdown += f"\n  BEAT STRUCTURE ({len(beats)} beats):\n"
                    for j, beat in enumerate(beats, 1):
                        beat_type = beat.get('type', 'unknown')
                        beat_note = beat.get('note', '')
                        beat_words = beat.get('target_words', 0)
                        scene_breakdown += f"    {j}. {beat_type.upper()} ({beat_words:,}w): {beat_note}\n"
                    scene_breakdown += f"  → Follow this beat structure for proper pacing and emphasis\n"

        prompt = f"""Generate full prose for a chapter using this self-contained story context.

STORY CONTEXT (chapters.yaml):
```yaml
{chapters_yaml}
```
{prev_summary}

TASK:
Generate {word_count_target:,} words of polished narrative prose for:
- Chapter {chapter_number}: "{current_chapter['title']}"
- POV: {current_chapter.get('pov', 'N/A')}
- Act: {current_chapter.get('act', 'N/A')}
{scene_breakdown}

CRITICAL - BEAT-DRIVEN SCENE DEVELOPMENT (NOT SUMMARIES):
This chapter has {num_scenes} SCENES to develop in {word_count_target:,} words.
Each scene is a COMPLETE DRAMATIC UNIT following its BEAT STRUCTURE (see breakdown above).

If beats are provided in the breakdown, follow them beat-by-beat:
  1. SETUP (10-15% of scene): Establish location, character state, goal
  2. OBSTACLE (15% of scene): First complication arises
  3. COMPLICATION (20% of scene): Stakes increase, tension builds
  4. REVERSAL (25% of scene): ★ PEAK MOMENT ★ - decision point, turn, revelation
  5. CONSEQUENCE (20% of scene): Immediate aftermath, character processing
  6. EXIT (10% of scene): Bridge to next scene with hook

If no beats provided, use classic 4-part structure:
  1. SETUP (15-20% of scene): Establish location, time, who's present
  2. DEVELOPMENT (40-50% of scene): Action, dialogue, obstacles, complications
  3. CLIMAX (15-20% of scene): Peak moment, emotional turning point
  4. RESOLUTION (15-20% of scene): Aftermath, bridge to next scene

★ REVERSAL/CLIMAX IS THE HEART OF THE SCENE ★
The reversal beat (or climax in 4-part) gets the MOST WORDS (25-30%).
This is the turn, the decision, the confrontation - don't rush it.

MINIMUM WORDS PER SCENE (not average - MINIMUM):
• This chapter: ~{avg_ws} words per scene
• Setup/transition scenes: {setup_range[0]}-{setup_range[1]} words minimum
• Standard dramatic scenes: {standard_range[0]}-{standard_range[1]} words minimum
• Climactic/peak scenes: {climax_range[0]}-{climax_range[1]}+ words minimum

SHOW vs TELL - CRITICAL DISTINCTION:

❌ TELLING (summary - avoid this):
"Sarah was angry with her brother for forgetting her birthday. She confronted him about it and he apologized."
(50 words - rushed summary)

✅ SHOWING (full scene - do this):
Sarah's jaw clenched as Mark walked in, whistling. Her birthday. Her thirtieth birthday. And he'd forgotten.

"Hey," he said, dropping his keys on the counter. "What's for dinner?"

The casual question hit like a slap. She'd spent the morning checking her phone, waiting for his text, his call, anything. "You're kidding."

"What?" He opened the fridge, oblivious.

"Mark." Her voice came out flat. "What day is it?"

He paused, milk carton in hand. His eyes widened. "Oh God. Sarah, I—"

"Don't." She held up a hand. "Just don't."

(380 words - full scene with dialogue, action, emotion)

WRITE EVERY SCENE AS A FULL DRAMATIC UNIT. Do NOT summarize or rush.
Each scene should feel complete and immersive. Let moments breathe.

NOTE: This chapter is in {current_chapter.get('act', 'N/A')}.
- Act I: Efficient setup, but still FULL scenes (not summaries)
- Act II: Standard dramatic development
- Act III: DEEPER emotional intensity, more immersive

GUIDELINES:
1. FOLLOW THE BEAT STRUCTURE for each scene (setup → obstacle → complication → REVERSAL → consequence → exit)
2. Give REVERSAL/TURN beats the most space (25-30% of scene) - this is where the magic happens
3. Use the metadata (tone, pacing, themes, narrative style) to guide your writing
4. Draw on character backgrounds, motivations, and arcs from the characters section
5. Use world-building details (locations, systems, atmosphere) to ground scenes
6. Follow scene objectives and value shifts (before → after transformation)
7. Perfect continuity from previous chapters (if any)
8. Use narrative style from metadata: {metadata.get('narrative_style', narrative_style)}
9. TARGET: {word_count_target:,} words total = {num_scenes} scenes × {avg_ws} w/s MINIMUM per scene
10. SHOW character emotions through action, dialogue, physical reactions
11. Include sensory details in EVERY scene (sight, sound, touch, smell, taste)
12. Let dialogue breathe - include reactions, pauses, character processing
13. Honor exit hooks - each scene should propel forward with question/decision/reveal/peril

Note: These guidelines serve the story. If specific instructions conflict with good storytelling or prose quality, prioritize what makes the scene work. You have creative latitude to deviate from overly prescriptive details when needed for narrative flow, character authenticity, or dramatic impact.

Return ONLY the prose text. Do NOT include:
- YAML formatting
- Chapter headers (we'll add those)
- Explanations or notes
- Scene markers or dividers

Just the flowing narrative prose ({word_count_target:,} words, {num_scenes} full dramatic scenes)."""

        # Generate with API
        try:
            # Estimate tokens (simplified - no longer checking premise/treatment)
            from ..utils.tokens import estimate_messages_tokens
            estimated_response_tokens = word_count_target + 500  # ~1 token per word + buffer

            # Use streaming_completion for prose (plain text, not YAML)
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional fiction writer. Return only the prose text without any formatting or explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Higher for creative prose
                display=True,
                display_label=f"Generating Chapter {chapter_number} prose",
                min_response_tokens=estimated_response_tokens
            )

            if not result:
                raise Exception("No response from API")

            # Extract response text (plain prose, not YAML)
            prose_text = result.get('content', result) if isinstance(result, dict) else result

            # Save prose directly to file
            chapter_file = self.project.chapters_dir / f"chapter-{chapter_number:02d}.md"
            self.project.chapters_dir.mkdir(exist_ok=True)

            # Add chapter header
            full_prose = f"# Chapter {chapter_number}: {current_chapter['title']}\n\n{prose_text}"

            chapter_file.write_text(full_prose, encoding='utf-8')

            word_count = len(prose_text.split())
            print(f"\n✅ Chapter {chapter_number} generated successfully")
            print(f"   Word count: {word_count:,}")

            return full_prose

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
        chapters_data = self.project.get_chapters_yaml()
        if not chapters_data:
            raise Exception("No chapters.yaml found. Generate chapters first.")

        all_chapters = chapters_data.get('chapters', [])
        if not all_chapters:
            raise Exception("No chapters found in chapters.yaml")

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
            # Retry logic: up to 2 attempts per chapter
            max_attempts = 2
            attempt = 1
            success = False

            while attempt <= max_attempts and not success:
                try:
                    if attempt > 1:
                        print(f"\n🔄 Retry {attempt}/{max_attempts} for Chapter {chapter_num}...")
                    else:
                        print(f"\n📖 Generating Chapter {chapter_num}/{end_chapter}...")

                    prose = await self.generate_chapter(
                        chapter_number=chapter_num,
                        narrative_style=narrative_style
                    )
                    results[chapter_num] = prose
                    success = True

                    # Show progress
                    print(f"✓ Chapter {chapter_num} complete")

                    # Each chapter adds to context for next
                    if chapter_num < end_chapter:
                        print(f"   Context updated for Chapter {chapter_num + 1}")

                except Exception as e:
                    print(f"❌ Failed to generate Chapter {chapter_num}: {e}")
                    if attempt < max_attempts:
                        import asyncio
                        wait_time = attempt * 2  # Exponential backoff: 2s, 4s, etc.
                        print(f"   Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        attempt += 1
                    else:
                        # Final attempt failed
                        print(f"   All {max_attempts} attempts failed for Chapter {chapter_num}")
                        print("   Stopping sequential generation due to repeated errors")
                        break

            # If we exhausted retries, stop the entire generation
            if not success:
                break

        print(f"\n{'='*60}")
        print(f"📊 Generation Summary:")
        print(f"   Completed: {len(results)}/{end_chapter - start_chapter + 1} chapters")
        print(f"   Total Words: {sum(len(p.split()) for p in results.values()):,}")
        print(f"{'='*60}\n")

        return results

    async def generate_chapter_with_competition(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited"
    ) -> str:
        """
        Generate chapter prose using multi-model competition with unified context.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style

        Returns:
            Winning chapter prose text
        """
        from .multi_model import MultiModelGenerator

        # Build unified context (self-contained chapters.yaml only)
        context = self.context_builder.build_context(
            project=self.project,
            context_level='prose',  # Include chapters.yaml (self-contained)
            include_downstream=False  # Chapters.yaml is self-contained
        )

        if 'chapters' not in context:
            raise Exception("No chapters found. Generate chapters first with /generate chapters")

        # Extract chapters from dict or list format
        chapters_data = context['chapters']
        if isinstance(chapters_data, dict):
            # New self-contained format
            chapters = chapters_data.get('chapters', [])
        else:
            # Legacy format (list)
            chapters = chapters_data

        # Find current chapter info
        current_chapter = None
        for ch in chapters:
            if ch.get('number') == chapter_number:
                current_chapter = ch
                break

        if not current_chapter:
            raise Exception(f"Chapter {chapter_number} not found in outlines")

        # Check token requirements
        token_calc = await self.calculate_prose_context_tokens(chapter_number)

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build prompt (same as generate_chapter_sequential)
        word_count_target = current_chapter.get('word_count_target', 3000)

        prompt = f"""Here is the current book content in YAML format:

```yaml
{context_yaml}
```

Generate full prose for Chapter {chapter_number}: "{current_chapter['title']}"

Guidelines:
1. Target ~{word_count_target} words of flowing narrative prose
2. Perfect continuity from previous chapters (if any exist)
3. Consistent character voices and development
4. Proper pacing relative to the story arc
5. Natural progression toward upcoming chapters
6. Narrative style: {narrative_style}
7. Build on established world-building, character traits, and plot threads
8. Follow the chapter outline's key events, character developments, relationship beats, and tension points

CRITICAL: Return your response as YAML with this structure:
```yaml
premise:
  text: |
    ... (keep existing premise unchanged)
  metadata: ...

treatment:
  text: |
    ... (keep existing treatment unchanged)

chapters:
  - number: 1
    title: "..."
    # ... (keep all chapter outlines unchanged)

prose:
  - chapter: {chapter_number}
    text: |
      # Chapter {chapter_number}: {current_chapter['title']}

      Your prose here... (~{word_count_target} words of narrative)
```

Do NOT wrap your response in additional markdown code fences (```).
Return ONLY the YAML content with all sections (premise + treatment + chapters + prose)."""

        # Create multi-model generator
        multi_gen = MultiModelGenerator(self.client, self.project)

        # Define generator function that takes model parameter
        async def generate_with_model(model: str) -> str:
            # Check model capabilities
            model_obj = await self.client.get_model(model)
            if not model_obj:
                raise Exception(f"Failed to fetch model capabilities for {model}")

            # Generate with this model using dry_run
            result = await self.client.streaming_completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional fiction writer. You always return valid YAML without additional formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                display=True,
                display_label=f"Generating Chapter {chapter_number} prose ({model})",
                min_response_tokens=token_calc['response_tokens']
            )

            if not result:
                raise Exception(f"No response from {model}")

            response_text = result.get('content', result) if isinstance(result, dict) else result

            # Parse with dry_run to validate but not save
            parse_result = self.parser.parse_and_save(
                response=response_text,
                project=self.project,
                target_lod='prose',
                original_context=context,
                dry_run=True
            )

            # Return the raw response for comparison
            return response_text

        # Run competition
        competition_result = await multi_gen.generate_parallel(
            generator_func=generate_with_model,
            content_type="prose",
            file_prefix=f"chapter_{chapter_number:02d}",
            context={
                'premise': context['premise']['text'],
                'treatment': context['treatment']['text'],
                'genre': self.project.metadata.genre if self.project.metadata else None,
                'chapter_number': chapter_number,
                'chapter_title': current_chapter['title']
            }
        )

        if not competition_result:
            raise Exception("Multi-model competition failed or was cancelled")

        # Get winning response
        winning_response = competition_result['winner']['content']

        # Now save the winner for real
        parse_result = self.parser.parse_and_save(
            response=winning_response,
            project=self.project,
            target_lod='prose',
            original_context=context,
            dry_run=False  # Actually save this time
        )

        # Read the saved prose
        chapter_file = self.project.path / "chapters" / f"chapter-{chapter_number:02d}.md"
        if chapter_file.exists():
            with open(chapter_file, 'r', encoding='utf-8') as f:
                prose_content = f.read()
                word_count = len(prose_content.split())
                print(f"\n✅ Chapter {chapter_number} generated successfully (multi-model)")
                print(f"   Word count: {word_count:,}")
                return prose_content
        else:
            raise Exception(f"Prose file not created for chapter {chapter_number}")