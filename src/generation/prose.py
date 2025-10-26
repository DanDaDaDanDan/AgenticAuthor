"""Prose generation (LOD0) for AgenticAuthor."""

import json
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path

from rich.console import Console
from datetime import datetime

from ..api import OpenRouterClient
from ..models import Project
from ..utils.tokens import estimate_tokens
from .lod_context import LODContextBuilder
from .depth_calculator import DepthCalculator
from ..prompts import get_prompt_loader


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
        self.console = Console()
        self.prompt_loader = get_prompt_loader()


    def load_all_chapters_with_prose(self) -> List[Dict[str, Any]]:
        """Load all chapter outlines and merge with any existing prose."""

        # Load chapter outlines from new architecture (chapter-beats/)
        chapters_data = self.project.get_chapters_yaml()
        if not chapters_data:
            raise Exception("No chapter outlines found. Generate chapters first with /generate chapters")

        # Extract chapters list from the structure
        chapters = chapters_data.get('chapters', [])
        if not chapters:
            raise Exception("No chapters found in chapter outlines. Generate chapters first with /generate chapters")

        # For each chapter, check if prose exists and load it
        for chapter in chapters:
            chapter_file = self.project.chapters_dir / f"chapter-{chapter['number']:02d}.md"
            if chapter_file.exists():
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    chapter['full_prose'] = f.read()
                    chapter['prose_generated'] = True
            else:
                chapter['prose_generated'] = False

        return chapters

    def get_taxonomy_selections(self) -> Optional[str]:
        """Load and format taxonomy selections from premise metadata."""
        metadata_file = self.project.premise_metadata_file
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

        # Response space needed (generous for quality prose)
        # Typical chapters: 3000-5000 words, allow flexibility
        response_needed = 6000  # ~4500 words of prose + buffer

        # Total needed with buffer
        total_needed = total_context + response_needed + 1000

        # Check if configured model is sufficient (use global settings)
        configured_model = self.model
        if not configured_model:
            from ..config import get_settings
            settings = get_settings()
            configured_model = settings.active_model

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
            "recommended_model": recommended_model
        }

    async def generate_chapter_sequential(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited",
        style_card: Optional[str] = None
    ) -> str:
        """
        Generate full prose for a chapter using ONLY chapters.yaml (self-contained).

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style
            style_card: Optional prose style guidance from misc/prose-style-card.md

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

        # Build previous chapters context with FULL PROSE (authoritative)
        prev_summary = ""
        if prev_chapters:
            prev_summary = "\nPREVIOUS CHAPTERS (full prose - authoritative):\n"
            for ch in prev_chapters:
                prev_summary += f"\n{'='*70}\n"
                prev_summary += f"Chapter {ch['number']}: {ch['title']}\n"
                prev_summary += f"{'='*70}\n\n"

                # Check if prose exists for this chapter
                prose_file = self.project.chapters_dir / f"chapter-{ch['number']:02d}.md"
                if prose_file.exists():
                    # Include FULL PROSE (authoritative - not outline)
                    prose_text = prose_file.read_text(encoding='utf-8')
                    # Strip chapter header if present
                    if prose_text.startswith(f"# Chapter {ch['number']}:"):
                        prose_text = '\n'.join(prose_text.split('\n')[1:]).strip()
                    prev_summary += f"{prose_text}\n\n"
                else:
                    # Fallback to outline summary (if prose not yet generated)
                    prev_summary += f"Summary (from outline): {ch.get('summary', 'N/A')}\n"
                    prev_summary += f"Note: Full prose not yet generated for this chapter\n\n"

        # Build modified chapters_data excluding previous chapter outlines (only current + future)
        # This prevents confusion about authority - prose is authoritative for completed chapters
        modified_chapters_data = {
            'metadata': chapters_data.get('metadata', {}),
            'characters': chapters_data.get('characters', []),
            'world': chapters_data.get('world', {}),
            'chapters': [
                ch for ch in chapters
                if ch['number'] >= chapter_number  # Only current + future chapters
            ]
        }

        # Build rich context markdown: chapter index, current outline (raw if available), future outlines
        from ..utils.markdown_extractors import MarkdownFormatter
        from pathlib import Path as _P

        # Chapter index (number, title, act)
        index_lines = ["## Chapter Index"]
        for ch in chapters:
            index_lines.append(f"- {ch.get('number','?')}: {ch.get('title','Untitled')} — {ch.get('act','N/A')}")
        index_md = "\n".join(index_lines) + "\n\n"

        # Current chapter outline MUST exist as raw beat file (no fallback)
        current_outline_file = self.project.chapter_beats_dir / f"chapter-{chapter_number:02d}.md"
        if not current_outline_file.exists():
            raise Exception(
                f"Chapter outline not found: {current_outline_file}. "
                f"Finalize chapters first or regenerate beats."
            )
        current_outline_md = current_outline_file.read_text(encoding='utf-8').strip()

        # Future chapter outlines: require raw files for each future chapter
        future_md = ""
        future_chapters = [ch for ch in chapters if ch['number'] > chapter_number]
        if future_chapters:
            parts = []
            for ch in future_chapters:
                num = ch.get('number')
                fpath = self.project.chapter_beats_dir / f"chapter-{num:02d}.md"
                if not fpath.exists():
                    raise Exception(
                        f"Missing future chapter outline: {fpath}. "
                        f"All future chapter beat files must exist before prose generation."
                    )
                parts.append(fpath.read_text(encoding='utf-8').strip())
            future_md = "\n\n---\n\n".join(parts)

        chapters_markdown = (
            index_md +
            "<<<CURRENT CHAPTER OUTLINE START>>>\n" + current_outline_md + "\n<<<CURRENT CHAPTER OUTLINE END>>>\n\n" +
            ("<<<FUTURE CHAPTER OUTLINES START>>>\n" + future_md + "\n<<<FUTURE CHAPTER OUTLINES END>>>\n" if future_md else "")
        )

        # Build prose generation prompt - QUALITY-FIRST approach
        # Support both structured scenes (new) and simple key_events (old) formats
        key_moments = current_chapter.get('scenes', current_chapter.get('key_events', []))
        uses_structured_scenes = (
            'scenes' in current_chapter and
            isinstance(key_moments, list) and
            len(key_moments) > 0 and
            isinstance(key_moments[0], dict)
        )

        # Extract beat sheet data (current format) - backward compatible
        # Beats are required: use 'beats' if present or 'key_events' from the outline
        beats = current_chapter.get('beats') or current_chapter.get('key_events', [])
        if not beats:
            raise Exception(
                "Current chapter outline missing beats/key_events. "
                "Regenerate chapter beats with the beat-sheet prompt before prose generation."
            )
        emotional_beat = current_chapter.get('emotional_beat', '')

        # Build chapter summary (legacy prose summary format)
        chapter_summary = current_chapter.get('summary', '')

        # Build key moments listing (not counting them as separate scenes!)
        moments_text = ""
        if uses_structured_scenes:
            # Structured scenes: Extract objectives and outcomes
            moments_text = "\nKEY MOMENTS TO INCLUDE:\n"
            for moment in key_moments:
                objective = moment.get('objective', moment.get('pov_goal', 'N/A'))
                outcome = moment.get('outcome', '')
                if outcome:
                    moments_text += f"- {objective} → {outcome}\n"
                else:
                    moments_text += f"- {objective}\n"
        else:
            # Simple key_events: Use as-is
            if key_moments:
                moments_text = "\nKEY MOMENTS TO INCLUDE:\n"
                for event in key_moments:
                    if isinstance(event, dict):
                        moments_text += f"- {event.get('description', str(event))}\n"
                    else:
                        moments_text += f"- {event}\n"

        # Prepare taxonomy constraints (optional)
        taxonomy_data = self.project.get_taxonomy() or {}
        import yaml as _yaml
        taxonomy_markdown = ""
        try:
            if taxonomy_data:
                taxonomy_markdown = _yaml.dump({'selections': taxonomy_data}, sort_keys=False, allow_unicode=True)
        except Exception:
            taxonomy_markdown = str(taxonomy_data)

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "generation/prose_generation",
            chapters_markdown=chapters_markdown,
            taxonomy_markdown=taxonomy_markdown,
            prev_summary=prev_summary,
            chapter_number=chapter_number,
            current_chapter=current_chapter,
            beats=beats,  # NEW: beat sheet format
            emotional_beat=emotional_beat,  # NEW: beat sheet format
            chapter_summary=chapter_summary,  # LEGACY: prose summary format
            moments_text=moments_text,  # LEGACY: key moments format
            metadata=metadata,
            narrative_style=narrative_style,
            style_card=style_card  # Optional style guidance
        )

        prompt = prompts['user']

        # Generate with API
        try:
            # Estimate generous response space (typical chapter: 3000-5000 words)
            from ..utils.tokens import estimate_messages_tokens
            estimated_response_tokens = 5000  # Reasonable default for quality prose

            # Get temperature and top_p from prompt config
            temperature = self.prompt_loader.get_temperature("generation/prose_generation", default=0.8)
            top_p = self.prompt_loader.get_metadata("generation/prose_generation").get('top_p', 0.9)

            # Use streaming_completion for prose (plain text, not YAML)
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts['system']},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                top_p=top_p,
                display=True,
                display_label=f"Generating Chapter {chapter_number} prose",
                reserve_tokens=estimated_response_tokens
            )

            if not result:
                raise Exception("No response from API")

            # Extract response text (plain prose, not YAML)
            prose_text = result.get('content', result) if isinstance(result, dict) else result

            # Validate response quality
            from ..utils.logging import get_logger
            logger = get_logger()

            if not prose_text or len(prose_text.strip()) < 100:
                error_msg = f"Response too short ({len(prose_text) if prose_text else 0} chars) - likely incomplete or failed"
                if logger:
                    logger.error(f"SUSPICIOUS RESPONSE: {error_msg}")
                raise Exception(error_msg)

            # Log successful extraction
            if logger:
                word_count = len(prose_text.split())
                logger.info(f"Prose extracted successfully: {len(prose_text)} characters, {word_count:,} words")

            # Save prose directly to file
            chapter_file = self.project.chapters_dir / f"chapter-{chapter_number:02d}.md"
            self.project.chapters_dir.mkdir(exist_ok=True)

            # Add chapter header
            full_prose = f"# Chapter {chapter_number}: {current_chapter['title']}\n\n{prose_text}"

            chapter_file.write_text(full_prose, encoding='utf-8')

            # Update combined context to include latest prose
            try:
                self.project.write_combined_markdown(target='chapters', include_prose=True)
            except Exception as e:
                # Don't fail the entire generation if combined markdown update fails
                # But DO log the issue so we know it happened
                from ..utils.logging import get_logger
                logger = get_logger()
                if logger:
                    logger.warning(f"Failed to update combined markdown after prose generation: {e}")
                print(f"   ⚠️  Warning: Could not update combined markdown ({e})")

            word_count = len(prose_text.split())
            print(f"\n✅ Chapter {chapter_number} generated successfully")
            print(f"   Word count: {word_count:,}")

            return full_prose

        except Exception as e:
            raise Exception(f"Failed to generate prose: {e}")

    async def generate_chapter(
        self,
        chapter_number: int,
        narrative_style: str = "third person limited",
        style_card: Optional[str] = None
    ) -> str:
        """
        Generate full prose for a chapter with complete story context.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style
            style_card: Optional prose style guidance from misc/prose-style-card.md

        Returns:
            Chapter prose text
        """
        return await self.generate_chapter_sequential(
            chapter_number=chapter_number,
            narrative_style=narrative_style,
            style_card=style_card
        )

    async def generate_all_chapters(
        self,
        narrative_style: str = "third person limited",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        style_card: Optional[str] = None
    ) -> Dict[int, str]:
        """
        Generate prose for all chapters sequentially with full context.

        Args:
            narrative_style: Narrative voice/style
            start_chapter: First chapter to generate
            end_chapter: Last chapter (None for all)
            style_card: Optional prose style guidance from misc/prose-style-card.md

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
                        narrative_style=narrative_style,
                        style_card=style_card
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
