"""Iteration coordinator to orchestrate the iteration process."""

from typing import Dict, Any, Optional
from pathlib import Path

from ...api import OpenRouterClient
from ...models import Project
from .intent import IntentAnalyzer
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
        target_chapters: Optional[list] = None,
        settings=None
    ):
        """
        Initialize iteration coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation tasks (optional)
            default_target: Default target for iterations (premise/treatment/chapters/prose)
            target_chapters: List of specific chapters to regenerate (None = all)
            settings: Settings object (for multi-model mode detection)
        """
        self.client = client
        self.project = project
        self.settings = settings
        self.model = model
        self.default_target = default_target
        self.target_chapters = target_chapters

        # Validate model
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        # Initialize components (all use the same model)
        self.intent_analyzer = IntentAnalyzer(client, model, default_target=default_target)
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

            # Step 4: Execute full regeneration (always regenerate, no scale detection)
            if logger:
                logger.info("COORDINATOR: Step 4 - Executing full regeneration...")

            result['scale'] = 'regenerate'
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
            current_chapter_count = len(current_chapters) if current_chapters else None

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

            # Always let the LLM determine optimal chapter count during iteration
            # User feedback may request consolidation/expansion, LLM needs freedom to restructure
            chapter_count = None  # Let DepthCalculator and LLM decide based on word target and feedback

            # Regenerate with feedback as guidance
            feedback_text = intent.get('description', '')

            # If specific chapters are targeted, add focus instruction
            if self.target_chapters:
                if logger:
                    logger.info(f"COORDINATOR: Targeting specific chapters: {self.target_chapters}")
                chapter_list = ', '.join(str(c) for c in self.target_chapters)
                feedback_text = f"{feedback_text}\n\nFOCUS: Apply this feedback specifically to chapters {chapter_list}. Full context is provided, but only modify the specified chapters."

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
                # Chapter regeneration (long-form)
                from ..prose import ProseGenerator
                generator = ProseGenerator(self.client, self.project, self.model)

                # Determine which chapters to regenerate
                if self.target_chapters:
                    # Regenerate specific chapters from chapter filter
                    chapters_to_regenerate = self.target_chapters
                    if logger:
                        logger.info(f"COORDINATOR: Regenerating specific chapters: {chapters_to_regenerate}")
                else:
                    # Extract single chapter from intent (natural language feedback)
                    chapter_num = self._extract_chapter_number(intent)
                    if not chapter_num:
                        raise ValueError("Cannot determine which chapter to regenerate")
                    chapters_to_regenerate = [chapter_num]
                    if logger:
                        logger.info(f"COORDINATOR: Regenerating single chapter from intent: {chapter_num}")

                # Regenerate each chapter with full context
                for chapter_num in chapters_to_regenerate:
                    if logger:
                        logger.info(f"COORDINATOR: Regenerating chapter {chapter_num}...")

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

                    if logger:
                        logger.info(f"COORDINATOR: Chapter {chapter_num} regenerated ({len(result.split())} words)")

        else:
            raise ValueError(f"Regeneration not implemented for {target_type}")

        return changes

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
