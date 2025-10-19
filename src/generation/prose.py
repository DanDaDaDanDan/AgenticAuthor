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

    def _format_validation_issues(self, issues: List[Dict[str, Any]]) -> str:
        """
        Format validation issues for readable display in iteration prompt.

        Args:
            issues: List of validation issues from _validate_prose_fidelity()
                    Each issue has: type, severity, element, reasoning, recommendation

        Returns:
            Formatted string with numbered issues ready for prompt inclusion
        """
        if not issues:
            return "No issues detected."

        formatted = []

        for i, issue in enumerate(issues, 1):
            issue_type = issue.get('type', 'unknown')
            element = issue.get('element', 'Unknown element')
            reasoning = issue.get('reasoning', 'No reasoning provided')
            recommendation = issue.get('recommendation', 'Fix this issue')

            # Format type nicely (e.g., "missing_scene" -> "Missing Scene")
            issue_type_formatted = issue_type.replace('_', ' ').title()

            formatted.append(
                f"Issue #{i}: {issue_type_formatted}\n"
                f"  Element: {element}\n"
                f"  Problem: {reasoning}\n"
                f"  Fix: {recommendation}"
            )

        return "\n\n".join(formatted)

    def _select_validation_issues(self, issues: List[Dict[str, Any]], context: str = "validation") -> List[Dict[str, Any]]:
        """
        Display validation issues and let user select which ones to incorporate.

        Args:
            issues: List of validation issues
            context: Context string for display (e.g., "chapter 3 prose")

        Returns:
            Filtered list of selected issues (or all issues if user selects all)
        """
        if not issues:
            return []

        self.console.print(f"\n[yellow]Detected {len(issues)} validation issue(s) in {context}:[/yellow]\n")

        # Display all issues with numbers
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get('type', 'unknown')
            element = issue.get('element', 'Unknown element')
            reasoning = issue.get('reasoning', 'No reasoning provided')
            severity = issue.get('severity', 'medium')

            # Format type nicely
            issue_type_formatted = issue_type.replace('_', ' ').title()

            # Color code by severity
            severity_color = "red" if severity == "critical" else "yellow" if severity == "high" else "dim"

            self.console.print(f"[cyan]{i}.[/cyan] [{severity_color}]{issue_type_formatted}[/{severity_color}]")
            self.console.print(f"   Element: {element}")
            self.console.print(f"   Problem: {reasoning}")
            self.console.print()

        # Prompt for selection
        self.console.print("[yellow]Which issues should be incorporated into iteration?[/yellow]")
        self.console.print("[dim]Options:[/dim]")
        self.console.print("  • Enter numbers (e.g., '1,3,5' or '1-3')")
        self.console.print("  • Enter 'all' to include all issues")
        self.console.print("  • Press Enter to include all issues (default)")
        self.console.print()

        try:
            selection = input("Enter selection: ").strip()
        except (KeyboardInterrupt, EOFError):
            # User cancelled - abort the entire operation
            self.console.print(f"\n[yellow]Selection cancelled by user.[/yellow]")
            raise KeyboardInterrupt("User cancelled issue selection")

        # Default to all if empty
        if not selection or selection.lower() == 'all':
            self.console.print(f"[green]✓[/green] Including all {len(issues)} issues\n")
            return issues

        # Parse selection
        selected_indices = set()
        try:
            parts = selection.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range (e.g., "1-3")
                    start, end = part.split('-')
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())

                    # Validate range direction
                    if start_idx > end_idx:
                        self.console.print(f"[yellow]⚠️  Range '{part}' is reversed. Did you mean {end_idx}-{start_idx}?[/yellow]")
                        # Swap to make it work
                        start_idx, end_idx = end_idx, start_idx

                    for idx in range(start_idx, end_idx + 1):
                        if 1 <= idx <= len(issues):
                            selected_indices.add(idx)
                else:
                    # Single number
                    idx = int(part)
                    if 1 <= idx <= len(issues):
                        selected_indices.add(idx)
        except ValueError:
            self.console.print(f"[red]Invalid selection format. Including all issues.[/red]\n")
            return issues

        # Filter issues
        selected_issues = [issues[i - 1] for i in sorted(selected_indices)]

        if selected_issues:
            self.console.print(f"[green]✓[/green] Selected {len(selected_issues)} of {len(issues)} issues\n")
        else:
            self.console.print(f"[yellow]No valid issues selected. Including all issues.[/yellow]\n")
            return issues

        return selected_issues

    async def _validate_prose_fidelity(
        self,
        prose_text: str,
        chapter_outline: Dict[str, Any],
        chapter_number: int
    ) -> tuple[bool, List[Dict[str, Any]]]:
        """
        Validate prose against chapter outline (separate LLM call).

        This validates that the prose faithfully implements the chapter outline
        without missing scenes, skipping character development, or deviating
        from the structural plan.

        Uses low temperature (0.1) for consistent, strict evaluation.

        Args:
            prose_text: Generated prose text
            chapter_outline: Chapter outline dict (from chapters.yaml)
            chapter_number: Chapter number for context

        Returns:
            Tuple of (is_valid, issues_list)
            - is_valid: True if no critical issues found
            - issues_list: List of issue dicts with type, severity, element, reasoning, recommendation
        """
        # Build validation prompt
        chapter_yaml = yaml.dump(chapter_outline, default_flow_style=False, allow_unicode=True)

        # Get scene/event count
        scenes = chapter_outline.get('scenes', chapter_outline.get('key_events', []))
        num_scenes = len(scenes)

        prompt = f"""You are a strict prose validation system. Your job is to detect when prose deviates from its chapter outline.

CHAPTER OUTLINE (source of truth):
```yaml
{chapter_yaml}
```

GENERATED PROSE TO VALIDATE:
```
{prose_text}
```

VALIDATION CRITERIA:

**ALLOWED** (expected variations):
- Specific dialogue and action details (as long as scene objectives are met)
- Sensory descriptions and atmospheric details
- Internal character thoughts and reactions
- Pacing and sentence-level style choices
- Minor sequence adjustments within a scene
- Elaboration on outline points with additional description

**FORBIDDEN** (critical deviations to flag):
- Missing entire scenes from the outline (prose has {num_scenes} required scenes)
- Skipping character development moments listed in outline
- Ignoring emotional beats specified in outline
- Wrong POV character (outline specifies: {chapter_outline.get('pov', 'N/A')})
- Significantly different scene outcomes than specified
- Missing major plot points or story beats
- Severe word count deviation (target: {chapter_outline.get('word_count_target', 3000)}, acceptable range: 70-130%)

YOUR TASK:

1. Check if ALL scenes from the outline are present in the prose (in some form)
2. Verify character developments and emotional beats were addressed
3. Check if word count is within acceptable range (70-130% of target)
4. Verify POV character consistency
5. Check that scene outcomes align with outline specifications

Return your analysis as JSON:

{{
  "valid": true|false,
  "issues": [
    {{
      "type": "missing_scene|skipped_development|wrong_pov|word_count_deviation|wrong_outcome|insufficient_detail",
      "severity": "critical|high|medium",
      "element": "Brief description of what's wrong",
      "reasoning": "Detailed explanation of the deviation",
      "recommendation": "How to fix it"
    }}
  ],
  "scene_coverage": {{
    "outlined_scenes": {num_scenes},
    "found_scenes": <number>,
    "missing_scenes": ["list of missing scene titles"]
  }},
  "word_count_check": {{
    "target": {chapter_outline.get('word_count_target', 3000)},
    "actual": <actual word count>,
    "percentage": <percentage of target>
  }}
}}

IMPORTANT:
- Only flag CRITICAL deviations (missing scenes, skipped developments, etc.)
- Do NOT flag creative elaboration or stylistic choices
- Do NOT flag minor reordering within scenes
- Be strict but not pedantic - the outline is a guide, not a script

Return ONLY the JSON, no additional commentary."""

        try:
            # Call validation API (temperature 0.1 for consistency)
            result = await self.client.json_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict prose validation system. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temp for consistent evaluation
                operation=f"prose-validation-chapter-{chapter_number}"
            )

            if not result:
                # Validation failed - assume valid (don't block on validation errors)
                return (True, [])

            # Parse result
            is_valid = result.get('valid', True)
            issues = result.get('issues', [])

            # Filter to critical/high severity only
            critical_issues = [
                issue for issue in issues
                if issue.get('severity') in ['critical', 'high']
            ]

            # Overall valid if no critical issues
            is_valid = len(critical_issues) == 0

            return (is_valid, critical_issues)

        except Exception as e:
            # Validation error - log but don't block generation
            print(f"⚠️  Prose validation error: {e}")
            return (True, [])  # Assume valid on error

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
        narrative_style: str = "third person limited",
        auto_fix: bool = False
    ) -> str:
        """
        Generate full prose for a chapter using ONLY chapters.yaml (self-contained).

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style
            auto_fix: If True, automatically regenerate with all validation issues (no prompts)

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

        # Serialize modified context to YAML for prompt
        chapters_yaml = yaml.dump(modified_chapters_data, sort_keys=False)

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
                scene_breakdown += f"\nScene {i}: \"{scene.get('scene', 'Untitled')}\"\n"
                scene_breakdown += f"  Location: {scene.get('location', 'N/A')}\n"

                # Simplified scene fields (backward compatible)
                objective = scene.get('objective', scene.get('pov_goal', 'N/A'))
                scene_breakdown += f"  Objective: {objective}\n"

                # Exit hook is optional
                exit_hook = scene.get('exit_hook')
                if exit_hook:
                    scene_breakdown += f"  Exit Hook: {exit_hook}\n"

                # Add beats array (handle both dict and string formats)
                beats = scene.get('beats', [])
                if beats:
                    scene_breakdown += f"\n  BEAT STRUCTURE ({len(beats)} beats):\n"
                    for j, beat in enumerate(beats, 1):
                        # Handle both old format (dict with type/note/target_words) and new format (simple string)
                        if isinstance(beat, dict):
                            beat_note = beat.get('note', '')
                            scene_breakdown += f"    {j}. {beat_note}\n"
                        else:
                            # New format: simple string
                            scene_breakdown += f"    {j}. {beat}\n"
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
                top_p=0.9,  # Focused sampling for quality
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

            # Validate prose fidelity (separate LLM call)
            # NOTE: Validation happens AFTER saving to aid debugging
            self.console.print(f"[dim]Validating prose fidelity...[/dim]")

            is_valid, critical_issues = await self._validate_prose_fidelity(
                prose_text=prose_text,
                chapter_outline=current_chapter,
                chapter_number=chapter_number
            )

            # Retry logic for iteration (max 5 attempts, matching chapter iteration)
            max_iteration_attempts = 5
            iteration_attempt = 0

            while not is_valid and critical_issues and iteration_attempt < max_iteration_attempts:
                # Display critical issues
                self.console.print(f"\n[bold red]{'='*70}[/bold red]")
                self.console.print(f"[bold red]✗ CRITICAL ISSUE DETECTED in Chapter {chapter_number} Prose[/bold red]")
                self.console.print(f"[bold red]{'='*70}[/bold red]\n")

                for issue in critical_issues:
                    self.console.print(f"[bold yellow]Issue Type:[/bold yellow] {issue.get('type', 'Unknown')}")
                    self.console.print(f"[bold yellow]Element:[/bold yellow] {issue.get('element', 'Unknown')}\n")

                    self.console.print(f"[yellow]Problem:[/yellow]")
                    self.console.print(f"  {issue.get('reasoning', 'No details provided')}\n")

                    self.console.print(f"[cyan]Recommendation:[/cyan]")
                    self.console.print(f"  {issue.get('recommendation', 'Review and fix')}\n")
                    self.console.print(f"[dim]{'-'*70}[/dim]\n")

                self.console.print(f"[bold yellow]⚠️  Prose contradicts the chapter outline.[/bold yellow]")
                self.console.print(f"[yellow]This may result in missing scenes or poor narrative quality.[/yellow]\n")

                # Check if auto-fix is enabled
                if auto_fix:
                    # Auto-fix: automatically iterate with ALL issues (no prompts)
                    prose_choice = "2"
                    self.console.print(f"[cyan]Auto-fix enabled: Automatically iterating with all {len(critical_issues)} issues...[/cyan]\n")
                else:
                    # Normal mode: show choices and prompt user
                    self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
                    self.console.print(f"  [cyan]1.[/cyan] Abort generation [bold](recommended)[/bold] - review outline or regenerate manually")
                    self.console.print(f"  [cyan]2.[/cyan] Iterate on prose to fix specific issues")
                    self.console.print(f"  [cyan]3.[/cyan] Ignore and continue [bold](NOT recommended)[/bold] - may result in poor quality")

                    try:
                        prose_choice = input("\nEnter choice (1-3): ").strip()
                    except (KeyboardInterrupt, EOFError):
                        self.console.print(f"\n[yellow]Cancelled by user. Aborting...[/yellow]")
                        raise KeyboardInterrupt("User cancelled prose validation")

                if prose_choice == "1":
                    # Abort generation
                    self.console.print(f"\n[red]Generation aborted due to prose fidelity issues[/red]")
                    self.console.print(f"[dim]Review prose at: chapters/chapter-{chapter_number:02d}.md[/dim]")
                    raise Exception(f"Chapter {chapter_number} prose validation failed - user aborted generation")

                elif prose_choice == "2":
                    # Iterate on prose with specific feedback from validation
                    iteration_attempt += 1
                    self.console.print(f"\n[yellow]Iterating on prose to fix specific issues (attempt {iteration_attempt}/{max_iteration_attempts})...[/yellow]")
                    self.console.print(f"[yellow]Previous prose saved to .agentic/debug/ for reference[/yellow]\n")

                    # Save previous prose for reference
                    debug_dir = self.project.path / ".agentic" / "debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = debug_dir / f"chapter-{chapter_number:02d}_failed_{timestamp}.md"
                    debug_file.write_text(full_prose, encoding='utf-8')

                    # Select issues: auto-fix uses ALL, normal mode prompts user
                    if auto_fix:
                        # Auto-fix: include ALL issues without prompting
                        selected_issues = critical_issues
                        self.console.print(f"[green]✓[/green] Auto-fix: Including all {len(critical_issues)} issues\n")
                    else:
                        # Normal mode: let user select which issues to incorporate
                        selected_issues = self._select_validation_issues(critical_issues, context=f"chapter {chapter_number} prose")

                    # Build iteration prompt with previous prose and selected issues
                    issues_formatted = self._format_validation_issues(selected_issues)
                    chapter_yaml = yaml.dump(current_chapter, default_flow_style=False, allow_unicode=True)

                    iteration_feedback = f"""SURGICAL PROSE FIXES FOR CHAPTER {chapter_number}:

The prose below has specific validation issues that need targeted fixes.
Your task is to fix these issues with surgical precision, making minimal changes.

CHAPTER OUTLINE (source of truth):
```yaml
{chapter_yaml}
```

YOUR PREVIOUS PROSE (mostly good - needs targeted fixes):
```
{prose_text}
```

ISSUES TO FIX:

{issues_formatted}

INSTRUCTIONS - BE SURGICAL:
1. Focus primarily on fixing the specific issues listed above
2. Preserve the existing prose quality and voice
3. You may make small adjustments to surrounding content if needed for flow
4. Avoid unnecessary rewrites of working scenes
5. For each issue:
   - Missing scenes: Add the complete scene (not a summary)
   - Skipped development: Develop the character moment fully
   - Wrong POV: Adjust POV perspective as needed
   - Word count deviation: Expand or trim targeted areas
6. Keep the same narrative tone and style
7. Maintain continuity with the rest of the prose

Think of this as surgical editing - fix what's broken with minimal collateral changes.
The goal is targeted fixes that resolve the violations while preserving what works.

Return the corrected prose as flowing narrative text (NOT YAML)."""

                    # Regenerate prose with iteration feedback
                    # Build full generation prompt with feedback
                    word_count_target = current_chapter.get('word_count_target', 3000)
                    scenes = current_chapter.get('scenes', current_chapter.get('key_events', []))
                    num_scenes = len(scenes)

                    iteration_prompt = f"""{iteration_feedback}

TARGET: {word_count_target:,} words total = {num_scenes} full dramatic scenes

Return ONLY the corrected prose text. Do NOT include:
- YAML formatting
- Chapter headers (we'll add those)
- Explanations or notes
- Scene markers or dividers

Just the flowing narrative prose ({word_count_target:,} words, {num_scenes} full dramatic scenes)."""

                    # Call API for iteration
                    result = await self.client.streaming_completion(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a professional fiction writer. Return only the prose text without any formatting or explanations."},
                            {"role": "user", "content": iteration_prompt}
                        ],
                        temperature=0.8,  # Same as generation for prose quality
                        top_p=0.9,  # Focused sampling for quality
                        display=True,
                        display_label=f"Iterating Chapter {chapter_number} prose",
                        min_response_tokens=int(word_count_target * 1.3)
                    )

                    if not result:
                        self.console.print(f"[red]✗ Iteration failed - no response from API[/red]")
                        break  # Exit retry loop

                    # Extract iteration result
                    prose_text = result.get('content', result) if isinstance(result, dict) else result
                    full_prose = f"# Chapter {chapter_number}: {current_chapter['title']}\n\n{prose_text}"

                    # Save iterated prose
                    chapter_file.write_text(full_prose, encoding='utf-8')
                    self.console.print(f"[green]✓[/green] Prose iteration complete")

                    # Validate again
                    self.console.print(f"[dim]Validating corrected prose...[/dim]")
                    is_valid, critical_issues = await self._validate_prose_fidelity(
                        prose_text=prose_text,
                        chapter_outline=current_chapter,
                        chapter_number=chapter_number
                    )

                    # Show results
                    if not is_valid and critical_issues:
                        if iteration_attempt >= max_iteration_attempts:
                            self.console.print(f"\n[yellow]⚠️  Prose still has issues after {max_iteration_attempts} attempts:[/yellow]")
                            for issue in critical_issues:
                                self.console.print(f"  • {issue.get('element', 'Unknown')}: {issue.get('reasoning', '')}")

                            # In auto mode, abort on failure
                            if auto_fix:
                                self.console.print(f"\n[red]Auto-fix: Max retries exhausted, aborting generation[/red]")
                                raise Exception(f"Auto-fix failed after {max_iteration_attempts} iteration attempts for chapter {chapter_number} prose")

                            self.console.print(f"\n[yellow]Continuing anyway (max iteration attempts reached)...[/yellow]\n")
                            break  # Exit retry loop
                        else:
                            self.console.print(f"\n[yellow]⚠️  Prose still has issues. Showing choices again...[/yellow]\n")
                            # Loop will continue and show choices again
                    else:
                        self.console.print(f"[green]✓[/green] Prose validation passed!\n")
                        break  # Exit retry loop

                elif prose_choice == "3":
                    # Ignore and continue
                    self.console.print(f"\n[yellow]⚠️  Ignoring prose fidelity issues...[/yellow]")
                    self.console.print(f"[yellow]Chapter may have quality issues or missing content.[/yellow]\n")
                    break  # Exit validation loop

                else:
                    # Invalid choice - treat as ignore
                    self.console.print(f"\n[yellow]Invalid choice. Ignoring issues and continuing...[/yellow]\n")
                    break  # Exit validation loop

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
        auto_fix: bool = False
    ) -> str:
        """
        Generate full prose for a chapter with complete story context.

        Args:
            chapter_number: Chapter to generate
            narrative_style: Narrative voice/style
            auto_fix: If True, automatically regenerate with all validation issues (no prompts)

        Returns:
            Chapter prose text
        """
        return await self.generate_chapter_sequential(
            chapter_number=chapter_number,
            narrative_style=narrative_style,
            auto_fix=auto_fix
        )

    async def generate_all_chapters(
        self,
        narrative_style: str = "third person limited",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        auto_fix: bool = False
    ) -> Dict[int, str]:
        """
        Generate prose for all chapters sequentially with full context.

        Args:
            narrative_style: Narrative voice/style
            start_chapter: First chapter to generate
            end_chapter: Last chapter (None for all)
            auto_fix: If True, automatically regenerate with all validation issues (no prompts)

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
                        auto_fix=auto_fix
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