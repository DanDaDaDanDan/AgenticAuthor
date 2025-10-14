"""Iteration coordinator to orchestrate the iteration process."""

from typing import Dict, Any, Optional
from pathlib import Path

from ...api import OpenRouterClient
from ...models import Project
from .intent import IntentAnalyzer
from .scale import ScaleDetector
from .diff import DiffGenerator, PatchError
from ..lod_context import LODContextBuilder
from ..lod_parser import LODResponseParser


class IterationCoordinator:
    """Coordinate the iteration process."""

    def __init__(
        self,
        client: OpenRouterClient,
        project: Project,
        model: Optional[str] = None,
        default_target: Optional[str] = None,
        settings=None
    ):
        """
        Initialize iteration coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation tasks (optional)
            default_target: Default target for iterations (premise/treatment/chapters/prose)
            settings: Settings object (for multi-model mode detection)
        """
        self.client = client
        self.project = project
        self.settings = settings
        self.model = model
        self.default_target = default_target

        # Validate model
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        # Initialize components (all use the same model)
        self.intent_analyzer = IntentAnalyzer(client, model, default_target=default_target)
        self.scale_detector = ScaleDetector(client, model)
        self.diff_generator = DiffGenerator(client, model)
        self.context_builder = LODContextBuilder()
        self.parser = LODResponseParser()

    async def process_feedback(
        self,
        feedback: str,
        auto_commit: bool = True,
        show_preview: bool = False
    ) -> Dict[str, Any]:
        """
        Process user feedback and execute iteration.

        Args:
            feedback: User's natural language feedback
            auto_commit: Whether to automatically commit changes
            show_preview: Whether to show preview before applying

        Returns:
            Result dict with success status, changes, and commit info

        Raises:
            ValueError: If feedback is invalid or cannot be processed
        """
        from ...utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info("="*60)
            logger.info("=== COORDINATOR: process_feedback START ===")
            logger.info(f"Feedback: {feedback}")
            logger.info(f"Model: {self.model}")
            logger.info(f"Default target: {self.default_target}")

        result = {
            'success': False,
            'feedback': feedback,
            'intent': None,
            'scale': None,
            'changes': [],
            'commit': None,
            'error': None
        }

        try:
            # Step 1: Analyze intent
            if logger:
                logger.info("COORDINATOR: Step 1 - Analyzing intent...")

            intent = await self.intent_analyzer.analyze(feedback, self.project)
            result['intent'] = intent

            if logger:
                logger.info(f"COORDINATOR: Intent analysis complete")
                logger.info(f"  - Intent type: {intent.get('intent_type')}")
                logger.info(f"  - Target type: {intent.get('target_type')}")
                logger.info(f"  - Confidence: {intent.get('confidence')}")
                logger.debug(f"  - Full intent: {intent}")

            # Step 2: Check confidence
            if logger:
                logger.info("COORDINATOR: Step 2 - Checking confidence...")

            if intent['confidence'] < 0.8:
                if logger:
                    logger.info(f"COORDINATOR: Low confidence ({intent['confidence']}), requesting clarification")
                return self._request_clarification(intent, result)

            if logger:
                logger.info(f"COORDINATOR: Confidence OK ({intent['confidence']})")

            # Step 3: Handle non-iteration intents
            if logger:
                logger.info("COORDINATOR: Step 3 - Checking intent type...")

            if intent['intent_type'] == 'analyze':
                if logger:
                    logger.info("COORDINATOR: Intent is 'analyze', not yet implemented")
                result['error'] = "Analysis system not yet implemented. Use /analyze command."
                return result

            if intent['intent_type'] == 'clarify':
                if logger:
                    logger.info("COORDINATOR: Intent is 'clarify', requesting clarification")
                return self._request_clarification(intent, result)

            if logger:
                logger.info(f"COORDINATOR: Intent type is '{intent['intent_type']}', proceeding")

            # Step 4: Detect scale
            if logger:
                logger.info("COORDINATOR: Step 4 - Detecting scale...")

            scale = await self._determine_scale(intent)
            result['scale'] = scale

            if logger:
                logger.info(f"COORDINATOR: Scale detected: {scale}")

            # Step 5: Execute based on scale
            if logger:
                logger.info(f"COORDINATOR: Step 5 - Executing {scale}...")

            if scale == "patch":
                if logger:
                    logger.info("COORDINATOR: Calling _execute_patch...")
                changes = await self._execute_patch(intent, show_preview)
            else:
                if logger:
                    logger.info("COORDINATOR: Calling _execute_regenerate...")
                changes = await self._execute_regenerate(intent)

            if logger:
                logger.info(f"COORDINATOR: Execution complete, {len(changes)} changes")

            result['changes'] = changes
            result['success'] = True

            if logger:
                logger.info("=== COORDINATOR: process_feedback END (SUCCESS) ===")
                logger.info("="*60)

            return result

        except Exception as e:
            if logger:
                logger.error(f"COORDINATOR: Exception in process_feedback: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"COORDINATOR: Traceback: {traceback.format_exc()}")
                logger.info("=== COORDINATOR: process_feedback END (ERROR) ===")
                logger.info("="*60)
            result['error'] = str(e)
            result['success'] = False
            return result

    async def _determine_scale(self, intent: Dict[str, Any]) -> str:
        """Determine if change should be patch or regenerate."""
        from ...utils.logging import get_logger
        logger = get_logger()

        if logger:
            logger.info("COORDINATOR: _determine_scale called")
            logger.info(f"  - Target type: {intent.get('target_type')}")

        # CRITICAL: Premise should ALWAYS be regenerated, never patched
        # Premise is too short and fundamental to use patch approach
        if intent.get('target_type') == 'premise':
            if logger:
                logger.info("COORDINATOR: Target is premise, returning 'regenerate'")
            return "regenerate"

        # First, try heuristic detection
        if logger:
            logger.info("COORDINATOR: Calling scale_detector.detect_scale (heuristic)...")

        scale = self.scale_detector.detect_scale(intent)

        if logger:
            logger.info(f"COORDINATOR: Heuristic scale: {scale}")

        # If unclear and we have content, ask the model
        if scale == "ask_model":
            if logger:
                logger.info("COORDINATOR: Scale unclear, getting target content...")

            content, content_type = self._get_target_content(intent)

            if content:
                if logger:
                    logger.info(f"COORDINATOR: Content found ({len(content)} chars), asking model for scale...")

                scale_data = await self.scale_detector.ask_model_for_scale(
                    intent, content, content_type
                )
                scale = scale_data['scale']

                if logger:
                    logger.info(f"COORDINATOR: Model returned scale: {scale}")
            else:
                # No content available, default to regenerate
                if logger:
                    logger.info("COORDINATOR: No content found, defaulting to 'regenerate'")
                scale = "regenerate"

        if logger:
            logger.info(f"COORDINATOR: _determine_scale returning: {scale}")

        return scale

    async def _execute_patch(
        self,
        intent: Dict[str, Any],
        show_preview: bool = False
    ) -> list:
        """
        Execute patch-based iteration using unified LOD context.

        ITERATION STRATEGIES:
        - Prose: Diff-based patching (most efficient, line-level changes)
        - Chapters/Treatment/Premise: YAML replacement (simple, maintains consistency)
        - Short-form prose: Diff-based patching of story.md (no chapters)

        Current approach sends full context and asks LLM to return updated YAML.
        This is token-intensive but ensures full consistency and is simple to implement.

        For large projects (20+ chapters), this could use 10k+ tokens round-trip.
        However, this is acceptable because:
        - Chapter iteration is infrequent compared to prose iteration
        - Maintaining consistency is more important than token optimization
        - Alternative (YAML diff-patching) is complex and error-prone

        FUTURE OPTIMIZATION: Consider diff-based patching for chapters.yaml
        when project size becomes a common issue.
        """
        changes = []
        target_lod = intent['target_type']

        # Special handling for prose iteration (diff-based - efficient)
        if target_lod == 'prose':
            # Check if short-form story
            if self.project.is_short_form():
                return await self._execute_short_story_patch(intent, show_preview)
            else:
                return await self._execute_prose_patch(intent, show_preview)

        # For other LODs, use YAML-based replacement (simple but complete)
        # Build unified context up to (and including) target LOD
        context = self.context_builder.build_context(
            project=self.project,
            context_level=target_lod,  # Include content up to this level
            include_downstream=False  # Don't send prose when iterating chapters
        )

        # Check if we have the required content
        if target_lod == 'premise' and 'premise' not in context:
            raise ValueError("No premise found. Generate premise first with /generate premise")
        elif target_lod == 'treatment' and 'treatment' not in context:
            raise ValueError("No treatment found. Generate treatment first with /generate treatment")
        elif target_lod == 'chapters' and 'chapters' not in context:
            raise ValueError("No chapters.yaml found. Generate chapters first with /generate chapters")

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build the iteration prompt
        prompt = f"""Current book content in YAML format:

```yaml
{context_yaml}
```

USER FEEDBACK: "{intent['description']}"

TARGET: {target_lod}{f" (specifically: {intent.get('target_id', 'all')})" if intent.get('target_id') else ""}

TASK:
1. Apply the user's requested changes to the {target_lod} section
2. Maintain internal consistency within this section
3. Keep the same overall structure and level of detail

RESPONSE FORMAT:
Return the updated content in YAML format.
Only modify what needs changing based on the feedback.

Return ONLY the YAML content. Do NOT wrap in markdown code fences (```)."""

        # Call LLM
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise story editor. You return valid YAML and maintain narrative consistency across all LOD levels."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,  # Lower for controlled edits
            stream=True,
            display=True,
            display_label=f"Updating {target_lod}"
        )

        if not result:
            raise ValueError("LLM returned no response")

        # Extract response
        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Parse and save (includes culling and upward sync detection)
        parse_result = self.parser.parse_and_save(
            response=response_text,
            project=self.project,
            target_lod=target_lod,
            original_context=context
        )

        # Build change info
        change_info = {
            'type': 'patch',
            'updated_files': parse_result['updated_files'],
            'deleted_files': parse_result['deleted_files'],
            'changes': parse_result.get('changes', {})
        }

        # Add chapter count if applicable
        if target_lod == 'chapters' and 'chapters.yaml' in parse_result['updated_files']:
            chapters = self.project.get_chapters()
            if chapters:
                change_info['chapter_count'] = len(chapters)

        changes.append(change_info)

        return changes

    async def _execute_prose_patch(
        self,
        intent: Dict[str, Any],
        show_preview: bool = False
    ) -> list:
        """
        Execute diff-based prose iteration with full context of ALL chapters.

        CRITICAL: Pass full prose of ALL chapters for maximum context.
        No truncation, context is king.
        """
        changes = []

        # Extract target chapter number
        chapter_num = self._extract_chapter_number(intent)
        if not chapter_num:
            raise ValueError("Cannot determine which chapter to iterate. Please specify chapter number.")

        # Get target chapter file
        chapter_file = self.project.chapters_dir / f'chapter-{chapter_num:02d}.md'
        if not chapter_file.exists():
            raise ValueError(f"Chapter {chapter_num} not found. Generate it first with /generate prose {chapter_num}")

        # Read original content
        original_content = chapter_file.read_text(encoding='utf-8')

        # Build FULL context with ALL chapter prose
        full_context = self.context_builder.build_prose_iteration_context(
            project=self.project,
            target_chapter=chapter_num
        )

        # Serialize context to YAML (includes chapters.yaml + ALL prose)
        context_yaml = self.context_builder.to_yaml_string(full_context)

        # Build additional context for diff generation
        additional_context = f"""Full Story Context (chapters.yaml + all prose):

```yaml
{context_yaml}
```

TARGET CHAPTER: {chapter_num}
You are modifying chapter {chapter_num}. All other chapters are provided for context."""

        # Create backup for undo
        backup_path = self.project.path / '.agentic' / 'debug' / f'chapter-{chapter_num:02d}.backup.md'
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(original_content, encoding='utf-8')

        # Generate diff
        try:
            diff = await self.diff_generator.generate_diff(
                original=original_content,
                intent=intent,
                file_path=f'chapters/chapter-{chapter_num:02d}.md',
                context=additional_context
            )

            # Get diff statistics
            stats = self.diff_generator.get_diff_statistics(diff)

            # Show preview if requested
            if show_preview:
                preview = self.diff_generator.create_preview(original_content, diff)
                print("\n=== Diff Preview ===")
                print(preview)
                print("\n=== Statistics ===")
                print(f"Lines added: {stats['added']}")
                print(f"Lines removed: {stats['removed']}")
                print(f"Lines changed: {stats['changed']}")
                print(f"Total changes: {stats['total_changes']}")

                # Ask for confirmation
                response = input("\nApply these changes? [y/N]: ")
                if response.lower() != 'y':
                    return [{
                        'type': 'patch',
                        'status': 'cancelled',
                        'message': 'User cancelled changes'
                    }]

            # Apply diff
            modified_content = self.diff_generator.apply_diff(original_content, diff)

            # Save modified content
            chapter_file.write_text(modified_content, encoding='utf-8')

            # Build change info
            change_info = {
                'type': 'prose_patch',
                'chapter': chapter_num,
                'updated_files': [f'chapters/chapter-{chapter_num:02d}.md'],
                'backup_path': str(backup_path.relative_to(self.project.path)),
                'statistics': stats,
                'word_count_before': len(original_content.split()),
                'word_count_after': len(modified_content.split())
            }

            changes.append(change_info)

            # Display statistics
            print(f"\n✓ Applied {stats['total_changes']} line changes to chapter {chapter_num}")
            print(f"  +{stats['added']} lines added")
            print(f"  -{stats['removed']} lines removed")
            print(f"  Backup saved to: {change_info['backup_path']}")
            print(f"  To undo: copy backup back to chapters/chapter-{chapter_num:02d}.md")

            return changes

        except Exception as e:
            # Restore from backup on error
            if backup_path.exists():
                chapter_file.write_text(backup_path.read_text(encoding='utf-8'), encoding='utf-8')
            raise ValueError(f"Failed to apply prose patch: {str(e)}")

    async def _execute_short_story_patch(
        self,
        intent: Dict[str, Any],
        show_preview: bool = False
    ) -> list:
        """
        Execute diff-based iteration on short-form story (story.md).

        For short stories, the entire story is in one file, so context is simpler.
        """
        changes = []

        # Check if story exists
        if not self.project.story_file.exists():
            raise ValueError("No story found. Generate story first with /generate prose")

        # Read original content
        original_content = self.project.get_story()
        if not original_content:
            raise ValueError("Story file is empty")

        # Build short story context
        context = self.context_builder.build_short_story_context(
            project=self.project,
            target_lod='prose'
        )

        # Serialize context to YAML
        context_yaml = self.context_builder.to_yaml_string(context)

        # Build additional context for diff generation
        additional_context = f"""Story Context:

```yaml
{context_yaml}
```

You are modifying a short-form story. The premise and treatment provide the story structure."""

        # Create backup for undo
        backup_path = self.project.path / '.agentic' / 'debug' / 'story.backup.md'
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(original_content, encoding='utf-8')

        # Generate diff
        try:
            diff = await self.diff_generator.generate_diff(
                original=original_content,
                intent=intent,
                file_path='story.md',
                context=additional_context
            )

            # Get diff statistics
            stats = self.diff_generator.get_diff_statistics(diff)

            # Show preview if requested
            if show_preview:
                preview = self.diff_generator.create_preview(original_content, diff)
                print("\n=== Diff Preview ===")
                print(preview)
                print("\n=== Statistics ===")
                print(f"Lines added: {stats['added']}")
                print(f"Lines removed: {stats['removed']}")
                print(f"Lines changed: {stats['changed']}")
                print(f"Total changes: {stats['total_changes']}")

                # Ask for confirmation
                response = input("\nApply these changes? [y/N]: ")
                if response.lower() != 'y':
                    return [{
                        'type': 'patch',
                        'status': 'cancelled',
                        'message': 'User cancelled changes'
                    }]

            # Apply diff
            modified_content = self.diff_generator.apply_diff(original_content, diff)

            # Save modified content
            self.project.save_story(modified_content)

            # Build change info
            change_info = {
                'type': 'short_story_patch',
                'updated_files': ['story.md'],
                'backup_path': str(backup_path.relative_to(self.project.path)),
                'statistics': stats,
                'word_count_before': len(original_content.split()),
                'word_count_after': len(modified_content.split())
            }

            changes.append(change_info)

            # Display statistics
            print(f"\n✓ Applied {stats['total_changes']} line changes to story")
            print(f"  +{stats['added']} lines added")
            print(f"  -{stats['removed']} lines removed")
            print(f"  Backup saved to: {change_info['backup_path']}")
            print(f"  To undo: copy backup back to story.md")

            return changes

        except Exception as e:
            # Restore from backup on error
            if backup_path.exists():
                self.project.story_file.write_text(backup_path.read_text(encoding='utf-8'), encoding='utf-8')
            raise ValueError(f"Failed to apply story patch: {str(e)}")

    async def _execute_regenerate(self, intent: Dict[str, Any]) -> list:
        """Execute full regeneration."""
        from ...utils.logging import get_logger
        logger = get_logger()

        changes = []

        target_type = intent['target_type']

        if logger:
            logger.info(f"=== COORDINATOR: _execute_regenerate START ===")
            logger.info(f"Target type: {target_type}")
            logger.info(f"Intent: {intent}")

        # Import generators as needed
        if target_type == 'premise':
            if logger:
                logger.info("COORDINATOR: Premise iteration - importing PremiseGenerator")

            from ..premise import PremiseGenerator
            generator = PremiseGenerator(self.client, self.project, self.model)

            # Extract feedback from intent
            feedback = intent.get('original_feedback', '')

            if logger:
                logger.info(f"COORDINATOR: Extracted feedback: '{feedback}'")
                logger.info(f"COORDINATOR: Calling generator.iterate()...")

            print(f"\n[DEBUG] coordinator: About to call generator.iterate('{feedback}')")

            # Use iterate() method which is designed for premise iteration
            # This loads current premise and applies feedback, unlike generate() which creates new premise
            try:
                result = await generator.iterate(feedback)

                print(f"[DEBUG] coordinator: generator.iterate() RETURNED")

                if logger:
                    logger.info(f"COORDINATOR: generator.iterate() returned successfully")
                    logger.debug(f"COORDINATOR: Result type: {type(result)}")
                    if result:
                        logger.debug(f"COORDINATOR: Result has {len(result)} fields")
                        logger.debug(f"COORDINATOR: Result keys: {list(result.keys()) if isinstance(result, dict) else 'NOT A DICT'}")
            except Exception as e:
                if logger:
                    logger.error(f"COORDINATOR: Exception in generator.iterate(): {type(e).__name__}: {e}")
                    import traceback
                    logger.error(f"COORDINATOR: Traceback: {traceback.format_exc()}")
                raise

            # premise.iterate() already saves to project, just extract info for changes
            changes.append({
                'type': 'regenerate',
                'target': 'premise',
                'file': 'premise_metadata.json',
                'word_count': len(result.get('premise', '').split())
            })

            if logger:
                logger.info(f"COORDINATOR: Added change info to changes list")
                logger.info(f"COORDINATOR: Word count: {len(result.get('premise', '').split())}")

        elif target_type == 'treatment':
            from ..treatment import TreatmentGenerator
            generator = TreatmentGenerator(self.client, self.project, self.model)

            # Use multi-model competition if enabled
            if self.settings and self.settings.multi_model_mode:
                result = await generator.generate_with_competition()
            else:
                result = await generator.generate()

            # Save treatment
            self.project.save_treatment(result)

            changes.append({
                'type': 'regenerate',
                'target': 'treatment',
                'file': 'treatment.md',
                'word_count': len(result.split())
            })

        elif target_type == 'chapters':
            # Multiple chapters - regenerate all chapter outlines with feedback
            from ..chapters import ChapterGenerator
            from ..depth_calculator import DepthCalculator
            generator = ChapterGenerator(self.client, self.project, self.model)

            # Get current chapter count from existing chapters
            current_chapters = self.project.list_chapters()
            chapter_count = len(current_chapters) if current_chapters else None

            # Get taxonomy data for intelligent word count calculation
            taxonomy_data = self.project.get_taxonomy() or {}

            # Extract genre from premise metadata
            premise_data = self.project.get_premise_metadata()
            if premise_data and isinstance(premise_data, dict):
                premise_metadata = premise_data.get('metadata', {})
                genre = premise_metadata.get('genre')
            else:
                genre = None

            # Infer genre from taxonomy if not explicitly set
            if not genre:
                if 'fantasy_subgenre' in taxonomy_data:
                    genre = 'fantasy'
                elif 'mystery_subgenre' in taxonomy_data:
                    genre = 'mystery'
                elif 'romance_subgenre' in taxonomy_data:
                    genre = 'romance'
                elif 'scifi_subgenre' in taxonomy_data:
                    genre = 'science-fiction'
                elif 'horror_subgenre' in taxonomy_data:
                    genre = 'horror'
                elif 'literary_style' in taxonomy_data:
                    genre = 'literary-fiction'
                elif 'historical_period' in taxonomy_data:
                    genre = 'historical-fiction'
                else:
                    genre = 'general'

            # Extract length_scope from taxonomy
            length_scope_value = taxonomy_data.get('length_scope')
            if isinstance(length_scope_value, list) and length_scope_value:
                length_scope = length_scope_value[0]
            else:
                length_scope = length_scope_value if isinstance(length_scope_value, str) else None

            # Get total_words using same logic as generation (priority: stored > calculated default)
            total_words = None

            # Try stored value first (from previous generation)
            chapters_yaml = self.project.get_chapters_yaml()
            if chapters_yaml and isinstance(chapters_yaml, dict):
                metadata = chapters_yaml.get('metadata', {})
                stored_target = metadata.get('target_word_count')
                if stored_target:
                    total_words = int(stored_target)
                    if logger:
                        logger.debug(f"Iteration: Found stored target_word_count: {total_words}")

                    # Validate stored target against current length_scope from taxonomy
                    if length_scope:
                        normalized_scope = length_scope.lower().replace(' ', '_')
                        form_ranges = DepthCalculator.FORM_RANGES.get(normalized_scope)
                        if form_ranges:
                            min_words, max_words = form_ranges
                            # If stored target is outside form range, recalculate
                            if total_words < min_words or total_words > max_words:
                                if logger:
                                    logger.warning(
                                        f"Iteration: Stored target {total_words:,} words is outside range for {length_scope} "
                                        f"({min_words:,}-{max_words:,}). Recalculating..."
                                    )
                                total_words = None  # Force recalculation

            # Calculate intelligent default if no stored value (or if invalidated)
            if total_words is None:
                if length_scope:
                    total_words = DepthCalculator.get_default_word_count(length_scope, genre)
                    if logger:
                        logger.debug(f"Iteration: Calculated default for {length_scope}/{genre}: {total_words} words")
                else:
                    # Fallback: use 'novel' baseline
                    total_words = DepthCalculator.get_default_word_count('novel', genre)
                    if logger:
                        logger.debug(f"Iteration: Using fallback default for novel/{genre}: {total_words} words")

            # Regenerate with feedback as guidance
            feedback_text = intent.get('description', '')

            # Use multi-model competition if enabled
            if self.settings and self.settings.multi_model_mode:
                result = await generator.generate_with_competition(
                    chapter_count=chapter_count,
                    total_words=total_words,
                    template=None,
                    feedback=feedback_text
                )
            else:
                result = await generator.generate(
                    chapter_count=chapter_count,
                    total_words=total_words,
                    feedback=feedback_text
                )

            changes.append({
                'type': 'regenerate',
                'target': 'chapters',
                'file': 'chapters.yaml',
                'count': len(result)
            })

        elif target_type in ['chapter', 'prose']:
            # Check if short-form story
            if self.project.is_short_form():
                # Regenerate entire short story
                from ..short_story import ShortStoryGenerator
                generator = ShortStoryGenerator(self.client, self.project, self.model)

                result = await generator.generate()

                changes.append({
                    'type': 'regenerate',
                    'target': 'story',
                    'file': 'story.md',
                    'word_count': len(result.split())
                })
            else:
                # Single chapter regeneration (long-form)
                chapter_num = self._extract_chapter_number(intent)

                if not chapter_num:
                    raise ValueError("Cannot determine which chapter to regenerate")

                from ..prose import ProseGenerator
                generator = ProseGenerator(self.client, self.project, self.model)

                # Use multi-model competition if enabled
                if self.settings and self.settings.multi_model_mode:
                    result = await generator.generate_chapter_with_competition(chapter_num)
                else:
                    result = await generator.generate_chapter_sequential(chapter_num)

                # Save chapter
                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                chapter_file.write_text(result, encoding='utf-8')

                changes.append({
                    'type': 'regenerate',
                    'target': f'chapter {chapter_num}',
                    'file': str(chapter_file.relative_to(self.project.path)),
                    'word_count': len(result.split())
                })

        else:
            raise ValueError(f"Regeneration not implemented for {target_type}")

        return changes

    def _get_target_content(self, intent: Dict[str, Any]) -> tuple[Optional[str], str]:
        """
        Get the content to be modified.

        Returns:
            Tuple of (content, content_type)
        """
        target_type = intent['target_type']

        if target_type == 'premise':
            premise = self.project.get_premise()
            return (premise, 'premise')

        elif target_type == 'treatment':
            treatment = self.project.get_treatment()
            return (treatment, 'treatment')

        elif target_type == 'chapters':
            # Multiple chapters - load chapters.yaml for patch/regen decision
            chapters_file = self.project.path / "chapters.yaml"
            if chapters_file.exists():
                content = chapters_file.read_text(encoding='utf-8')
                return (content, 'chapters')
            return (None, 'chapters')

        elif target_type == 'chapter':
            # Single chapter - if default_target is 'chapters', load chapters.yaml
            # Otherwise, load prose
            if self.default_target == 'chapters':
                # User is iterating chapters - load chapters.yaml unconditionally
                chapters_file = self.project.path / "chapters.yaml"
                if chapters_file.exists():
                    content = chapters_file.read_text(encoding='utf-8')
                    return (content, 'chapters')
                raise ValueError("No chapters.yaml found. Generate chapters first with /generate chapters")
            else:
                # User is iterating prose
                chapter_num = self._extract_chapter_number(intent)
                if not chapter_num:
                    raise ValueError("Cannot determine chapter number")

                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_file.exists():
                    content = chapter_file.read_text(encoding='utf-8')
                    return (content, f'chapter {chapter_num}')
                raise ValueError(
                    f"No prose found for chapter {chapter_num}. "
                    f"Generate with /generate prose {chapter_num} or use /iterate chapters for outlines."
                )

        elif target_type == 'prose':
            # Explicitly prose - always load prose file
            chapter_num = self._extract_chapter_number(intent)
            if not chapter_num:
                raise ValueError("Cannot determine chapter number")

            chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
            if chapter_file.exists():
                content = chapter_file.read_text(encoding='utf-8')
                return (content, f'chapter {chapter_num}')
            raise ValueError(
                f"No prose found for chapter {chapter_num}. "
                f"Generate with /generate prose {chapter_num}"
            )

        return (None, target_type)

    def _get_target_file_path(self, intent: Dict[str, Any]) -> Path:
        """Get file path for target content."""
        target_type = intent['target_type']

        if target_type == 'premise':
            return self.project.premise_file

        elif target_type == 'treatment':
            return self.project.treatment_file

        elif target_type == 'chapters':
            # Multiple chapters - return chapters.yaml
            return self.project.path / "chapters.yaml"

        elif target_type == 'chapter':
            # Single chapter - if default_target is 'chapters', return chapters.yaml
            if self.default_target == 'chapters':
                return self.project.path / "chapters.yaml"
            else:
                # Return prose file
                chapter_num = self._extract_chapter_number(intent)
                if chapter_num:
                    return self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"

        elif target_type == 'prose':
            # Explicitly prose - always return prose file
            chapter_num = self._extract_chapter_number(intent)
            if chapter_num:
                return self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"

        raise ValueError(f"Cannot determine file path for {target_type}")

    def _extract_chapter_number(self, intent: Dict[str, Any]) -> Optional[int]:
        """Extract chapter number from intent."""
        target_id = intent.get('target_id')

        if target_id:
            # Try to parse as integer
            try:
                return int(target_id)
            except (ValueError, TypeError):
                # Try to extract number from string like "chapter 3" or "3-5"
                import re
                match = re.search(r'\d+', str(target_id))
                if match:
                    return int(match.group())

        # Try to extract from feedback
        feedback = intent.get('original_feedback', '')
        import re
        match = re.search(r'chapter\s+(\d+)', feedback, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None

    def _build_context(self, intent: Dict[str, Any]) -> str:
        """Build additional context for diff generation."""
        context_parts = []

        # Add premise if modifying chapter
        if intent['target_type'] in ['chapter', 'prose']:
            premise = self.project.get_premise()
            if premise:
                context_parts.append(f"Story Premise:\n{premise[:200]}...")

        # Add treatment summary if available
        if intent['target_type'] == 'prose':
            treatment = self.project.get_treatment()
            if treatment:
                context_parts.append(f"Treatment Summary:\n{treatment[:300]}...")

        return '\n\n'.join(context_parts)


    def _request_clarification(
        self,
        intent: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request clarification from user."""
        result['success'] = False
        result['needs_clarification'] = True

        # Generate clarification question based on intent
        reasoning = intent.get('reasoning', 'Intent is unclear')

        result['clarification_needed'] = {
            'reason': reasoning,
            'suggestions': self._generate_suggestions(intent)
        }

        return result

    def _generate_suggestions(self, intent: Dict[str, Any]) -> list:
        """Generate helpful suggestions for user."""
        suggestions = []

        target_type = intent.get('target_type')

        if target_type == 'chapter':
            if not intent.get('target_id'):
                suggestions.append("Please specify which chapter you want to modify (e.g., 'chapter 3')")

        if intent.get('scope') == 'unclear':
            suggestions.append("Please clarify how extensive the change should be")

        if intent.get('action') == 'unclear':
            suggestions.append("Please describe more specifically what you want to change")

        # Generic suggestion
        if not suggestions:
            suggestions.append("Please provide more details about what you want to change")

        return suggestions
